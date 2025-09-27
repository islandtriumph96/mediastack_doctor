"""Tests for diff functionality."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from mediastack_doctor.utils.diff import (
    diff_runs,
    save_run_manifest,
    get_last_run_id,
    _compare_checks,
    _is_significant_change,
)


class TestDiff:
    """Test diff functionality."""
    
    def test_save_and_load_run_manifest(self):
        """Test saving and loading run manifests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "test_run"
            run_dir.mkdir()
            
            checks = [
                {
                    "id": "H1",
                    "title": "CPU Usage",
                    "severity": "info",
                    "evidence": "CPU usage is 23.4%",
                    "category": "Host & Filesystems"
                },
                {
                    "id": "G1",
                    "title": "VPN Connection",
                    "severity": "fail",
                    "evidence": "VPN connection failed",
                    "category": "Gluetun / PIA"
                }
            ]
            
            save_run_manifest(run_dir, "20240101_120000", checks)
            
            # Check manifest file exists
            manifest_path = run_dir / "run_manifest.json"
            assert manifest_path.exists()
            
            # Load and verify content
            with open(manifest_path, "r") as f:
                manifest = json.load(f)
            
            assert manifest["timestamp"] == "20240101_120000"
            assert "H1" in manifest["checks"]
            assert "G1" in manifest["checks"]
            assert manifest["checks"]["H1"]["severity"] == "info"
            assert manifest["checks"]["G1"]["severity"] == "fail"
    
    def test_compare_checks_no_changes(self):
        """Test comparing identical checks."""
        prev_checks = {
            "H1": {
                "title": "CPU Usage",
                "severity": "info",
                "evidence": "CPU usage is 23.4%"
            }
        }
        
        current_checks = {
            "H1": {
                "title": "CPU Usage",
                "severity": "info",
                "evidence": "CPU usage is 23.4%"
            }
        }
        
        changes = _compare_checks(prev_checks, current_checks)
        assert changes == []
    
    def test_compare_checks_severity_change(self):
        """Test comparing checks with severity changes."""
        prev_checks = {
            "H1": {
                "title": "CPU Usage",
                "severity": "info",
                "evidence": "CPU usage is 23.4%"
            }
        }
        
        current_checks = {
            "H1": {
                "title": "CPU Usage",
                "severity": "warn",
                "evidence": "CPU usage is 85.2%"
            }
        }
        
        changes = _compare_checks(prev_checks, current_checks)
        assert len(changes) == 1
        assert changes[0]["type"] == "severity_change"
        assert changes[0]["prev_severity"] == "info"
        assert changes[0]["current_severity"] == "warn"
    
    def test_compare_checks_new_check(self):
        """Test comparing checks with new check added."""
        prev_checks = {
            "H1": {
                "title": "CPU Usage",
                "severity": "info",
                "evidence": "CPU usage is 23.4%"
            }
        }
        
        current_checks = {
            "H1": {
                "title": "CPU Usage",
                "severity": "info",
                "evidence": "CPU usage is 23.4%"
            },
            "H2": {
                "title": "Memory Usage",
                "severity": "warn",
                "evidence": "Memory usage is 85%"
            }
        }
        
        changes = _compare_checks(prev_checks, current_checks)
        assert len(changes) == 1
        assert changes[0]["type"] == "new"
        assert changes[0]["check_id"] == "H2"
    
    def test_compare_checks_removed_check(self):
        """Test comparing checks with removed check."""
        prev_checks = {
            "H1": {
                "title": "CPU Usage",
                "severity": "info",
                "evidence": "CPU usage is 23.4%"
            },
            "H2": {
                "title": "Memory Usage",
                "severity": "warn",
                "evidence": "Memory usage is 85%"
            }
        }
        
        current_checks = {
            "H1": {
                "title": "CPU Usage",
                "severity": "info",
                "evidence": "CPU usage is 23.4%"
            }
        }
        
        changes = _compare_checks(prev_checks, current_checks)
        assert len(changes) == 1
        assert changes[0]["type"] == "removed"
        assert changes[0]["check_id"] == "H2"
    
    def test_is_significant_change(self):
        """Test significant change detection."""
        # Significant change
        assert _is_significant_change("CPU usage is 23.4%", "CPU usage is 85.2%") is True
        
        # Insignificant change (similar numbers)
        assert _is_significant_change("CPU usage is 23.4%", "CPU usage is 23.5%") is False
        
        # Whitespace only change
        assert _is_significant_change("CPU usage is 23.4%", "  CPU usage is 23.4%  ") is False
        
        # Empty to non-empty
        assert _is_significant_change("", "CPU usage is 23.4%") is True
        
        # Non-empty to empty
        assert _is_significant_change("CPU usage is 23.4%", "") is True
        
        # Both empty
        assert _is_significant_change("", "") is False
    
    def test_diff_runs_success(self):
        """Test successful run diffing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            prev_run_dir = Path(temp_dir) / "prev_run"
            current_run_dir = Path(temp_dir) / "current_run"
            
            prev_run_dir.mkdir()
            current_run_dir.mkdir()
            
            # Create manifests
            prev_manifest = {
                "timestamp": "20240101_120000",
                "checks": {
                    "H1": {
                        "title": "CPU Usage",
                        "severity": "info",
                        "evidence": "CPU usage is 23.4%"
                    }
                }
            }
            
            current_manifest = {
                "timestamp": "20240101_130000",
                "checks": {
                    "H1": {
                        "title": "CPU Usage",
                        "severity": "warn",
                        "evidence": "CPU usage is 85.2%"
                    }
                }
            }
            
            # Save manifests
            with open(prev_run_dir / "run_manifest.json", "w") as f:
                json.dump(prev_manifest, f)
            
            with open(current_run_dir / "run_manifest.json", "w") as f:
                json.dump(current_manifest, f)
            
            # Test diff
            diff_result = diff_runs(prev_run_dir, current_run_dir)
            assert diff_result is not None
            assert "Severity Changes" in diff_result
            assert "H1" in diff_result
    
    def test_diff_runs_no_manifests(self):
        """Test diffing runs without manifests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            prev_run_dir = Path(temp_dir) / "prev_run"
            current_run_dir = Path(temp_dir) / "current_run"
            
            prev_run_dir.mkdir()
            current_run_dir.mkdir()
            
            # Test diff without manifests
            diff_result = diff_runs(prev_run_dir, current_run_dir)
            assert diff_result is None
    
    def test_get_last_run_id(self):
        """Test getting last run ID."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            # No runs
            last_run = get_last_run_id(output_dir)
            assert last_run is None
            
            # Create run directories
            run1 = output_dir / "20240101_120000"
            run2 = output_dir / "20240101_130000"
            run3 = output_dir / "20240101_140000"
            
            run1.mkdir()
            run2.mkdir()
            run3.mkdir()
            
            # Get last run
            last_run = get_last_run_id(output_dir)
            assert last_run == "20240101_140000"
