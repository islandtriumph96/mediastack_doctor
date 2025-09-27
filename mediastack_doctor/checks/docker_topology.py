"""Docker topology and container diagnostics."""

from typing import Any, Dict, List, Optional, Set


def run_checks(registry: Any, docker_client: Any) -> List[Dict[str, Any]]:
    """Run Docker topology checks."""
    checks = []
    
    # Container health checks
    checks.extend(_check_container_health(docker_client))
    
    # Network topology checks
    checks.extend(_check_network_topology(docker_client))
    
    # Volume and mount checks
    checks.extend(_check_volumes_mounts(docker_client))
    
    # Port collision checks
    checks.extend(_check_port_collisions(docker_client))
    
    # Image and update checks
    checks.extend(_check_images_updates(docker_client))
    
    return checks


def _check_container_health(docker_client: Any) -> List[Dict[str, Any]]:
    """Check container health and status with detailed evidence."""
    checks = []
    
    containers = docker_client.list_containers()
    
    if not containers:
        checks.append({
            "id": "D1",
            "category": "Docker Topology",
            "title": "Docker Containers",
            "severity": "warn",
            "evidence": "No containers found",
            "why_it_matters": "Expected media stack containers are not running",
            "suggested_fix": "Check Docker Compose or container startup",
        })
        return checks
    
    # Check each container with detailed evidence
    expected_services = {
        "gluetun", "qbittorrent", "radarr", "sonarr", "sonarr-anime", 
        "prowlarr", "sabnzbd", "unpackerr", "overseerr", "filebrowser", 
        "cloudflared", "plex"
    }
    
    running_containers = set()
    unhealthy_containers = []
    restarting_containers = []
    
    for container in containers:
        container_name = container["name"]
        status = container["status"]
        state = container.get("state", {})
        
        running_containers.add(container_name)
        
        # Collect detailed evidence for each container
        container_evidence = _collect_container_evidence(container_name, docker_client)
        
        # Check health status
        health = state.get("Health", {})
        if health:
            health_status = health.get("Status", "unknown")
            if health_status not in ["healthy", "none"]:
                unhealthy_containers.append(f"{container_name} ({health_status})")
        
        # Check restart count
        restart_count = state.get("RestartCount", 0)
        if restart_count > 5:
            restarting_containers.append(f"{container_name} ({restart_count} restarts)")
        
        # Create detailed check for each container
        if not status.startswith("Up"):
            severity = "fail"
            evidence = f"{container_name} is {status}"
            if container_evidence.exit_code:
                evidence += f" (ExitCode: {container_evidence.exit_code})"
            if container_evidence.restart_count > 0:
                evidence += f" (RestartCount: {container_evidence.restart_count})"
        else:
            if container_evidence.health_status == "unhealthy":
                severity = "fail"
                evidence = f"{container_name} is running but unhealthy"
            elif container_evidence.restart_count > 1:
                severity = "warn"
                evidence = f"{container_name} is running but has restarted {container_evidence.restart_count} times"
            else:
                severity = "info"
                evidence = f"{container_name} is running and healthy"
        
        # Add container evidence to the check
        check_data = {
            "id": f"D2_{container_name.replace('-', '_').replace(':', '_')}",
            "category": "Docker Topology",
            "title": f"Container Status - {container_name}",
            "severity": severity,
            "evidence": evidence,
            "why_it_matters": "Container status affects service availability",
            "suggested_fix": f"Check logs and restart {container_name}: docker logs {container_name}",
            "container_evidence": {
                "name": container_evidence.name,
                "status": container_evidence.status,
                "health_status": container_evidence.health_status,
                "restart_count": container_evidence.restart_count,
                "exit_code": container_evidence.exit_code,
                "started_at": container_evidence.started_at,
                "ports": container_evidence.ports,
                "networks": container_evidence.networks,
                "volumes": container_evidence.volumes,
                "log_errors": container_evidence.log_errors
            }
        }
        
        checks.append(check_data)
    
    # Check for missing expected services
    missing_services = expected_services - running_containers
    if missing_services:
        checks.append({
            "id": "D3",
            "category": "Docker Topology",
            "title": "Missing Expected Services",
            "severity": "warn",
            "evidence": f"Missing services: {', '.join(missing_services)}",
            "why_it_matters": "Expected media stack services are not running",
            "suggested_fix": "Start missing services with docker-compose up -d",
        })
    
    # Check unhealthy containers
    if unhealthy_containers:
        checks.append({
            "id": "D4",
            "category": "Docker Topology",
            "title": "Unhealthy Containers",
            "severity": "fail",
            "evidence": f"Unhealthy containers: {', '.join(unhealthy_containers)}",
            "why_it_matters": "Unhealthy containers may not function properly",
            "suggested_fix": "Check container logs and health check configuration",
        })
    
    # Check frequently restarting containers
    if restarting_containers:
        checks.append({
            "id": "D5",
            "category": "Docker Topology",
            "title": "Frequently Restarting Containers",
            "severity": "warn",
            "evidence": f"Frequently restarting: {', '.join(restarting_containers)}",
            "why_it_matters": "Frequent restarts indicate configuration or resource issues",
            "suggested_fix": "Check container logs and resource limits",
        })
    
    return checks


