"""Prometheus monitoring checks."""

import requests
from typing import Any, Dict, List, Optional


def run_checks(registry: Any, docker_client: Any) -> List[Dict[str, Any]]:
    """Run Prometheus monitoring checks."""
    checks = []
    
    # Get Prometheus URL from registry
    prometheus_url = None
    try:
        if hasattr(registry, 'get_service'):
            prometheus_service = registry.get_service("prometheus")
            if prometheus_service and hasattr(prometheus_service, 'url'):
                prometheus_url = prometheus_service.url
        
        # Fallback to environment variable
        if not prometheus_url:
            import os
            prometheus_url = os.getenv("PROMETHEUS_URL")
    except Exception:
        pass
    
    if not prometheus_url:
        checks.append({
            "id": "PT1",
            "category": "Prometheus Monitoring",
            "title": "Prometheus Targets",
            "severity": "info",
            "evidence": "Prometheus URL not configured in registry",
            "why_it_matters": "Cannot verify Prometheus monitoring targets",
            "suggested_fix": "Configure Prometheus URL: mediastack-doctor registry set prometheus --url http://prometheus:9090",
        })
        return checks
    
    # Check Prometheus targets
    checks.extend(_check_prometheus_targets(prometheus_url))
    
    return checks


def _check_prometheus_targets(prometheus_url: str) -> List[Dict[str, Any]]:
    """Check Prometheus targets for expected services."""
    checks = []
    
    try:
        # Get targets from Prometheus API
        targets_url = f"{prometheus_url.rstrip('/')}/api/v1/targets"
        response = requests.get(targets_url, timeout=10)
        
        if response.status_code != 200:
            checks.append({
                "id": "PT1",
                "category": "Prometheus Monitoring",
                "title": "Prometheus Targets",
                "severity": "warn",
                "evidence": f"Cannot access Prometheus API: HTTP {response.status_code}",
                "why_it_matters": "Cannot verify monitoring targets",
                "suggested_fix": "Check Prometheus server status and URL configuration",
            })
            return checks
        
        data = response.json()
        targets = data.get("data", {}).get("activeTargets", [])
        
        # Expected targets for media stack
        expected_targets = {
            "node_exporter": {
                "job": "node",
                "description": "Host system metrics",
                "required": True
            },
            "cadvisor": {
                "job": "cadvisor",
                "description": "Container metrics",
                "required": True
            },
            "cloudflared": {
                "job": "cloudflared",
                "description": "Cloudflared tunnel metrics",
                "required": False
            },
            "prometheus": {
                "job": "prometheus",
                "description": "Prometheus self-monitoring",
                "required": False
            }
        }
        
        # Check for each expected target
        found_targets = {}
        for target in targets:
            job_name = target.get("labels", {}).get("job", "")
            if job_name in expected_targets:
                found_targets[job_name] = target
        
        # Check each expected target
        for target_name, target_info in expected_targets.items():
            if target_name in found_targets:
                target = found_targets[target_name]
                health = target.get("health", "unknown")
                last_error = target.get("lastError", "")
                
                if health == "up":
                    severity = "info"
                    evidence = f"{target_info['description']} is healthy"
                    why = f"{target_info['description']} monitoring is working"
                    fix = None
                elif health == "down":
                    severity = "warn" if not target_info["required"] else "fail"
                    evidence = f"{target_info['description']} is down"
                    if last_error:
                        evidence += f": {last_error}"
                    why = f"{target_info['description']} monitoring is not working"
                    fix = f"Check {target_name} service status and Prometheus configuration"
                else:
                    severity = "warn"
                    evidence = f"{target_info['description']} health unknown"
                    why = f"{target_info['description']} monitoring status unclear"
                    fix = f"Check {target_name} service and Prometheus target configuration"
                
                checks.append({
                    "id": f"PT1_{target_name}",
                    "category": "Prometheus Monitoring",
                    "title": f"Prometheus Target - {target_info['description']}",
                    "severity": severity,
                    "evidence": evidence,
                    "why_it_matters": why,
                    "suggested_fix": fix,
                })
            else:
                if target_info["required"]:
                    severity = "warn"
                    evidence = f"{target_info['description']} target not found"
                    why = f"Missing required monitoring for {target_info['description']}"
                    fix = f"Configure {target_name} target in Prometheus"
                else:
                    severity = "info"
                    evidence = f"{target_info['description']} target not found (optional)"
                    why = f"Optional monitoring for {target_info['description']} not configured"
                    fix = None
                
                checks.append({
                    "id": f"PT1_{target_name}",
                    "category": "Prometheus Monitoring",
                    "title": f"Prometheus Target - {target_info['description']}",
                    "severity": severity,
                    "evidence": evidence,
                    "why_it_matters": why,
                    "suggested_fix": fix,
                })
        
        # Summary check
        up_targets = len([t for t in found_targets.values() if t.get("health") == "up"])
        total_targets = len(found_targets)
        
        if total_targets > 0:
            checks.append({
                "id": "PT1_SUMMARY",
                "category": "Prometheus Monitoring",
                "title": "Prometheus Targets Summary",
                "severity": "info",
                "evidence": f"{up_targets}/{total_targets} targets are healthy",
                "why_it_matters": "Prometheus monitoring health summary",
                "suggested_fix": None,
            })
    
    except requests.exceptions.ConnectionError:
        checks.append({
            "id": "PT1",
            "category": "Prometheus Monitoring",
            "title": "Prometheus Targets",
            "severity": "warn",
            "evidence": f"Cannot connect to Prometheus at {prometheus_url}",
            "why_it_matters": "Prometheus server is not reachable",
            "suggested_fix": "Check Prometheus server status and network connectivity",
        })
    except requests.exceptions.Timeout:
        checks.append({
            "id": "PT1",
            "category": "Prometheus Monitoring",
            "title": "Prometheus Targets",
            "severity": "warn",
            "evidence": f"Prometheus API timeout at {prometheus_url}",
            "why_it_matters": "Prometheus server is slow to respond",
            "suggested_fix": "Check Prometheus server performance and network latency",
        })
    except Exception as e:
        checks.append({
            "id": "PT1",
            "category": "Prometheus Monitoring",
            "title": "Prometheus Targets",
            "severity": "warn",
            "evidence": f"Error checking Prometheus targets: {e}",
            "why_it_matters": "Cannot verify monitoring configuration",
            "suggested_fix": "Check Prometheus configuration and API access",
        })
    
    return checks
