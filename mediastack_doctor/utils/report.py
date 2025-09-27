"""Report generation utilities."""

import json
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader

from .redact import Redactor


class ReportGenerator:
    """Generate diagnostic reports in multiple formats."""
    
    def __init__(self, output_dir: Path, redact: bool = True) -> None:
        """Initialize report generator."""
        self.output_dir = output_dir
        self.redact = redact
        self.redactor = Redactor() if redact else None
        
        # Setup Jinja2 environment
        template_dir = Path(__file__).parent.parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=True
        )
    
    def generate_reports(
        self, 
        checks: List[Dict[str, Any]], 
        registry: Any, 
        docker_client: Any,
        advisor_fixes: List[str] = None
    ) -> None:
        """Generate all report formats."""
        # Prepare report data
        report_data = self._prepare_report_data(checks, registry, docker_client, advisor_fixes)
        
        # Generate Markdown report
        self._generate_markdown_report(report_data)
        
        # Generate JSON report
        self._generate_json_report(report_data)
        
        # Generate support bundle
        self._generate_support_bundle(report_data, docker_client)
    
    def _agg_category_stats(self, checks: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
        """Aggregate statistics by category."""
        cat_stats = {}
        for check in checks:
            category = check.get("category", "Uncategorized")
            severity = (check.get("severity") or "").lower()
            
            if category not in cat_stats:
                cat_stats[category] = {"total": 0, "passed": 0, "warnings": 0, "failed": 0}
            
            stats = cat_stats[category]
            stats["total"] += 1
            
            if severity in ("pass", "ok", "success", "info"):
                stats["passed"] += 1
            elif severity in ("warn", "warning"):
                stats["warnings"] += 1
            elif severity in ("fail", "error", "fatal"):
                stats["failed"] += 1
            # else: treat unknown severity as neither pass/warn/fail (keeps totals consistent)
        
        return cat_stats

    def _prepare_report_data(
        self, 
        checks: List[Dict[str, Any]], 
        registry: Any, 
        docker_client: Any,
        advisor_fixes: List[str] = None
    ) -> Dict[str, Any]:
        """Prepare data for report generation."""
        # Calculate category statistics
        cat_stats = self._agg_category_stats(checks)
        
        # Group checks by category with stats
        categories = {}
        for check in checks:
            category = check.get("category", "Uncategorized")
            if category not in categories:
                categories[category] = {
                    "stats": cat_stats.get(category, {"total": 0, "passed": 0, "warnings": 0, "failed": 0}),
                    "checks": []
                }
            categories[category]["checks"].append(check)
        
        # Calculate summary statistics
        total_checks = len(checks)
        passed = sum(1 for c in checks if c.get("severity") == "info")
        warnings = sum(1 for c in checks if c.get("severity") == "warn")
        failed = sum(1 for c in checks if c.get("severity") == "fail")
        
        # Get system info
        system_info = self._get_system_info()
        
        # Get Docker info
        docker_info = self._get_docker_info(docker_client)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": total_checks,
                "passed": passed,
                "warnings": warnings,
                "failed": failed,
                "success_rate": (passed / total_checks * 100) if total_checks > 0 else 0,
            },
            "categories": categories,
            "checks": checks,
            "system_info": system_info,
            "docker_info": docker_info,
            "registry": registry.to_redacted_dict() if registry else {},
            "advisor_fixes": advisor_fixes or [],
        }
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information."""
        import platform
        import psutil
        
        return {
            "hostname": platform.node(),
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": psutil.cpu_count(),
            "memory_total": psutil.virtual_memory().total,
            "disk_usage": {
                mount.mountpoint: {
                    "total": psutil.disk_usage(mount.mountpoint).total,
                    "used": psutil.disk_usage(mount.mountpoint).used,
                    "free": psutil.disk_usage(mount.mountpoint).free,
                }
                for mount in psutil.disk_partitions()
                if mount.mountpoint.startswith("/mnt/")
            },
        }
    
    def _get_docker_info(self, docker_client: Any) -> Dict[str, Any]:
        """Get Docker information."""
        try:
            containers = docker_client.list_containers()
            networks = docker_client.list_networks()
            
            return {
                "container_count": len(containers),
                "network_count": len(networks),
                "containers": [
                    {
                        "name": c["name"],
                        "image": c["image"],
                        "status": c["status"],
                    }
                    for c in containers
                ],
                "networks": [
                    {
                        "name": n["name"],
                        "driver": n["driver"],
                        "scope": n["scope"],
                    }
                    for n in networks
                ],
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _generate_markdown_report(self, data: Dict[str, Any]) -> None:
        """Generate Markdown report."""
        try:
            template = self.jinja_env.get_template("report.md.j2")
            content = template.render(**data)
            
            report_path = self.output_dir / "report.md"
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            # Fallback to simple markdown
            self._generate_simple_markdown_report(data)
    
    def _generate_simple_markdown_report(self, data: Dict[str, Any]) -> None:
        """Generate simple Markdown report as fallback."""
        report_path = self.output_dir / "report.md"
        
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"# MediaStack Doctor Report\n\n")
            f.write(f"**Generated:** {data['timestamp']}\n\n")
            
            # Summary
            summary = data["summary"]
            f.write(f"## Summary\n\n")
            f.write(f"- **Total Checks:** {summary['total']}\n")
            f.write(f"- **Passed:** {summary['passed']} ✅\n")
            f.write(f"- **Warnings:** {summary['warnings']} ⚠️\n")
            f.write(f"- **Failed:** {summary['failed']} ❌\n")
            f.write(f"- **Success Rate:** {summary['success_rate']:.1f}%\n\n")
            
            # Categories
            for category, checks in data["categories"].items():
                f.write(f"## {category}\n\n")
                
                for check in checks:
                    severity = check.get("severity", "info")
                    icon = "✅" if severity == "info" else "⚠️" if severity == "warn" else "❌"
                    
                    f.write(f"### {icon} {check.get('title', 'Unknown Check')}\n\n")
                    
                    if check.get("evidence"):
                        f.write(f"**Evidence:** {check['evidence']}\n\n")
                    
                    if check.get("why_it_matters"):
                        f.write(f"**Why it matters:** {check['why_it_matters']}\n\n")
                    
                    if check.get("suggested_fix"):
                        fixes = check["suggested_fix"]
                        if isinstance(fixes, list):
                            f.write("**Suggested fixes:**\n")
                            for fix in fixes:
                                f.write(f"- {fix}\n")
                        else:
                            f.write(f"**Suggested fix:** {fixes}\n")
                        f.write("\n")
    
    def _generate_json_report(self, data: Dict[str, Any]) -> None:
        """Generate JSON report."""
        report_path = self.output_dir / "report.json"
        
        # Redact sensitive data if needed
        if self.redactor:
            data = self.redactor.redact_dict(data)
        
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    
    def _generate_support_bundle(
        self, 
        data: Dict[str, Any], 
        docker_client: Any
    ) -> None:
        """Generate support bundle with logs and configs."""
        bundle_path = self.output_dir / "support_bundle.tar.gz"
        
        with tarfile.open(bundle_path, "w:gz") as tar:
            # Add report files
            for file_name in ["report.md", "report.json"]:
                file_path = self.output_dir / file_name
                if file_path.exists():
                    tar.add(file_path, arcname=file_name)
            
            # Add system logs
            self._add_system_logs(tar)
            
            # Add Docker logs
            self._add_docker_logs(tar, docker_client)
            
            # Add registry (redacted)
            if data.get("registry"):
                registry_data = json.dumps(data["registry"], indent=2)
                tar.addfile(
                    tarfile.TarInfo("registry.json"),
                    fileobj=json.dumps(data["registry"], indent=2).encode()
                )
    
    def _add_system_logs(self, tar: tarfile.TarFile) -> None:
        """Add system logs to support bundle."""
        try:
            import subprocess
            
            # Add journalctl logs
            result = subprocess.run(
                ["journalctl", "-k", "-S", "24 hours ago", "--no-pager"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                tar.addfile(
                    tarfile.TarInfo("system_logs.txt"),
                    fileobj=result.stdout.encode()
                )
        except Exception:
            pass  # Skip if journalctl not available
    
    def _add_docker_logs(self, tar: tarfile.TarFile, docker_client: Any) -> None:
        """Add Docker logs to support bundle."""
        try:
            containers = docker_client.list_containers()
            
            for container in containers[:10]:  # Limit to first 10 containers
                container_name = container["name"]
                logs = docker_client.get_container_logs(container_name, since="1h")
                
                if logs:
                    # Redact logs if needed
                    if self.redactor:
                        logs = self.redactor.redact_text(logs)
                    
                    tar.addfile(
                        tarfile.TarInfo(f"docker_logs_{container_name}.txt"),
                        fileobj=logs.encode()
                    )
        except Exception:
            pass  # Skip if Docker not available
    
    def save_run_manifest(self, timestamp: str, checks: List[Dict[str, Any]]) -> None:
        """Save run manifest for future diffing."""
        from .diff import save_run_manifest
        save_run_manifest(self.output_dir, timestamp, checks)
