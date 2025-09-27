"""SABnzbd diagnostics."""

from typing import Any, Dict, List, Optional

import requests


def run_checks(registry: Any, docker_client: Any) -> List[Dict[str, Any]]:
    """Run SABnzbd checks."""
    checks = []
    
    # Get SABnzbd info
    sab_info = _get_sabnzbd_info(registry, docker_client)
    
    if not sab_info:
        checks.append({
            "id": "S1",
            "category": "SABnzbd",
            "title": "SABnzbd Container",
            "severity": "fail",
            "evidence": "SABnzbd container not found",
            "why_it_matters": "SABnzbd is not running",
            "suggested_fix": "Start SABnzbd container",
        })
        return checks
    
    # API connectivity
    checks.extend(_check_sabnzbd_api(sab_info))
    
    # Queue and configuration
    checks.extend(_check_sabnzbd_config(sab_info))
    
    return checks


def _get_sabnzbd_info(registry: Any, docker_client: Any) -> Optional[Dict[str, Any]]:
    """Get SABnzbd connection information."""
    # Try registry first
    sab_service = registry.get_service("sabnzbd")
    
    # Find container
    containers = docker_client.list_containers()
    sab_container = None
    
    for container in containers:
        container_name = container["name"].lower()
        if "sabnzbd" in container_name or "sab" in container_name:
            sab_container = container
            break
    
    if not sab_container:
        return None
    
    # Get network info
    network_info = docker_client.get_container_network_info(sab_container["name"])
    
    # Determine URL
    url = None
    if sab_service and sab_service.url:
        url = sab_service.url
    else:
        # Try to construct URL from container info
        ports = network_info.get("ports", {})
        for container_port, host_bindings in ports.items():
            if "8080" in container_port:
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
    if sab_service and sab_service.api_key_secret_ref:
        api_key = registry.get_secret(sab_service.api_key_secret_ref)
    
    return {
        "container": sab_container,
        "url": url,
        "api_key": api_key,
        "network_info": network_info,
    }


def _check_sabnzbd_api(sab_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check SABnzbd API connectivity."""
    checks = []
    
    url = sab_info["url"]
    api_key = sab_info["api_key"]
    
    try:
        # Test API connectivity
        params = {"output": "json"}
        if api_key:
            params["apikey"] = api_key
        
        response = requests.get(f"{url}/api", params=params, timeout=10)
        
        if response.status_code == 200:
            checks.append({
                "id": "S2",
                "category": "SABnzbd",
                "title": "SABnzbd API Connectivity",
                "severity": "info",
                "evidence": f"SABnzbd API is accessible at {url}",
                "why_it_matters": "SABnzbd API is working properly",
                "suggested_fix": None,
            })
        else:
            checks.append({
                "id": "S3",
                "category": "SABnzbd",
                "title": "SABnzbd API Connectivity",
                "severity": "fail",
                "evidence": f"SABnzbd API returned status {response.status_code}",
                "why_it_matters": "SABnzbd API is not accessible",
                "suggested_fix": "Check SABnzbd container status and configuration",
            })
    
    except requests.exceptions.ConnectionError:
        checks.append({
            "id": "S4",
            "category": "SABnzbd",
            "title": "SABnzbd API Connectivity",
            "severity": "fail",
            "evidence": f"Cannot connect to SABnzbd at {url}",
            "why_it_matters": "SABnzbd API is not reachable",
            "suggested_fix": "Check SABnzbd container status and network configuration",
        })
    except Exception as e:
        checks.append({
            "id": "S5",
            "category": "SABnzbd",
            "title": "SABnzbd API Connectivity",
            "severity": "fail",
            "evidence": f"Error connecting to SABnzbd: {e}",
            "why_it_matters": "SABnzbd API is not accessible",
            "suggested_fix": "Check SABnzbd logs and configuration",
        })
    
    return checks


def _check_sabnzbd_config(sab_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check SABnzbd configuration."""
    checks = []
    
    url = sab_info["url"]
    api_key = sab_info["api_key"]
    
    if not api_key:
        checks.append({
            "id": "S6",
            "category": "SABnzbd",
            "title": "SABnzbd API Key",
            "severity": "warn",
            "evidence": "No API key configured for SABnzbd",
            "why_it_matters": "Cannot test SABnzbd functionality without API key",
            "suggested_fix": "Configure SABnzbd API key in registry",
        })
        return checks
    
    try:
        # Get queue status
        params = {"output": "json", "apikey": api_key, "mode": "queue"}
        response = requests.get(f"{url}/api", params=params, timeout=10)
        
        if response.status_code == 200:
            queue_data = response.json()
            queue = queue_data.get("queue", {})
            
            if queue:
                checks.append({
                    "id": "S7",
                    "category": "SABnzbd",
                    "title": "SABnzbd Queue",
                    "severity": "info",
                    "evidence": f"SABnzbd queue is accessible",
                    "why_it_matters": "SABnzbd is processing downloads",
                    "suggested_fix": None,
                })
            else:
                checks.append({
                    "id": "S8",
                    "category": "SABnzbd",
                    "title": "SABnzbd Queue",
                    "severity": "info",
                    "evidence": "SABnzbd queue is empty",
                    "why_it_matters": "SABnzbd is ready to process downloads",
                    "suggested_fix": None,
                })
        
        # Get configuration
        params = {"output": "json", "apikey": api_key, "mode": "get_config"}
        response = requests.get(f"{url}/api", params=params, timeout=10)
        
        if response.status_code == 200:
            config_data = response.json()
            config = config_data.get("config", {})
            
            # Check download directory
            download_dir = config.get("download_dir", "")
            if download_dir:
                checks.append({
                    "id": "S9",
                    "category": "SABnzbd",
                    "title": "SABnzbd Download Directory",
                    "severity": "info",
                    "evidence": f"Download directory: {download_dir}",
                    "why_it_matters": "SABnzbd download directory is configured",
                    "suggested_fix": None,
                })
            
            # Check completed directory
            complete_dir = config.get("complete_dir", "")
            if complete_dir:
                checks.append({
                    "id": "S10",
                    "category": "SABnzbd",
                    "title": "SABnzbd Complete Directory",
                    "severity": "info",
                    "evidence": f"Complete directory: {complete_dir}",
                    "why_it_matters": "SABnzbd complete directory is configured",
                    "suggested_fix": None,
                })
    
    except Exception as e:
        checks.append({
            "id": "S11",
            "category": "SABnzbd",
            "title": "SABnzbd Configuration",
            "severity": "warn",
            "evidence": f"Could not check SABnzbd configuration: {e}",
            "why_it_matters": "Cannot verify SABnzbd configuration",
            "suggested_fix": "Check SABnzbd API access and configuration",
        })
    
    return checks
