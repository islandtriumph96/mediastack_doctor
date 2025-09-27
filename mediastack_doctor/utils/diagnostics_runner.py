"""Diagnostics runner utility - shared between CLI and menu."""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    Console = None


def run_diagnostics_impl(
    registry: Any,
    docker_client: Any,
    output_dir: Path,
    advisor: bool = True,
    quick: bool = False,
    verbose: bool = True,
    sections: Optional[str] = None,
    thresholds: Optional[Dict[str, Any]] = None,
    redact: bool = True,
    allow_external_checks: bool = False
) -> Dict[str, Any]:
    """
    Run diagnostics implementation that can be called from CLI or menu.
    
    Returns:
        Dict with results including run_dir, checks, and summary
    """
    console = Console() if HAS_RICH else None
    
    # Create timestamped output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_dir / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    
    if console and HAS_RICH:
        console.print(f"\n[bold green]Starting diagnostics...[/bold green]")
        console.print(f"[blue]Output directory: {run_dir}[/blue]")
    else:
        print(f"\nStarting diagnostics...")
        print(f"Output directory: {run_dir}")
    
    # Load thresholds
    from .thresholds import load_thresholds, DEFAULT_THRESHOLDS, ThresholdsError
    
    try:
        thresholds_config = thresholds if thresholds else DEFAULT_THRESHOLDS
        if console and HAS_RICH and verbose:
            console.print(f"[dim]Using thresholds: {thresholds_config}[/dim]")
    except Exception:
        thresholds_config = DEFAULT_THRESHOLDS
    
    # Determine which sections to run
    if quick:
        section_list = ["host", "docker"]
    elif sections:
        section_list = sections.split(",")
    else:
        section_list = [
            "host", "docker", "gluetun", "qbittorrent", "arr", 
            "sabnzbd", "plex", "cloudflared", "overseerr"
        ]
    
    # Import check modules
    from ..checks import (
        host, docker_topology, gluetun, qbittorrent, arr,
        sabnzbd, plex, cloudflared, overseerr
    )
    
    section_modules = {
        "host": host,
        "docker": docker_topology,
        "gluetun": gluetun,
        "qbittorrent": qbittorrent,
        "arr": arr,
        "sabnzbd": sabnzbd,
        "plex": plex,
        "cloudflared": cloudflared,
        "overseerr": overseerr,
    }
    
    all_checks = []
    
    # Run checks with progress tracking
    if console and HAS_RICH:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            for section_name in section_list:
                if section_name not in section_modules:
                    continue
                    
                task = progress.add_task(f"Running {section_name} checks...", total=None)
                section_module = section_modules[section_name]
                
                try:
                    if section_name == "host":
                        section_checks = section_module.run_checks(registry, docker_client, thresholds=thresholds_config)
                    elif section_name == "gluetun":
                        section_checks = section_module.run_checks(registry, docker_client, allow_external_checks)
                    else:
                        section_checks = section_module.run_checks(registry, docker_client)
                    
                    all_checks.extend(section_checks)
                    progress.update(task, description=f"✓ {section_name} checked")
                    
                except Exception as e:
                    # Add error check
                    all_checks.append({
                        "id": f"{section_name.upper()}_ERROR",
                        "category": section_name.title(),
                        "title": f"{section_name.title()} Checks Failed",
                        "severity": "fail",
                        "evidence": str(e),
                        "why_it_matters": f"Could not run {section_name} diagnostics",
                        "suggested_fix": f"Check {section_name} module and dependencies",
                    })
                    progress.update(task, description=f"✗ {section_name} failed")
    else:
        for section_name in section_list:
            if section_name not in section_modules:
                continue
                
            print(f"Running {section_name} checks...")
            section_module = section_modules[section_name]
            
            try:
                if section_name == "host":
                    section_checks = section_module.run_checks(registry, docker_client, thresholds=thresholds_config)
                elif section_name == "gluetun":
                    section_checks = section_module.run_checks(registry, docker_client, allow_external_checks)
                else:
                    section_checks = section_module.run_checks(registry, docker_client)
                
                all_checks.extend(section_checks)
                print(f"✓ {section_name} completed ({len(section_checks)} checks)")
                
            except Exception as e:
                all_checks.append({
                    "id": f"{section_name.upper()}_ERROR",
                    "category": section_name.title(),
                    "title": f"{section_name.title()} Checks Failed",
                    "severity": "fail",
                    "evidence": str(e),
                    "why_it_matters": f"Could not run {section_name} diagnostics",
                    "suggested_fix": f"Check {section_name} module and dependencies",
                })
                print(f"✗ {section_name} failed: {e}")
    
    # Generate advisor recommendations if requested
    advisor_fixes = []
    if advisor:
        try:
            from .advisor_rules import generate_evidence_based_fixes
            
            # Collect container evidence for advisor
            container_evidence_map = {}
            if docker_client:
                try:
                    containers = docker_client.list_containers()
                    for container in containers:
                        container_name = container["name"]
                        from ..checks.docker_topology import _collect_container_evidence
                        container_evidence_map[container_name] = _collect_container_evidence(container_name, docker_client)
                except Exception:
                    pass  # Ignore evidence collection errors
            
            advisor_fixes = generate_evidence_based_fixes(all_checks, container_evidence_map, thresholds_config, verbose)
        except Exception as e:
            if console and HAS_RICH:
                console.print(f"[red]Error generating advisor recommendations:[/red] {e}")
            else:
                print(f"Error generating advisor recommendations: {e}")
            advisor_fixes = []
    
    # Generate reports if requested
    try:
        from .report import ReportGenerator
        
        report_generator = ReportGenerator(run_dir, redact)
        report_generator.generate_reports(all_checks, registry, docker_client, advisor_fixes, verbose, thresholds_config)
        report_generator.save_run_manifest(timestamp, all_checks)
        
        if console and HAS_RICH:
            console.print(f"[green]✓ Reports generated in {run_dir}[/green]")
        else:
            print(f"✓ Reports generated in {run_dir}")
            
    except Exception as e:
        # Fallback: save simple JSON report
        import json
        from .thresholds import get_flat_thresholds
        
        try:
            flat_thresholds = get_flat_thresholds(thresholds_config)
        except Exception:
            flat_thresholds = {}
        
        simple_report = {
            "timestamp": timestamp,
            "checks": all_checks,
            "advisor_fixes": advisor_fixes,
            "thresholds": flat_thresholds
        }
        json_path = run_dir / "report.json"
        with open(json_path, "w") as f:
            json.dump(simple_report, f, indent=2)
        
        if console and HAS_RICH:
            console.print(f"[yellow]Simple JSON report saved: {json_path}[/yellow]")
        else:
            print(f"Simple JSON report saved: {json_path}")
    
    # Calculate summary
    passed = sum(1 for c in all_checks if c.get("severity") == "info")
    warnings = sum(1 for c in all_checks if c.get("severity") == "warn")
    failed = sum(1 for c in all_checks if c.get("severity") == "fail")
    
    summary = {
        "total": len(all_checks),
        "passed": passed,
        "warnings": warnings,
        "failed": failed,
        "success_rate": (passed / len(all_checks) * 100) if all_checks else 0
    }
    
    return {
        "run_dir": run_dir,
        "checks": all_checks,
        "summary": summary,
        "advisor_fixes": advisor_fixes,
        "timestamp": timestamp
    }
