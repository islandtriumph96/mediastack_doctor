"""qBittorrent diagnostics."""

import base64
import json
from typing import Any, Dict, List, Optional

import requests


def run_checks(registry: Any, docker_client: Any) -> List[Dict[str, Any]]:
    """Run qBittorrent checks."""
    checks = []
    
    # Find qBittorrent container and get connection info
    qb_info = _get_qbittorrent_info(registry, docker_client)
    
    if not qb_info:
        checks.append({
            "id": "Q1",
            "category": "qBittorrent (inside Gluetun)",
            "title": "qBittorrent Container",
            "severity": "fail",
            "evidence": "qBittorrent container not found",
            "why_it_matters": "qBittorrent is not running",
            "suggested_fix": "Start qBittorrent container",
        })
        return checks
    
    # WebUI connectivity checks
    checks.extend(_check_webui_connectivity(qb_info))
    
    # API authentication checks
    checks.extend(_check_api_auth(qb_info))
    
    # Configuration checks
    checks.extend(_check_configuration(qb_info))
    
    # Path consistency checks
    checks.extend(_check_path_consistency(qb_info, docker_client))
    
    return checks


def _get_qbittorrent_info(registry: Any, docker_client: Any) -> Optional[Dict[str, Any]]:
    """Get qBittorrent connection information."""
    # Try registry first
    qb_service = registry.get_service("qbittorrent")
    
    # Find container
    containers = docker_client.list_containers()
    qb_container = None
    
    for container in containers:
        container_name = container["name"].lower()
        if "qbittorrent" in container_name or "qb" in container_name:
            qb_container = container
            break
    
    if not qb_container:
        return None
    
    # Get network info
    network_info = docker_client.get_container_network_info(qb_container["name"])
    
    # Determine URL
    url = None
    if qb_service and qb_service.url:
        url = qb_service.url
    else:
        # Try to construct URL from container info
        ports = network_info.get("ports", {})
        for container_port, host_bindings in ports.items():
            if "8080" in container_port or "8081" in container_port:
                if host_bindings:
                    for binding in host_bindings:
                        if binding.get("HostPort"):
                            port = binding["HostPort"]
                            url = f"http://localhost:{port}"
                            break
                break
    
    if not url:
        return None
    
    # Get credentials
    username = None
    password = None
    
    if qb_service:
        username = qb_service.username
        if qb_service.password_secret_ref:
            password = registry.get_secret(qb_service.password_secret_ref)
    
    return {
        "container": qb_container,
        "url": url,
        "username": username,
        "password": password,
        "network_info": network_info,
    }


