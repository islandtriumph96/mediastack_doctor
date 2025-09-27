"""Gluetun/PIA VPN diagnostics."""

import re
import subprocess
from typing import Any, Dict, List, Optional


def run_checks(registry: Any, docker_client: Any, allow_external_checks: bool = False) -> List[Dict[str, Any]]:
    """Run Gluetun/PIA VPN checks."""
    checks = []
    
    # Find Gluetun container
    gluetun_container = _find_gluetun_container(docker_client, registry)
    
    if not gluetun_container:
        checks.append({
            "id": "G1",
            "category": "Gluetun / PIA",
            "title": "Gluetun Container",
            "severity": "fail",
            "evidence": "Gluetun container not found",
            "why_it_matters": "VPN functionality is not available",
            "suggested_fix": "Start Gluetun container with proper PIA configuration",
        })
        return checks
    
    # VPN connection checks
    checks.extend(_check_vpn_connection(gluetun_container, docker_client))
    
    # Port-forward checks
    checks.extend(_check_port_forward(gluetun_container, docker_client, allow_external_checks))
    
    # Firewall checks
    checks.extend(_check_firewall_rules(gluetun_container, docker_client))
    
    # DNS leak checks
    checks.extend(_check_dns_leaks(gluetun_container, docker_client))
    
    # qBittorrent leak guard (G5)
    checks.extend(_check_qbittorrent_leak_guard(gluetun_container, docker_client))
    
    # PF reliability scoring (G6)
    checks.extend(_check_pf_reliability(gluetun_container, docker_client))
    
    return checks


def _find_gluetun_container(docker_client: Any, registry: Any) -> Optional[Dict[str, Any]]:
    """Find Gluetun container."""
    containers = docker_client.list_containers()
    
    # Try registry first
    gluetun_service = registry.get_service("gluetun")
    if gluetun_service and gluetun_service.container:
        for container in containers:
            if container["name"] == gluetun_service.container:
                return container
    
    # Search by name patterns
    for container in containers:
        container_name = container["name"].lower()
        if "gluetun" in container_name:
            return container
    
    return None


def _check_vpn_connection(gluetun_container: Dict[str, Any], docker_client: Any) -> List[Dict[str, Any]]:
    """Check VPN connection status."""
    checks = []
    
    container_name = gluetun_container["name"]
    logs = docker_client.get_container_logs(container_name, since="15m")
    
    # Check for connection success
    if "VPN connection established" in logs or "VPN is ready" in logs:
        checks.append({
            "id": "G2",
            "category": "Gluetun / PIA",
            "title": "VPN Connection Status",
            "severity": "info",
            "evidence": "VPN connection is established",
            "why_it_matters": "VPN is working and traffic is being routed through PIA",
            "suggested_fix": None,
        })
    elif "VPN connection failed" in logs or "Failed to connect" in logs:
        checks.append({
            "id": "G3",
            "category": "Gluetun / PIA",
            "title": "VPN Connection Status",
            "severity": "fail",
            "evidence": "VPN connection failed",
            "why_it_matters": "VPN is not working, traffic may be exposed",
            "suggested_fix": "Check PIA credentials and server configuration in Gluetun",
        })
    else:
        checks.append({
            "id": "G4",
            "category": "Gluetun / PIA",
            "title": "VPN Connection Status",
            "severity": "warn",
            "evidence": "Cannot determine VPN connection status from logs",
            "why_it_matters": "VPN status is unclear",
            "suggested_fix": "Check Gluetun logs: docker logs gluetun",
        })
    
    # Check for PIA server region
    region_match = re.search(r"Connected to ([A-Za-z0-9\s]+) server", logs)
    if region_match:
        region = region_match.group(1).strip()
        checks.append({
            "id": "G5",
            "category": "Gluetun / PIA",
            "title": "PIA Server Region",
            "severity": "info",
            "evidence": f"Connected to PIA server: {region}",
            "why_it_matters": "VPN is connected to a specific PIA server region",
            "suggested_fix": None,
        })
    
    # Check for connection protocol
    protocol_match = re.search(r"(OpenVPN|WireGuard) connection", logs)
    if protocol_match:
        protocol = protocol_match.group(1)
        checks.append({
            "id": "G6",
            "category": "Gluetun / PIA",
            "title": "VPN Protocol",
            "severity": "info",
            "evidence": f"Using {protocol} protocol",
            "why_it_matters": f"{protocol} is being used for VPN connection",
            "suggested_fix": None,
        })
    
    return checks


