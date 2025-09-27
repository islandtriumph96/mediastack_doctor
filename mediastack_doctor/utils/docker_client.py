"""Docker client wrapper for container discovery and inspection."""

import json
import subprocess
import sys
from typing import Any, Dict, List, Optional

import docker
from docker.errors import DockerException


class DockerClient:
    """Docker client with fallback to CLI."""
    
    def __init__(self) -> None:
        """Initialize Docker client."""
        self._client: Optional[docker.DockerClient] = None
        self._use_cli = False
        
        try:
            self._client = docker.from_env()
            # Test connection
            self._client.ping()
        except (DockerException, Exception):
            self._use_cli = True
            print("Warning: Docker SDK not available, falling back to CLI")
    
    def list_containers(self, all_containers: bool = False) -> List[Dict[str, Any]]:
        """List Docker containers."""
        if self._client and not self._use_cli:
            try:
                containers = self._client.containers.list(all=all_containers)
                return [
                    {
                        "id": c.id,
                        "name": c.name,
                        "image": c.image.tags[0] if c.image.tags else c.image.id,
                        "status": c.status,
                        "state": c.attrs.get("State", {}),
                        "config": c.attrs.get("Config", {}),
                        "network_settings": c.attrs.get("NetworkSettings", {}),
                        "mounts": c.attrs.get("Mounts", []),
                        "labels": c.attrs.get("Config", {}).get("Labels", {}),
                    }
                    for c in containers
                ]
            except Exception as e:
                print(f"Warning: Docker SDK failed: {e}")
                self._use_cli = True
        
        if self._use_cli:
            return self._list_containers_cli(all_containers)
        
        return []
    
    def _list_containers_cli(self, all_containers: bool = False) -> List[Dict[str, Any]]:
        """List containers using Docker CLI."""
        try:
            cmd = ["docker", "ps"]
            if all_containers:
                cmd.append("-a")
            cmd.extend(["--format", "json"])
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            containers = []
            
            for line in result.stdout.strip().split("\n"):
                if line:
                    try:
                        container_data = json.loads(line)
                        # Get full container details
                        inspect_result = subprocess.run(
                            ["docker", "inspect", container_data["ID"]],
                            capture_output=True,
                            text=True,
                            check=True
                        )
                        full_data = json.loads(inspect_result.stdout)[0]
                        
                        # Handle Names field which might be a list
                        names = container_data.get("Names", "")
                        if isinstance(names, list):
                            name = names[0] if names else ""
                        else:
                            name = names
                        
                        containers.append({
                            "id": container_data["ID"],
                            "name": name,
                            "image": container_data["Image"],
                            "status": container_data["Status"],
                            "state": full_data.get("State", {}),
                            "config": full_data.get("Config", {}),
                            "network_settings": full_data.get("NetworkSettings", {}),
                            "mounts": full_data.get("Mounts", []),
                            "labels": full_data.get("Config", {}).get("Labels", {}),
                        })
                    except (json.JSONDecodeError, subprocess.CalledProcessError):
                        continue
            
            return containers
        except subprocess.CalledProcessError as e:
            print(f"Warning: Docker CLI failed: {e}")
            return []
    
    def get_container_logs(self, container_name: str, since: str = "15m") -> str:
        """Get container logs."""
        if self._client and not self._use_cli:
            try:
                container = self._client.containers.get(container_name)
                return container.logs(since=since).decode("utf-8", errors="replace")
            except Exception:
                pass
        
        # Fallback to CLI
        try:
            result = subprocess.run(
                ["docker", "logs", "--since", since, container_name],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError:
            return ""
    
    def inspect_container(self, container_name: str) -> Optional[Dict[str, Any]]:
        """Inspect container details."""
        if self._client and not self._use_cli:
            try:
                container = self._client.containers.get(container_name)
                return container.attrs
            except Exception:
                pass
        
        # Fallback to CLI
        try:
            result = subprocess.run(
                ["docker", "inspect", container_name],
                capture_output=True,
                text=True,
                check=True
            )
            data = json.loads(result.stdout)
            return data[0] if data else None
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            return None
    
    def list_networks(self) -> List[Dict[str, Any]]:
        """List Docker networks."""
        if self._client and not self._use_cli:
            try:
                networks = self._client.networks.list()
                return [
                    {
                        "id": n.id,
                        "name": n.name,
                        "driver": n.attrs.get("Driver", ""),
                        "scope": n.attrs.get("Scope", ""),
                        "containers": n.attrs.get("Containers", {}),
                        "ipam": n.attrs.get("IPAM", {}),
                    }
                    for n in networks
                ]
            except Exception:
                pass
        
        # Fallback to CLI
        try:
            result = subprocess.run(
                ["docker", "network", "ls", "--format", "json"],
                capture_output=True,
                text=True,
                check=True
            )
            networks = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    try:
                        network_data = json.loads(line)
                        # Get full network details
                        inspect_result = subprocess.run(
                            ["docker", "network", "inspect", network_data["ID"]],
                            capture_output=True,
                            text=True,
                            check=True
                        )
                        full_data = json.loads(inspect_result.stdout)[0]
                        
                        networks.append({
                            "id": network_data["ID"],
                            "name": network_data["Name"],
                            "driver": full_data.get("Driver", ""),
                            "scope": full_data.get("Scope", ""),
                            "containers": full_data.get("Containers", {}),
                            "ipam": full_data.get("IPAM", {}),
                        })
                    except (json.JSONDecodeError, subprocess.CalledProcessError):
                        continue
            
            return networks
        except subprocess.CalledProcessError:
            return []
    
    def discover_services(self) -> Dict[str, Dict[str, Any]]:
        """Discover services from running containers."""
        containers = self.list_containers()
        services = {}
        
        # Common service patterns
        service_patterns = {
            "qbittorrent": ["qbittorrent", "qb"],
            "radarr": ["radarr"],
            "sonarr": ["sonarr"],
            "sonarr-anime": ["sonarr-anime", "sonarr_anime"],
            "prowlarr": ["prowlarr"],
            "sabnzbd": ["sabnzbd", "sab"],
            "unpackerr": ["unpackerr"],
            "overseerr": ["overseerr"],
            "filebrowser": ["filebrowser"],
            "cloudflared": ["cloudflared"],
            "gluetun": ["gluetun"],
            "plex": ["plex"],
        }
        
        for container in containers:
            container_name = container["name"]
            image = container["image"]
            network_settings = container.get("network_settings", {})
            
            # Find matching service
            service_name = None
            for svc_name, patterns in service_patterns.items():
                if any(pattern in container_name.lower() or pattern in image.lower() 
                      for pattern in patterns):
                    service_name = svc_name
                    break
            
            if not service_name:
                continue
            
            # Extract connection info
            ports = network_settings.get("Ports", {})
            published_ports = []
            service_url = None
            
            # Find published ports
            for container_port, host_bindings in ports.items():
                if host_bindings:
                    for binding in host_bindings:
                        if binding.get("HostPort"):
                            published_ports.append(int(binding["HostPort"]))
                            
                            # Try to construct service URL
                            if not service_url:
                                port_num = binding["HostPort"]
                                if "8080" in container_port or "8081" in container_port:
                                    service_url = f"http://localhost:{port_num}"
                                elif "7878" in container_port:  # Radarr
                                    service_url = f"http://localhost:{port_num}"
                                elif "8989" in container_port:  # Sonarr
                                    service_url = f"http://localhost:{port_num}"
                                elif "9696" in container_port:  # Prowlarr
                                    service_url = f"http://localhost:{port_num}"
                                elif "32400" in container_port:  # Plex
                                    service_url = f"http://localhost:{port_num}"
                                elif "5055" in container_port:  # Overseerr
                                    service_url = f"http://localhost:{port_num}"
            
            services[service_name] = {
                "container": container_name,
                "url": service_url,
                "ports": published_ports,
                "image": image,
                "status": container["status"],
            }
        
        return services
    
    def get_container_network_info(self, container_name: str) -> Dict[str, Any]:
        """Get detailed network information for a container."""
        container = self.inspect_container(container_name)
        if not container:
            return {}
        
        network_settings = container.get("NetworkSettings", {})
        networks = network_settings.get("Networks", {})
        
        return {
            "networks": networks,
            "ip_address": network_settings.get("IPAddress", ""),
            "gateway": network_settings.get("Gateway", ""),
            "bridge": network_settings.get("Bridge", ""),
            "ports": network_settings.get("Ports", {}),
        }
    
    def is_container_healthy(self, container_name: str) -> bool:
        """Check if container is healthy."""
        container = self.inspect_container(container_name)
        if not container:
            return False
        
        state = container.get("State", {})
        health = state.get("Health", {})
        
        if health:
            return health.get("Status") == "healthy"
        
        # Fallback to running status
        return state.get("Status") == "running"
