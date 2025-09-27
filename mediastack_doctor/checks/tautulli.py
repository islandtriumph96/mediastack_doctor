"""Tautulli integration checks."""

import requests
from typing import Any, Dict, List, Optional


def run_checks(registry: Any, docker_client: Any) -> List[Dict[str, Any]]:
    """Run Tautulli checks."""
    checks = []
    
    # Get Tautulli info
    tautulli_info = _get_tautulli_info(registry, docker_client)
    
    if not tautulli_info:
        checks.append({
            "id": "T1",
            "category": "Tautulli",
            "title": "Tautulli Service",
            "severity": "info",
            "evidence": "Tautulli not configured in registry",
            "why_it_matters": "Tautulli provides detailed Plex analytics and monitoring",
            "suggested_fix": "Configure Tautulli: mediastack-doctor registry set tautulli --url http://tautulli:8181 --api-key-secret-ref tautulli_apikey",
        })
        return checks
    
    # API connectivity
    checks.extend(_check_tautulli_api(tautulli_info))
    
    # Transcode analysis
    checks.extend(_check_transcode_activity(tautulli_info))
    
    # Stream analysis
    checks.extend(_check_stream_analysis(tautulli_info))
    
    return checks


def _get_tautulli_info(registry: Any, docker_client: Any) -> Optional[Dict[str, Any]]:
    """Get Tautulli connection information."""
    # Try registry first
    try:
        if hasattr(registry, 'get_service'):
            tautulli_service = registry.get_service("tautulli")
            if tautulli_service:
                return {
                    "url": tautulli_service.url,
                    "api_key": registry.get_secret(tautulli_service.api_key_secret_ref) if tautulli_service.api_key_secret_ref else None,
                    "container": None,  # Will be filled by Docker discovery
                }
    except Exception:
        pass
    
    # Try Docker discovery
    try:
        containers = docker_client.list_containers()
        for container in containers:
            if "tautulli" in container["name"].lower():
                # Get container network info
                network_info = docker_client.get_container_network_info(container["name"])
                if network_info:
                    networks = network_info.get("networks", {})
                    for network_name, network_details in networks.items():
                        ip_address = network_details.get("IPAddress", "")
                        if ip_address:
                            return {
                                "url": f"http://{ip_address}:8181",
                                "api_key": None,  # Will need to be configured
                                "container": container,
                            }
    except Exception:
        pass
    
    return None


