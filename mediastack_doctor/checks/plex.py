"""Plex server diagnostics."""

from typing import Any, Dict, List, Optional

import requests


def run_checks(registry: Any, docker_client: Any) -> List[Dict[str, Any]]:
    """Run Plex checks."""
    checks = []
    
    # Get Plex info
    plex_info = _get_plex_info(registry, docker_client)
    
    if not plex_info:
        checks.append({
            "id": "P1",
            "category": "Plex",
            "title": "Plex Container",
            "severity": "fail",
            "evidence": "Plex container not found",
            "why_it_matters": "Plex media server is not running",
            "suggested_fix": "Start Plex container",
        })
        return checks
    
    # Server connectivity
    checks.extend(_check_plex_connectivity(plex_info))
    
    # Library and media access
    checks.extend(_check_plex_libraries(plex_info))
    
    # Remote access
    checks.extend(_check_plex_remote_access(plex_info))
    
    # Hardware transcode detection (P4)
    checks.extend(_check_hardware_transcode(plex_info, docker_client))
    
    return checks


def _get_plex_info(registry: Any, docker_client: Any) -> Optional[Dict[str, Any]]:
    """Get Plex connection information."""
    # Try registry first
    plex_service = registry.get_service("plex")
    
    # Find container
    containers = docker_client.list_containers()
    plex_container = None
    
    for container in containers:
        container_name = container["name"].lower()
        if "plex" in container_name:
            plex_container = container
            break
    
    if not plex_container:
        return None
    
    # Get network info
    network_info = docker_client.get_container_network_info(plex_container["name"])
    
    # Determine URL
    url = None
    if plex_service and plex_service.url:
        url = plex_service.url
    else:
        # Try to construct URL from container info
        ports = network_info.get("ports", {})
        for container_port, host_bindings in ports.items():
            if "32400" in container_port:
                if host_bindings:
                    for binding in host_bindings:
                        if binding.get("HostPort"):
                            port = binding["HostPort"]
                            url = f"http://localhost:{port}"
                            break
                break
    
    if not url:
        return None
    
    # Get token
    token = None
    if plex_service and plex_service.token_secret_ref:
        token = registry.get_secret(plex_service.token_secret_ref)
    
    return {
        "container": plex_container,
        "url": url,
        "token": token,
        "network_info": network_info,
    }


