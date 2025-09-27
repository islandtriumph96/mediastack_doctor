"""Tests for advisor functionality."""

import pytest

from mediastack_doctor.utils.advisor import (
    generate_advisor_fixes,
    get_compose_snippets,
    get_env_snippets,
)


class TestAdvisor:
    """Test advisor functionality."""
    
    def test_generate_advisor_fixes_empty(self):
        """Test advisor with no checks."""
        checks = []
        fixes = generate_advisor_fixes(checks)
        assert fixes == []
    
    def test_generate_advisor_fixes_with_suggested_fix(self):
        """Test advisor with checks that have suggested fixes."""
        checks = [
            {
                "id": "H1",
                "title": "CPU Usage",
                "severity": "warn",
                "evidence": "High CPU usage",
                "suggested_fix": "Check for runaway processes"
            }
        ]
        
        fixes = generate_advisor_fixes(checks)
        assert len(fixes) == 1
        assert "CPU Usage" in fixes[0]
        assert "Check for runaway processes" in fixes[0]
    
    def test_generate_advisor_fixes_with_list_suggested_fix(self):
        """Test advisor with checks that have list suggested fixes."""
        checks = [
            {
                "id": "G1",
                "title": "Firewall Rules",
                "severity": "fail",
                "evidence": "Firewall blocking Docker",
                "suggested_fix": [
                    "Add Docker networks to FIREWALL_INPUT_SUBNETS",
                    "Configure FIREWALL_OUTBOUND_SUBNETS"
                ]
            }
        ]
        
        fixes = generate_advisor_fixes(checks)
        assert len(fixes) == 1
        assert "Firewall Rules" in fixes[0]
        assert "Add Docker networks" in fixes[0]
        assert "Configure FIREWALL_OUTBOUND_SUBNETS" in fixes[0]
    
    def test_generate_advisor_fixes_ignores_info_severity(self):
        """Test that advisor ignores info severity checks."""
        checks = [
            {
                "id": "H1",
                "title": "CPU Usage",
                "severity": "info",
                "evidence": "Normal CPU usage",
                "suggested_fix": "No action needed"
            }
        ]
        
        fixes = generate_advisor_fixes(checks)
        assert fixes == []
    
    def test_generate_advisor_fixes_gluetun_patterns(self):
        """Test advisor with Gluetun-specific checks."""
        checks = [
            {
                "id": "G1",
                "title": "VPN Connection",
                "severity": "fail",
                "evidence": "VPN connection failed"
            }
        ]
        
        fixes = generate_advisor_fixes(checks)
        assert len(fixes) == 1
        assert "VPN Connection" in fixes[0]
        assert "PIA credentials" in fixes[0]
    
    def test_generate_advisor_fixes_qbittorrent_patterns(self):
        """Test advisor with qBittorrent-specific checks."""
        checks = [
            {
                "id": "Q1",
                "title": "WebUI Connectivity",
                "severity": "fail",
                "evidence": "Cannot connect to WebUI"
            }
        ]
        
        fixes = generate_advisor_fixes(checks)
        assert len(fixes) == 1
        assert "WebUI Connectivity" in fixes[0]
        assert "qBittorrent container" in fixes[0]
    
    def test_generate_advisor_fixes_arr_patterns(self):
        """Test advisor with Arr-specific checks."""
        checks = [
            {
                "id": "A1",
                "title": "API Connectivity",
                "severity": "warn",
                "evidence": "API not accessible"
            }
        ]
        
        fixes = generate_advisor_fixes(checks)
        assert len(fixes) == 1
        assert "API Connectivity" in fixes[0]
        assert "API key" in fixes[0]
    
    def test_get_compose_snippets(self):
        """Test compose snippets retrieval."""
        snippets = get_compose_snippets()
        
        assert "gluetun_firewall" in snippets
        assert "qbittorrent_gluetun" in snippets
        assert "consistent_volumes" in snippets
        assert "plex_remote_access" in snippets
        
        # Check that snippets contain expected content
        assert "FIREWALL_INPUT_SUBNETS" in snippets["gluetun_firewall"]
        assert "network_mode: service:gluetun" in snippets["qbittorrent_gluetun"]
        assert "/mnt/PLEX22TB" in snippets["consistent_volumes"]
        assert "PLEX_CLAIM" in snippets["plex_remote_access"]
    
    def test_get_env_snippets(self):
        """Test environment snippets retrieval."""
        snippets = get_env_snippets()
        
        assert "pia_credentials" in snippets
        assert "pia_port_forward" in snippets
        assert "dns_servers" in snippets
        
        # Check that snippets contain expected content
        assert "VPN_SERVICE_PROVIDER" in snippets["pia_credentials"]
        assert "PORT_FORWARDING" in snippets["pia_port_forward"]
        assert "DNS_SERVERS" in snippets["dns_servers"]
