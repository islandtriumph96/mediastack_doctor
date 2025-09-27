"""Advisor mode for generating actionable remediation steps."""

from typing import Any, Dict, List


def generate_advisor_fixes(checks: List[Dict[str, Any]]) -> List[str]:
    """Generate actionable fixes for failed and warning checks."""
    fixes = []
    
    for check in checks:
        severity = check.get("severity", "info")
        if severity in ["fail", "warn"]:
            fix = _generate_fix_for_check(check)
            if fix:
                fixes.append(fix)
    
    return fixes


def _generate_fix_for_check(check: Dict[str, Any]) -> str:
    """Generate a specific fix for a check."""
    check_id = check.get("id", "")
    title = check.get("title", "")
    evidence = check.get("evidence", "")
    suggested_fix = check.get("suggested_fix")
    
    # If there's already a suggested fix, use it
    if suggested_fix:
        if isinstance(suggested_fix, list):
            return f"**{title}**: " + "; ".join(suggested_fix)
        else:
            return f"**{title}**: {suggested_fix}"
    
    # Generate specific fixes based on check ID patterns
    if check_id.startswith("G"):  # Gluetun checks
        return _generate_gluetun_fix(check_id, title, evidence)
    elif check_id.startswith("Q"):  # qBittorrent checks
        return _generate_qbittorrent_fix(check_id, title, evidence)
    elif check_id.startswith("A"):  # Arr checks
        return _generate_arr_fix(check_id, title, evidence)
    elif check_id.startswith("D"):  # Docker checks
        return _generate_docker_fix(check_id, title, evidence)
    elif check_id.startswith("H"):  # Host checks
        return _generate_host_fix(check_id, title, evidence)
    elif check_id.startswith("P"):  # Plex checks
        return _generate_plex_fix(check_id, title, evidence)
    elif check_id.startswith("C"):  # Cloudflared checks
        return _generate_cloudflared_fix(check_id, title, evidence)
    else:
        return f"**{title}**: Review configuration and check logs"


def _generate_gluetun_fix(check_id: str, title: str, evidence: str) -> str:
    """Generate Gluetun-specific fixes."""
    if "VPN connection" in title:
        return f"**{title}**: Check PIA credentials and server configuration in Gluetun environment variables"
    elif "Port-forward" in title:
        return f"**{title}**: Verify PIA account has port-forwarding enabled and check Gluetun PF configuration"
    elif "Firewall" in title:
        return f"**{title}**: Add Docker bridge networks to FIREWALL_INPUT_SUBNETS: `FIREWALL_INPUT_SUBNETS=172.17.0.0/16,192.168.0.0/16`"
    elif "DNS" in title:
        return f"**{title}**: Configure PIA DNS servers in Gluetun: `DNS_SERVERS=209.222.18.222,209.222.18.218`"
    else:
        return f"**{title}**: Check Gluetun configuration and logs"


def _generate_qbittorrent_fix(check_id: str, title: str, evidence: str) -> None:
    """Generate qBittorrent-specific fixes."""
    if "WebUI" in title:
        return f"**{title}**: Check qBittorrent container status and port configuration. If behind Gluetun, ensure firewall allows Docker networks"
    elif "API" in title:
        return f"**{title}**: Configure qBittorrent credentials: `mediastack-doctor registry set qbittorrent --username admin --password-secret-ref qb_password`"
    elif "Network" in title:
        return f"**{title}**: Configure qBittorrent to use Gluetun network: `network_mode: service:gluetun` or add to Gluetun network"
    elif "Path" in title:
        return f"**{title}**: Ensure consistent volume mounts across all containers. Use same host paths for downloads and media"
    else:
        return f"**{title}**: Check qBittorrent configuration and container logs"


def _generate_arr_fix(check_id: str, title: str, evidence: str) -> str:
    """Generate Arr-specific fixes."""
    if "API" in title:
        return f"**{title}**: Configure API key: `mediastack-doctor registry set <service> --api-key-secret-ref <service>_apikey`"
    elif "Download Client" in title:
        return f"**{title}**: Configure download client in Arr settings. For qBittorrent behind Gluetun, use LAN IP or Docker gateway (172.17.0.1:8081)"
    elif "Indexer" in title:
        return f"**{title}**: Configure indexers in Prowlarr and sync with Arr applications"
    elif "Path" in title:
        return f"**{title}**: Ensure consistent root folder paths across Arr applications and download clients"
    else:
        return f"**{title}**: Check Arr configuration and API connectivity"