def _check_plex_connectivity(plex_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check Plex server connectivity."""
    checks = []
    
    url = plex_info["url"]
    token = plex_info["token"]
    
    try:
        # Test basic connectivity
        response = requests.get(f"{url}/", timeout=10)
        
        if response.status_code == 200:
            checks.append({
                "id": "P2",
                "category": "Plex",
                "title": "Plex Server Connectivity",
                "severity": "info",
                "evidence": f"Plex server is accessible at {url}",
                "why_it_matters": "Plex server is running and accessible",
                "suggested_fix": None,
            })
        else:
            checks.append({
                "id": "P3",
                "category": "Plex",
                "title": "Plex Server Connectivity",
                "severity": "fail",
                "evidence": f"Plex server returned status {response.status_code}",
                "why_it_matters": "Plex server is not accessible",
                "suggested_fix": "Check Plex container status and configuration",
            })
    
    except requests.exceptions.ConnectionError:
        checks.append({
            "id": "P4",
            "category": "Plex",
            "title": "Plex Server Connectivity",
            "severity": "fail",
            "evidence": f"Cannot connect to Plex server at {url}",
            "why_it_matters": "Plex server is not reachable",
            "suggested_fix": "Check Plex container status and network configuration",
        })
    except Exception as e:
        checks.append({
            "id": "P5",
            "category": "Plex",
            "title": "Plex Server Connectivity",
            "severity": "fail",
            "evidence": f"Error connecting to Plex server: {e}",
            "why_it_matters": "Plex server is not accessible",
            "suggested_fix": "Check Plex logs and configuration",
        })
    
    return checks


def _check_plex_libraries(plex_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check Plex libraries and media access."""
    checks = []
    
    url = plex_info["url"]
    token = plex_info["token"]
    
    if not token:
        checks.append({
            "id": "P6",
            "category": "Plex",
            "title": "Plex Token",
            "severity": "warn",
            "evidence": "No Plex token configured",
            "why_it_matters": "Cannot test Plex API functionality without token",
            "suggested_fix": "Configure Plex token in registry",
        })
        return checks
    
    try:
        # Test API connectivity
        headers = {"X-Plex-Token": token}
        response = requests.get(f"{url}/library/sections", headers=headers, timeout=10)
        
        if response.status_code == 200:
            checks.append({
                "id": "P7",
                "category": "Plex",
                "title": "Plex API Access",
                "severity": "info",
                "evidence": "Plex API is accessible with provided token",
                "why_it_matters": "Plex API is working properly",
                "suggested_fix": None,
            })
            
            # Check libraries
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.text)
            libraries = root.findall(".//Directory")
            
            if libraries:
                checks.append({
                    "id": "P8",
                    "category": "Plex",
                    "title": "Plex Libraries",
                    "severity": "info",
                    "evidence": f"{len(libraries)} library(ies) configured",
                    "why_it_matters": "Plex has libraries configured for media",
                    "suggested_fix": None,
                })
                
                # Check library paths
                for library in libraries:
                    library_title = library.get("title", "Unknown")
                    library_type = library.get("type", "Unknown")
                    
                    checks.append({
                        "id": f"P9_{library.get('key', 'unknown')}",
                        "category": "Plex",
                        "title": f"Plex Library - {library_title}",
                        "severity": "info",
                        "evidence": f"Library '{library_title}' ({library_type}) is configured",
                        "why_it_matters": f"Plex library '{library_title}' is available",
                        "suggested_fix": None,
                    })
            else:
                checks.append({
                    "id": "P10",
                    "category": "Plex",
                    "title": "Plex Libraries",
                    "severity": "warn",
                    "evidence": "No libraries configured",
                    "why_it_matters": "Plex has no libraries for media",
                    "suggested_fix": "Configure libraries in Plex server",
                })
        
        else:
            checks.append({
                "id": "P11",
                "category": "Plex",
                "title": "Plex API Access",
                "severity": "fail",
                "evidence": f"Plex API returned status {response.status_code}",
                "why_it_matters": "Cannot access Plex API",
                "suggested_fix": "Check Plex token and server configuration",
            })
    
    except Exception as e:
        checks.append({
            "id": "P12",
            "category": "Plex",
            "title": "Plex Libraries",
            "severity": "warn",
            "evidence": f"Could not check Plex libraries: {e}",
            "why_it_matters": "Cannot verify Plex library configuration",
            "suggested_fix": "Check Plex API access and library configuration",
        })
    
    return checks


