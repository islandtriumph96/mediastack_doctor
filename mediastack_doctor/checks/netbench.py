"""Network benchmarking and throughput tests."""

import json
import subprocess
import time
from typing import Any, Dict, List, Optional


def run_checks(registry: Any, docker_client: Any, netbench_mode: str = "quick") -> List[Dict[str, Any]]:
    """Run network benchmarking checks."""
    checks = []
    
    if netbench_mode == "skip":
        return checks
    
    # WAN speed test (NB1)
    checks.extend(_check_wan_speedtest(netbench_mode))
    
    # LAN iperf3 test (NB2)
    checks.extend(_check_lan_iperf3(registry, netbench_mode))
    
    return checks


def _check_wan_speedtest(mode: str) -> List[Dict[str, Any]]:
    """Check WAN speed using speedtest-cli (NB1)."""
    checks = []
    
    # Check if speedtest-cli is available
    try:
        result = subprocess.run(
            ["speedtest-cli", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            checks.append({
                "id": "NB1",
                "category": "Network Benchmarking",
                "title": "WAN Speed Test",
                "severity": "info",
                "evidence": "speedtest-cli not available",
                "why_it_matters": "Cannot measure WAN throughput without speedtest-cli",
                "suggested_fix": "Install speedtest-cli: sudo apt install speedtest-cli",
            })
            return checks
    except (subprocess.TimeoutExpired, FileNotFoundError):
        checks.append({
            "id": "NB1",
            "category": "Network Benchmarking",
                "title": "WAN Speed Test",
            "severity": "info",
            "evidence": "speedtest-cli not available",
            "why_it_matters": "Cannot measure WAN throughput without speedtest-cli",
            "suggested_fix": "Install speedtest-cli: sudo apt install speedtest-cli",
        })
        return checks
    
    # Run speed test
    try:
        timeout = 30 if mode == "quick" else 60
        result = subprocess.run(
            ["speedtest-cli", "--json", "--simple"],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode == 0:
            # Parse JSON output
            try:
                data = json.loads(result.stdout)
                download = data.get("download", 0) / 1000000  # Convert to Mbps
                upload = data.get("upload", 0) / 1000000
                ping = data.get("ping", 0)
                
                # Determine severity based on speeds
                if download < 10 or upload < 1:
                    severity = "warn"
                    why = "Low WAN speeds may impact media streaming and downloads"
                    fix = "Check internet connection and consider upgrading plan"
                elif download < 50 or upload < 5:
                    severity = "info"
                    why = "Moderate WAN speeds should be adequate for most media operations"
                    fix = None
                else:
                    severity = "info"
                    why = "Good WAN speeds support high-quality streaming and fast downloads"
                    fix = None
                
                checks.append({
                    "id": "NB1",
                    "category": "Network Benchmarking",
                    "title": "WAN Speed Test",
                    "severity": severity,
                    "evidence": f"Download: {download:.1f} Mbps, Upload: {upload:.1f} Mbps, Ping: {ping:.1f} ms",
                    "why_it_matters": why,
                    "suggested_fix": fix,
                })
                
            except json.JSONDecodeError:
                # Fallback to simple output parsing
                lines = result.stdout.strip().split('\n')
                download = upload = ping = 0
                
                for line in lines:
                    if 'Download:' in line:
                        try:
                            download = float(line.split()[1])
                        except (IndexError, ValueError):
                            pass
                    elif 'Upload:' in line:
                        try:
                            upload = float(line.split()[1])
                        except (IndexError, ValueError):
                            pass
                    elif 'Ping:' in line:
                        try:
                            ping = float(line.split()[1])
                        except (IndexError, ValueError):
                            pass
                
                if download > 0 or upload > 0:
                    checks.append({
                        "id": "NB1",
                        "category": "Network Benchmarking",
                        "title": "WAN Speed Test",
                        "severity": "info",
                        "evidence": f"Download: {download:.1f} Mbps, Upload: {upload:.1f} Mbps, Ping: {ping:.1f} ms",
                        "why_it_matters": "WAN throughput measured successfully",
                        "suggested_fix": None,
                    })
                else:
                    checks.append({
                        "id": "NB1",
                        "category": "Network Benchmarking",
                        "title": "WAN Speed Test",
                        "severity": "warn",
                        "evidence": "Speed test completed but results unclear",
                        "why_it_matters": "Cannot determine WAN performance",
                        "suggested_fix": "Check internet connection and try again",
                    })
        
        else:
            checks.append({
                "id": "NB1",
                "category": "Network Benchmarking",
                "title": "WAN Speed Test",
                "severity": "warn",
                "evidence": f"Speed test failed: {result.stderr.strip()}",
                "why_it_matters": "Cannot measure WAN performance",
                "suggested_fix": "Check internet connection and speedtest-cli configuration",
            })
    
    except subprocess.TimeoutExpired:
        checks.append({
            "id": "NB1",
            "category": "Network Benchmarking",
            "title": "WAN Speed Test",
            "severity": "warn",
            "evidence": "Speed test timed out",
            "why_it_matters": "WAN test took too long, may indicate connection issues",
            "suggested_fix": "Check internet connection stability",
        })
    except Exception as e:
        checks.append({
            "id": "NB1",
            "category": "Network Benchmarking",
            "title": "WAN Speed Test",
            "severity": "warn",
            "evidence": f"Speed test error: {e}",
            "why_it_matters": "Cannot measure WAN performance",
            "suggested_fix": "Check speedtest-cli installation and internet connection",
        })
    
    return checks


def _check_lan_iperf3(registry: Any, mode: str) -> List[Dict[str, Any]]:
    """Check LAN speed using iperf3 (NB2)."""
    checks = []
    
    # Check if iperf3 is available
    try:
        result = subprocess.run(
            ["iperf3", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            checks.append({
                "id": "NB2",
                "category": "Network Benchmarking",
                "title": "LAN Speed Test",
                "severity": "info",
                "evidence": "iperf3 not available",
                "why_it_matters": "Cannot measure LAN throughput without iperf3",
                "suggested_fix": "Install iperf3: sudo apt install iperf3",
            })
            return checks
    except (subprocess.TimeoutExpired, FileNotFoundError):
        checks.append({
            "id": "NB2",
            "category": "Network Benchmarking",
            "title": "LAN Speed Test",
            "severity": "info",
            "evidence": "iperf3 not available",
            "why_it_matters": "Cannot measure LAN throughput without iperf3",
            "suggested_fix": "Install iperf3: sudo apt install iperf3",
        })
        return checks
    
    # Get iperf3 server from registry
    iperf_host = None
    try:
        # Try to get from registry
        if hasattr(registry, 'get_service'):
            net_service = registry.get_service("net")
            if net_service and hasattr(net_service, 'iperf_host'):
                iperf_host = net_service.iperf_host
        
        # Fallback to environment or common defaults
        if not iperf_host:
            import os
            iperf_host = os.getenv("IPERF_HOST", "192.168.1.1")  # Common router IP
    except Exception:
        iperf_host = "192.168.1.1"
    
    # Test iperf3 server connectivity first
    try:
        result = subprocess.run(
            ["iperf3", "-c", iperf_host, "-t", "1", "-J"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            # Parse JSON output
            try:
                data = json.loads(result.stdout)
                end_data = data.get("end", {})
                sum_sent = end_data.get("sum_sent", {})
                sum_received = end_data.get("sum_received", {})
                
                send_bps = sum_sent.get("bits_per_second", 0) / 1000000  # Convert to Mbps
                recv_bps = sum_received.get("bits_per_second", 0) / 1000000
                
                # Determine severity based on LAN speeds
                if send_bps < 100 or recv_bps < 100:
                    severity = "warn"
                    why = "Low LAN speeds may impact local media streaming and file transfers"
                    fix = "Check network cables, switch/router performance, and WiFi signal strength"
                elif send_bps < 500 or recv_bps < 500:
                    severity = "info"
                    why = "Moderate LAN speeds should be adequate for most local operations"
                    fix = None
                else:
                    severity = "info"
                    why = "Good LAN speeds support high-quality local streaming and fast transfers"
                    fix = None
                
                checks.append({
                    "id": "NB2",
                    "category": "Network Benchmarking",
                    "title": "LAN Speed Test",
                    "severity": severity,
                    "evidence": f"Send: {send_bps:.1f} Mbps, Receive: {recv_bps:.1f} Mbps (to {iperf_host})",
                    "why_it_matters": why,
                    "suggested_fix": fix,
                })
                
            except json.JSONDecodeError:
                checks.append({
                    "id": "NB2",
                    "category": "Network Benchmarking",
                    "title": "LAN Speed Test",
                    "severity": "warn",
                    "evidence": f"iperf3 test completed but results unclear (to {iperf_host})",
                    "why_it_matters": "Cannot determine LAN performance",
                    "suggested_fix": "Check iperf3 server configuration and network connectivity",
                })
        
        else:
            checks.append({
                "id": "NB2",
                "category": "Network Benchmarking",
                "title": "LAN Speed Test",
                "severity": "warn",
                "evidence": f"iperf3 server not reachable at {iperf_host}",
                "why_it_matters": "Cannot measure LAN performance without iperf3 server",
                "suggested_fix": f"Configure iperf3 server at {iperf_host} or set IPERF_HOST environment variable",
            })
    
    except subprocess.TimeoutExpired:
        checks.append({
            "id": "NB2",
            "category": "Network Benchmarking",
            "title": "LAN Speed Test",
            "severity": "warn",
            "evidence": f"iperf3 test timed out (to {iperf_host})",
            "why_it_matters": "LAN test took too long, may indicate network issues",
            "suggested_fix": "Check network connectivity and iperf3 server status",
        })
    except Exception as e:
        checks.append({
            "id": "NB2",
            "category": "Network Benchmarking",
            "title": "LAN Speed Test",
            "severity": "warn",
            "evidence": f"iperf3 test error: {e}",
            "why_it_matters": "Cannot measure LAN performance",
            "suggested_fix": "Check iperf3 installation and network configuration",
        })
    
    return checks
