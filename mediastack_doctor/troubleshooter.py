"""Service troubleshooting and snapshot creation."""

import os
import json
import tarfile
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class ServiceTroubleshooter:
    """Creates diagnostic snapshots for specific services."""

    def __init__(self, registry, docker_client):
        self.registry = registry
        self.docker_client = docker_client
        self.output_dir = Path.home() / "mediastack-doctor" / "outputs"

    def create_snapshot(self, service_name: str) -> Path:
        """Create a diagnostic snapshot for a service."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_dir = self.output_dir / f"snapshot_{service_name}_{timestamp}"
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        snapshot_data = {
            "service": service_name,
            "timestamp": timestamp,
            "host_info": self._get_host_info(),
            "docker_info": self._get_docker_info(service_name),
            "network_info": self._get_network_info(service_name),
            "logs": self._get_service_logs(service_name),
            "api_responses": self._get_api_responses(service_name),
            "recommendations": self._get_recommendations(service_name)
        }

        # Save JSON data
        json_path = snapshot_dir / "snapshot.json"
        with open(json_path, "w") as f:
            json.dump(snapshot_data, f, indent=2, default=str)

        # Save readable markdown
        md_path = snapshot_dir / "snapshot.md"
        self._save_markdown_snapshot(md_path, snapshot_data)

        # Create tar.gz of logs and configs
        tar_path = snapshot_dir / "snapshot.tar.gz"
        self._create_logs_archive(snapshot_dir, tar_path, service_name)

        return snapshot_dir

    def _get_host_info(self) -> Dict[str, Any]:
        """Get basic host information."""
        try:
            import psutil
            import platform

            return {
                "hostname": platform.node(),
                "platform": platform.platform(),
                "cpu_count": psutil.cpu_count(),
                "memory_total": psutil.virtual_memory().total,
                "disk_usage": {
                    mount: {
                        "total": usage.total,
                        "used": usage.used,
                        "free": usage.free,
                        "percent": usage.percent
                    }
                    for mount, usage in [
                        ("/", psutil.disk_usage("/")),
                        ("/mnt/PLEX22TB", psutil.disk_usage("/mnt/PLEX22TB")),
                        ("/mnt/GDRIVE36", psutil.disk_usage("/mnt/GDRIVE36"))
                    ] if os.path.exists(mount)
                }
            }
        except Exception as e:
            return {"error": f"Could not get host info: {e}"}

    def _get_docker_info(self, service_name: str) -> Dict[str, Any]:
        """Get Docker container information for the service."""
        if not self.docker_client:
            return {"error": "Docker client not available"}

        try:
            containers = self.docker_client.list_containers()
            service_containers = []

            for container in containers:
                container_name = container["name"].lower()
                if service_name in container_name or service_name.replace("-", "_") in container_name:
                    service_containers.append(container)

            if not service_containers:
                return {"error": f"No containers found for service: {service_name}"}

            container_info = []
            for container in service_containers:
                container_name = container["name"]

                # Get detailed container info
                try:
                    inspect_data = self.docker_client.inspect_container(container_name)
                    container_info.append({
                        "name": container_name,
                        "status": container["status"],
                        "image": container.get("image", "unknown"),
                        "ports": inspect_data.get("NetworkSettings", {}).get("Ports", []),
                        "networks": list(inspect_data.get("NetworkSettings", {}).get("Networks", {}).keys()),
                        "mounts": [
                            {
                                "source": mount.get("Source", ""),
                                "destination": mount.get("Destination", ""),
                                "type": mount.get("Type", "")
                            }
                            for mount in inspect_data.get("Mounts", [])
                        ]
                    })
                except Exception as e:
                    container_info.append({
                        "name": container_name,
                        "status": container["status"],
                        "error": f"Could not inspect: {e}"
                    })

            return {"containers": container_info}

        except Exception as e:
            return {"error": f"Could not get Docker info: {e}"}

    def _get_network_info(self, service_name: str) -> Dict[str, Any]:
        """Get network information for the service."""
        try:
            # Get network interfaces
            network_info = {}

            # Get IP addresses
            try:
                result = subprocess.run(
                    ["ip", "addr", "show"],
                    capture_output=True, text=True, timeout=10
                )
                network_info["ip_addresses"] = result.stdout
            except Exception as e:
                network_info["ip_error"] = f"Could not get IP addresses: {e}"

            # Get routing table
            try:
                result = subprocess.run(
                    ["ip", "route", "show"],
                    capture_output=True, text=True, timeout=10
                )
                network_info["routing"] = result.stdout
            except Exception as e:
                network_info["route_error"] = f"Could not get routing: {e}"

            # Get Docker networks
            if self.docker_client:
                try:
                    networks = self.docker_client.networks()
                    network_info["docker_networks"] = [
                        {
                            "name": net["Name"],
                            "driver": net["Driver"],
                            "scope": net.get("Scope", "local")
                        }
                        for net in networks
                    ]
                except Exception as e:
                    network_info["docker_networks_error"] = f"Could not get Docker networks: {e}"

            return network_info

        except Exception as e:
            return {"error": f"Could not get network info: {e}"}

    def _get_service_logs(self, service_name: str) -> Dict[str, Any]:
        """Get recent logs for the service."""
        if not self.docker_client:
            return {"error": "Docker client not available"}

        try:
            containers = self.docker_client.list_containers()
            service_containers = []

            for container in containers:
                container_name = container["name"].lower()
                if service_name in container_name or service_name.replace("-", "_") in container_name:
                    service_containers.append(container["name"])

            if not service_containers:
                return {"error": f"No containers found for service: {service_name}"}

            logs_data = {}
            for container_name in service_containers:
                try:
                    logs = self.docker_client.get_container_logs(container_name, since="1h")
                    logs_data[container_name] = logs.split('\n')[-100:]  # Last 100 lines
                except Exception as e:
                    logs_data[container_name] = f"Could not get logs: {e}"

            return {"containers": logs_data}

        except Exception as e:
            return {"error": f"Could not get service logs: {e}"}

    def _get_api_responses(self, service_name: str) -> Dict[str, Any]:
        """Get API responses for the service."""
        if not HAS_REQUESTS:
            return {"error": "requests library not available"}

        service_config = self.registry.get_service(service_name)
        if not service_config or not service_config.url:
            return {"error": f"Service {service_name} not configured"}

        url = service_config.url
        api_responses = {}

        try:
            # Test basic connectivity
            response = requests.head(url, timeout=10)
            api_responses["connectivity"] = {
                "status_code": response.status_code,
                "headers": dict(response.headers)
            }

        except Exception as e:
            api_responses["connectivity"] = {"error": f"Could not connect: {e}"}

        # Service-specific API calls
        if service_name == "qbittorrent":
            api_responses.update(self._get_qbittorrent_api(url))
        elif service_name in ["radarr", "sonarr", "prowlarr"]:
            api_responses.update(self._get_arr_api(url, service_name))
        elif service_name == "plex":
            api_responses.update(self._get_plex_api(url))

        return api_responses

    def _get_qbittorrent_api(self, url: str) -> Dict[str, Any]:
        """Get qBittorrent API responses."""
        responses = {}

        try:
            # Try to get version (requires auth)
            response = requests.get(f"{url}/api/v2/app/version", timeout=10)
            responses["version"] = {
                "status_code": response.status_code,
                "content": response.text if response.status_code == 200 else "Authentication required"
            }
        except Exception as e:
            responses["version"] = {"error": f"Could not get version: {e}"}

        return responses

    def _get_arr_api(self, url: str, service_name: str) -> Dict[str, Any]:
        """Get Arr service API responses."""
        responses = {}

        try:
            # Try to get system status (requires API key)
            response = requests.get(f"{url}/api/v3/system/status", timeout=10)
            responses["system_status"] = {
                "status_code": response.status_code,
                "content": response.text[:500] if response.status_code == 200 else "Authentication required"
            }
        except Exception as e:
            responses["system_status"] = {"error": f"Could not get system status: {e}"}

        return responses

    def _get_plex_api(self, url: str) -> Dict[str, Any]:
        """Get Plex API responses."""
        responses = {}

        try:
            # Try to get server identity (requires token)
            response = requests.get(f"{url}/identity", timeout=10)
            responses["identity"] = {
                "status_code": response.status_code,
                "content": response.text[:500] if response.status_code == 200 else "Authentication required"
            }
        except Exception as e:
            responses["identity"] = {"error": f"Could not get identity: {e}"}

        return responses

    def _get_recommendations(self, service_name: str) -> Dict[str, Any]:
        """Get troubleshooting recommendations."""
        recommendations = {
            "general": [
                "Check Docker container logs: docker logs <container_name>",
                "Verify network connectivity: docker exec <container> curl -s ifconfig.me",
                "Check container resource usage: docker stats <container_name>",
                "Review service configuration files in container"
            ],
            "specific": {}
        }

        # Service-specific recommendations
        if service_name == "qbittorrent":
            recommendations["specific"] = [
                "Verify qBittorrent WebUI credentials",
                "Check VPN connectivity if using Gluetun",
                "Verify download paths and permissions",
                "Check torrent client port forwarding"
            ]
        elif service_name in ["radarr", "sonarr", "prowlarr"]:
            recommendations["specific"] = [
                "Verify API key configuration",
                "Check indexer connectivity",
                "Verify download client integration",
                "Review quality profiles and naming"
            ]
        elif service_name == "plex":
            recommendations["specific"] = [
                "Check Plex authentication token",
                "Verify media library paths",
                "Test remote access connectivity",
                "Review transcoding settings"
            ]
        elif service_name == "gluetun":
            recommendations["specific"] = [
                "Check VPN credentials and region",
                "Verify port forwarding configuration",
                "Test DNS leak protection",
                "Review firewall rules"
            ]

        return recommendations

    def _save_markdown_snapshot(self, md_path: Path, data: Dict[str, Any]):
        """Save snapshot data as readable markdown."""
        with open(md_path, "w") as f:
            f.write(f"# Service Snapshot: {data['service']}\n\n")
            f.write(f"**Generated:** {data['timestamp']}\n\n")

            # Host information
            f.write("## Host Information\n\n")
            host_info = data["host_info"]
            if "error" not in host_info:
                f.write(f"**Hostname:** {host_info.get('hostname', 'Unknown')}\n")
                f.write(f"**Platform:** {host_info.get('platform', 'Unknown')}\n")
                f.write(f"**CPU Cores:** {host_info.get('cpu_count', 'Unknown')}\n")
                f.write(f"**Memory Total:** {host_info.get('memory_total', 0) // (1024**3)} GB\n\n")

                # Disk usage
                if "disk_usage" in host_info:
                    f.write("### Disk Usage\n")
                    for mount, usage in host_info["disk_usage"].items():
                        f.write(f"- **{mount}:** {usage['percent']:.1f}% used ({usage['used'] // (1024**3)} GB / {usage['total'] // (1024**3)} GB)\n")
                    f.write("\n")
            else:
                f.write(f"Error getting host info: {host_info['error']}\n\n")

            # Docker information
            f.write("## Docker Information\n\n")
            docker_info = data["docker_info"]
            if "error" not in docker_info and "containers" in docker_info:
                for container in docker_info["containers"]:
                    f.write(f"### {container['name']}\n")
                    f.write(f"- **Status:** {container.get('status', 'Unknown')}\n")
                    f.write(f"- **Image:** {container.get('image', 'Unknown')}\n")

                    if "ports" in container and container["ports"]:
                        f.write("- **Port Bindings:**\n")
                        for port in container["ports"]:
                            if isinstance(port, dict):
                                f.write(f"  - {port.get('PrivatePort', 'N/A')}:{port.get('PublicPort', 'N/A')}\n")
                            else:
                                f.write(f"  - {port}\n")

                    if "networks" in container and container["networks"]:
                        f.write(f"- **Networks:** {', '.join(container['networks'])}\n")

                    if "mounts" in container and container["mounts"]:
                        f.write("- **Mounts:**\n")
                        for mount in container["mounts"]:
                            f.write(f"  - {mount['source']} → {mount['destination']}\n")

                    f.write("\n")
            else:
                f.write(f"Error getting Docker info: {docker_info.get('error', 'Unknown')}\n\n")

            # Network information
            f.write("## Network Information\n\n")
            network_info = data["network_info"]
            if "error" not in network_info:
                if "ip_addresses" in network_info:
                    f.write("### IP Addresses\n")
                    f.write("```\n")
                    f.write(network_info["ip_addresses"])
                    f.write("```\n\n")

                if "routing" in network_info:
                    f.write("### Routing Table\n")
                    f.write("```\n")
                    f.write(network_info["routing"])
                    f.write("```\n\n")

                if "docker_networks" in network_info:
                    f.write("### Docker Networks\n")
                    for net in network_info["docker_networks"]:
                        f.write(f"- **{net['name']}** ({net['driver']}, {net['scope']})\n")
                    f.write("\n")
            else:
                f.write(f"Error getting network info: {network_info['error']}\n\n")

            # Logs
            f.write("## Recent Logs\n\n")
            logs = data["logs"]
            if "error" not in logs and "containers" in logs:
                for container_name, log_lines in logs["containers"].items():
                    f.write(f"### {container_name} (last 100 lines)\n")
                    f.write("```\n")
                    f.write('\n'.join(log_lines[-50:]))  # Last 50 lines for readability
                    f.write("\n```\n\n")
            else:
                f.write(f"Error getting logs: {logs.get('error', 'Unknown')}\n\n")

            # API responses
            f.write("## API Responses\n\n")
            api_responses = data["api_responses"]
            if "error" not in api_responses:
                for endpoint, response_data in api_responses.items():
                    f.write(f"### {endpoint.title()}\n")
                    if "error" in response_data:
                        f.write(f"Error: {response_data['error']}\n\n")
                    elif "status_code" in response_data:
                        f.write(f"**Status:** {response_data['status_code']}\n")
                        if "content" in response_data:
                            f.write("**Response:**\n```\n")
                            f.write(str(response_data["content"])[:500])
                            f.write("\n```\n\n")
                        if "headers" in response_data:
                            f.write("**Headers:**\n```\n")
                            for key, value in response_data["headers"].items():
                                f.write(f"{key}: {value}\n")
                            f.write("```\n\n")
            else:
                f.write(f"Error getting API responses: {api_responses['error']}\n\n")

            # Recommendations
            f.write("## Troubleshooting Recommendations\n\n")
            recommendations = data["recommendations"]

            f.write("### General Steps\n")
            for rec in recommendations["general"]:
                f.write(f"- {rec}\n")
            f.write("\n")

            f.write("### Service-Specific Steps\n")
            for rec in recommendations["specific"]:
                f.write(f"- {rec}\n")
            f.write("\n")

            f.write("---\n\n")
            f.write("*This snapshot was generated by MediaStack Doctor for troubleshooting purposes.*\n")

    def _create_logs_archive(self, snapshot_dir: Path, tar_path: Path, service_name: str):
        """Create a tar.gz archive of logs and configs."""
        try:
            with tarfile.open(tar_path, "w:gz") as tar:
                # Add logs
                logs_dir = snapshot_dir / "logs"
                logs_dir.mkdir(exist_ok=True)

                # Get container logs
                if self.docker_client:
                    containers = self.docker_client.list_containers()
                    for container in containers:
                        container_name = container["name"].lower()
                        if service_name in container_name or service_name.replace("-", "_") in container_name:
                            try:
                                logs = self.docker_client.get_container_logs(container_name, since="24h")
                                log_file = logs_dir / f"{container_name}.log"
                                with open(log_file, "w") as f:
                                    f.write(logs)
                                tar.add(log_file, arcname=f"logs/{container_name}.log")
                            except Exception:
                                pass  # Skip if can't get logs

                # Add any config files if they exist
                config_files = [
                    "/etc/hosts",
                    "/etc/resolv.conf",
                    "/proc/version"
                ]

                for config_file in config_files:
                    if os.path.exists(config_file):
                        try:
                            tar.add(config_file, arcname=f"configs/{os.path.basename(config_file)}")
                        except Exception:
                            pass

        except Exception as e:
            # Create a simple error file if tar creation fails
            error_file = snapshot_dir / "archive_error.txt"
            with open(error_file, "w") as f:
                f.write(f"Could not create logs archive: {e}\n")
