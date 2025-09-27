"""Overseerr diagnostics."""

from typing import Any, Dict, List, Optional

import requests


def run_checks(registry: Any, docker_client: Any) -> List[Dict[str, Any]]:
    """Run Overseerr checks."""
    checks = []
    
    # Get Overseerr info
    overseerr_info = _get_overseerr_info(registry, docker_client)
    
    if not overseerr_info:
        checks.append({
            "id": "O1",
            "category": "Overseerr / Filebrowser / Cloudflared",
            "title": "Overseerr Container",
            "severity": "fail",
            "evidence": "Overseerr container not found",
            "why_it_matters": "Overseerr is not running",
            "suggested_fix": "Start Overseerr container",
        })
        return checks
    
    # API connectivity
    checks.extend(_check_overseerr_api(overseerr_info))
    
    # Service connections
    checks.extend(_check_overseerr_connections(overseerr_info))
    
    return checks


def _get_overseerr_info(registry: Any, docker_client: Any) -> Optional[Dict[str, Any]]:
    """Get Overseerr connection information."""
    # Try registry first
    overseerr_service = registry.get_service("overseerr")
    
    # Find container
    containers = docker_client.list_containers()
    overseerr_container = None
    
    for container in containers:
        container_name = container["name"].lower()
        if "overseerr" in container_name:
            overseerr_container = container
            break
    
    if not overseerr_container:
        return None
    
    # Get network info
    network_info = docker_client.get_container_network_info(overseerr_container["name"])
    
    # Determine URL
    url = None
    if overseerr_service and overseerr_service.url:
        url = overseerr_service.url
    else:
        # Try to construct URL from container info
        ports = network_info.get("ports", {})
        for container_port, host_bindings in ports.items():
            if "5055" in container_port:
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
    if overseerr_service and overseerr_service.api_key_secret_ref:
        api_key = registry.get_secret(overseerr_service.api_key_secret_ref)
    
    return {
        "container": overseerr_container,
        "url": url,
        "api_key": api_key,
        "network_info": network_info,
    }


def _check_overseerr_api(overseerr_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check Overseerr API connectivity."""
    checks = []
    
    url = overseerr_info["url"]
    api_key = overseerr_info["api_key"]
    
    try:
        # Test basic connectivity
        response = requests.get(f"{url}/api/v1/status", timeout=10)
        
        if response.status_code == 200:
            checks.append({
                "id": "O2",
                "category": "Overseerr / Filebrowser / Cloudflared",
                "title": "Overseerr API Connectivity",
                "severity": "info",
                "evidence": f"Overseerr API is accessible at {url}",
                "why_it_matters": "Overseerr API is working properly",
                "suggested_fix": None,
            })
        else:
            checks.append({
                "id": "O3",
                "category": "Overseerr / Filebrowser / Cloudflared",
                "title": "Overseerr API Connectivity",
                "severity": "fail",
                "evidence": f"Overseerr API returned status {response.status_code}",
                "why_it_matters": "Overseerr API is not accessible",
                "suggested_fix": "Check Overseerr container status and configuration",
            })
    
    except requests.exceptions.ConnectionError:
        checks.append({
            "id": "O4",
            "category": "Overseerr / Filebrowser / Cloudflared",
            "title": "Overseerr API Connectivity",
            "severity": "fail",
            "evidence": f"Cannot connect to Overseerr at {url}",
            "why_it_matters": "Overseerr API is not reachable",
            "suggested_fix": "Check Overseerr container status and network configuration",
        })
    except Exception as e:
        checks.append({
            "id": "O5",
            "category": "Overseerr / Filebrowser / Cloudflared",
            "title": "Overseerr API Connectivity",
            "severity": "fail",
            "evidence": f"Error connecting to Overseerr: {e}",
            "why_it_matters": "Overseerr API is not accessible",
            "suggested_fix": "Check Overseerr logs and configuration",
        })
    
    return checks


def _check_overseerr_connections(overseerr_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check Overseerr service connections."""
    checks = []
    
    url = overseerr_info["url"]
    api_key = overseerr_info["api_key"]
    
    if not api_key:
        checks.append({
            "id": "O6",
            "category": "Overseerr / Filebrowser / Cloudflared",
            "title": "Overseerr API Key",
            "severity": "warn",
            "evidence": "No API key configured for Overseerr",
            "why_it_matters": "Cannot test Overseerr functionality without API key",
            "suggested_fix": "Configure Overseerr API key in registry",
        })
        return checks
    
    try:
        # Test service connections
        headers = {"X-Api-Key": api_key}
        response = requests.get(f"{url}/api/v1/settings/services", headers=headers, timeout=10)
        
        if response.status_code == 200:
            services = response.json()
            
            # Check for connected services
            connected_services = []
            for service in services:
                if service.get("enabled"):
                    connected_services.append(service.get("name", "Unknown"))
            
            if connected_services:
                checks.append({
                    "id": "O7",
                    "category": "Overseerr / Filebrowser / Cloudflared",
                    "title": "Overseerr Service Connections",
                    "severity": "info",
                    "evidence": f"Connected to services: {', '.join(connected_services)}",
                    "why_it_matters": "Overseerr is connected to media services",
                    "suggested_fix": None,
                })
            else:
                checks.append({
                    "id": "O8",
                    "category": "Overseerr / Filebrowser / Cloudflared",
                    "title": "Overseerr Service Connections",
                    "severity": "warn",
                    "evidence": "No services connected",
                    "why_it_matters": "Overseerr cannot manage media without service connections",
                    "suggested_fix": "Configure service connections in Overseerr",
                })
        
        else:
            checks.append({
                "id": "O9",
                "category": "Overseerr / Filebrowser / Cloudflared",
                "title": "Overseerr Service Connections",
                "severity": "warn",
                "evidence": f"Could not check service connections: {response.status_code}",
                "why_it_matters": "Cannot verify Overseerr service configuration",
                "suggested_fix": "Check Overseerr API access and service configuration",
            })
    
    except Exception as e:
        checks.append({
            "id": "O10",
            "category": "Overseerr / Filebrowser / Cloudflared",
            "title": "Overseerr Service Connections",
            "severity": "warn",
            "evidence": f"Could not check service connections: {e}",
            "why_it_matters": "Cannot verify Overseerr service configuration",
            "suggested_fix": "Check Overseerr API access and service configuration",
        })
    
    return checks
