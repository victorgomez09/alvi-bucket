import requests
import json
import os
from pathlib import Path
import boto3
from botocore.exceptions import ClientError

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings

# --- MinecraftJarCache Class (Modified for API integration and Spigot removal) ---

class MinecraftJarCache:
    MOJANG_VERSION_MANIFEST = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
    PAPERMC_API = "https://api.papermc.io/v2/projects/paper/"
    FORGE_MAVEN_BASE = "https://maven.minecraftforge.net/net/minecraftforge/forge/"
    NEOFORGE_MAVEN_BASE = "https://maven.neoforged.net/releases/net/neoforged/neoforge/"

    def __init__(self, bucket_name: str, endpoint_url: str, access_key: str, secret_key: str):
        """Initializes the cache with S3/MinIO configuration and ensures the bucket exists."""
        self.bucket_name = bucket_name
        self.s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        self.local_cache_dir = Path("/tmp/jar_cache") # Use /tmp for ephemeral storage
        self.local_cache_dir.mkdir(parents=True, exist_ok=True)
        self.version_manifest = None 
        
        # --- NEW LOGIC: Check and Create Bucket ---
        try:
            # Check if the bucket exists using head_bucket
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            print(f"S3 Bucket '{self.bucket_name}' already exists.")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            # MinIO/S3 returns a 404/NoSuchBucket error if the bucket is missing
            if error_code == '404' or error_code == 'NoSuchBucket':
                try:
                    self.s3_client.create_bucket(Bucket=self.bucket_name)
                    print(f"S3 Bucket '{self.bucket_name}' created successfully.")
                except ClientError as ce:
                    print(f"Failed to create S3 bucket '{self.bucket_name}': {ce}")
                    # Re-raise if creation fails for other reasons (e.g., permissions)
                    raise
            else:
                # Re-raise any other unexpected S3 connection/client errors
                raise
        # ------------------------------------------
        
    # --- Internal Utility Methods ---

    def _upload_to_s3(self, file_path: Path, s3_key: str) -> bool:
        """Uploads a file from the local path to the specified S3 key."""
        try:
            self.s3_client.upload_file(str(file_path), self.bucket_name, s3_key)
            return True
        except ClientError as e:
            # Note: This is where the original NoSuchBucket error occurred, 
            # but the fix in __init__ should prevent it now.
            print(f"S3 Upload Error for {s3_key}: {e}")
            return False

    def _s3_file_exists(self, s3_key: str) -> bool:
        """Checks if an object exists in the S3 bucket."""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError:
            return False
        
    def _download_and_cache(self, url: str, platform: str, version: str, s3_key: str) -> str | None:
        """Checks S3 cache first, downloads if missing, uploads to S3, and returns the S3 key."""
        
        # 1. Check S3 Cache
        if self._s3_file_exists(s3_key):
            return s3_key

        # 2. Download and Local Save (Cache Miss)
        local_temp_path = self.local_cache_dir / s3_key.replace("/", "_")
        local_temp_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            response = requests.get(url, stream=True, timeout=300) # 5 minute timeout
            response.raise_for_status()
            
            with open(local_temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
        except requests.exceptions.RequestException as e:
            print(f"Error downloading {platform} {version}: {e}")
            if local_temp_path.exists(): os.remove(local_temp_path)
            return None

        # 3. Upload to S3 and Clean Up
        if self._upload_to_s3(local_temp_path, s3_key):
            os.remove(local_temp_path)
            return s3_key
        else:
            return None

    # --- Platform-Specific Fetchers (Returning S3 key) ---
    
    def _get_vanilla_jar(self, version: str) -> str | None:
        if self.version_manifest is None:
            try:
                response = requests.get(self.MOJANG_VERSION_MANIFEST)
                response.raise_for_status()
                self.version_manifest = response.json()
            except requests.exceptions.RequestException:
                return None

        version_info = next((v for v in self.version_manifest.get('versions', []) if v['id'] == version), None)
        if not version_info: return None
        
        try:
            details_response = requests.get(version_info['url'])
            details_response.raise_for_status()
            version_details = details_response.json()
            server_download_url = version_details['downloads']['server']['url']
        except (requests.exceptions.RequestException, KeyError):
            return None
        
        s3_key = f"vanilla/{version}/server.jar"
        return self._download_and_cache(server_download_url, "Vanilla", version, s3_key)

    def _get_papermc_jar(self, mc_version: str, build: str = 'latest') -> str | None:
        version_url = f"{self.PAPERMC_API}versions/{mc_version}"
        try:
            version_data = requests.get(version_url).json()
        except requests.exceptions.RequestException:
            return None

        if not version_data.get('builds'): return None

        target_build = version_data['builds'][-1] if build == 'latest' else build

        download_url = (
            f"{self.PAPERMC_API}versions/{mc_version}/builds/{target_build}/download"
        )
        
        version_string = f"{mc_version}-b{target_build}"
        s3_key = f"paper/{mc_version}/build-{target_build}.jar"
        return self._download_and_cache(download_url, "PaperMC", version_string, s3_key)
        
    def _get_maven_jar(self, platform: str, version: str, maven_base_url: str) -> str | None:
        jar_name = f"{platform.lower()}-{version}-installer.jar"
        download_url = f"{maven_base_url}{version}/{jar_name}"
        s3_key = f"{platform.lower()}/{version}/{jar_name}"
        return self._download_and_cache(download_url, platform, version, s3_key)

    # --- Public API Interface ---
    
    def get_jar_s3_key(self, platform: str, version: str, build: str = 'latest') -> str | None:
        platform = platform.lower()
        if platform == 'vanilla':
            return self._get_vanilla_jar(version)
        elif platform == 'paper':
            return self._get_papermc_jar(version, build)
        elif platform == 'forge':
            return self._get_maven_jar('Forge', version, self.FORGE_MAVEN_BASE)
        elif platform == 'neoforge':
            return self._get_maven_jar('NeoForge', version, self.NEOFORGE_MAVEN_BASE)
        else:
            return None # Unsupported platform

    def get_jar_direct_url(self, s3_key: str, expires_in: int = 3600) -> str:
        """Generates a secure, pre-signed URL for direct download."""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expires_in 
            )
            return url
        except Exception as e:
            print(f"Error generating pre-signed URL for {s3_key}: {e}")
            return ""