def _collect_container_evidence(container_name: str, docker_client: Any) -> 'ContainerEvidence':
    """Collect detailed evidence from container inspection."""
    from ..utils.advisor_rules import ContainerEvidence
    
    try:
        # Get detailed container info
        container_info = docker_client.inspect_container(container_name)
        if not container_info:
            return ContainerEvidence(
                name=container_name,
                status="unknown",
                health_status=None,
                restart_count=0,
                exit_code=None,
                started_at=None,
                ports=[],
                networks=[],
                volumes=[],
                log_errors=[]
            )
        
        # Extract state information
        state = container_info.get("State", {})
        health = state.get("Health", {})
        
        # Get restart count
        restart_count = state.get("RestartCount", 0)
        
        # Get exit code
        exit_code = state.get("ExitCode")
        
        # Get started time
        started_at = state.get("StartedAt")
        
        # Get health status
        health_status = health.get("Status") if health else None
        
        # Get port mappings
        ports = []
        port_bindings = container_info.get("NetworkSettings", {}).get("PortBindings", {})
        for container_port, host_bindings in port_bindings.items():
            if host_bindings:
                for binding in host_bindings:
                    host_ip = binding.get("HostIp", "0.0.0.0")
                    host_port = binding.get("HostPort", "")
                    ports.append(f"{host_ip}:{host_port}→{container_port}")
        
        # Get networks
        networks = []
        network_settings = container_info.get("NetworkSettings", {})
        for network_name, network_info in network_settings.get("Networks", {}).items():
            ip_address = network_info.get("IPAddress", "")
            networks.append(f"{network_name}({ip_address})")
        
        # Get volume mounts
        volumes = []
        mounts = container_info.get("Mounts", [])
        for mount in mounts:
            source = mount.get("Source", "")
            destination = mount.get("Destination", "")
            volumes.append(f"{source}→{destination}")
        
        # Get recent log errors
        log_errors = []
        try:
            logs = docker_client.get_container_logs(container_name, since="2m")
            if logs:
                error_keywords = ["error", "fatal", "panic", "traceback", "oom-kill", "timeout"]
                for line in logs.split('\n')[-50:]:  # Last 50 lines
                    if any(keyword in line.lower() for keyword in error_keywords):
                        log_errors.append(line.strip()[:100])  # Truncate long lines
                        if len(log_errors) >= 3:  # Limit to 3 errors
                            break
        except Exception:
            pass  # Ignore log collection errors
        
        return ContainerEvidence(
            name=container_name,
            status=state.get("Status", "unknown"),
            health_status=health_status,
            restart_count=restart_count,
            exit_code=exit_code,
            started_at=started_at,
            ports=ports,
            networks=networks,
            volumes=volumes,
            log_errors=log_errors
        )
        
    except Exception as e:
        # Return minimal evidence on error
        return ContainerEvidence(
            name=container_name,
            status="error",
            health_status=None,
            restart_count=0,
            exit_code=None,
            started_at=None,
            ports=[],
            networks=[],
            volumes=[],
            log_errors=[f"Error collecting evidence: {str(e)}"]
        )


