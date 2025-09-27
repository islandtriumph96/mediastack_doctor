"""Storage health and filesystem checks."""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional


def run_checks(registry: Any, docker_client: Any, deep_mode: bool = False) -> List[Dict[str, Any]]:
    """Run storage health checks."""
    checks = []
    
    # SMART health checks (S3)
    checks.extend(_check_smart_health())
    
    # I/O latency checks (S4) - only in deep mode
    if deep_mode:
        checks.extend(_check_io_latency())
    
    return checks


def _check_smart_health() -> List[Dict[str, Any]]:
    """Check SMART health for disks backing media mounts (S3)."""
    checks = []
    
    # Check if smartctl is available
    try:
        result = subprocess.run(
            ["smartctl", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            checks.append({
                "id": "S3",
                "category": "Storage Health",
                "title": "SMART Health Check",
                "severity": "info",
                "evidence": "smartctl not available",
                "why_it_matters": "Cannot check disk health without smartctl",
                "suggested_fix": "Install smartmontools: sudo apt install smartmontools",
            })
            return checks
    except (subprocess.TimeoutExpired, FileNotFoundError):
        checks.append({
            "id": "S3",
            "category": "Storage Health",
            "title": "SMART Health Check",
            "severity": "info",
            "evidence": "smartctl not available",
            "why_it_matters": "Cannot check disk health without smartctl",
            "suggested_fix": "Install smartmontools: sudo apt install smartmontools",
        })
        return checks
    
    # Find disks backing media mounts
    media_mounts = ["/mnt/PLEX22TB", "/mnt/GDRIVE36"]
    checked_disks = set()
    
    for mount_point in media_mounts:
        if os.path.exists(mount_point):
            try:
                # Get the device backing this mount
                result = subprocess.run(
                    ["df", "-P", mount_point],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 1:
                        device = lines[1].split()[0]
                        
                        # Extract the base device (remove partition number)
                        if device.startswith('/dev/'):
                            base_device = device.rstrip('0123456789')
                            if base_device not in checked_disks:
                                checked_disks.add(base_device)
                                checks.extend(_check_disk_smart(base_device, mount_point))
            except Exception:
                continue
    
    # If no media mounts found, check common storage devices
    if not checked_disks:
        common_devices = ["/dev/sda", "/dev/sdb", "/dev/nvme0n1", "/dev/nvme1n1"]
        for device in common_devices:
            if os.path.exists(device):
                checks.extend(_check_disk_smart(device, "system"))
                break
    
    return checks


def _check_disk_smart(device: str, mount_point: str) -> List[Dict[str, Any]]:
    """Check SMART health for a specific disk."""
    checks = []
    
    try:
        # Get SMART health status
        result = subprocess.run(
            ["smartctl", "-H", device],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            output = result.stdout.lower()
            
            if "passed" in output:
                severity = "info"
                evidence = f"SMART health PASSED for {device} (backing {mount_point})"
                why = "Disk health is good"
                fix = None
            elif "failed" in output:
                severity = "fail"
                evidence = f"SMART health FAILED for {device} (backing {mount_point})"
                why = "Disk health is critical - immediate attention required"
                fix = "Backup data immediately and replace the disk"
            else:
                severity = "warn"
                evidence = f"SMART health status unclear for {device} (backing {mount_point})"
                why = "Disk health status is ambiguous"
                fix = "Check disk health manually and consider replacement"
            
            checks.append({
                "id": f"S3_{device.replace('/', '_')}",
                "category": "Storage Health",
                "title": f"SMART Health - {device}",
                "severity": severity,
                "evidence": evidence,
                "why_it_matters": why,
                "suggested_fix": fix,
            })
            
            # Get additional SMART attributes if health is not passed
            if "passed" not in output:
                checks.extend(_get_smart_attributes(device, mount_point))
        
        else:
            checks.append({
                "id": f"S3_{device.replace('/', '_')}",
                "category": "Storage Health",
                "title": f"SMART Health - {device}",
                "severity": "warn",
                "evidence": f"Cannot read SMART data for {device} (backing {mount_point})",
                "why_it_matters": "Cannot assess disk health",
                "suggested_fix": "Check disk permissions and SMART support",
            })
    
    except subprocess.TimeoutExpired:
        checks.append({
            "id": f"S3_{device.replace('/', '_')}",
            "category": "Storage Health",
            "title": f"SMART Health - {device}",
            "severity": "warn",
            "evidence": f"SMART check timed out for {device} (backing {mount_point})",
            "why_it_matters": "Disk may be slow or unresponsive",
            "suggested_fix": "Check disk performance and consider replacement",
        })
    except Exception as e:
        checks.append({
            "id": f"S3_{device.replace('/', '_')}",
            "category": "Storage Health",
            "title": f"SMART Health - {device}",
            "severity": "warn",
            "evidence": f"Error checking SMART for {device}: {e}",
            "why_it_matters": "Cannot assess disk health",
            "suggested_fix": "Check disk accessibility and SMART support",
        })
    
    return checks


def _get_smart_attributes(device: str, mount_point: str) -> List[Dict[str, Any]]:
    """Get detailed SMART attributes for a disk."""
    checks = []
    
    try:
        result = subprocess.run(
            ["smartctl", "-A", device],
            capture_output=True,
            text=True,
            timeout=15
        )
        
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            
            # Look for critical attributes
            critical_attributes = {
                "Reallocated_Sector_Ct": "Reallocated Sectors",
                "Current_Pending_Sector": "Pending Sectors",
                "Offline_Uncorrectable": "Offline Uncorrectable",
                "Temperature_Celsius": "Temperature",
                "Power_On_Hours": "Power-On Hours",
            }
            
            for line in lines:
                parts = line.split()
                if len(parts) >= 10:
                    attr_id = parts[0]
                    attr_name = parts[1]
                    raw_value = parts[9]
                    
                    if attr_name in critical_attributes:
                        display_name = critical_attributes[attr_name]
                        
                        # Check for concerning values
                        if attr_name == "Reallocated_Sector_Ct" and raw_value != "0":
                            checks.append({
                                "id": f"S3_{device.replace('/', '_')}_{attr_name}",
                                "category": "Storage Health",
                                "title": f"SMART Attribute - {display_name}",
                                "severity": "warn",
                                "evidence": f"{display_name}: {raw_value} (backing {mount_point})",
                                "why_it_matters": "Reallocated sectors indicate disk wear",
                                "suggested_fix": "Monitor disk health and consider replacement if count increases",
                            })
                        elif attr_name == "Current_Pending_Sector" and raw_value != "0":
                            checks.append({
                                "id": f"S3_{device.replace('/', '_')}_{attr_name}",
                                "category": "Storage Health",
                                "title": f"SMART Attribute - {display_name}",
                                "severity": "fail",
                                "evidence": f"{display_name}: {raw_value} (backing {mount_point})",
                                "why_it_matters": "Pending sectors indicate potential data loss",
                                "suggested_fix": "Backup data immediately and replace disk",
                            })
                        elif attr_name == "Temperature_Celsius":
                            try:
                                temp = int(raw_value)
                                if temp > 60:
                                    checks.append({
                                        "id": f"S3_{device.replace('/', '_')}_{attr_name}",
                                        "category": "Storage Health",
                                        "title": f"SMART Attribute - {display_name}",
                                        "severity": "warn",
                                        "evidence": f"{display_name}: {temp}°C (backing {mount_point})",
                                        "why_it_matters": "High disk temperature can cause failures",
                                        "suggested_fix": "Improve cooling and monitor temperature",
                                    })
                            except ValueError:
                                pass
    
    except Exception:
        pass  # Ignore errors in detailed attribute checking
    
    return checks


def _check_io_latency() -> List[Dict[str, Any]]:
    """Check I/O latency using dd tests (S4)."""
    checks = []
    
    # Test I/O latency on media mounts
    media_mounts = ["/mnt/PLEX22TB", "/mnt/GDRIVE36"]
    
    for mount_point in media_mounts:
        if os.path.exists(mount_point) and os.access(mount_point, os.W_OK):
            checks.extend(_test_mount_io_latency(mount_point))
    
    return checks


def _test_mount_io_latency(mount_point: str) -> List[Dict[str, Any]]:
    """Test I/O latency on a specific mount point."""
    checks = []
    
    try:
        # Create a temporary file for testing
        with tempfile.NamedTemporaryFile(dir=mount_point, delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            # Test write latency (8MB test)
            import time
            start_time = time.time()
            
            result = subprocess.run(
                ["dd", "if=/dev/zero", f"of={temp_path}", "bs=1M", "count=8", "oflag=direct"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            write_time = time.time() - start_time
            
            if result.returncode == 0:
                # Calculate write speed
                write_speed = 8 / write_time  # MB/s
                
                # Test read latency
                start_time = time.time()
                
                result = subprocess.run(
                    ["dd", f"if={temp_path}", "of=/dev/null", "bs=1M", "oflag=direct"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                read_time = time.time() - start_time
                
                if result.returncode == 0:
                    read_speed = 8 / read_time  # MB/s
                    
                    # Determine severity based on speeds
                    if write_speed < 10 or read_speed < 10:
                        severity = "warn"
                        evidence = f"Slow I/O: Write {write_speed:.1f} MB/s, Read {read_speed:.1f} MB/s"
                        why = "Slow I/O performance may impact media operations"
                        fix = "Check disk health, cables, and consider SSD upgrade"
                    elif write_speed < 50 or read_speed < 50:
                        severity = "info"
                        evidence = f"Moderate I/O: Write {write_speed:.1f} MB/s, Read {read_speed:.1f} MB/s"
                        why = "I/O performance is adequate for most operations"
                        fix = None
                    else:
                        severity = "info"
                        evidence = f"Good I/O: Write {write_speed:.1f} MB/s, Read {read_speed:.1f} MB/s"
                        why = "I/O performance is good"
                        fix = None
                    
                    checks.append({
                        "id": f"S4_{mount_point.replace('/', '_').replace('mnt_', '')}",
                        "category": "Storage Health",
                        "title": f"I/O Latency Test - {mount_point}",
                        "severity": severity,
                        "evidence": evidence,
                        "why_it_matters": why,
                        "suggested_fix": fix,
                    })
                else:
                    checks.append({
                        "id": f"S4_{mount_point.replace('/', '_').replace('mnt_', '')}",
                        "category": "Storage Health",
                        "title": f"I/O Latency Test - {mount_point}",
                        "severity": "warn",
                        "evidence": f"Read test failed: {result.stderr.strip()}",
                        "why_it_matters": "Cannot test read performance",
                        "suggested_fix": "Check disk health and permissions",
                    })
            else:
                checks.append({
                    "id": f"S4_{mount_point.replace('/', '_').replace('mnt_', '')}",
                    "category": "Storage Health",
                    "title": f"I/O Latency Test - {mount_point}",
                    "severity": "warn",
                    "evidence": f"Write test failed: {result.stderr.strip()}",
                    "why_it_matters": "Cannot test write performance",
                    "suggested_fix": "Check disk health and write permissions",
                })
        
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_path)
            except OSError:
                pass
    
    except Exception as e:
        checks.append({
            "id": f"S4_{mount_point.replace('/', '_').replace('mnt_', '')}",
            "category": "Storage Health",
            "title": f"I/O Latency Test - {mount_point}",
            "severity": "warn",
            "evidence": f"I/O test error: {e}",
            "why_it_matters": "Cannot test I/O performance",
            "suggested_fix": "Check disk accessibility and permissions",
        })
    
    return checks