def _generate_docker_fix(check_id: str, title: str, evidence: str) -> str:
    """Generate Docker-specific fixes."""
    if "Container" in title:
        return f"**{title}**: Check container logs: `docker logs <container_name>` and restart if needed: `docker restart <container_name>`"
    elif "Network" in title:
        return f"**{title}**: Review Docker network configuration and ensure containers are on correct networks"
    elif "Port" in title:
        return f"**{title}**: Check for port conflicts and update port mappings in docker-compose.yml"
    elif "Mount" in title:
        return f"**{title}**: Verify volume mounts and ensure host paths exist and are accessible"
    else:
        return f"**{title}**: Check Docker configuration and container status"


def _generate_host_fix(check_id: str, title: str, evidence: str) -> str:
    """Generate host-specific fixes."""
    if "CPU" in title:
        return f"**{title}**: Check for runaway processes: `top` or `htop`. Consider upgrading hardware or optimizing applications"
    elif "Memory" in title:
        return f"**{title}**: Free up memory by closing unnecessary applications or adding more RAM"
    elif "Disk" in title:
        return f"**{title}**: Clean up disk space: `sudo apt autoremove && sudo apt autoclean`. Consider expanding storage"
    elif "Network" in title:
        return f"**{title}**: Check network cable and interface configuration"
    elif "Thermal" in title:
        return f"**{title}**: Check cooling system, clean dust, and ensure proper ventilation"
    else:
        return f"**{title}**: Check system resources and configuration"


def _generate_plex_fix(check_id: str, title: str, evidence: str) -> str:
    """Generate Plex-specific fixes."""
    if "Connectivity" in title:
        return f"**{title}**: Check Plex container status and port configuration"
    elif "API" in title:
        return f"**{title}**: Configure Plex token: `mediastack-doctor registry set plex --token-secret-ref plex_token`"
    elif "Library" in title:
        return f"**{title}**: Configure libraries in Plex server settings and ensure media paths are accessible"
    elif "Remote" in title:
        return f"**{title}**: Configure remote access in Plex settings. For Cloudflare, consider Zero-Trust authentication"
    else:
        return f"**{title}**: Check Plex configuration and server status"


def _generate_cloudflared_fix(check_id: str, title: str, evidence: str) -> str:
    """Generate Cloudflared-specific fixes."""
    if "Tunnel" in title:
        return f"**{title}**: Check Cloudflared configuration and tunnel credentials"
    elif "Metrics" in title:
        return f"**{title}**: Configure metrics endpoint: `mediastack-doctor registry set cloudflared --metrics-url http://cloudflared:2000/metrics`"
    elif "Routes" in title:
        return f"**{title}**: Verify tunnel routes and ensure backend services are accessible"
    else:
        return f"**{title}**: Check Cloudflared configuration and tunnel status"


def get_compose_snippets() -> Dict[str, str]:
    """Get common Docker Compose snippets for fixes."""
    return {
        "gluetun_firewall": """
# Gluetun firewall configuration
environment:
  - FIREWALL_INPUT_SUBNETS=172.17.0.0/16,192.168.0.0/16
  - FIREWALL_OUTBOUND_SUBNETS=192.168.0.0/16
""",
        "qbittorrent_gluetun": """
# qBittorrent behind Gluetun
network_mode: service:gluetun
# OR
networks:
  - gluetun
""",
        "consistent_volumes": """
# Consistent volume mounts
volumes:
  - /mnt/PLEX22TB:/data
  - /mnt/GDRIVE36:/media
""",
        "plex_remote_access": """
# Plex remote access (prefer direct access)
environment:
  - PLEX_CLAIM=your-claim-token
  - PLEX_UID=1000
  - PLEX_GID=1000
""",
    }


def get_env_snippets() -> Dict[str, str]:
    """Get common environment variable snippets for fixes."""
    return {
        "pia_credentials": """
# PIA credentials for Gluetun
VPN_SERVICE_PROVIDER=private internet access
VPN_TYPE=openvpn
OPENVPN_USER=your-pia-username
OPENVPN_PASSWORD=your-pia-password
""",
        "pia_port_forward": """
# PIA port forwarding
PORT_FORWARDING=on
PORT_FORWARDING_STATUS_FILE=/tmp/gluetun/forwarded_port
""",
        "dns_servers": """
# DNS configuration
DNS_SERVERS=209.222.18.222,209.222.18.218
DNS_KEEP_NAMESERVER=off
""",
    }