# --- DRF View Implementation ---

class JarDownloadView(APIView):
    """
    API endpoint to request a Minecraft server JAR, ensuring it is cached 
    in S3/MinIO, and returning a pre-signed download URL.
    
    Expected Query Params:
    - platform: [vanilla, paper, forge, neoforge] (Required)
    - version: The Minecraft version (e.g., 1.20.1) (Required)
    - build: Specific build number (Optional, defaults to 'latest' for Paper)
    """
    
    def get(self, request):
        platform = request.query_params.get('platform')
        version = request.query_params.get('version')
        build = request.query_params.get('build', 'latest')
        
        if not platform or not version:
            return Response({
                "error": "Missing required parameters.",
                "example": "/api/jar/download/?platform=paper&version=1.20.1"
            }, status=status.HTTP_400_BAD_REQUEST)
            
        supported_platforms = ['vanilla', 'paper', 'forge', 'neoforge']
        if platform.lower() not in supported_platforms:
            return Response({
                "error": f"Unsupported platform '{platform}'. Supported: {', '.join(supported_platforms)}"
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Initialize the cache using Django settings
            # This call now ensures the S3 bucket exists before proceeding.
            cache = MinecraftJarCache(
                bucket_name=settings.S3_BUCKET_NAME,
                endpoint_url=settings.S3_ENDPOINT,
                access_key=settings.S3_ACCESS_KEY,
                secret_key=settings.S3_SECRET_KEY,
            )
        except Exception as e:
            print(f"Cache Initialization Error: {e}")
            return Response({
                "error": "Server configuration error or failed to connect/create S3 bucket."
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 1. Ensure the JAR is in the cache (downloads and uploads if missing)
        s3_key = cache.get_jar_s3_key(platform, version, build)
        
        if not s3_key:
            return Response({
                "error": f"Could not find or cache the JAR for {platform} version {version}."
            }, status=status.HTTP_404_NOT_FOUND)

        # 2. Generate the temporary, consumable URL (valid for 1 hour)
        download_url = cache.get_jar_direct_url(s3_key, expires_in=3600) 
        
        if not download_url:
             return Response({
                "error": "Failed to generate a secure download URL."
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 3. Return the success response
        return Response({
            "platform": platform,
            "version": version,
            "s3_key": s3_key,
            "download_url": download_url,
            "message": "Use the 'download_url' to consume the JAR directly from S3. Link is valid for 1 hour."
        }, status=status.HTTP_200_OK)