def _check_port_forward(gluetun_container: Dict[str, Any], docker_client: Any, allow_external: bool) -> List[Dict[str, Any]]:
    """Check port-forward functionality."""
    checks = []
    
    container_name = gluetun_container["name"]
    logs = docker_client.get_container_logs(container_name, since="1h")
    
    # Look for port-forward information in logs
    pf_match = re.search(r"Port forwarded is (\d+)", logs)
    if pf_match:
        port = pf_match.group(1)
        checks.append({
            "id": "G7",
            "category": "Gluetun / PIA",
            "title": "Port-Forward Status",
            "severity": "info",
            "evidence": f"Port-forward active: {port}",
            "why_it_matters": "Port-forward is working for better seeding performance",
            "suggested_fix": None,
        })
        
        # Test port-forward if external checks are allowed
        if allow_external:
            checks.extend(_test_port_forward_external(port))
    else:
        checks.append({
            "id": "G8",
            "category": "Gluetun / PIA",
            "title": "Port-Forward Status",
            "severity": "warn",
            "evidence": "No port-forward information found in logs",
            "why_it_matters": "Port-forward may not be working, affecting seeding performance",
            "suggested_fix": "Check PIA port-forward configuration in Gluetun environment variables",
        })
    
    # Check for port-forward errors
    if "Port forwarding failed" in logs or "Failed to get port" in logs:
        checks.append({
            "id": "G9",
            "category": "Gluetun / PIA",
            "title": "Port-Forward Errors",
            "severity": "fail",
            "evidence": "Port-forward errors detected in logs",
            "why_it_matters": "Port-forward is not working properly",
            "suggested_fix": "Check PIA account status and port-forward settings",
        })
    
    return checks


def _test_port_forward_external(port: str) -> List[Dict[str, Any]]:
    """Test port-forward externally (if allowed)."""
    checks = []
    
    try:
        # This would use a service like canyouseeme.org or similar
        # For now, just indicate that external testing is available
        checks.append({
            "id": "G10",
            "category": "Gluetun / PIA",
            "title": "Port-Forward External Test",
            "severity": "info",
            "evidence": f"External port-forward testing available for port {port}",
            "why_it_matters": "External testing can verify port-forward is working",
            "suggested_fix": "Use online port checker to verify port {port} is accessible",
        })
    except Exception:
        checks.append({
            "id": "G11",
            "category": "Gluetun / PIA",
            "title": "Port-Forward External Test",
            "severity": "warn",
            "evidence": "External port-forward testing failed",
            "why_it_matters": "Cannot verify port-forward externally",
            "suggested_fix": "Check internet connectivity and firewall settings",
        })
    
    return checks