def _check_tautulli_api(tautulli_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check Tautulli API connectivity."""
    checks = []
    
    url = tautulli_info["url"]
    api_key = tautulli_info.get("api_key")
    
    if not api_key:
        checks.append({
            "id": "T1",
            "category": "Tautulli",
            "title": "Tautulli API Key",
            "severity": "warn",
            "evidence": "Tautulli API key not configured",
            "why_it_matters": "Cannot access Tautulli analytics without API key",
            "suggested_fix": "Configure Tautulli API key: mediastack-doctor registry secret set tautulli_apikey",
        })
        return checks
    
    try:
        # Test API connectivity
        params = {
            "apikey": api_key,
            "cmd": "get_server_info"
        }
        
        response = requests.get(f"{url}/api/v2", params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("response", {}).get("result") == "success":
                server_info = data.get("response", {}).get("data", {})
                server_name = server_info.get("server_name", "Unknown")
                server_version = server_info.get("version", "Unknown")
                
                checks.append({
                    "id": "T1",
                    "category": "Tautulli",
                    "title": "Tautulli API Connectivity",
                    "severity": "info",
                    "evidence": f"Connected to {server_name} (v{server_version})",
                    "why_it_matters": "Tautulli API is accessible and working",
                    "suggested_fix": None,
                })
            else:
                checks.append({
                    "id": "T1",
                    "category": "Tautulli",
                    "title": "Tautulli API Connectivity",
                    "severity": "warn",
                    "evidence": f"API error: {data.get('response', {}).get('message', 'Unknown error')}",
                    "why_it_matters": "Tautulli API returned an error",
                    "suggested_fix": "Check Tautulli API key and server configuration",
                })
        else:
            checks.append({
                "id": "T1",
                "category": "Tautulli",
                "title": "Tautulli API Connectivity",
                "severity": "warn",
                "evidence": f"HTTP {response.status_code} from Tautulli API",
                "why_it_matters": "Cannot access Tautulli API",
                "suggested_fix": "Check Tautulli server status and URL configuration",
            })
    
    except requests.exceptions.ConnectionError:
        checks.append({
            "id": "T1",
            "category": "Tautulli",
            "title": "Tautulli API Connectivity",
            "severity": "warn",
            "evidence": f"Cannot connect to Tautulli at {url}",
            "why_it_matters": "Tautulli server is not reachable",
            "suggested_fix": "Check Tautulli container status and network configuration",
        })
    except requests.exceptions.Timeout:
        checks.append({
            "id": "T1",
            "category": "Tautulli",
            "title": "Tautulli API Connectivity",
            "severity": "warn",
            "evidence": f"Tautulli API timeout at {url}",
            "why_it_matters": "Tautulli server is slow to respond",
            "suggested_fix": "Check Tautulli server performance and network latency",
        })
    except Exception as e:
        checks.append({
            "id": "T1",
            "category": "Tautulli",
            "title": "Tautulli API Connectivity",
            "severity": "warn",
            "evidence": f"Error accessing Tautulli API: {e}",
            "why_it_matters": "Cannot verify Tautulli connectivity",
            "suggested_fix": "Check Tautulli configuration and API access",
        })
    
    return checks


def _check_transcode_activity(tautulli_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check transcode activity and performance."""
    checks = []
    
    url = tautulli_info["url"]
    api_key = tautulli_info.get("api_key")
    
    if not api_key:
        return checks
    
    try:
        # Get transcode statistics for last 24 hours
        params = {
            "apikey": api_key,
            "cmd": "get_history",
            "length": 100,  # Get last 100 sessions
            "time_range": 1  # Last 24 hours
        }
        
        response = requests.get(f"{url}/api/v2", params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("response", {}).get("result") == "success":
                history = data.get("response", {}).get("data", {}).get("data", [])
                
                # Analyze transcode activity
                transcode_sessions = []
                total_sessions = len(history)
                
                for session in history:
                    if session.get("transcode_decision") == "transcode":
                        transcode_sessions.append(session)
                
                transcode_count = len(transcode_sessions)
                transcode_percentage = (transcode_count / total_sessions * 100) if total_sessions > 0 else 0
                
                # Check for sustained transcoding
                if transcode_count > 10:  # More than 10 transcodes in 24h
                    severity = "warn"
                    evidence = f"High transcode activity: {transcode_count} transcodes in 24h ({transcode_percentage:.1f}% of sessions)"
                    why = "High transcode activity may indicate missing hardware acceleration or inefficient settings"
                    fix = "Consider enabling hardware transcoding or optimizing media formats"
                elif transcode_count > 5:
                    severity = "info"
                    evidence = f"Moderate transcode activity: {transcode_count} transcodes in 24h ({transcode_percentage:.1f}% of sessions)"
                    why = "Some transcoding is normal, but monitor for optimization opportunities"
                    fix = None
                else:
                    severity = "info"
                    evidence = f"Low transcode activity: {transcode_count} transcodes in 24h ({transcode_percentage:.1f}% of sessions)"
                    why = "Low transcode activity indicates good media format compatibility"
                    fix = None
                
                checks.append({
                    "id": "T2",
                    "category": "Tautulli",
                    "title": "Transcode Activity Analysis",
                    "severity": severity,
                    "evidence": evidence,
                    "why_it_matters": why,
                    "suggested_fix": fix,
                })
                
                # Check for hardware acceleration usage
                hw_transcode_count = 0
                for session in transcode_sessions:
                    if session.get("transcode_hw_decoding") or session.get("transcode_hw_encoding"):
                        hw_transcode_count += 1
                
                if transcode_count > 0:
                    hw_percentage = (hw_transcode_count / transcode_count * 100)
                    
                    if hw_percentage < 50 and transcode_count > 5:
                        checks.append({
                            "id": "T3",
                            "category": "Tautulli",
                            "title": "Hardware Acceleration Usage",
                            "severity": "warn",
                            "evidence": f"Only {hw_percentage:.1f}% of transcodes used hardware acceleration",
                            "why_it_matters": "Low hardware acceleration usage may cause high CPU usage",
                            "suggested_fix": "Enable hardware transcoding in Plex settings and ensure GPU access",
                        })
                    else:
                        checks.append({
                            "id": "T3",
                            "category": "Tautulli",
                            "title": "Hardware Acceleration Usage",
                            "severity": "info",
                            "evidence": f"{hw_percentage:.1f}% of transcodes used hardware acceleration",
                            "why_it_matters": "Hardware acceleration is being utilized effectively",
                            "suggested_fix": None,
                        })
    
    except Exception as e:
        checks.append({
            "id": "T2",
            "category": "Tautulli",
            "title": "Transcode Activity Analysis",
            "severity": "warn",
            "evidence": f"Error analyzing transcode activity: {e}",
            "why_it_matters": "Cannot analyze transcode performance",
            "suggested_fix": "Check Tautulli API access and data availability",
        })
    
    return checks


def _check_stream_analysis(tautulli_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check stream analysis and bandwidth usage."""
    checks = []
    
    url = tautulli_info["url"]
    api_key = tautulli_info.get("api_key")
    
    if not api_key:
        return checks
    
    try:
        # Get current activity
        params = {
            "apikey": api_key,
            "cmd": "get_activity"
        }
        
        response = requests.get(f"{url}/api/v2", params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("response", {}).get("result") == "success":
                sessions = data.get("response", {}).get("data", {}).get("sessions", [])
                
                if sessions:
                    # Analyze current streams
                    total_bandwidth = 0
                    transcoding_streams = 0
                    
                    for session in sessions:
                        bandwidth = session.get("bandwidth", 0)
                        total_bandwidth += bandwidth
                        
                        if session.get("transcode_decision") == "transcode":
                            transcoding_streams += 1
                    
                    # Convert to Mbps
                    total_bandwidth_mbps = total_bandwidth / 1000000
                    
                    checks.append({
                        "id": "T4",
                        "category": "Tautulli",
                        "title": "Current Stream Analysis",
                        "severity": "info",
                        "evidence": f"{len(sessions)} active streams, {total_bandwidth_mbps:.1f} Mbps total, {transcoding_streams} transcoding",
                        "why_it_matters": "Current streaming activity and bandwidth usage",
                        "suggested_fix": None,
                    })
                    
                    # Check for high bandwidth usage
                    if total_bandwidth_mbps > 100:  # 100 Mbps
                        checks.append({
                            "id": "T5",
                            "category": "Tautulli",
                            "title": "High Bandwidth Usage",
                            "severity": "warn",
                            "evidence": f"High bandwidth usage: {total_bandwidth_mbps:.1f} Mbps",
                            "why_it_matters": "High bandwidth usage may impact network performance",
                            "suggested_fix": "Consider bandwidth limits or quality settings optimization",
                        })
                else:
                    checks.append({
                        "id": "T4",
                        "category": "Tautulli",
                        "title": "Current Stream Analysis",
                        "severity": "info",
                        "evidence": "No active streams",
                        "why_it_matters": "No current streaming activity",
                        "suggested_fix": None,
                    })
    
    except Exception as e:
        checks.append({
            "id": "T4",
            "category": "Tautulli",
            "title": "Stream Analysis",
            "severity": "warn",
            "evidence": f"Error analyzing streams: {e}",
            "why_it_matters": "Cannot analyze current streaming activity",
            "suggested_fix": "Check Tautulli API access and data availability",
        })
    
    return checks
