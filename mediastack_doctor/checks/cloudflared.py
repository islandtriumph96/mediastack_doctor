"""Cloudflared tunnel diagnostics."""

from typing import Any, Dict, List, Optional

import requests


def run_checks(registry: Any, docker_client: Any) -> List[Dict[str, Any]]:
    """Run Cloudflared checks."""
    checks = []
    
    # Get Cloudflared info
    cf_info = _get_cloudflared_info(registry, docker_client)
    
    if not cf_info:
        checks.append({
            "id": "C1",
            "category": "Overseerr / Filebrowser / Cloudflared",
            "title": "Cloudflared Container",
            "severity": "fail",
            "evidence": "Cloudflared container not found",
            "why_it_matters": "Cloudflared tunnel is not running",
            "suggested_fix": "Start Cloudflared container",
        })
        return checks
    
    # Tunnel health
    checks.extend(_check_tunnel_health(cf_info))
    
    # Metrics endpoint
    checks.extend(_check_metrics_endpoint(cf_info))
    
    # Routes check (C3)
    checks.extend(_check_cloudflared_routes(cf_info, docker_client))
    
    return checks


def _get_cloudflared_info(registry: Any, docker_client: Any) -> Optional[Dict[str, Any]]:
    """Get Cloudflared connection information."""
    # Try registry first
    cf_service = registry.get_service("cloudflared")
    
    # Find container
    containers = docker_client.list_containers()
    cf_container = None
    
    for container in containers:
        container_name = container["name"].lower()
        if "cloudflared" in container_name or "cloudflare" in container_name:
            cf_container = container
            break
    
    if not cf_container:
        return None
    
    # Get network info
    network_info = docker_client.get_container_network_info(cf_container["name"])
    
    # Get metrics URL
    metrics_url = None
    if cf_service and cf_service.metrics_url:
        metrics_url = cf_service.metrics_url
    else:
        # Try to construct metrics URL
        ports = network_info.get("ports", {})
        for container_port, host_bindings in ports.items():
            if "2000" in container_port:  # Default metrics port
                if host_bindings:
                    for binding in host_bindings:
                        if binding.get("HostPort"):
                            port = binding["HostPort"]
                            metrics_url = f"http://localhost:{port}/metrics"
                            break
                break
    
    return {
        "container": cf_container,
        "metrics_url": metrics_url,
        "network_info": network_info,
    }