def _check_firewall_rules(gluetun_container: Dict[str, Any], docker_client: Any) -> List[Dict[str, Any]]:
    """Check firewall rules for Docker network access."""
    checks = []
    
    container_name = gluetun_container["name"]
    container_info = docker_client.inspect_container(container_name)
    
    if not container_info:
        return checks
    
    # Check environment variables for firewall settings
    config = container_info.get("Config", {})
    env_vars = config.get("Env", [])
    
    firewall_input = None
    firewall_outbound = None
    
    for env_var in env_vars:
        if env_var.startswith("FIREWALL_INPUT_SUBNETS="):
            firewall_input = env_var.split("=", 1)[1]
        elif env_var.startswith("FIREWALL_OUTBOUND_SUBNETS="):
            firewall_outbound = env_var.split("=", 1)[1]
    
    # Check if Docker bridge networks are allowed
    if firewall_input:
        if "172.17.0.0/16" in firewall_input or "172.18.0.0/16" in firewall_input:
            checks.append({
                "id": "G12",
                "category": "Gluetun / PIA",
                "title": "Firewall Input Rules",
                "severity": "info",
                "evidence": f"Docker bridge networks allowed: {firewall_input}",
                "why_it_matters": "Docker containers can communicate with Gluetun",
                "suggested_fix": None,
            })
        else:
            checks.append({
                "id": "G13",
                "category": "Gluetun / PIA",
                "title": "Firewall Input Rules",
                "severity": "warn",
                "evidence": f"Docker bridge networks may not be allowed: {firewall_input}",
                "why_it_matters": "Docker containers may not be able to communicate with Gluetun",
                "suggested_fix": "Add Docker bridge networks to FIREWALL_INPUT_SUBNETS (e.g., 172.17.0.0/16,172.18.0.0/16)",
            })
    else:
        checks.append({
            "id": "G14",
            "category": "Gluetun / PIA",
            "title": "Firewall Input Rules",
            "severity": "warn",
            "evidence": "No FIREWALL_INPUT_SUBNETS configured",
            "why_it_matters": "Firewall may block Docker container communication",
            "suggested_fix": "Configure FIREWALL_INPUT_SUBNETS to allow Docker networks",
        })
    
    # Check LAN access
    if firewall_input:
        if "192.168.0.0/16" in firewall_input or "10.0.0.0/8" in firewall_input:
            checks.append({
                "id": "G15",
                "category": "Gluetun / PIA",
                "title": "LAN Access Rules",
                "severity": "info",
                "evidence": f"LAN networks allowed: {firewall_input}",
                "why_it_matters": "LAN access is configured for local services",
                "suggested_fix": None,
            })
        else:
            checks.append({
                "id": "G16",
                "category": "Gluetun / PIA",
                "title": "LAN Access Rules",
                "severity": "warn",
                "evidence": f"LAN networks may not be allowed: {firewall_input}",
                "why_it_matters": "LAN services may not be accessible through Gluetun",
                "suggested_fix": "Add LAN networks to FIREWALL_INPUT_SUBNETS (e.g., 192.168.0.0/16)",
            })
    
    return checks


def _check_dns_leaks(gluetun_container: Dict[str, Any], docker_client: Any) -> List[Dict[str, Any]]:
    """Check for DNS leaks."""
    checks = []
    
    container_name = gluetun_container["name"]
    logs = docker_client.get_container_logs(container_name, since="1h")
    
    # Check for DNS configuration
    if "DNS server" in logs:
        dns_match = re.search(r"DNS server: ([\d.]+)", logs)
        if dns_match:
            dns_server = dns_match.group(1)
            
            # Check if it's a PIA DNS server
            if dns_server.startswith("10.") or dns_server.startswith("209.222.18"):
                checks.append({
                    "id": "G17",
                    "category": "Gluetun / PIA",
                    "title": "DNS Configuration",
                    "severity": "info",
                    "evidence": f"Using PIA DNS server: {dns_server}",
                    "why_it_matters": "DNS queries are routed through VPN",
                    "suggested_fix": None,
                })
            else:
                checks.append({
                    "id": "G18",
                    "category": "Gluetun / PIA",
                    "title": "DNS Configuration",
                    "severity": "warn",
                    "evidence": f"Using non-PIA DNS server: {dns_server}",
                    "why_it_matters": "DNS queries may not be routed through VPN",
                    "suggested_fix": "Configure PIA DNS servers in Gluetun",
                })
    
    # Check for DNS leak protection
    if "DNS leak protection" in logs and "enabled" in logs:
        checks.append({
            "id": "G19",
            "category": "Gluetun / PIA",
            "title": "DNS Leak Protection",
            "severity": "info",
            "evidence": "DNS leak protection is enabled",
            "why_it_matters": "DNS queries are protected from leaks",
            "suggested_fix": None,
        })
    elif "DNS leak protection" in logs and "disabled" in logs:
        checks.append({
            "id": "G20",
            "category": "Gluetun / PIA",
            "title": "DNS Leak Protection",
            "severity": "warn",
            "evidence": "DNS leak protection is disabled",
            "why_it_matters": "DNS queries may leak outside VPN",
            "suggested_fix": "Enable DNS leak protection in Gluetun configuration",
        })
    
    return checks


