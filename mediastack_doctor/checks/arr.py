"""Arr stack (Radarr, Sonarr, Prowlarr) diagnostics."""

from typing import Any, Dict, List, Optional

import requests


def run_checks(registry: Any, docker_client: Any) -> List[Dict[str, Any]]:
    """Run Arr stack checks."""
    checks = []
    
    # Check each Arr service
    arr_services = [
        ("radarr", "Radarr", 7878),
        ("sonarr", "Sonarr", 8989),
        ("sonarr-anime", "Sonarr Anime", 8989),
        ("prowlarr", "Prowlarr", 9696),
    ]
    
    for service_key, service_name, default_port in arr_services:
        service_info = _get_arr_service_info(registry, docker_client, service_key, service_name, default_port)
        
        if service_info:
            # API connectivity
            checks.extend(_check_arr_api(service_info))
            
            # Download client connectivity
            checks.extend(_check_download_client(service_info))
            
            # Indexer connectivity (for Prowlarr)
            if service_key == "prowlarr":
                checks.extend(_check_indexer_sync(service_info))
            
            # Path consistency
            checks.extend(_check_path_consistency(service_info, docker_client))
    
    # Path Parity check (A6)
    checks.extend(_check_path_parity(registry, docker_client))
    
    return checks


def _get_arr_service_info(
    registry: Any, 
    docker_client: Any, 
    service_key: str, 
    service_name: str, 
    default_port: int
) -> Optional[Dict[str, Any]]:
    """Get Arr service connection information."""
    # Try registry first
    service = registry.get_service(service_key)
    
    # Find container
    containers = docker_client.list_containers()
    container = None
    
    for c in containers:
        container_name = c["name"].lower()
        if service_key.replace("-", "") in container_name or service_name.lower() in container_name:
            container = c
            break
    
    if not container:
        return None
    
    # Get network info
    network_info = docker_client.get_container_network_info(container["name"])
    
    # Determine URL
    url = None
    if service and service.url:
        url = service.url
    else:
        # Try to construct URL from container info
        ports = network_info.get("ports", {})
        for container_port, host_bindings in ports.items():
            if str(default_port) in container_port:
                if host_bindings:
                    for binding in host_bindings:
                        if binding.get("HostPort"):
                            port = binding["HostPort"]
                            url = f"http://localhost:{port}"
                            break
                break
    
    if not url:
        return None
    
    # Get API key
    api_key = None
    if service and service.api_key_secret_ref:
        api_key = registry.get_secret(service.api_key_secret_ref)
    
    return {
        "service_key": service_key,
        "service_name": service_name,
        "container": container,
        "url": url,
        "api_key": api_key,
        "network_info": network_info,
    }