def _check_network_topology(docker_client: Any) -> List[Dict[str, Any]]:
    """Check Docker network topology."""
    checks = []
    
    networks = docker_client.list_networks()
    containers = docker_client.list_containers()
    
    if not networks:
        checks.append({
            "id": "D6",
            "category": "Docker Topology",
            "title": "Docker Networks",
            "severity": "warn",
            "evidence": "No Docker networks found",
            "why_it_matters": "Containers need networks to communicate",
            "suggested_fix": "Check Docker network configuration",
        })
        return checks
    
    # Analyze network topology
    network_map = {}
    for network in networks:
        network_name = network["name"]
        containers_in_network = network.get("containers", {})
        network_map[network_name] = list(containers_in_network.keys())
    
    # Check for qBittorrent in Gluetun network
    gluetun_network = None
    qbittorrent_network = None
    
    for container in containers:
        container_name = container["name"]
        network_settings = container.get("network_settings", {})
        networks = network_settings.get("Networks", {})
        
        if "gluetun" in container_name.lower():
            gluetun_network = list(networks.keys())[0] if networks else None
        
        if "qbittorrent" in container_name.lower() or "qb" in container_name.lower():
            qbittorrent_network = list(networks.keys())[0] if networks else None
    
    # Check if qBittorrent is using Gluetun network
    if gluetun_network and qbittorrent_network:
        if gluetun_network == qbittorrent_network:
            checks.append({
                "id": "D7",
                "category": "Docker Topology",
                "title": "qBittorrent Network Configuration",
                "severity": "info",
                "evidence": f"qBittorrent is on same network as Gluetun ({gluetun_network})",
                "why_it_matters": "qBittorrent traffic will be routed through VPN",
                "suggested_fix": None,
            })
        else:
            checks.append({
                "id": "D8",
                "category": "Docker Topology",
                "title": "qBittorrent Network Configuration",
                "severity": "warn",
                "evidence": f"qBittorrent is on {qbittorrent_network}, Gluetun is on {gluetun_network}",
                "why_it_matters": "qBittorrent traffic may not be routed through VPN",
                "suggested_fix": "Configure qBittorrent to use Gluetun network or network_mode: service:gluetun",
            })
    
    # Check for orphaned networks
    default_networks = {"bridge", "host", "none"}
    custom_networks = [n for n in network_map.keys() if n not in default_networks]
    
    if len(custom_networks) > 3:
        checks.append({
            "id": "D9",
            "category": "Docker Topology",
            "title": "Network Count",
            "severity": "info",
            "evidence": f"Found {len(custom_networks)} custom networks: {', '.join(custom_networks)}",
            "why_it_matters": "Multiple networks may indicate complex topology",
            "suggested_fix": "Review network configuration for simplicity",
        })
    
    # Check for containers without networks
    containers_without_networks = []
    for container in containers:
        container_name = container["name"]
        network_settings = container.get("network_settings", {})
        networks = network_settings.get("Networks", {})
        
        if not networks:
            containers_without_networks.append(container_name)
    
    if containers_without_networks:
        checks.append({
            "id": "D10",
            "category": "Docker Topology",
            "title": "Containers Without Networks",
            "severity": "warn",
            "evidence": f"Containers without networks: {', '.join(containers_without_networks)}",
            "why_it_matters": "Containers without networks cannot communicate",
            "suggested_fix": "Assign networks to containers or check network_mode configuration",
        })
    
    return checks


def _check_volumes_mounts(docker_client: Any) -> List[Dict[str, Any]]:
    """Check volume and mount configurations."""
    checks = []
    
    containers = docker_client.list_containers()
    
    # Expected mount points
    expected_mounts = ["/mnt/PLEX22TB", "/mnt/GDRIVE36"]
    
    # Check each container's mounts
    mount_consistency = {}
    for container in containers:
        container_name = container["name"]
        mounts = container.get("mounts", [])
        
        container_mounts = []
        for mount in mounts:
            if mount.get("Type") == "bind":
                source = mount.get("Source", "")
                destination = mount.get("Destination", "")
                
                if any(expected in source for expected in expected_mounts):
                    container_mounts.append({
                        "source": source,
                        "destination": destination,
                        "mode": mount.get("Mode", "rw")
                    })
        
        if container_mounts:
            mount_consistency[container_name] = container_mounts
    
    # Check mount consistency across services
    if mount_consistency:
        # Group by mount source
        mount_sources = {}
        for container, mounts in mount_consistency.items():
            for mount in mounts:
                source = mount["source"]
                if source not in mount_sources:
                    mount_sources[source] = []
                mount_sources[source].append({
                    "container": container,
                    "destination": mount["destination"],
                    "mode": mount["mode"]
                })
        
        # Check for consistent mount paths
        for source, containers in mount_sources.items():
            if len(containers) > 1:
                destinations = [c["destination"] for c in containers]
                if len(set(destinations)) > 1:
                    checks.append({
                        "id": "D11",
                        "category": "Docker Topology",
                        "title": f"Mount Path Consistency - {source}",
                        "severity": "warn",
                        "evidence": f"Different mount destinations: {destinations}",
                        "why_it_matters": "Inconsistent mount paths can cause file access issues",
                        "suggested_fix": f"Standardize mount destinations for {source} across all containers",
                    })
                else:
                    checks.append({
                        "id": "D12",
                        "category": "Docker Topology",
                        "title": f"Mount Path Consistency - {source}",
                        "severity": "info",
                        "evidence": f"Consistent mount destination: {destinations[0]}",
                        "why_it_matters": "Consistent mount paths ensure proper file access",
                        "suggested_fix": None,
                    })
    
    # Check for missing expected mounts
    services_that_should_have_mounts = ["radarr", "sonarr", "sonarr-anime", "qbittorrent", "sabnzbd", "unpackerr"]
    
    for service in services_that_should_have_mounts:
        service_containers = [c for c in containers if c.get("name") and service in c["name"].lower()]
        
        if service_containers:
            container = service_containers[0]
            mounts = container.get("mounts", [])
            has_media_mount = any(
                any(expected in mount.get("Source", "") for expected in expected_mounts)
                for mount in mounts
            )
            
            if not has_media_mount:
                checks.append({
                    "id": f"D13_{service}",
                    "category": "Docker Topology",
                    "title": f"Missing Media Mount - {service}",
                    "severity": "fail",
                    "evidence": f"{service} container has no media volume mounts",
                    "why_it_matters": f"{service} cannot access media files without proper mounts",
                    "suggested_fix": f"Add volume mounts for {service} to access media directories",
                })
    
    return checks