def _check_qbittorrent_leak_guard(gluetun_container: Dict[str, Any], docker_client: Any) -> List[Dict[str, Any]]:
    """Check qBittorrent leak guard - verify it only uses Gluetun network (G5)."""
    checks = []
    
    # Find qBittorrent container
    containers = docker_client.list_containers()
    qbittorrent_container = None
    
    for container in containers:
        if "qbittorrent" in container["name"].lower():
            qbittorrent_container = container
            break
    
    if not qbittorrent_container:
        checks.append({
            "id": "G5",
            "category": "Gluetun / PIA",
            "title": "qBittorrent Leak Guard",
            "severity": "info",
            "evidence": "qBittorrent container not found",
            "why_it_matters": "Cannot verify qBittorrent network isolation",
            "suggested_fix": "Ensure qBittorrent container is running",
        })
        return checks
    
    # Check container network configuration
    container_info = docker_client.inspect_container(qbittorrent_container["name"])
    if not container_info:
        checks.append({
            "id": "G5",
            "category": "Gluetun / PIA",
            "title": "qBittorrent Leak Guard",
            "severity": "warn",
            "evidence": "Cannot inspect qBittorrent container",
            "why_it_matters": "Cannot verify network configuration",
            "suggested_fix": "Check qBittorrent container status",
        })
        return checks
    
    # Check network mode
    host_config = container_info.get("HostConfig", {})
    network_mode = host_config.get("NetworkMode", "")
    
    # Check for published ports (these bypass Gluetun)
    port_bindings = host_config.get("PortBindings", {})
    
    # Check if qBittorrent is using Gluetun network
    using_gluetun = False
    if network_mode == f"container:{gluetun_container['name']}":
        using_gluetun = True
    elif network_mode == f"service:{gluetun_container['name']}":
        using_gluetun = True
    
    # Check for any published ports that bypass Gluetun
    bypass_ports = []
    for container_port, host_bindings in port_bindings.items():
        if host_bindings:
            for binding in host_bindings:
                if binding.get("HostIp") and binding["HostIp"] != "127.0.0.1":
                    bypass_ports.append(f"{binding['HostIp']}:{binding['HostPort']}")
    
    if using_gluetun and not bypass_ports:
        checks.append({
            "id": "G5",
            "category": "Gluetun / PIA",
            "title": "qBittorrent Leak Guard",
            "severity": "info",
            "evidence": "qBittorrent is properly isolated behind Gluetun",
            "why_it_matters": "qBittorrent traffic is properly routed through VPN",
            "suggested_fix": None,
        })
    elif using_gluetun and bypass_ports:
        checks.append({
            "id": "G5",
            "category": "Gluetun / PIA",
            "title": "qBittorrent Leak Guard",
            "severity": "fail",
            "evidence": f"qBittorrent has bypass ports: {', '.join(bypass_ports)}",
            "why_it_matters": "Published ports bypass Gluetun and may leak traffic",
            "suggested_fix": "Remove published ports from qBittorrent container to ensure all traffic goes through Gluetun",
        })
    else:
        checks.append({
            "id": "G5",
            "category": "Gluetun / PIA",
            "title": "qBittorrent Leak Guard",
            "severity": "fail",
            "evidence": f"qBittorrent is not using Gluetun network (mode: {network_mode})",
            "why_it_matters": "qBittorrent traffic is not routed through VPN",
            "suggested_fix": "Configure qBittorrent to use Gluetun network: network_mode: service:gluetun",
        })
    
    return checks