def _check_arr_api(service_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check Arr service API connectivity."""
    checks = []
    
    service_name = service_info["service_name"]
    url = service_info["url"]
    api_key = service_info["api_key"]
    
    # Test basic connectivity
    try:
        response = requests.get(f"{url}/api/v3/system/status", timeout=10)
        
        if response.status_code == 200:
            checks.append({
                "id": f"A1_{service_info['service_key']}",
                "category": "Arr Stack (Radarr, Sonarr, Prowlarr)",
                "title": f"{service_name} API Connectivity",
                "severity": "info",
                "evidence": f"{service_name} API is accessible at {url}",
                "why_it_matters": f"{service_name} API is working properly",
                "suggested_fix": None,
            })
        elif response.status_code == 401:
            if api_key:
                checks.append({
                    "id": f"A2_{service_info['service_key']}",
                    "category": "Arr Stack (Radarr, Sonarr, Prowlarr)",
                    "title": f"{service_name} API Authentication",
                    "severity": "fail",
                    "evidence": f"{service_name} API authentication failed",
                    "why_it_matters": f"Cannot access {service_name} API with provided credentials",
                    "suggested_fix": f"Check API key for {service_name} in registry",
                })
            else:
                checks.append({
                    "id": f"A3_{service_info['service_key']}",
                    "category": "Arr Stack (Radarr, Sonarr, Prowlarr)",
                    "title": f"{service_name} API Authentication",
                    "severity": "warn",
                    "evidence": f"No API key configured for {service_name}",
                    "why_it_matters": f"Cannot test {service_name} API functionality",
                    "suggested_fix": f"Configure API key for {service_name} in registry",
                })
        else:
            checks.append({
                "id": f"A4_{service_info['service_key']}",
                "category": "Arr Stack (Radarr, Sonarr, Prowlarr)",
                "title": f"{service_name} API Connectivity",
                "severity": "fail",
                "evidence": f"{service_name} API returned status {response.status_code}",
                "why_it_matters": f"{service_name} API is not accessible",
                "suggested_fix": f"Check {service_name} container status and configuration",
            })
    
    except requests.exceptions.ConnectionError:
        checks.append({
            "id": f"A5_{service_info['service_key']}",
            "category": "Arr Stack (Radarr, Sonarr, Prowlarr)",
            "title": f"{service_name} API Connectivity",
            "severity": "fail",
            "evidence": f"Cannot connect to {service_name} at {url}",
            "why_it_matters": f"{service_name} API is not reachable",
            "suggested_fix": f"Check {service_name} container status and network configuration",
        })
    except Exception as e:
        checks.append({
            "id": f"A6_{service_info['service_key']}",
            "category": "Arr Stack (Radarr, Sonarr, Prowlarr)",
            "title": f"{service_name} API Connectivity",
            "severity": "fail",
            "evidence": f"Error connecting to {service_name}: {e}",
            "why_it_matters": f"{service_name} API is not accessible",
            "suggested_fix": f"Check {service_name} logs and configuration",
        })
    
    return checks


def _check_download_client(service_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check download client connectivity."""
    checks = []
    
    service_name = service_info["service_name"]
    url = service_info["url"]
    api_key = service_info["api_key"]
    
    if not api_key:
        return checks
    
    try:
        # Test download client connectivity
        headers = {"X-Api-Key": api_key}
        response = requests.get(f"{url}/api/v3/downloadclient", headers=headers, timeout=10)
        
        if response.status_code == 200:
            download_clients = response.json()
            
            if download_clients:
                checks.append({
                    "id": f"A7_{service_info['service_key']}",
                    "category": "Arr Stack (Radarr, Sonarr, Prowlarr)",
                    "title": f"{service_name} Download Client",
                    "severity": "info",
                    "evidence": f"{len(download_clients)} download client(s) configured",
                    "why_it_matters": f"{service_name} has download clients configured",
                    "suggested_fix": None,
                })
                
                # Test each download client
                for client in download_clients:
                    client_name = client.get("name", "Unknown")
                    client_type = client.get("implementation", "Unknown")
                    
                    # Test download client
                    test_response = requests.post(
                        f"{url}/api/v3/downloadclient/test",
                        headers=headers,
                        json={"id": client["id"]},
                        timeout=10
                    )
                    
                    if test_response.status_code == 200:
                        checks.append({
                            "id": f"A8_{service_info['service_key']}_{client['id']}",
                            "category": "Arr Stack (Radarr, Sonarr, Prowlarr)",
                            "title": f"{service_name} Download Client Test - {client_name}",
                            "severity": "info",
                            "evidence": f"Download client {client_name} ({client_type}) test passed",
                            "why_it_matters": f"{service_name} can communicate with {client_name}",
                            "suggested_fix": None,
                        })
                    else:
                        checks.append({
                            "id": f"A9_{service_info['service_key']}_{client['id']}",
                            "category": "Arr Stack (Radarr, Sonarr, Prowlarr)",
                            "title": f"{service_name} Download Client Test - {client_name}",
                            "severity": "fail",
                            "evidence": f"Download client {client_name} test failed: {test_response.status_code}",
                            "why_it_matters": f"{service_name} cannot communicate with {client_name}",
                            "suggested_fix": f"Check {client_name} configuration and connectivity",
                        })
            else:
                checks.append({
                    "id": f"A10_{service_info['service_key']}",
                    "category": "Arr Stack (Radarr, Sonarr, Prowlarr)",
                    "title": f"{service_name} Download Client",
                    "severity": "warn",
                    "evidence": "No download clients configured",
                    "why_it_matters": f"{service_name} cannot download content without download clients",
                    "suggested_fix": f"Configure download clients (qBittorrent, SABnzbd) in {service_name}",
                })
    
    except Exception as e:
        checks.append({
            "id": f"A11_{service_info['service_key']}",
            "category": "Arr Stack (Radarr, Sonarr, Prowlarr)",
            "title": f"{service_name} Download Client",
            "severity": "warn",
            "evidence": f"Could not test download clients: {e}",
            "why_it_matters": f"Cannot verify {service_name} download client configuration",
            "suggested_fix": f"Check {service_name} API access and download client configuration",
        })
    
    return checks


def _check_indexer_sync(service_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check Prowlarr indexer sync."""
    checks = []
    
    service_name = service_info["service_name"]
    url = service_info["url"]
    api_key = service_info["api_key"]
    
    if not api_key:
        return checks
    
    try:
        headers = {"X-Api-Key": api_key}
        
        # Check indexers
        indexers_response = requests.get(f"{url}/api/v1/indexer", headers=headers, timeout=10)
        
        if indexers_response.status_code == 200:
            indexers = indexers_response.json()
            
            if indexers:
                checks.append({
                    "id": "A12",
                    "category": "Arr Stack (Radarr, Sonarr, Prowlarr)",
                    "title": f"{service_name} Indexers",
                    "severity": "info",
                    "evidence": f"{len(indexers)} indexer(s) configured",
                    "why_it_matters": f"{service_name} has indexers for content discovery",
                    "suggested_fix": None,
                })
                
                # Check indexer health
                healthy_indexers = 0
                for indexer in indexers:
                    if indexer.get("enable"):
                        healthy_indexers += 1
                
                if healthy_indexers > 0:
                    checks.append({
                        "id": "A13",
                        "category": "Arr Stack (Radarr, Sonarr, Prowlarr)",
                        "title": f"{service_name} Indexer Health",
                        "severity": "info",
                        "evidence": f"{healthy_indexers} enabled indexer(s)",
                        "why_it_matters": f"{service_name} has active indexers for content discovery",
                        "suggested_fix": None,
                    })
                else:
                    checks.append({
                        "id": "A14",
                        "category": "Arr Stack (Radarr, Sonarr, Prowlarr)",
                        "title": f"{service_name} Indexer Health",
                        "severity": "warn",
                        "evidence": "No enabled indexers",
                        "why_it_matters": f"{service_name} cannot discover content without enabled indexers",
                        "suggested_fix": f"Enable indexers in {service_name} configuration",
                    })
            else:
                checks.append({
                    "id": "A15",
                    "category": "Arr Stack (Radarr, Sonarr, Prowlarr)",
                    "title": f"{service_name} Indexers",
                    "severity": "warn",
                    "evidence": "No indexers configured",
                    "why_it_matters": f"{service_name} cannot discover content without indexers",
                    "suggested_fix": f"Configure indexers in {service_name}",
                })
        
        # Check applications (Radarr, Sonarr connections)
        apps_response = requests.get(f"{url}/api/v1/application", headers=headers, timeout=10)
        
        if apps_response.status_code == 200:
            apps = apps_response.json()
            
            if apps:
                checks.append({
                    "id": "A16",
                    "category": "Arr Stack (Radarr, Sonarr, Prowlarr)",
                    "title": f"{service_name} Application Sync",
                    "severity": "info",
                    "evidence": f"Connected to {len(apps)} application(s)",
                    "why_it_matters": f"{service_name} is syncing indexers with Arr applications",
                    "suggested_fix": None,
                })
            else:
                checks.append({
                    "id": "A17",
                    "category": "Arr Stack (Radarr, Sonarr, Prowlarr)",
                    "title": f"{service_name} Application Sync",
                    "severity": "warn",
                    "evidence": "No applications connected",
                    "why_it_matters": f"{service_name} is not syncing indexers with Arr applications",
                    "suggested_fix": f"Configure application connections in {service_name}",
                })
    
    except Exception as e:
        checks.append({
            "id": "A18",
            "category": "Arr Stack (Radarr, Sonarr, Prowlarr)",
            "title": f"{service_name} Indexer Sync",
            "severity": "warn",
            "evidence": f"Could not check indexer sync: {e}",
            "why_it_matters": f"Cannot verify {service_name} indexer configuration",
            "suggested_fix": f"Check {service_name} API access and indexer configuration",
        })
    
    return checks


def _check_path_consistency(service_info: Dict[str, Any], docker_client: Any) -> List[Dict[str, Any]]:
    """Check path consistency with other services."""
    checks = []
    
    service_name = service_info["service_name"]
    container = service_info["container"]
    
    # Get container mounts
    mounts = container.get("mounts", [])
    
    service_mounts = []
    for mount in mounts:
        if mount.get("Type") == "bind":
            source = mount.get("Source", "")
            destination = mount.get("Destination", "")
            
            if any(expected in source for expected in ["/mnt/PLEX22TB", "/mnt/GDRIVE36"]):
                service_mounts.append({
                    "source": source,
                    "destination": destination
                })
    
    if not service_mounts:
        checks.append({
            "id": f"A19_{service_info['service_key']}",
            "category": "Arr Stack (Radarr, Sonarr, Prowlarr)",
            "title": f"{service_name} Media Mounts",
            "severity": "fail",
            "evidence": f"No media volume mounts found for {service_name}",
            "why_it_matters": f"{service_name} cannot access media directories",
            "suggested_fix": f"Add volume mounts for media directories to {service_name} container",
        })
        return checks
    
    # Check mount consistency with qBittorrent
    qb_containers = docker_client.list_containers()
    qb_container = None
    
    for c in qb_containers:
        if "qbittorrent" in c["name"].lower() or "qb" in c["name"].lower():
            qb_container = c
            break
    
    if qb_container:
        qb_mounts = qb_container.get("mounts", [])
        qb_mount_sources = set()
        
        for mount in qb_mounts:
            if mount.get("Type") == "bind":
                source = mount.get("Source", "")
                if any(expected in source for expected in ["/mnt/PLEX22TB", "/mnt/GDRIVE36"]):
                    qb_mount_sources.add(source)
        
        service_mount_sources = set(mount["source"] for mount in service_mounts)
        
        if service_mount_sources != qb_mount_sources:
            checks.append({
                "id": f"A20_{service_info['service_key']}",
                "category": "Arr Stack (Radarr, Sonarr, Prowlarr)",
                "title": f"{service_name} Path Consistency",
                "severity": "warn",
                "evidence": f"Mount sources differ between {service_name} and qBittorrent",
                "why_it_matters": "Inconsistent mount paths can cause file access issues",
                "suggested_fix": f"Ensure {service_name} and qBittorrent use the same mount sources",
            })
        else:
            checks.append({
                "id": f"A21_{service_info['service_key']}",
                "category": "Arr Stack (Radarr, Sonarr, Prowlarr)",
                "title": f"{service_name} Path Consistency",
                "severity": "info",
                "evidence": f"Mount sources consistent between {service_name} and qBittorrent",
                "why_it_matters": "Consistent mount paths ensure proper file access",
                "suggested_fix": None,
            })
    
    return checks


def _check_path_parity(registry: Any, docker_client: Any) -> List[Dict[str, Any]]:
    """Check path parity across all services (A6)."""
    checks = []
    
    # Get all containers
    containers = docker_client.list_containers()
    
    # Build path map
    path_map = {}
    service_paths = {}
    
    # Expected services and their typical paths
    expected_services = {
        "radarr": {"downloads": "/downloads", "media": "/media"},
        "sonarr": {"downloads": "/downloads", "media": "/media"},
        "sonarr-anime": {"downloads": "/downloads", "media": "/media"},
        "qbittorrent": {"downloads": "/downloads"},
        "sabnzbd": {"downloads": "/downloads", "completed": "/completed"},
        "unpackerr": {"downloads": "/downloads", "completed": "/completed"},
    }
    
    # Collect actual paths from containers
    for container in containers:
        container_name = container["name"]
        mounts = container.get("mounts", [])
        
        # Find service type
        service_type = None
        for service in expected_services.keys():
            if service in container_name.lower():
                service_type = service
                break
        
        if not service_type:
            continue
        
        # Extract mount paths
        container_paths = {}
        for mount in mounts:
            if mount.get("Type") == "bind":
                source = mount.get("Source", "")
                destination = mount.get("Destination", "")
                
                # Check if this is a media/download path
                if any(expected in source for expected in ["/mnt/PLEX22TB", "/mnt/GDRIVE36"]):
                    if "/downloads" in destination or "/download" in destination:
                        container_paths["downloads"] = {"source": source, "destination": destination}
                    elif "/media" in destination or "/tv" in destination or "/movies" in destination:
                        container_paths["media"] = {"source": source, "destination": destination}
                    elif "/completed" in destination:
                        container_paths["completed"] = {"source": source, "destination": destination}
        
        if container_paths:
            service_paths[service_type] = container_paths
    
    # Analyze path consistency
    if not service_paths:
        checks.append({
            "id": "A6",
            "category": "Arr Stack (Radarr, Sonarr, Prowlarr)",
            "title": "Path Parity Check",
            "severity": "warn",
            "evidence": "No media services found with volume mounts",
            "why_it_matters": "Cannot verify path consistency without mounted services",
            "suggested_fix": "Ensure media services have proper volume mounts configured",
        })
        return checks
    
    # Check for path mismatches
    download_sources = set()
    media_sources = set()
    
    for service, paths in service_paths.items():
        if "downloads" in paths:
            download_sources.add(paths["downloads"]["source"])
        if "media" in paths:
            media_sources.add(paths["media"]["source"])
    
    # Check download path consistency
    if len(download_sources) > 1:
        checks.append({
            "id": "A6_DOWNLOADS",
            "category": "Arr Stack (Radarr, Sonarr, Prowlarr)",
            "title": "Download Path Consistency",
            "severity": "fail",
            "evidence": f"Multiple download sources: {', '.join(download_sources)}",
            "why_it_matters": "Inconsistent download paths can cause file access issues and failed imports",
            "suggested_fix": "Standardize download paths across all services. Use consistent volume mounts in docker-compose.yml",
        })
    elif download_sources:
        checks.append({
            "id": "A6_DOWNLOADS_OK",
            "category": "Arr Stack (Radarr, Sonarr, Prowlarr)",
            "title": "Download Path Consistency",
            "severity": "info",
            "evidence": f"Consistent download source: {list(download_sources)[0]}",
            "why_it_matters": "Consistent download paths ensure proper file access",
            "suggested_fix": None,
        })
    
    # Check media path consistency
    if len(media_sources) > 1:
        checks.append({
            "id": "A6_MEDIA",
            "category": "Arr Stack (Radarr, Sonarr, Prowlarr)",
            "title": "Media Path Consistency",
            "severity": "warn",
            "evidence": f"Multiple media sources: {', '.join(media_sources)}",
            "why_it_matters": "Multiple media sources may be intentional but should be verified",
            "suggested_fix": "Verify media path configuration matches your storage setup",
        })
    elif media_sources:
        checks.append({
            "id": "A6_MEDIA_OK",
            "category": "Arr Stack (Radarr, Sonarr, Prowlarr)",
            "title": "Media Path Consistency",
            "severity": "info",
            "evidence": f"Consistent media source: {list(media_sources)[0]}",
            "why_it_matters": "Consistent media paths ensure proper library organization",
            "suggested_fix": None,
        })
    
    # Check for common path issues
    common_issues = []
    
    # Check for /downloads vs /data mismatch
    for service, paths in service_paths.items():
        if "downloads" in paths:
            dest = paths["downloads"]["destination"]
            if dest == "/data" and service in ["radarr", "sonarr"]:
                common_issues.append(f"{service} uses /data instead of /downloads")
    
    if common_issues:
        checks.append({
            "id": "A6_COMMON_ISSUES",
            "category": "Arr Stack (Radarr, Sonarr, Prowlarr)",
            "title": "Common Path Issues",
            "severity": "warn",
            "evidence": f"Path issues found: {'; '.join(common_issues)}",
            "why_it_matters": "Common path mismatches can cause import failures",
            "suggested_fix": "Standardize on /downloads for download paths and /media for media paths",
        })
    
    # Generate compose snippet if issues found
    if any(check["severity"] in ["fail", "warn"] for check in checks if check["id"].startswith("A6")):
        compose_snippet = _generate_path_parity_compose_snippet(service_paths)
        checks.append({
            "id": "A6_COMPOSE_SNIPPET",
            "category": "Arr Stack (Radarr, Sonarr, Prowlarr)",
            "title": "Recommended Compose Configuration",
            "severity": "info",
            "evidence": "Path parity issues detected",
            "why_it_matters": "Consistent volume configuration prevents path-related issues",
            "suggested_fix": f"Use this docker-compose.yml snippet:\n```yaml\n{compose_snippet}\n```",
        })
    
    return checks


def _generate_path_parity_compose_snippet(service_paths: Dict[str, Dict[str, Dict[str, str]]]) -> str:
    """Generate a docker-compose snippet for consistent paths."""
    snippet = """# Consistent volume configuration
volumes:
  - /mnt/PLEX22TB:/media
  - /mnt/GDRIVE36:/downloads

# Example service configuration
services:
  radarr:
    volumes:
      - /mnt/PLEX22TB:/media
      - /mnt/GDRIVE36:/downloads
    environment:
      - PUID=1000
      - PGID=1000

  sonarr:
    volumes:
      - /mnt/PLEX22TB:/media
      - /mnt/GDRIVE36:/downloads
    environment:
      - PUID=1000
      - PGID=1000

  qbittorrent:
    volumes:
      - /mnt/GDRIVE36:/downloads
    environment:
      - PUID=1000
      - PGID=1000"""
    
    return snippet