def _check_port_collisions(docker_client: Any) -> List[Dict[str, Any]]:
    """Check for port collisions and conflicts."""
    checks = []
    
    containers = docker_client.list_containers()
    
    # Collect all published ports
    published_ports = {}
    for container in containers:
        container_name = container["name"]
        network_settings = container.get("network_settings", {})
        ports = network_settings.get("Ports", {})
        
        for container_port, host_bindings in ports.items():
            if host_bindings:
                for binding in host_bindings:
                    host_port = binding.get("HostPort")
                    if host_port:
                        if host_port in published_ports:
                            published_ports[host_port].append(container_name)
                        else:
                            published_ports[host_port] = [container_name]
    
    # Check for port collisions
    collisions = {port: containers for port, containers in published_ports.items() if len(containers) > 1}
    
    if collisions:
        for port, containers in collisions.items():
            checks.append({
                "id": f"D14_{port}",
                "category": "Docker Topology",
                "title": f"Port Collision - {port}",
                "severity": "fail",
                "evidence": f"Port {port} is used by multiple containers: {', '.join(containers)}",
                "why_it_matters": "Port collisions prevent services from starting properly",
                "suggested_fix": f"Change port mapping for one of: {', '.join(containers)}",
            })
    
    # Check for common service ports
    expected_ports = {
        "8080": "SABnzbd",
        "8081": "qBittorrent",
        "7878": "Radarr",
        "8989": "Sonarr",
        "9696": "Prowlarr",
        "32400": "Plex",
        "5055": "Overseerr",
    }
    
    for port, service in expected_ports.items():
        if port in published_ports:
            containers = published_ports[port]
            expected_container = next((c for c in containers if service.lower() in c.lower()), None)
            
            if expected_container:
                checks.append({
                    "id": f"D15_{port}",
                    "category": "Docker Topology",
                    "title": f"Service Port - {service}",
                    "severity": "info",
                    "evidence": f"{service} is accessible on port {port}",
                    "why_it_matters": f"{service} is properly exposed",
                    "suggested_fix": None,
                })
            else:
                checks.append({
                    "id": f"D16_{port}",
                    "category": "Docker Topology",
                    "title": f"Service Port - {service}",
                    "severity": "warn",
                    "evidence": f"Port {port} is used by {', '.join(containers)}, expected {service}",
                    "why_it_matters": f"Port {port} may not be serving {service} as expected",
                    "suggested_fix": f"Verify {service} is running and accessible on port {port}",
                })
    
    return checks


def _check_images_updates(docker_client: Any) -> List[Dict[str, Any]]:
    """Check Docker images and update status."""
    checks = []
    
    containers = docker_client.list_containers()
    
    # Check for stale images
    stale_containers = []
    for container in containers:
        container_name = container["name"]
        image = container["image"]
        
        # Check if image has a tag (not just SHA)
        if "@sha256:" in image or ":" not in image:
            stale_containers.append(f"{container_name} ({image})")
    
    if stale_containers:
        checks.append({
            "id": "D17",
            "category": "Docker Topology",
            "title": "Container Images",
            "severity": "warn",
            "evidence": f"Containers with untagged images: {', '.join(stale_containers)}",
            "why_it_matters": "Untagged images may be outdated or from failed builds",
            "suggested_fix": "Update containers with proper image tags: docker-compose pull && docker-compose up -d",
        })
    
    # Check for containers using latest tag
    latest_containers = []
    for container in containers:
        container_name = container["name"]
        image = container["image"]
        
        if ":latest" in image:
            latest_containers.append(f"{container_name} ({image})")
    
    if latest_containers:
        checks.append({
            "id": "D18",
            "category": "Docker Topology",
            "title": "Latest Tag Usage",
            "severity": "info",
            "evidence": f"Containers using latest tag: {', '.join(latest_containers)}",
            "why_it_matters": "Latest tag may cause unexpected updates",
            "suggested_fix": "Consider using specific version tags for stability",
        })
    
    return checks