def _check_tunnel_health(cf_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check Cloudflared tunnel health."""
    checks = []
    
    container = cf_info["container"]
    container_name = container["name"]
    
    # Check container logs for tunnel status
    from ..utils.docker_client import DockerClient
    docker_client = DockerClient()
    logs = docker_client.get_container_logs(container_name, since="15m")
    
    if "tunnel is ready" in logs.lower() or "tunnel started" in logs.lower():
        checks.append({
            "id": "C2",
            "category": "Overseerr / Filebrowser / Cloudflared",
            "title": "Cloudflared Tunnel Status",
            "severity": "info",
            "evidence": "Cloudflared tunnel is ready",
            "why_it_matters": "Cloudflared tunnel is working properly",
            "suggested_fix": None,
        })
    elif "tunnel failed" in logs.lower() or "error" in logs.lower():
        checks.append({
            "id": "C3",
            "category": "Overseerr / Filebrowser / Cloudflared",
            "title": "Cloudflared Tunnel Status",
            "severity": "fail",
            "evidence": "Cloudflared tunnel errors detected in logs",
            "why_it_matters": "Cloudflared tunnel is not working properly",
            "suggested_fix": "Check Cloudflared configuration and tunnel credentials",
        })
    else:
        checks.append({
            "id": "C4",
            "category": "Overseerr / Filebrowser / Cloudflared",
            "title": "Cloudflared Tunnel Status",
            "severity": "warn",
            "evidence": "Cannot determine tunnel status from logs",
            "why_it_matters": "Tunnel status is unclear",
            "suggested_fix": "Check Cloudflared logs: docker logs cloudflared",
        })
    
    return checks


def _check_metrics_endpoint(cf_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check Cloudflared metrics endpoint."""
    checks = []
    
    metrics_url = cf_info["metrics_url"]
    
    if not metrics_url:
        checks.append({
            "id": "C5",
            "category": "Overseerr / Filebrowser / Cloudflared",
            "title": "Cloudflared Metrics",
            "severity": "warn",
            "evidence": "No metrics URL configured",
            "why_it_matters": "Cannot monitor Cloudflared tunnel metrics",
            "suggested_fix": "Configure metrics URL for Cloudflared",
        })
        return checks
    
    try:
        response = requests.get(metrics_url, timeout=10)
        
        if response.status_code == 200:
            checks.append({
                "id": "C6",
                "category": "Overseerr / Filebrowser / Cloudflared",
                "title": "Cloudflared Metrics",
                "severity": "info",
                "evidence": f"Metrics endpoint accessible at {metrics_url}",
                "why_it_matters": "Cloudflared metrics are available for monitoring",
                "suggested_fix": None,
            })
            
            # Parse metrics for tunnel info
            metrics_text = response.text
            if "cloudflared_tunnel_total_requests" in metrics_text:
                checks.append({
                    "id": "C7",
                    "category": "Overseerr / Filebrowser / Cloudflared",
                    "title": "Cloudflared Tunnel Metrics",
                    "severity": "info",
                    "evidence": "Tunnel metrics are being collected",
                    "why_it_matters": "Tunnel is processing requests",
                    "suggested_fix": None,
                })
        else:
            checks.append({
                "id": "C8",
                "category": "Overseerr / Filebrowser / Cloudflared",
                "title": "Cloudflared Metrics",
                "severity": "warn",
                "evidence": f"Metrics endpoint returned status {response.status_code}",
                "why_it_matters": "Cannot access Cloudflared metrics",
                "suggested_fix": "Check Cloudflared metrics configuration",
            })
    
    except requests.exceptions.ConnectionError:
        checks.append({
            "id": "C9",
            "category": "Overseerr / Filebrowser / Cloudflared",
            "title": "Cloudflared Metrics",
            "severity": "warn",
            "evidence": f"Cannot connect to metrics endpoint at {metrics_url}",
            "why_it_matters": "Cannot monitor Cloudflared tunnel metrics",
            "suggested_fix": "Check Cloudflared metrics port configuration",
        })
    except Exception as e:
            checks.append({
                "id": "C10",
                "category": "Overseerr / Filebrowser / Cloudflared",
                "title": "Cloudflared Metrics",
                "severity": "warn",
                "evidence": f"Error accessing metrics: {e}",
                "why_it_matters": "Cannot monitor Cloudflared tunnel metrics",
                "suggested_fix": "Check Cloudflared configuration and metrics endpoint",
            })
    
    return checks


def _check_cloudflared_routes(cf_info: Dict[str, Any], docker_client: Any) -> List[Dict[str, Any]]:
    """Check Cloudflared routes and backend connectivity (C3)."""
    checks = []
    
    container = cf_info["container"]
    container_name = container["name"]
    
    # Get container environment variables
    container_info = docker_client.inspect_container(container_name)
    if not container_info:
        checks.append({
            "id": "C3",
            "category": "Overseerr / Filebrowser / Cloudflared",
            "title": "Cloudflared Routes",
            "severity": "warn",
            "evidence": "Cannot inspect Cloudflared container",
            "why_it_matters": "Cannot verify tunnel routes configuration",
            "suggested_fix": "Check Cloudflared container status and configuration",
        })
        return checks
    
    # Extract environment variables
    config = container_info.get("Config", {})
    env_vars = config.get("Env", [])
    
    routes = []
    tunnel_token = None
    
    for env_var in env_vars:
        if env_var.startswith("TUNNEL_TOKEN="):
            tunnel_token = env_var.split("=", 1)[1]
        elif env_var.startswith("TUNNEL_HOSTNAME="):
            # Extract hostname from environment
            hostname = env_var.split("=", 1)[1]
            routes.append({"hostname": hostname, "service": "unknown"})
    
    # Try to get routes from metrics if available
    metrics_url = cf_info.get("metrics_url")
    if metrics_url:
        try:
            response = requests.get(metrics_url, timeout=10)
            if response.status_code == 200:
                metrics_text = response.text
                
                # Parse metrics for route information
                import re
                route_matches = re.findall(r'cloudflared_tunnel_total_requests\{hostname="([^"]+)"', metrics_text)
                for hostname in route_matches:
                    routes.append({"hostname": hostname, "service": "unknown"})
        
        except Exception:
            pass  # Continue with environment-based detection
    
    if not routes:
        checks.append({
            "id": "C3_NO_ROUTES",
            "category": "Overseerr / Filebrowser / Cloudflared",
            "title": "Cloudflared Routes",
            "severity": "warn",
            "evidence": "No tunnel routes detected",
            "why_it_matters": "Cloudflared tunnel may not be properly configured",
            "suggested_fix": "Configure tunnel routes in Cloudflared configuration",
        })
        return checks
    
    # Check each route
    for route in routes:
        hostname = route["hostname"]
        
        # Determine expected service based on hostname patterns
        expected_service = None
        if "overseerr" in hostname.lower():
            expected_service = "overseerr"
        elif "filebrowser" in hostname.lower():
            expected_service = "filebrowser"
        elif "plex" in hostname.lower():
            expected_service = "plex"
        elif "radarr" in hostname.lower():
            expected_service = "radarr"
        elif "sonarr" in hostname.lower():
            expected_service = "sonarr"
        
        if expected_service:
            route["service"] = expected_service
            
            # Check if service is accessible
            service_accessible = _check_backend_service(expected_service, docker_client)
            
            if service_accessible:
                checks.append({
                    "id": f"C3_{expected_service}",
                    "category": "Overseerr / Filebrowser / Cloudflared",
                    "title": f"Cloudflared Route - {expected_service}",
                    "severity": "info",
                    "evidence": f"Route {hostname} → {expected_service} is accessible",
                    "why_it_matters": f"Cloudflared tunnel is properly routing {expected_service}",
                    "suggested_fix": None,
                })
                
                # Special warning for Plex
                if expected_service == "plex":
                    checks.append({
                        "id": f"C3_{expected_service}_WARNING",
                        "category": "Overseerr / Filebrowser / Cloudflared",
                        "title": f"Plex via Cloudflare",
                        "severity": "warn",
                        "evidence": f"Plex is routed through Cloudflare tunnel ({hostname})",
                        "why_it_matters": "Plex clients often prefer direct access or app.plex.tv for better performance",
                        "suggested_fix": "Consider using Plex's native remote access instead of Cloudflare tunnel, or implement Zero-Trust authentication",
                    })
            else:
                checks.append({
                    "id": f"C3_{expected_service}_FAIL",
                    "category": "Overseerr / Filebrowser / Cloudflared",
                    "title": f"Cloudflared Route - {expected_service}",
                    "severity": "fail",
                    "evidence": f"Route {hostname} → {expected_service} backend is not accessible",
                    "why_it_matters": f"Cloudflared tunnel cannot reach {expected_service} backend",
                    "suggested_fix": f"Check {expected_service} container status and network configuration",
                })
        else:
            checks.append({
                "id": f"C3_UNKNOWN_{hostname.replace('.', '_')}",
                "category": "Overseerr / Filebrowser / Cloudflared",
                "title": f"Cloudflared Route - {hostname}",
                "severity": "info",
                "evidence": f"Route {hostname} detected (unknown service)",
                "why_it_matters": "Cloudflared tunnel has a route configured",
                "suggested_fix": "Verify this route is intentional and properly configured",
            })
    
    # Summary check
    if routes:
        accessible_routes = len([c for c in checks if c.get("id", "").startswith("C3_") and c.get("severity") == "info" and not c.get("id", "").endswith("_WARNING")])
        total_routes = len(routes)
        
        checks.append({
            "id": "C3_SUMMARY",
            "category": "Overseerr / Filebrowser / Cloudflared",
            "title": "Cloudflared Routes Summary",
            "severity": "info",
            "evidence": f"{accessible_routes}/{total_routes} routes are accessible",
            "why_it_matters": "Cloudflared tunnel route health summary",
            "suggested_fix": None,
        })
    
    return checks


def _check_backend_service(service_name: str, docker_client: Any) -> bool:
    """Check if a backend service is accessible."""
    containers = docker_client.list_containers()
    
    # Find the service container
    service_container = None
    for container in containers:
        if service_name in container["name"].lower():
            service_container = container
            break
    
    if not service_container:
        return False
    
    # Check if container is running
    status = service_container.get("status", "")
    if not status.startswith("Up"):
        return False
    
    # Try to get network info and test connectivity
    try:
        network_info = docker_client.get_container_network_info(service_container["name"])
        networks = network_info.get("networks", {})
        
        if not networks:
            return False
        
        # Get the first network and try to construct a URL
        network_name = list(networks.keys())[0]
        network_details = networks[network_name]
        ip_address = network_details.get("IPAddress", "")
        
        if not ip_address:
            return False
        
        # Try to determine the port and test connectivity
        ports = network_info.get("ports", {})
        for container_port, host_bindings in ports.items():
            if host_bindings:
                # Extract port number
                port_match = container_port.split("/")[0]
                try:
                    port = int(port_match)
                    
                    # Test connectivity
                    import requests
                    url = f"http://{ip_address}:{port}"
                    response = requests.get(url, timeout=5)
                    return response.status_code in [200, 401, 403]  # Any response is good
                except (ValueError, requests.exceptions.RequestException):
                    continue
        
        return False
    
    except Exception:
        return False