def _check_pf_reliability(gluetun_container: Dict[str, Any], docker_client: Any) -> List[Dict[str, Any]]:
    """Check Gluetun port-forward reliability score (G6)."""
    checks = []
    
    container_name = gluetun_container["name"]
    
    try:
        # Get logs from last 24 hours
        logs = docker_client.get_container_logs(container_name, since="24h")
        
        if not logs:
            checks.append({
                "id": "G6",
                "category": "Gluetun / PIA",
                "title": "Port-Forward Reliability",
                "severity": "warn",
                "evidence": "Cannot retrieve Gluetun logs",
                "why_it_matters": "Cannot assess port-forward stability",
                "suggested_fix": "Check Gluetun container logs access",
            })
            return checks
        
        # Parse logs for PF events
        pf_events = []
        pf_errors = []
        pf_renewals = []
        
        for line in logs.split('\n'):
            line_lower = line.lower()
            
            # Count PF renewals
            if "port forwarded" in line_lower or "port forward" in line_lower:
                pf_renewals.append(line)
            
            # Count PF errors
            if any(error in line_lower for error in [
                "port forward error",
                "failed to get port",
                "port forward failed",
                "pf error",
                "unable to get port"
            ]):
                pf_errors.append(line)
            
            # Count general PF events
            if any(event in line_lower for event in [
                "port forward",
                "pf:",
                "port forwarded",
                "got port"
            ]):
                pf_events.append(line)
        
        # Calculate reliability score
        total_events = len(pf_events)
        error_count = len(pf_errors)
        renewal_count = len(pf_renewals)
        
        if total_events == 0:
            checks.append({
                "id": "G6",
                "category": "Gluetun / PIA",
                "title": "Port-Forward Reliability",
                "severity": "warn",
                "evidence": "No port-forward events found in logs",
                "why_it_matters": "Cannot assess port-forward activity",
                "suggested_fix": "Check if port-forwarding is enabled in PIA account",
            })
            return checks
        
        # Calculate score (0.0 to 1.0)
        if error_count == 0:
            reliability_score = 1.0
        else:
            reliability_score = max(0.0, 1.0 - (error_count / total_events))
        
        # Determine severity and message
        if reliability_score >= 0.9:
            severity = "info"
            evidence = f"PF health: {reliability_score:.2f} (excellent) - {renewal_count} renewals, {error_count} errors"
            why = "Port-forward is very stable"
            fix = None
        elif reliability_score >= 0.7:
            severity = "info"
            evidence = f"PF health: {reliability_score:.2f} (good) - {renewal_count} renewals, {error_count} errors"
            why = "Port-forward is generally stable"
            fix = None
        elif reliability_score >= 0.5:
            severity = "warn"
            evidence = f"PF health: {reliability_score:.2f} (fair) - {renewal_count} renewals, {error_count} errors"
            why = "Port-forward has some stability issues"
            fix = "Consider switching to a more stable PIA region or check network stability"
        else:
            severity = "fail"
            evidence = f"PF health: {reliability_score:.2f} (poor) - {renewal_count} renewals, {error_count} errors"
            why = "Port-forward is very unstable"
            fix = "Switch to a stable PIA region (CA Montreal/Toronto) and check network stability"
        
        checks.append({
            "id": "G6",
            "category": "Gluetun / PIA",
            "title": "Port-Forward Reliability",
            "severity": severity,
            "evidence": evidence,
            "why_it_matters": why,
            "suggested_fix": fix,
        })
        
        # Add advisor snippet for stable regions if score is low
        if reliability_score < 0.7:
            checks.append({
                "id": "G6_ADVISOR",
                "category": "Gluetun / PIA",
                "title": "Stable PIA Regions",
                "severity": "info",
                "evidence": "Port-forward reliability is below optimal",
                "why_it_matters": "Stable regions improve port-forward reliability",
                "suggested_fix": """For better PF stability, use these PIA regions:
```yaml
environment:
  - VPN_SERVICE_PROVIDER=private internet access
  - VPN_TYPE=openvpn
  - OPENVPN_USER=your-pia-username
  - OPENVPN_PASSWORD=your-pia-password
  - SERVER_REGIONS=Canada Montreal,Canada Toronto,Netherlands,Switzerland
  - PORT_FORWARDING=on
```""",
            })
    
    except Exception as e:
        checks.append({
            "id": "G6",
            "category": "Gluetun / PIA",
            "title": "Port-Forward Reliability",
            "severity": "warn",
            "evidence": f"Error analyzing PF reliability: {e}",
            "why_it_matters": "Cannot assess port-forward stability",
            "suggested_fix": "Check Gluetun container logs and port-forward configuration",
        })
    
    return checks