def _check_plex_remote_access(plex_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check Plex remote access configuration."""
    checks = []
    
    url = plex_info["url"]
    token = plex_info["token"]
    
    if not token:
        return checks
    
    try:
        # Check remote access status
        headers = {"X-Plex-Token": token}
        response = requests.get(f"{url}/status/sessions", headers=headers, timeout=10)
        
        if response.status_code == 200:
            checks.append({
                "id": "P13",
                "category": "Plex",
                "title": "Plex Remote Access",
                "severity": "info",
                "evidence": "Plex remote access is configured",
                "why_it_matters": "Plex can be accessed remotely",
                "suggested_fix": None,
            })
        else:
            checks.append({
                "id": "P14",
                "category": "Plex",
                "title": "Plex Remote Access",
                "severity": "warn",
                "evidence": f"Plex remote access status unclear: {response.status_code}",
                "why_it_matters": "Remote access status is unclear",
                "suggested_fix": "Check Plex remote access configuration",
            })
    
    except Exception as e:
        checks.append({
            "id": "P15",
            "category": "Plex",
            "title": "Plex Remote Access",
            "severity": "warn",
            "evidence": f"Could not check Plex remote access: {e}",
            "why_it_matters": "Cannot verify Plex remote access configuration",
            "suggested_fix": "Check Plex remote access settings",
        })
    
    return checks


def _check_hardware_transcode(plex_info: Dict[str, Any], docker_client: Any) -> List[Dict[str, Any]]:
    """Check Plex hardware transcoding status (P4)."""
    checks = []
    
    container = plex_info.get("container")
    if not container:
        checks.append({
            "id": "P4",
            "category": "Plex",
            "title": "Hardware Transcoding",
            "severity": "warn",
            "evidence": "Plex container not found",
            "why_it_matters": "Cannot check hardware transcoding configuration",
            "suggested_fix": "Ensure Plex container is running",
        })
        return checks
    
    container_name = container["name"]
    
    # Check container environment for hardware acceleration
    container_info = docker_client.inspect_container(container_name)
    if not container_info:
        checks.append({
            "id": "P4",
            "category": "Plex",
            "title": "Hardware Transcoding",
            "severity": "warn",
            "evidence": "Cannot inspect Plex container",
            "why_it_matters": "Cannot check hardware transcoding configuration",
            "suggested_fix": "Check Plex container status",
        })
        return checks
    
    # Check for device mappings (GPU access)
    host_config = container_info.get("HostConfig", {})
    devices = host_config.get("Devices", [])
    device_requests = host_config.get("DeviceRequests", [])
    
    # Check for Intel QSV (Quick Sync Video)
    intel_qsv = False
    nvidia_gpu = False
    vaapi = False
    
    # Check device mappings
    for device in devices:
        device_path = device.get("PathOnHost", "")
        if "/dev/dri" in device_path:
            intel_qsv = True
            vaapi = True
        elif "/dev/nvidia" in device_path:
            nvidia_gpu = True
    
    # Check device requests (newer Docker format)
    for request in device_requests:
        capabilities = request.get("Capabilities", [])
        if "gpu" in capabilities:
            nvidia_gpu = True
        if "compute" in capabilities:
            intel_qsv = True
    
    # Check environment variables
    config = container_info.get("Config", {})
    env_vars = config.get("Env", [])
    
    for env_var in env_vars:
        if env_var.startswith("NVIDIA_VISIBLE_DEVICES="):
            nvidia_gpu = True
        elif env_var.startswith("VAAPI_DEVICE="):
            vaapi = True
        elif env_var.startswith("INTEL_QSV="):
            intel_qsv = True
    
    # Determine hardware acceleration status
    hw_accel_detected = intel_qsv or nvidia_gpu or vaapi
    hw_accel_type = []
    
    if intel_qsv:
        hw_accel_type.append("Intel QSV")
    if nvidia_gpu:
        hw_accel_type.append("NVIDIA NVENC")
    if vaapi:
        hw_accel_type.append("VAAPI")
    
    if hw_accel_detected:
        checks.append({
            "id": "P4",
            "category": "Plex",
            "title": "Hardware Transcoding",
            "severity": "info",
            "evidence": f"Hardware acceleration detected: {', '.join(hw_accel_type)}",
            "why_it_matters": "Hardware transcoding can significantly improve performance and reduce CPU usage",
            "suggested_fix": None,
        })
    else:
        checks.append({
            "id": "P4",
            "category": "Plex",
            "title": "Hardware Transcoding",
            "severity": "warn",
            "evidence": "No hardware acceleration detected",
            "why_it_matters": "Software transcoding may cause high CPU usage and poor performance",
            "suggested_fix": "Configure hardware acceleration for better transcoding performance",
        })
        
        # Add advisor snippet for Intel QSV on NUC
        checks.append({
            "id": "P4_ADVISOR",
            "category": "Plex",
            "title": "Hardware Acceleration Setup",
            "severity": "info",
            "evidence": "Hardware acceleration not configured",
            "why_it_matters": "Hardware acceleration setup guidance",
            "suggested_fix": """For Intel QSV on NUC, add to docker-compose.yml:
```yaml
services:
  plex:
    devices:
      - /dev/dri:/dev/dri
    environment:
      - INTEL_QSV=1
      - VAAPI_DEVICE=/dev/dri/renderD128
    privileged: true
```""",
        })
    
    return checks
