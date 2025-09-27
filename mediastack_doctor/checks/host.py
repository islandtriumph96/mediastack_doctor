"""Host system diagnostics."""

import os
import subprocess
import time
from typing import Any, Dict, List, Optional

import psutil


def run_checks(registry: Any, docker_client: Any = None, nic: Optional[str] = None, pcap_duration: Optional[int] = None, thresholds: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Run host system checks."""
    from ..utils.thresholds import DEFAULT_THRESHOLDS
    
    # Use provided thresholds or defaults
    if not thresholds:
        thresholds = DEFAULT_THRESHOLDS
    
    checks = []
    
    # CPU and Memory checks
    checks.extend(_check_cpu_memory(thresholds))
    
    # Disk checks
    checks.extend(_check_disks())
    
    # Network checks
    checks.extend(_check_network(nic))
    
    # System logs checks
    checks.extend(_check_system_logs())
    
    # Thermal checks
    checks.extend(_check_thermal(thresholds))
    
    # Packet capture analysis
    if pcap_duration and pcap_duration > 0:
        checks.extend(_check_network_traffic(nic, pcap_duration))
    
    return checks


def _check_cpu_memory(thresholds: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check CPU and memory usage."""
    checks = []
    
    # Get CPU thresholds
    cpu_warn = thresholds.get("cpu", {}).get("warn", 80.0)
    cpu_fail = thresholds.get("cpu", {}).get("fail", 90.0)
    
    # CPU usage
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count()
    
    if cpu_percent > cpu_fail:
        severity = "fail"
        evidence = f"CPU usage is {cpu_percent:.1f}% (exceeds FAIL threshold of {cpu_fail}%)"
        why = f"CPU usage {cpu_percent:.1f}% exceeds critical threshold of {cpu_fail}% - can cause system instability"
        fix = "Check for runaway processes, consider upgrading hardware, or optimize applications"
    elif cpu_percent > cpu_warn:
        severity = "warn"
        evidence = f"CPU usage is {cpu_percent:.1f}% (exceeds WARN threshold of {cpu_warn}%)"
        why = f"CPU usage {cpu_percent:.1f}% exceeds warning threshold of {cpu_warn}% - may impact performance"
        fix = "Monitor CPU usage and consider optimization"
    else:
        severity = "info"
        evidence = f"CPU usage is {cpu_percent:.1f}% (within normal range)"
        why = "CPU usage is within acceptable thresholds"
        fix = None
    
    checks.append({
        "id": "H1",
        "category": "Host & Filesystems",
        "title": "CPU Usage",
        "severity": severity,
        "evidence": evidence,
        "why_it_matters": why,
        "suggested_fix": fix,
    })
    
    # Memory usage
    memory = psutil.virtual_memory()
    memory_percent = memory.percent
    
    if memory_percent > 95:
        severity = "fail"
        evidence = f"Memory usage is {memory_percent:.1f}% ({memory.used / (1024**3):.1f}GB used)"
        why = "Critical memory usage can cause system crashes and data loss"
        fix = "Free up memory, close unnecessary applications, or add more RAM"
    elif memory_percent > 85:
        severity = "warn"
        evidence = f"Memory usage is {memory_percent:.1f}% ({memory.used / (1024**3):.1f}GB used)"
        why = "High memory usage may cause performance issues"
        fix = "Monitor memory usage and consider freeing up resources"
    else:
        severity = "info"
        evidence = f"Memory usage is {memory_percent:.1f}% ({memory.used / (1024**3):.1f}GB used)"
        why = "Memory usage is within normal range"
        fix = None
    
    checks.append({
        "id": "H2",
        "category": "Host & Filesystems",
        "title": "Memory Usage",
        "severity": severity,
        "evidence": evidence,
        "why_it_matters": why,
        "suggested_fix": fix,
    })
    
    # Swap usage
    swap = psutil.swap_memory()
    if swap.total > 0:
        swap_percent = swap.percent
        
        if swap_percent > 50:
            severity = "warn"
            evidence = f"Swap usage is {swap_percent:.1f}% ({swap.used / (1024**3):.1f}GB used)"
            why = "High swap usage indicates memory pressure and can cause performance degradation"
            fix = "Increase RAM or optimize memory usage"
        else:
            severity = "info"
            evidence = f"Swap usage is {swap_percent:.1f}% ({swap.used / (1024**3):.1f}GB used)"
            why = "Swap usage is within normal range"
            fix = None
        
        checks.append({
            "id": "H3",
            "category": "Host & Filesystems",
            "title": "Swap Usage",
            "severity": severity,
            "evidence": evidence,
            "why_it_matters": why,
            "suggested_fix": fix,
        })
    
    # Top processes
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            processes.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    # Sort by CPU usage
    processes.sort(key=lambda x: x['cpu_percent'] or 0, reverse=True)
    top_cpu = processes[:3]
    
    if any(p['cpu_percent'] and p['cpu_percent'] > 50 for p in top_cpu):
        severity = "warn"
        process_list = [f"{p['name']} ({p['cpu_percent']:.1f}%)" for p in top_cpu if p['cpu_percent']]
        evidence = f"High CPU processes: {', '.join(process_list)}"
        why = "High CPU processes may impact system performance"
        fix = "Investigate and optimize high CPU processes"
    else:
        severity = "info"
        process_list = [f"{p['name']} ({p['cpu_percent']:.1f}%)" for p in top_cpu if p['cpu_percent']]
        evidence = f"Top CPU processes: {', '.join(process_list)}"
        why = "CPU process usage is normal"
        fix = None
    
    checks.append({
        "id": "H4",
        "category": "Host & Filesystems",
        "title": "Top CPU Processes",
        "severity": severity,
        "evidence": evidence,
        "why_it_matters": why,
        "suggested_fix": fix,
    })
    
    return checks


def _check_disks() -> List[Dict[str, Any]]:
    """Check disk usage and health."""
    checks = []
    
    # Check specific media mount points
    media_mounts = ["/mnt/PLEX22TB", "/mnt/GDRIVE36"]
    
    for mount_point in media_mounts:
        if os.path.exists(mount_point):
            try:
                usage = psutil.disk_usage(mount_point)
                percent_used = (usage.used / usage.total) * 100
                
                if percent_used > 95:
                    severity = "fail"
                    evidence = f"{mount_point} is {percent_used:.1f}% full ({usage.free / (1024**3):.1f}GB free)"
                    why = "Critical disk space can cause service failures and data loss"
                    fix = f"Free up space on {mount_point} or add more storage"
                elif percent_used > 85:
                    severity = "warn"
                    evidence = f"{mount_point} is {percent_used:.1f}% full ({usage.free / (1024**3):.1f}GB free)"
                    why = "Low disk space may cause issues with media operations"
                    fix = f"Monitor and clean up {mount_point} regularly"
                else:
                    severity = "info"
                    evidence = f"{mount_point} is {percent_used:.1f}% full ({usage.free / (1024**3):.1f}GB free)"
                    why = "Disk space is adequate"
                    fix = None
                
                checks.append({
                    "id": f"H5_{mount_point.replace('/', '_').replace('mnt_', '')}",
                    "category": "Host & Filesystems",
                    "title": f"Disk Usage - {mount_point}",
                    "severity": severity,
                    "evidence": evidence,
                    "why_it_matters": why,
                    "suggested_fix": fix,
                })
                
                # Check if mount is read-write
                if os.access(mount_point, os.W_OK):
                    checks.append({
                        "id": f"H6_{mount_point.replace('/', '_').replace('mnt_', '')}_rw",
                        "category": "Host & Filesystems",
                        "title": f"Mount Write Access - {mount_point}",
                        "severity": "info",
                        "evidence": f"{mount_point} is writable",
                        "why_it_matters": "Write access is required for media operations",
                        "suggested_fix": None,
                    })
                else:
                    checks.append({
                        "id": f"H6_{mount_point.replace('/', '_').replace('mnt_', '')}_ro",
                        "category": "Host & Filesystems",
                        "title": f"Mount Write Access - {mount_point}",
                        "severity": "fail",
                        "evidence": f"{mount_point} is read-only",
                        "why_it_matters": "Read-only mount prevents media operations",
                        "suggested_fix": f"Check mount options and permissions for {mount_point}",
                    })
                
            except OSError as e:
                checks.append({
                    "id": f"H7_{mount_point.replace('/', '_').replace('mnt_', '')}_error",
                    "category": "Host & Filesystems",
                    "title": f"Disk Access - {mount_point}",
                    "severity": "fail",
                    "evidence": f"Cannot access {mount_point}: {e}",
                    "why_it_matters": "Cannot access media storage",
                    "suggested_fix": f"Check mount status and permissions for {mount_point}",
                })
        else:
            checks.append({
                "id": f"H8_{mount_point.replace('/', '_').replace('mnt_', '')}_missing",
                "category": "Host & Filesystems",
                "title": f"Mount Point - {mount_point}",
                "severity": "warn",
                "evidence": f"Mount point {mount_point} does not exist",
                "why_it_matters": "Expected media mount point is missing",
                "suggested_fix": f"Check if {mount_point} should be mounted",
            })
    
    # Check root filesystem
    try:
        root_usage = psutil.disk_usage("/")
        root_percent = (root_usage.used / root_usage.total) * 100
        
        if root_percent > 95:
            severity = "fail"
            evidence = f"Root filesystem is {root_percent:.1f}% full ({root_usage.free / (1024**3):.1f}GB free)"
            why = "Critical root filesystem space can cause system instability"
            fix = "Free up space on root filesystem immediately"
        elif root_percent > 85:
            severity = "warn"
            evidence = f"Root filesystem is {root_percent:.1f}% full ({root_usage.free / (1024**3):.1f}GB free)"
            why = "Low root filesystem space may cause issues"
            fix = "Clean up root filesystem and consider expanding storage"
        else:
            severity = "info"
            evidence = f"Root filesystem is {root_percent:.1f}% full ({root_usage.free / (1024**3):.1f}GB free)"
            why = "Root filesystem space is adequate"
            fix = None
        
        checks.append({
            "id": "H9",
            "category": "Host & Filesystems",
            "title": "Root Filesystem Usage",
            "severity": severity,
            "evidence": evidence,
            "why_it_matters": why,
            "suggested_fix": fix,
        })
    except OSError:
        pass
    
    return checks


def _check_network(nic: Optional[str] = None) -> List[Dict[str, Any]]:
    """Check network interfaces and connectivity."""
    checks = []
    
    # Get network interfaces
    interfaces = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    
    # Find the primary interface
    primary_interface = None
    if nic:
        primary_interface = nic
    else:
        # Try to find the most active interface
        for interface, addrs in interfaces.items():
            if interface.startswith(('eth', 'en', 'wlan', 'wl')):
                if interface in stats and stats[interface].isup:
                    primary_interface = interface
                    break
    
    if primary_interface and primary_interface in interfaces:
        interface_stats = stats.get(primary_interface)
        if interface_stats:
            if interface_stats.isup:
                checks.append({
                    "id": "H10",
                    "category": "Host & Filesystems",
                    "title": f"Network Interface - {primary_interface}",
                    "severity": "info",
                    "evidence": f"{primary_interface} is up with speed {interface_stats.speed}Mbps",
                    "why_it_matters": "Network interface is operational",
                    "suggested_fix": None,
                })
            else:
                checks.append({
                    "id": "H11",
                    "category": "Host & Filesystems",
                    "title": f"Network Interface - {primary_interface}",
                    "severity": "fail",
                    "evidence": f"{primary_interface} is down",
                    "why_it_matters": "Network interface is not operational",
                    "suggested_fix": f"Check network cable and interface configuration for {primary_interface}",
                })
    
    # Check network connections
    try:
        connections = psutil.net_connections()
        established = len([c for c in connections if c.status == 'ESTABLISHED'])
        
        if established > 1000:
            severity = "warn"
            evidence = f"High number of established connections: {established}"
            why = "High connection count may indicate network issues or resource exhaustion"
            fix = "Monitor network connections and check for connection leaks"
        else:
            severity = "info"
            evidence = f"Established connections: {established}"
            why = "Connection count is within normal range"
            fix = None
        
        checks.append({
            "id": "H12",
            "category": "Host & Filesystems",
            "title": "Network Connections",
            "severity": severity,
            "evidence": evidence,
            "why_it_matters": why,
            "suggested_fix": fix,
        })
    except (psutil.AccessDenied, OSError):
        pass
    
    return checks


def _check_system_logs() -> List[Dict[str, Any]]:
    """Check system logs for errors."""
    checks = []
    
    # Check for common error patterns in journalctl
    try:
        result = subprocess.run(
            ["journalctl", "-k", "-S", "24 hours ago", "--no-pager", "-p", "err"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0 and result.stdout.strip():
            error_count = len(result.stdout.strip().split('\n'))
            
            # Look for specific error patterns
            error_patterns = {
                "i915": "GPU driver issues",
                "thermal": "Thermal throttling",
                "power": "Power management issues",
                "memory": "Memory errors",
                "disk": "Disk I/O errors",
            }
            
            found_errors = []
            for pattern, description in error_patterns.items():
                if pattern in result.stdout.lower():
                    found_errors.append(description)
            
            if found_errors:
                severity = "warn"
                evidence = f"Found {error_count} kernel errors in last 24h: {', '.join(found_errors)}"
                why = "Kernel errors may indicate hardware or driver issues"
                fix = "Check hardware health and update drivers if needed"
            else:
                severity = "info"
                evidence = f"Found {error_count} kernel errors in last 24h (no critical patterns)"
                why = "Some kernel errors are normal, but should be monitored"
                fix = "Monitor system logs for recurring issues"
            
            checks.append({
                "id": "H13",
                "category": "Host & Filesystems",
                "title": "System Log Errors",
                "severity": severity,
                "evidence": evidence,
                "why_it_matters": why,
                "suggested_fix": fix,
            })
        else:
            checks.append({
                "id": "H14",
                "category": "Host & Filesystems",
                "title": "System Log Errors",
                "severity": "info",
                "evidence": "No kernel errors found in last 24 hours",
                "why_it_matters": "System is running without critical errors",
                "suggested_fix": None,
            })
    
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        checks.append({
            "id": "H15",
            "category": "Host & Filesystems",
            "title": "System Log Errors",
            "severity": "warn",
            "evidence": "Cannot access system logs (journalctl not available)",
            "why_it_matters": "Cannot monitor system health through logs",
            "suggested_fix": "Install systemd or check log access permissions",
        })
    
    return checks


def _check_thermal(thresholds: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check thermal sensors if available."""
    checks = []
    
    # Check thermal zones
    thermal_zones = []
    try:
        thermal_path = "/sys/class/thermal"
        if os.path.exists(thermal_path):
            for zone in os.listdir(thermal_path):
                if zone.startswith("thermal_zone"):
                    zone_path = os.path.join(thermal_path, zone)
                    type_path = os.path.join(zone_path, "type")
                    temp_path = os.path.join(zone_path, "temp")
                    
                    if os.path.exists(type_path) and os.path.exists(temp_path):
                        try:
                            with open(type_path, "r") as f:
                                zone_type = f.read().strip()
                            with open(temp_path, "r") as f:
                                temp_millicelsius = int(f.read().strip())
                                temp_celsius = temp_millicelsius / 1000
                            
                            thermal_zones.append({
                                "type": zone_type,
                                "temperature": temp_celsius
                            })
                        except (OSError, ValueError):
                            continue
    except OSError:
        pass
    
    if thermal_zones:
        # Get temperature thresholds
        temp_warn = thresholds.get("temp_c", {}).get("warn", 85.0)
        temp_fail = thresholds.get("temp_c", {}).get("fail", 92.0)
        
        max_temp = max(zone["temperature"] for zone in thermal_zones)
        hot_zones = [zone for zone in thermal_zones if zone["temperature"] > temp_warn]
        
        if max_temp > temp_fail:
            severity = "fail"
            evidence = f"Critical temperature: {max_temp:.1f}°C (exceeds FAIL threshold of {temp_fail}°C)"
            why = f"Temperature {max_temp:.1f}°C exceeds critical threshold of {temp_fail}°C - risk of thermal throttling and hardware damage"
            fix = "Immediate cooling required: check fans, clean dust, improve ventilation"
        elif max_temp > temp_warn:
            severity = "warn"
            evidence = f"Elevated temperature: {max_temp:.1f}°C (exceeds WARN threshold of {temp_warn}°C)"
            why = f"Temperature {max_temp:.1f}°C exceeds warning threshold of {temp_warn}°C - may cause performance issues"
            fix = "Monitor temperatures and ensure adequate cooling"
        else:
            severity = "info"
            evidence = f"Temperature normal: {max_temp:.1f}°C (within acceptable range)"
            why = "Temperatures are within safe operating thresholds"
            fix = None
        
        checks.append({
            "id": "H16",
            "category": "Host & Filesystems",
            "title": "Thermal Status",
            "severity": severity,
            "evidence": evidence,
            "why_it_matters": why,
            "suggested_fix": fix,
        })
    else:
        checks.append({
            "id": "H17",
            "category": "Host & Filesystems",
            "title": "Thermal Status",
            "severity": "info",
            "evidence": "No thermal sensors available",
            "why_it_matters": "Cannot monitor system temperature",
            "suggested_fix": "Thermal monitoring not available on this system",
        })
    
    return checks


def _check_network_traffic(nic: Optional[str], duration: int) -> List[Dict[str, Any]]:
    """Check network traffic using packet capture."""
    checks = []
    
    from ..utils.pcap import capture_top_talkers
    
    # Capture network traffic
    result = capture_top_talkers(duration=duration, interface=nic)
    
    if not result["available"]:
        checks.append({
            "id": "H18",
            "category": "Host & Filesystems",
            "title": "Network Traffic Analysis",
            "severity": "info",
            "evidence": result["reason"],
            "why_it_matters": "Cannot analyze network traffic without tcpdump",
            "suggested_fix": "Install tcpdump: sudo apt install tcpdump",
        })
        return checks
    
    # Analyze top flows
    top_flows = result["top_flows"]
    
    if not top_flows:
        checks.append({
            "id": "H19",
            "category": "Host & Filesystems",
            "title": "Network Traffic Analysis",
            "severity": "info",
            "evidence": f"No significant traffic flows detected on {result['interface']}",
            "why_it_matters": "Network appears to be idle or traffic is minimal",
            "suggested_fix": None,
        })
        return checks
    
    # Create summary of top flows
    flow_summary = []
    total_bytes = 0
    
    for flow in top_flows:
        flow_summary.append(f"{flow['src']} ↔ {flow['dst']} ({flow['bytes']} bytes)")
        total_bytes += flow["bytes"]
    
    # Determine severity based on traffic patterns
    if total_bytes > 100 * 1024 * 1024:  # 100MB
        severity = "info"
        why = "High network activity detected"
        fix = "Monitor for unusual traffic patterns"
    elif total_bytes > 10 * 1024 * 1024:  # 10MB
        severity = "info"
        why = "Moderate network activity"
        fix = None
    else:
        severity = "info"
        why = "Low network activity"
        fix = None
    
    checks.append({
        "id": "H20",
        "category": "Host & Filesystems",
        "title": "Network Traffic Analysis",
        "severity": severity,
        "evidence": f"Top flows on {result['interface']}: {'; '.join(flow_summary[:3])}",
        "why_it_matters": why,
        "suggested_fix": fix,
    })
    
    # Check for suspicious traffic patterns
    suspicious_flows = []
    for flow in top_flows:
        # Check for external traffic to high ports
        if any(port in flow["src"] or port in flow["dst"] for port in [":22", ":3389", ":5900"]):
            suspicious_flows.append(f"{flow['src']} ↔ {flow['dst']}")
    
    if suspicious_flows:
        checks.append({
            "id": "H21",
            "category": "Host & Filesystems",
            "title": "Suspicious Network Traffic",
            "severity": "warn",
            "evidence": f"Traffic to admin ports detected: {'; '.join(suspicious_flows)}",
            "why_it_matters": "Traffic to administrative ports may indicate security concerns",
            "suggested_fix": "Review firewall rules and ensure only authorized access to admin ports",
        })
    
    return checks
