import json
from rest_framework import views
from rest_framework.response import Response
from rest_framework import status
import requests
import xml.etree.ElementTree as ET
import logging

# Set up logging for the service
logger = logging.getLogger(__name__)

def _fetch_json(url, key=None, filter_func=None):
        """Generic handler for JSON API calls."""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            data = response.json()
            
            if key and key in data:
                versions = data[key]
                if filter_func:
                    versions = filter_func(versions)
                return versions
            
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching data from {url}: {e}")
            return []
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON from {url}")
            return []

def _fetch_xml_versions(url, server_name, limit=5):
    """Generic handler for Maven XML metadata API calls."""
    versions = []
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        
        # Locate the <versions> element within versioning
        versions_element = root.find('.//versioning/versions')
        
        if versions_element is not None:
            # Extract all versions and reverse to get latest first
            all_versions = [v.text for v in versions_element.findall('version')]
            
            # Simple filtering: remove development/beta tags and get the latest
            stable_versions = [
                v for v in all_versions[::-1] 
                if not any(tag in v.upper() for tag in ['SNAPSHOT', 'BETA', 'RC', 'MDC'])
            ]

            # Extract a limited list of unique Minecraft versions
            unique_mc_versions = []
            mc_versions_set = set()

            for full_version in stable_versions:
                # The Minecraft version is typically the part before the first hyphen
                mc_version = full_version.split('-')[0]
                if mc_version not in mc_versions_set:
                    unique_mc_versions.append(full_version)
                    mc_versions_set.add(mc_version)
                    if len(unique_mc_versions) >= limit:
                        break
            
            versions = unique_mc_versions
        
    except (requests.RequestException, requests.Timeout) as e:
        logger.error(f"Error fetching {server_name} data: {e}")
        versions = [f"{server_name} versions unavailable (Error: {e.__class__.__name__})"]
    except ET.ParseError:
        logger.error(f"Failed to parse {server_name} XML metadata.")
        versions = [f"{server_name} versions unavailable (Error: XML Parse Failed)"]

    return versions
    
class VanillaVersions(views.APIView):
    URL_VANILLA = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
    
    @staticmethod
    def _filter_vanilla(versions):
        # Sort versions by releaseTime to ensure we get the absolute latest
        release_versions = sorted(
            [v for v in versions if v['type'] == 'release'],
            key=lambda x: x['releaseTime'],
            reverse=True
        )
        return [v['id'] for v in release_versions]

    def get(self, request):
        """Fetches the latest official stable Vanilla versions."""
        manifest = _fetch_json(
            self.URL_VANILLA, 
            key='versions', 
            filter_func=self._filter_vanilla
        )
    
        return Response(manifest, status=status.HTTP_200_OK) if manifest else Response("Vanilla versions unavailable")
    
class PaperVersions(views.APIView):
    URL_PAPER = "https://api.papermc.io/v2/projects/paper"

    @staticmethod
    def _filter_paper(data):
        # PaperMC API returns versions in ascending order, so we reverse it
        versions = data.get('versions', [])
        return versions[::-1][:len(versions)]
    
    def get(self, request):
        """Fetches the latest Paper versions."""

        versions = _fetch_json(
            self.URL_PAPER, 
            filter_func=self._filter_paper
        )

        return Response(versions, status=status.HTTP_200_OK) if versions else ["Paper versions unavailable"]
    
class ForgeVersions(views.APIView):
    URL_FORGE_MAVEN = "https://files.minecraftforge.net/maven/net/minecraftforge/forge/maven-metadata.xml"

    def get(self, request):
        """Fetches Forge versions by parsing the Maven metadata XML file."""
        versions = _fetch_xml_versions(self.URL_FORGE_MAVEN, "Forge")

        return Response(versions, status=status.HTTP_200_OK) if versions else ["Forge versions unavailable"]
    
class NeoForgeVersions(views.APIView):
    URL_NEOFORGE_MAVEN = "https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml"

    def get(self, request):
        versions = _fetch_xml_versions(self.URL_NEOFORGE_MAVEN, "NeoForge")

        return Response(versions, status=status.HTTP_200_OK) if versions else ["Neoforge versions unavailable"]