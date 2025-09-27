"""Tests for path parity functionality."""

import pytest
from unittest.mock import Mock

from mediastack_doctor.checks.arr import _check_path_parity, _generate_path_parity_compose_snippet


class TestPathParity:
    """Test path parity functionality."""
    
    def test_path_parity_no_services(self):
        """Test path parity with no services."""
        registry = Mock()
        docker_client = Mock()
        docker_client.list_containers.return_value = []
        
        checks = _check_path_parity(registry, docker_client)
        
        assert len(checks) == 1
        assert checks[0]["id"] == "A6"
        assert checks[0]["severity"] == "warn"
        assert "No media services found" in checks[0]["evidence"]
    
    def test_path_parity_consistent_paths(self):
        """Test path parity with consistent paths."""
        registry = Mock()
        docker_client = Mock()
        
        # Mock containers with consistent paths
        containers = [
            {
                "name": "radarr",
                "mounts": [
                    {
                        "Type": "bind",
                        "Source": "/mnt/GDRIVE36",
                        "Destination": "/downloads"
                    },
                    {
                        "Type": "bind",
                        "Source": "/mnt/PLEX22TB",
                        "Destination": "/media"
                    }
                ]
            },
            {
                "name": "sonarr",
                "mounts": [
                    {
                        "Type": "bind",
                        "Source": "/mnt/GDRIVE36",
                        "Destination": "/downloads"
                    },
                    {
                        "Type": "bind",
                        "Source": "/mnt/PLEX22TB",
                        "Destination": "/media"
                    }
                ]
            },
            {
                "name": "qbittorrent",
                "mounts": [
                    {
                        "Type": "bind",
                        "Source": "/mnt/GDRIVE36",
                        "Destination": "/downloads"
                    }
                ]
            }
        ]
        
        docker_client.list_containers.return_value = containers
        
        checks = _check_path_parity(registry, docker_client)
        
        # Should have consistent path checks
        download_check = next((c for c in checks if c["id"] == "A6_DOWNLOADS_OK"), None)
        media_check = next((c for c in checks if c["id"] == "A6_MEDIA_OK"), None)
        
        assert download_check is not None
        assert download_check["severity"] == "info"
        assert "/mnt/GDRIVE36" in download_check["evidence"]
        
        assert media_check is not None
        assert media_check["severity"] == "info"
        assert "/mnt/PLEX22TB" in media_check["evidence"]
    
    def test_path_parity_inconsistent_paths(self):
        """Test path parity with inconsistent paths."""
        registry = Mock()
        docker_client = Mock()
        
        # Mock containers with inconsistent paths
        containers = [
            {
                "name": "radarr",
                "mounts": [
                    {
                        "Type": "bind",
                        "Source": "/mnt/GDRIVE36",
                        "Destination": "/downloads"
                    }
                ]
            },
            {
                "name": "sonarr",
                "mounts": [
                    {
                        "Type": "bind",
                        "Source": "/mnt/PLEX22TB",  # Different source!
                        "Destination": "/downloads"
                    }
                ]
            }
        ]
        
        docker_client.list_containers.return_value = containers
        
        checks = _check_path_parity(registry, docker_client)
        
        # Should have inconsistent path check
        download_check = next((c for c in checks if c["id"] == "A6_DOWNLOADS"), None)
        
        assert download_check is not None
        assert download_check["severity"] == "fail"
        assert "Multiple download sources" in download_check["evidence"]
        assert "/mnt/GDRIVE36" in download_check["evidence"]
        assert "/mnt/PLEX22TB" in download_check["evidence"]
    
    def test_path_parity_common_issues(self):
        """Test path parity with common path issues."""
        registry = Mock()
        docker_client = Mock()
        
        # Mock containers with /data instead of /downloads
        containers = [
            {
                "name": "radarr",
                "mounts": [
                    {
                        "Type": "bind",
                        "Source": "/mnt/GDRIVE36",
                        "Destination": "/data"  # Wrong destination
                    }
                ]
            }
        ]
        
        docker_client.list_containers.return_value = containers
        
        checks = _check_path_parity(registry, docker_client)
        
        # Should have common issues check
        common_issues_check = next((c for c in checks if c["id"] == "A6_COMMON_ISSUES"), None)
        
        assert common_issues_check is not None
        assert common_issues_check["severity"] == "warn"
        assert "radarr uses /data instead of /downloads" in common_issues_check["evidence"]
    
    def test_path_parity_compose_snippet(self):
        """Test compose snippet generation."""
        service_paths = {
            "radarr": {
                "downloads": {"source": "/mnt/GDRIVE36", "destination": "/downloads"},
                "media": {"source": "/mnt/PLEX22TB", "destination": "/media"}
            },
            "sonarr": {
                "downloads": {"source": "/mnt/GDRIVE36", "destination": "/downloads"},
                "media": {"source": "/mnt/PLEX22TB", "destination": "/media"}
            }
        }
        
        snippet = _generate_path_parity_compose_snippet(service_paths)
        
        assert "volumes:" in snippet
        assert "/mnt/PLEX22TB:/media" in snippet
        assert "/mnt/GDRIVE36:/downloads" in snippet
        assert "services:" in snippet
        assert "radarr:" in snippet
        assert "sonarr:" in snippet
        assert "qbittorrent:" in snippet
        assert "PUID=1000" in snippet
        assert "PGID=1000" in snippet
    
    def test_path_parity_with_compose_snippet(self):
        """Test that compose snippet is generated when issues are found."""
        registry = Mock()
        docker_client = Mock()
        
        # Mock containers with inconsistent paths to trigger compose snippet
        containers = [
            {
                "name": "radarr",
                "mounts": [
                    {
                        "Type": "bind",
                        "Source": "/mnt/GDRIVE36",
                        "Destination": "/downloads"
                    }
                ]
            },
            {
                "name": "sonarr",
                "mounts": [
                    {
                        "Type": "bind",
                        "Source": "/mnt/PLEX22TB",  # Different source
                        "Destination": "/downloads"
                    }
                ]
            }
        ]
        
        docker_client.list_containers.return_value = containers
        
        checks = _check_path_parity(registry, docker_client)
        
        # Should have compose snippet check
        compose_check = next((c for c in checks if c["id"] == "A6_COMPOSE_SNIPPET"), None)
        
        assert compose_check is not None
        assert compose_check["severity"] == "info"
        assert "docker-compose.yml snippet" in compose_check["suggested_fix"]
        assert "```yaml" in compose_check["suggested_fix"]