def _check_webui_connectivity(qb_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check qBittorrent WebUI connectivity."""
    checks = []
    
    url = qb_info["url"]
    
    try:
        # Test basic connectivity
        response = requests.get(f"{url}/api/v2/app/version", timeout=10)
        
        if response.status_code == 200:
            checks.append({
                "id": "Q2",
                "category": "qBittorrent (inside Gluetun)",
                "title": "WebUI Connectivity",
                "severity": "info",
                "evidence": f"WebUI accessible at {url}",
                "why_it_matters": "qBittorrent WebUI is reachable",
                "suggested_fix": None,
            })
        elif response.status_code == 403:
            checks.append({
                "id": "Q3",
                "category": "qBittorrent (inside Gluetun)",
                "title": "WebUI Connectivity",
                "severity": "warn",
                "evidence": f"WebUI requires authentication at {url}",
                "why_it_matters": "WebUI is accessible but requires login",
                "suggested_fix": "Configure authentication credentials",
            })
        else:
            checks.append({
                "id": "Q4",
                "category": "qBittorrent (inside Gluetun)",
                "title": "WebUI Connectivity",
                "severity": "fail",
                "evidence": f"WebUI returned status {response.status_code} at {url}",
                "why_it_matters": "WebUI is not accessible",
                "suggested_fix": "Check qBittorrent container status and port configuration",
            })
    
    except requests.exceptions.ConnectionError:
        checks.append({
            "id": "Q5",
            "category": "qBittorrent (inside Gluetun)",
            "title": "WebUI Connectivity",
            "severity": "fail",
            "evidence": f"Cannot connect to {url}",
            "why_it_matters": "qBittorrent WebUI is not reachable",
            "suggested_fix": "Check container status, network configuration, and firewall rules",
        })
    except requests.exceptions.Timeout:
        checks.append({
            "id": "Q6",
            "category": "qBittorrent (inside Gluetun)",
            "title": "WebUI Connectivity",
            "severity": "fail",
            "evidence": f"Connection timeout to {url}",
            "why_it_matters": "qBittorrent WebUI is not responding",
            "suggested_fix": "Check container health and resource usage",
        })
    except Exception as e:
        checks.append({
            "id": "Q7",
            "category": "qBittorrent (inside Gluetun)",
            "title": "WebUI Connectivity",
            "severity": "fail",
            "evidence": f"Error connecting to {url}: {e}",
            "why_it_matters": "qBittorrent WebUI is not accessible",
            "suggested_fix": "Check container logs and configuration",
        })
    
    return checks


def _check_api_auth(qb_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check qBittorrent API authentication."""
    checks = []
    
    url = qb_info["url"]
    username = qb_info.get("username")
    password = qb_info.get("password")
    
    if not username or not password:
        checks.append({
            "id": "Q8",
            "category": "qBittorrent (inside Gluetun)",
            "title": "API Authentication",
            "severity": "warn",
            "evidence": "No authentication credentials configured",
            "why_it_matters": "Cannot test API functionality without credentials",
            "suggested_fix": "Configure qBittorrent username and password in registry",
        })
        return checks
    
    try:
        # Test login
        session = requests.Session()
        login_data = {
            "username": username,
            "password": password
        }
        
        login_response = session.post(f"{url}/api/v2/auth/login", data=login_data, timeout=10)
        
        if login_response.text == "Ok.":
            checks.append({
                "id": "Q9",
                "category": "qBittorrent (inside Gluetun)",
                "title": "API Authentication",
                "severity": "info",
                "evidence": "API authentication successful",
                "why_it_matters": "qBittorrent API is accessible with provided credentials",
                "suggested_fix": None,
            })
            
            # Test API functionality
            checks.extend(_test_api_functionality(session, url))
            
        else:
            checks.append({
                "id": "Q10",
                "category": "qBittorrent (inside Gluetun)",
                "title": "API Authentication",
                "severity": "fail",
                "evidence": f"API authentication failed: {login_response.text}",
                "why_it_matters": "Cannot access qBittorrent API",
                "suggested_fix": "Check username and password, or reset qBittorrent authentication",
            })
    
    except Exception as e:
        checks.append({
            "id": "Q11",
            "category": "qBittorrent (inside Gluetun)",
            "title": "API Authentication",
            "severity": "fail",
            "evidence": f"API authentication error: {e}",
            "why_it_matters": "Cannot test qBittorrent API",
            "suggested_fix": "Check network connectivity and qBittorrent status",
        })
    
    return checks


def _test_api_functionality(session: requests.Session, url: str) -> List[Dict[str, Any]]:
    """Test qBittorrent API functionality."""
    checks = []
    
    try:
        # Test version endpoint
        version_response = session.get(f"{url}/api/v2/app/version", timeout=10)
        if version_response.status_code == 200:
            version = version_response.text.strip('"')
            checks.append({
                "id": "Q12",
                "category": "qBittorrent (inside Gluetun)",
                "title": "API Version",
                "severity": "info",
                "evidence": f"qBittorrent version: {version}",
                "why_it_matters": "API is functional and version is accessible",
                "suggested_fix": None,
            })
        
        # Test preferences
        prefs_response = session.get(f"{url}/api/v2/app/preferences", timeout=10)
        if prefs_response.status_code == 200:
            prefs = prefs_response.json()
            
            # Check save path
            save_path = prefs.get("save_path", "")
            if save_path:
                checks.append({
                    "id": "Q13",
                    "category": "qBittorrent (inside Gluetun)",
                    "title": "Download Path",
                    "severity": "info",
                    "evidence": f"Download path: {save_path}",
                    "why_it_matters": "Download path is configured",
                    "suggested_fix": None,
                })
            
            # Check categories
            categories_response = session.get(f"{url}/api/v2/torrents/categories", timeout=10)
            if categories_response.status_code == 200:
                categories = categories_response.json()
                
                if categories:
                    category_list = list(categories.keys())
                    checks.append({
                        "id": "Q14",
                        "category": "qBittorrent (inside Gluetun)",
                        "title": "Categories Configuration",
                        "severity": "info",
                        "evidence": f"Categories configured: {', '.join(category_list)}",
                        "why_it_matters": "Categories are set up for organized downloads",
                        "suggested_fix": None,
                    })
                    
                    # Check for anime category
                    if any("anime" in cat.lower() for cat in category_list):
                        checks.append({
                            "id": "Q15",
                            "category": "qBittorrent (inside Gluetun)",
                            "title": "Anime Category",
                            "severity": "info",
                            "evidence": "Anime category is configured",
                            "why_it_matters": "Anime downloads can be properly categorized",
                            "suggested_fix": None,
                        })
                    else:
                        checks.append({
                            "id": "Q16",
                            "category": "qBittorrent (inside Gluetun)",
                            "title": "Anime Category",
                            "severity": "warn",
                            "evidence": "No anime category found",
                            "why_it_matters": "Anime downloads may not be properly categorized",
                            "suggested_fix": "Create an 'anime' category in qBittorrent",
                        })
        
        # Test torrent list
        torrents_response = session.get(f"{url}/api/v2/torrents/info", timeout=10)
        if torrents_response.status_code == 200:
            torrents = torrents_response.json()
            active_torrents = len([t for t in torrents if t.get("state") in ["downloading", "uploading", "stalledDL", "stalledUP"]])
            
            checks.append({
                "id": "Q17",
                "category": "qBittorrent (inside Gluetun)",
                "title": "Active Torrents",
                "severity": "info",
                "evidence": f"{active_torrents} active torrents out of {len(torrents)} total",
                "why_it_matters": "qBittorrent is managing torrents",
                "suggested_fix": None,
            })
    
    except Exception as e:
        checks.append({
            "id": "Q18",
            "category": "qBittorrent (inside Gluetun)",
            "title": "API Functionality",
            "severity": "warn",
            "evidence": f"API functionality test failed: {e}",
            "why_it_matters": "Some API features may not be working",
            "suggested_fix": "Check qBittorrent logs and configuration",
        })
    
    return checks


def _check_configuration(qb_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check qBittorrent configuration."""
    checks = []
    
    # This would require API access, so we'll do basic checks
    container = qb_info["container"]
    network_info = qb_info["network_info"]
    
    # Check if container is using Gluetun network
    networks = network_info.get("networks", {})
    is_in_gluetun_network = any("gluetun" in net_name.lower() for net_name in networks.keys())
    
    if is_in_gluetun_network:
        checks.append({
            "id": "Q19",
            "category": "qBittorrent (inside Gluetun)",
            "title": "Network Configuration",
            "severity": "info",
            "evidence": "qBittorrent is on Gluetun network",
            "why_it_matters": "qBittorrent traffic is routed through VPN",
            "suggested_fix": None,
        })
    else:
        checks.append({
            "id": "Q20",
            "category": "qBittorrent (inside Gluetun)",
            "title": "Network Configuration",
            "severity": "warn",
            "evidence": "qBittorrent is not on Gluetun network",
            "why_it_matters": "qBittorrent traffic may not be routed through VPN",
            "suggested_fix": "Configure qBittorrent to use Gluetun network or network_mode: service:gluetun",
        })
    
    return checks


def _check_path_consistency(qb_info: Dict[str, Any], docker_client: Any) -> List[Dict[str, Any]]:
    """Check path consistency with other services."""
    checks = []
    
    # Get qBittorrent container mounts
    container = qb_info["container"]
    mounts = container.get("mounts", [])
    
    qb_mounts = []
    for mount in mounts:
        if mount.get("Type") == "bind":
            source = mount.get("Source", "")
            destination = mount.get("Destination", "")
            
            if any(expected in source for expected in ["/mnt/PLEX22TB", "/mnt/GDRIVE36"]):
                qb_mounts.append({
                    "source": source,
                    "destination": destination
                })
    
    if not qb_mounts:
        checks.append({
            "id": "Q21",
            "category": "qBittorrent (inside Gluetun)",
            "title": "Media Mounts",
            "severity": "fail",
            "evidence": "No media volume mounts found",
            "why_it_matters": "qBittorrent cannot access media directories",
            "suggested_fix": "Add volume mounts for media directories to qBittorrent container",
        })
        return checks
    
    # Check mount consistency with other services
    other_containers = docker_client.list_containers()
    media_services = ["radarr", "sonarr", "sonarr-anime", "sabnzbd", "unpackerr"]
    
    for service in media_services:
        service_containers = [c for c in other_containers if service in c["name"].lower()]
        
        if service_containers:
            service_container = service_containers[0]
            service_mounts = service_container.get("mounts", [])
            
            # Check if service has same mount sources
            service_mount_sources = set()
            for mount in service_mounts:
                if mount.get("Type") == "bind":
                    source = mount.get("Source", "")
                    if any(expected in source for expected in ["/mnt/PLEX22TB", "/mnt/GDRIVE36"]):
                        service_mount_sources.add(source)
            
            qb_mount_sources = set(mount["source"] for mount in qb_mounts)
            
            if service_mount_sources != qb_mount_sources:
                checks.append({
                    "id": f"Q22_{service}",
                    "category": "qBittorrent (inside Gluetun)",
                    "title": f"Path Consistency - {service}",
                    "severity": "warn",
                    "evidence": f"Mount sources differ between qBittorrent and {service}",
                    "why_it_matters": "Inconsistent mount paths can cause file access issues",
                    "suggested_fix": f"Ensure {service} and qBittorrent use the same mount sources",
                })
            else:
                checks.append({
                    "id": f"Q23_{service}",
                    "category": "qBittorrent (inside Gluetun)",
                    "title": f"Path Consistency - {service}",
                    "severity": "info",
                    "evidence": f"Mount sources consistent between qBittorrent and {service}",
                    "why_it_matters": "Consistent mount paths ensure proper file access",
                    "suggested_fix": None,
                })
    
    return checks
