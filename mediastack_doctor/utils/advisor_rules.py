"""Advisor rules with evidence-first logic and anti-spam rules."""

import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass


# Remove old Thresholds class - now using dict-based thresholds from utils.thresholds


@dataclass
class ContainerEvidence:
    """Evidence collected from container inspection."""
    name: str
    status: str
    health_status: Optional[str]
    restart_count: int
    exit_code: Optional[int]
    started_at: Optional[str]
    ports: List[str]
    networks: List[str]
    volumes: List[str]
    log_errors: List[str]


class AdvisorRules:
    """Evidence-based advisor rules with anti-spam logic."""
    
    def __init__(self, thresholds: Optional[Dict[str, Any]] = None):
        from .thresholds import DEFAULT_THRESHOLDS, validate_thresholds_dict
        
        if thresholds and validate_thresholds_dict(thresholds):
            self.thresholds = thresholds
        else:
            self.thresholds = DEFAULT_THRESHOLDS
            
        self.error_keywords = [
            "traceback", "panic", "fatal", "oom-kill", 
            "bind: address already in use", "connection refused",
            "permission denied", "no space left", "timeout"
        ]
    
    def should_suggest_restart(self, container_evidence: ContainerEvidence) -> Tuple[bool, str]:
        """
        Determine if a container restart should be suggested based on evidence.
        Returns (should_restart, reason)
        """
        # Gate 1: Health check failing
        if container_evidence.health_status and container_evidence.health_status != "healthy":
            return True, f"Health check failing: {container_evidence.health_status}"
        
        # Gate 2: Recent restarts
        if container_evidence.restart_count > 1:
            return True, f"Multiple restarts detected: {container_evidence.restart_count}"
        
        # Gate 3: Non-zero exit code
        if container_evidence.exit_code and container_evidence.exit_code != 0:
            return True, f"Last exit code: {container_evidence.exit_code}"
        
        # Gate 4: Error keywords in logs
        if container_evidence.log_errors:
            error_summary = ", ".join(container_evidence.log_errors[:3])
            return True, f"Errors in logs: {error_summary}"
        
        return False, "Container appears healthy"
    
    def get_host_context(self, checks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract host context from checks."""
        host_context = {
            "cpu_high": False,
            "temp_high": False,
            "disk_warning": False,
            "cpu_value": None,
            "temp_value": None,
            "disk_value": None
        }
        
        for check in checks:
            check_id = check.get("id", "")
            evidence = check.get("evidence", "")
            severity = check.get("severity", "")
            
            # CPU check
            if check_id == "H1" and severity in ["warn", "fail"]:
                cpu_match = re.search(r'(\d+\.?\d*)%', evidence)
                if cpu_match:
                    cpu_value = float(cpu_match.group(1))
                    host_context["cpu_value"] = cpu_value
                    cpu_warn = self.thresholds.get("cpu", {}).get("warn", 80.0)
                    host_context["cpu_high"] = cpu_value > cpu_warn
            
            # Thermal check
            if check_id == "H16" and severity in ["warn", "fail"]:
                temp_match = re.search(r'(\d+\.?\d*)°C', evidence)
                if temp_match:
                    temp_value = float(temp_match.group(1))
                    host_context["temp_value"] = temp_value
                    temp_warn = self.thresholds.get("temp_c", {}).get("warn", 85.0)
                    host_context["temp_high"] = temp_value > temp_warn
            
            # Disk check
            if "Disk Usage" in check.get("title", "") and severity in ["warn", "fail"]:
                disk_match = re.search(r'(\d+\.?\d*)%', evidence)
                if disk_match:
                    disk_value = float(disk_match.group(1))
                    host_context["disk_value"] = disk_value
                    disk_warn = self.thresholds.get("disk_pct", {}).get("warn", 85.0)
                    host_context["disk_warning"] = disk_value > disk_warn
        
        return host_context
    
    def generate_evidence_based_recommendation(
        self, 
        check: Dict[str, Any], 
        container_evidence: Optional[ContainerEvidence] = None,
        host_context: Optional[Dict[str, Any]] = None,
        verbose: bool = False
    ) -> Dict[str, Any]:
        """Generate evidence-based recommendation for a check."""
        check_id = check.get("id", "")
        title = check.get("title", "")
        severity = check.get("severity", "")
        evidence = check.get("evidence", "")
        
        recommendation = {
            "check_id": check_id,
            "title": title,
            "severity": severity,
            "evidence": evidence,
            "why": "",
            "reproduce_commands": [],
            "next_step": "",
            "host_context": ""
        }
        
        # Add host context warning if applicable
        if host_context and (host_context.get("cpu_high") or host_context.get("temp_high")):
            cpu_info = f"CPU {host_context.get('cpu_value', 'N/A')}%" if host_context.get("cpu_high") else ""
            temp_info = f"Temp {host_context.get('temp_value', 'N/A')}°C" if host_context.get("temp_high") else ""
            context_parts = [p for p in [cpu_info, temp_info] if p]
            recommendation["host_context"] = f"⚠️ Host stressed: {', '.join(context_parts)}; symptoms may be systemic."
        
        # Container-specific logic
        if container_evidence:
            should_restart, restart_reason = self.should_suggest_restart(container_evidence)
            
            if "Container Status" in title:
                if should_restart:
                    recommendation["why"] = f"Container restart needed: {restart_reason}"
                    recommendation["next_step"] = f"Restart {container_evidence.name}: docker restart {container_evidence.name}"
                    recommendation["reproduce_commands"] = [
                        f"docker inspect {container_evidence.name} --format '{{{{json .State}}}}' | jq .",
                        f"docker logs {container_evidence.name} --tail 50",
                        f"docker ps --filter name={container_evidence.name}"
                    ]
                else:
                    recommendation["why"] = f"Container appears healthy: {restart_reason}"
                    recommendation["next_step"] = "No restart needed; investigate configuration or host issues"
                    recommendation["reproduce_commands"] = [
                        f"docker inspect {container_evidence.name} --format '{{{{json .State}}}}' | jq .",
                        f"docker logs {container_evidence.name} --tail 20"
                    ]
        
        # Host-specific logic
        elif check_id.startswith("H"):
            if "CPU Usage" in title:
                cpu_match = re.search(r'(\d+\.?\d*)%', evidence)
                if cpu_match:
                    cpu_value = float(cpu_match.group(1))
                    cpu_fail = self.thresholds.get("cpu", {}).get("fail", 90.0)
                    cpu_warn = self.thresholds.get("cpu", {}).get("warn", 80.0)
                    
                    if cpu_value > cpu_fail:
                        recommendation["why"] = f"CPU usage {cpu_value}% exceeds FAIL threshold ({cpu_fail}%)"
                        recommendation["next_step"] = "Identify high CPU processes and optimize or upgrade hardware"
                        recommendation["reproduce_commands"] = [
                            "top -H -o %CPU",
                            "ps aux --sort=-%cpu | head -10",
                            "htop"
                        ]
                    elif cpu_value > cpu_warn:
                        recommendation["why"] = f"CPU usage {cpu_value}% exceeds WARN threshold ({cpu_warn}%)"
                        recommendation["next_step"] = "Monitor CPU usage and investigate if sustained"
                        recommendation["reproduce_commands"] = [
                            "top -H -o %CPU",
                            "ps aux --sort=-%cpu | head -5"
                        ]
            
            elif "Thermal" in title:
                temp_match = re.search(r'(\d+\.?\d*)°C', evidence)
                if temp_match:
                    temp_value = float(temp_match.group(1))
                    temp_fail = self.thresholds.get("temp_c", {}).get("fail", 92.0)
                    temp_warn = self.thresholds.get("temp_c", {}).get("warn", 85.0)
                    
                    if temp_value > temp_fail:
                        recommendation["why"] = f"Temperature {temp_value}°C exceeds FAIL threshold ({temp_fail}°C)"
                        recommendation["next_step"] = "Immediate cooling required; check fans, clean dust, improve ventilation"
                        recommendation["reproduce_commands"] = [
                            "sensors",
                            "cat /sys/class/thermal/thermal_zone*/temp",
                            "systemctl status thermald"
                        ]
                    elif temp_value > temp_warn:
                        recommendation["why"] = f"Temperature {temp_value}°C exceeds WARN threshold ({temp_warn}°C)"
                        recommendation["next_step"] = "Monitor temperature; check cooling system"
                        recommendation["reproduce_commands"] = [
                            "sensors",
                            "cat /sys/class/thermal/thermal_zone*/temp"
                        ]
            
            elif "Disk Usage" in title:
                disk_match = re.search(r'(\d+\.?\d*)%', evidence)
                if disk_match:
                    disk_value = float(disk_match.group(1))
                    disk_fail = self.thresholds.get("disk_pct", {}).get("fail", 95.0)
                    disk_warn = self.thresholds.get("disk_pct", {}).get("warn", 85.0)
                    
                    if disk_value > disk_fail:
                        recommendation["why"] = f"Disk usage {disk_value}% exceeds FAIL threshold ({disk_fail}%)"
                        recommendation["next_step"] = "Immediate cleanup required; services may fail"
                        recommendation["reproduce_commands"] = [
                            "df -h",
                            "du -sh /mnt/PLEX22TB/* | sort -hr | head -10",
                            "find /mnt/PLEX22TB -type f -size +1G -exec ls -lh {} \\;"
                        ]
                    elif disk_value > disk_warn:
                        recommendation["why"] = f"Disk usage {disk_value}% exceeds WARN threshold ({disk_warn}%)"
                        recommendation["next_step"] = "Plan cleanup; consider moving temp paths to other drives"
                        recommendation["reproduce_commands"] = [
                            "df -h",
                            "du -sh /mnt/PLEX22TB/* | sort -hr | head -5"
                        ]
        
        # Service-specific logic
        elif "qBittorrent" in title:
            recommendation["why"] = "qBittorrent connectivity or configuration issue"
            recommendation["next_step"] = "Check API connectivity and credentials; verify VPN routing"
            recommendation["reproduce_commands"] = [
                "curl -sS http://localhost:8080/api/v2/app/version",
                "docker logs qbittorrent --tail 50",
                "docker exec qbittorrent curl -s ifconfig.me"
            ]
        
        elif "Gluetun" in title or "VPN" in title:
            recommendation["why"] = "VPN connectivity or port-forwarding issue"
            recommendation["next_step"] = "Check VPN status and port-forwarding; consider switching PIA regions"
            recommendation["reproduce_commands"] = [
                "docker logs gluetun --tail 50",
                "docker exec gluetun curl -s ifconfig.me",
                "docker exec gluetun cat /tmp/gluetun/forwarded_port"
            ]
        
        elif "Arr" in title or "Radarr" in title or "Sonarr" in title:
            recommendation["why"] = "Arr service connectivity or configuration issue"
            recommendation["next_step"] = "Check API connectivity and download client integration"
            recommendation["reproduce_commands"] = [
                "curl -sS http://localhost:7878/api/v3/system/status",
                "curl -sS http://localhost:8989/api/v3/system/status",
                "docker logs radarr --tail 30",
                "docker logs sonarr --tail 30"
            ]
        
        # Default fallback
        if not recommendation["why"]:
            recommendation["why"] = f"Check failed with severity: {severity}"
            recommendation["next_step"] = check.get("suggested_fix", "Investigate the issue")
            recommendation["reproduce_commands"] = [
                f"# Check {title}",
                f"# Evidence: {evidence}"
            ]
        
        return recommendation


def generate_evidence_based_fixes(
    checks: List[Dict[str, Any]], 
    container_evidence_map: Optional[Dict[str, ContainerEvidence]] = None,
    thresholds: Optional[Dict[str, Any]] = None,
    verbose: bool = False
) -> List[Dict[str, Any]]:
    """Generate evidence-based fixes for checks."""
    advisor = AdvisorRules(thresholds)
    host_context = advisor.get_host_context(checks)
    
    recommendations = []
    
    for check in checks:
        if check.get("severity") in ["warn", "fail"]:
            # Get container evidence if available
            container_evidence = None
            if container_evidence_map:
                # Try to match by container name in check title
                title = check.get("title", "")
                for name, evidence in container_evidence_map.items():
                    if name.lower() in title.lower():
                        container_evidence = evidence
                        break
            
            recommendation = advisor.generate_evidence_based_recommendation(
                check, container_evidence, host_context, verbose
            )
            recommendations.append(recommendation)
    
    return recommendations
