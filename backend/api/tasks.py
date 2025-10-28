import json
import requests
from api.models import Version
from celery import shared_task
import logging

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

@shared_task
def fetchVanillaVersions():
    print("Fetching vanilla versions...")
    URL_VANILLA = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"

    def _filter_vanilla(versions):
        # Sort versions by releaseTime to ensure we get the absolute latest
        release_versions = sorted(
            [v for v in versions if v['type'] == 'release'],
            key=lambda x: x['releaseTime'],
            reverse=True
        )

        return [v['id'] for v in release_versions]
    
    manifest = _fetch_json(
        URL_VANILLA, 
        key='versions', 
        filter_func=_filter_vanilla
    )

    for version_number in manifest:
        logger.info(f"Vanilla version found: {version_number}")
        obj, created = Version.objects.get_or_create(version_number=version_number)
        print(f"Vanilla version processed: {version_number}")
        if created:
            # si necesitas asignar un tipo relacionado, hazlo explícito aquí
            # from api.models import Type
            # type_obj, _ = Type.objects.get_or_create(name="vanilla")
            # obj.type = type_obj
            # obj.save()
            pass