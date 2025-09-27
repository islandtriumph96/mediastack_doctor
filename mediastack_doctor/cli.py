#!/usr/bin/env python3
"""Main CLI entry point for MediaStack Doctor."""

import os
import sys
from pathlib import Path
from typing import Optional

# Graceful imports - CLI should work even without external dependencies
try:
    import click
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table
    HAS_RICH = True
except ImportError:
    # Fallback for systems without rich/click
    HAS_RICH = False
    print("Warning: rich/click not available. Install with: pip install rich click")
    sys.exit(1)

from .registry import Registry

# Graceful Docker client import
try:
    from .utils.docker_client import DockerClient
    HAS_DOCKER = True
except ImportError:
    HAS_DOCKER = False
    DockerClient = None

# Graceful report generator import
try:
    from .utils.report import ReportGenerator
    HAS_REPORT = True
except ImportError:
    HAS_REPORT = False
    ReportGenerator = None
from .checks import (
    host,
    docker_topology,
    gluetun,
    qbittorrent,
    arr,
    sabnzbd,
    plex,
    cloudflared,
    overseerr,
)

console = Console()


@click.group()
@click.version_option(version="0.1.0")
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=Path.home() / "mediastack-doctor" / "outputs",
    help="Output directory for reports and support bundles",
)
@click.option(
    "--redact/--no-redact",
    default=True,
    help="Redact sensitive information in reports",
)
@click.option(
    "--allow-external-checks/--no-external-checks",
    default=False,
    help="Allow external connectivity checks (port-forward tests)",
)
@click.pass_context
def cli_group(
    ctx: click.Context,
    output_dir: Path,
    redact: bool,
    allow_external_checks: bool,
) -> None:
    """MediaStack Doctor - Comprehensive diagnostics for self-hosted media stack."""
    ctx.ensure_object(dict)
    ctx.obj["output_dir"] = output_dir
    ctx.obj["redact"] = redact
    ctx.obj["allow_external_checks"] = allow_external_checks
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)


@cli_group.command()
@click.option(
    "--qb-url",
    help="qBittorrent WebUI URL (overrides registry)",
)
@click.option(
    "--qb-user",
    help="qBittorrent username (overrides registry)",
)
@click.option(
    "--qb-pass",
    help="qBittorrent password (overrides registry)",
)
@click.option(
    "--plex-token",
    help="Plex token (overrides registry)",
)
@click.option(
    "--plex-url",
    help="Plex server URL (overrides registry)",
)
@click.option(
    "--cloudflared-metrics",
    help="Cloudflared metrics URL (overrides registry)",
)
@click.option(
    "--gluetun-host",
    help="Gluetun container name (overrides registry)",
)
@click.option(
    "--nic",
    help="Preferred network interface for tests",
)
@click.option(
    "--pcap",
    type=int,
    help="Run packet capture for N seconds (optional, 0 to skip)",
)
@click.option(
    "--advisor/--no-advisor",
    default=False,
    help="Show actionable remediation steps",
)
@click.option(
    "--diff",
    help="Compare with previous run (use 'last' or run ID)",
)
@click.option(
    "--sections",
    help="Comma-separated list of sections to run (host,docker,gluetun,qbittorrent,arr,sabnzbd,plex,cloudflared,overseerr)",
)
@click.option(
    "--netbench",
    type=click.Choice(["skip", "quick", "full"]),
    default="skip",
    help="Network benchmarking mode (skip/quick/full)",
)
@click.option(
    "--deep/--no-deep",
    default=False,
    help="Run deep checks (SMART, I/O latency, etc.)",
)
@click.option(
    "--verbose", "--why",
    is_flag=True,
    help="Show detailed evidence and reproduce commands",
)
@click.option(
    "--thresholds",
    type=click.Path(path_type=Path),
    help="Path to thresholds configuration file",
)
@click.pass_context
def run(
    ctx: click.Context,
    qb_url: Optional[str],
    qb_user: Optional[str],
    qb_pass: Optional[str],
    plex_token: Optional[str],
    plex_url: Optional[str],
    cloudflared_metrics: Optional[str],
    gluetun_host: Optional[str],
    nic: Optional[str],
    pcap: Optional[int],
    advisor: bool,
    diff: Optional[str],
    sections: Optional[str],
    netbench: str,
    deep: bool,
    verbose: bool,
    thresholds: Optional[Path],
) -> None:
    """Run comprehensive diagnostics on the media stack."""
    output_dir = ctx.obj["output_dir"]
    redact = ctx.obj["redact"]
    allow_external_checks = ctx.obj["allow_external_checks"]
    
    # Handle diff mode
    if diff:
        _handle_diff_mode(output_dir, diff)
        return
    
    # Load registry
    registry = Registry.load()
    
    # Check if registry has any services configured
    if not registry._data.get("services") and not any([qb_url, qb_user, plex_token, plex_url]):
        console.print("\n[yellow]⚠️  No services configured in registry[/yellow]")
        console.print("[dim]Consider running:[/dim]")
        console.print("[dim]  mediastack-doctor registry discover --save[/dim]")
        console.print("[dim]  mediastack-doctor registry set <service> --url <url>[/dim]")
        console.print("[dim]Or use CLI flags for quick testing[/dim]\n")
    
    # Override registry with CLI flags
    if qb_url:
        registry.set_service_url("qbittorrent", qb_url)
    if qb_user:
        registry.set_service_username("qbittorrent", qb_user)
    if qb_pass:
        registry.set_secret("qb_password", qb_pass)
    if plex_token:
        registry.set_secret("plex_token", plex_token)
    if plex_url:
        registry.set_service_url("plex", plex_url)
    if cloudflared_metrics:
        registry.set_service_metrics_url("cloudflared", cloudflared_metrics)
    if gluetun_host:
        registry.set_service_container("gluetun", gluetun_host)
    
    # Initialize Docker client (gracefully handle missing Docker)
    if HAS_DOCKER:
        try:
            docker_client = DockerClient()
        except Exception as e:
            console.print(f"[yellow]Warning: Docker client failed: {e}[/yellow]")
            docker_client = None
    else:
        console.print("[yellow]Warning: Docker not available, skipping Docker-dependent checks[/yellow]")
        docker_client = None
    
    # Create timestamped output directory
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_dir / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    
    console.print(Panel.fit(
        f"[bold blue]MediaStack Doctor[/bold blue]\n"
        f"Running diagnostics at {timestamp}\n"
        f"Output: {run_dir}",
        title="Starting Diagnostics"
    ))
    
    # Determine which sections to run
    available_sections = {
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
    
    # Add netbench if not skipped
    if netbench != "skip":
        from .checks import netbench
        available_sections["netbench"] = netbench
    
    # Add Prometheus monitoring
    from .checks import prometheus
    available_sections["prometheus"] = prometheus
    
    # Add Tautulli integration
    from .checks import tautulli
    available_sections["tautulli"] = tautulli
    
    # Add storage health checks
    from .checks import storage
    available_sections["storage"] = storage
    
    if sections:
        requested_sections = [s.strip() for s in sections.split(",")]
        sections_to_run = {k: v for k, v in available_sections.items() if k in requested_sections}
        if not sections_to_run:
            console.print("[red]No valid sections specified[/red]")
            return
    else:
        sections_to_run = available_sections
    
    # Run checks
    all_checks = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        
        for section_name, section_module in sections_to_run.items():
            task = progress.add_task(f"Checking {section_name}...", total=None)
            
            if section_name == "host":
                section_checks = section_module.run_checks(registry, nic, pcap)
            elif section_name in ["gluetun", "netbench", "storage"] and docker_client is None:
                # Skip Docker-dependent sections if Docker is not available
                section_checks = [{
                    "id": f"{section_name.upper()}_SKIP",
                    "category": section_name.title(),
                    "title": f"{section_name.title()} Checks",
                    "severity": "info",
                    "evidence": "Docker not available, skipping Docker-dependent checks",
                    "why_it_matters": f"Cannot run {section_name} checks without Docker",
                    "suggested_fix": "Install Docker or run without Docker-dependent sections",
                }]
            elif section_name == "gluetun":
                section_checks = section_module.run_checks(registry, docker_client, allow_external_checks)
            elif section_name == "netbench":
                section_checks = section_module.run_checks(registry, docker_client, netbench)
            elif section_name == "storage":
                section_checks = section_module.run_checks(registry, docker_client, deep)
            elif section_name == "host":
                # Pass thresholds to host checks
                section_checks = section_module.run_checks(registry, docker_client, thresholds=thresholds_config)
            else:
                if docker_client is None and section_name in ["docker", "qbittorrent", "arr", "sabnzbd", "plex", "cloudflared", "overseerr", "prometheus", "tautulli"]:
                    section_checks = [{
                        "id": f"{section_name.upper()}_SKIP",
                        "category": section_name.title(),
                        "title": f"{section_name.title()} Checks",
                        "severity": "info",
                        "evidence": "Docker not available, skipping Docker-dependent checks",
                        "why_it_matters": f"Cannot run {section_name} checks without Docker",
                        "suggested_fix": "Install Docker or run without Docker-dependent sections",
                    }]
                else:
                    section_checks = section_module.run_checks(registry, docker_client)
            
            all_checks.extend(section_checks)
            progress.update(task, description=f"✓ {section_name} checked")
    
    # Load thresholds with robust error handling
    from .utils.thresholds import load_thresholds, DEFAULT_THRESHOLDS, ThresholdsError
    
    thresholds_input = str(thresholds) if thresholds else None
    try:
        thresholds_config = load_thresholds(thresholds_input)
        if thresholds:
            console.print(f"[blue]✓ Loaded thresholds from {thresholds}[/blue]")
        if verbose:
            console.print(f"[dim]Active thresholds: {thresholds_config}[/dim]")
    except ThresholdsError as e:
        console.print(f"[red]Thresholds error:[/red] {e}")
        console.print("[yellow]Falling back to default thresholds.[/yellow]")
        thresholds_config = DEFAULT_THRESHOLDS
    except Exception as e:
        console.print(f"[red]Unexpected error loading thresholds:[/red] {e}")
        console.print("[yellow]Falling back to default thresholds.[/yellow]")
        thresholds_config = DEFAULT_THRESHOLDS
    
    # Generate reports
    console.print("\n[bold]Generating reports...[/bold]")
    if HAS_REPORT:
        report_generator = ReportGenerator(run_dir, redact)
    else:
        console.print("[yellow]Warning: Report generation not available[/yellow]")
        report_generator = None
    
    # Handle advisor mode with evidence-based logic
    advisor_fixes = []
    if advisor:
        from .utils.advisor_rules import generate_evidence_based_fixes
        
        # Collect container evidence for advisor
        container_evidence_map = {}
        if docker_client:
            try:
                containers = docker_client.list_containers()
                for container in containers:
                    container_name = container["name"]
                    from .checks.docker_topology import _collect_container_evidence
                    container_evidence_map[container_name] = _collect_container_evidence(container_name, docker_client)
            except Exception:
                pass  # Ignore evidence collection errors
        
        try:
            advisor_fixes = generate_evidence_based_fixes(all_checks, container_evidence_map, thresholds_config, verbose)
        except Exception as e:
            console.print(f"[red]Error generating advisor recommendations:[/red] {e}")
            advisor_fixes = []
    
    # Generate reports with advisor and diff support
    if report_generator:
        report_generator.generate_reports(all_checks, registry, docker_client, advisor_fixes, verbose, thresholds_config)
        # Save run manifest for diffing
        report_generator.save_run_manifest(timestamp, all_checks)
    else:
        # Fallback: just save a simple JSON report
        import json
        from .utils.thresholds import get_flat_thresholds
        
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
        console.print(f"[green]Simple JSON report saved: {json_path}[/green]")
    
    # Show summary
    show_summary(all_checks, run_dir, advisor_fixes)


def _handle_diff_mode(output_dir: Path, diff_target: str) -> None:
    """Handle diff mode to compare with previous runs."""
    from .utils.diff import diff_runs
    
    if diff_target == "last":
        # Find the most recent run
        run_dirs = [d for d in output_dir.iterdir() if d.is_dir()]
        if not run_dirs:
            console.print("[red]No previous runs found[/red]")
            return
        
        latest_run = max(run_dirs, key=lambda d: d.name)
        diff_target = latest_run.name
    
    # Find the target run directory
    target_dir = output_dir / diff_target
    if not target_dir.exists():
        console.print(f"[red]Run {diff_target} not found[/red]")
        return
    
    # Find the most recent run for comparison
    run_dirs = [d for d in output_dir.iterdir() if d.is_dir() and d.name != diff_target]
    if not run_dirs:
        console.print("[red]No other runs found for comparison[/red]")
        return
    
    current_run = max(run_dirs, key=lambda d: d.name)
    
    # Generate diff
    diff_result = diff_runs(target_dir, current_run)
    
    if diff_result:
        console.print(Panel.fit(
            f"[bold]Diff: {diff_target} → {current_run.name}[/bold]\n\n" + diff_result,
            title="Run Comparison"
        ))
    else:
        console.print("[green]No changes detected between runs[/green]")


def show_summary(checks: list, output_dir: Path, advisor_fixes: list = None) -> None:
    """Display a summary of check results."""
    table = Table(title="Diagnostics Summary")
    table.add_column("Category", style="cyan")
    table.add_column("Passed", style="green")
    table.add_column("Warnings", style="yellow")
    table.add_column("Failed", style="red")
    
    categories = {}
    for check in checks:
        cat = check.get("category", "Unknown")
        if cat not in categories:
            categories[cat] = {"pass": 0, "warn": 0, "fail": 0}
        
        severity = check.get("severity", "info")
        if severity == "info":
            categories[cat]["pass"] += 1
        elif severity == "warn":
            categories[cat]["warn"] += 1
        elif severity == "fail":
            categories[cat]["fail"] += 1
    
    for category, counts in categories.items():
        table.add_row(
            category,
            str(counts["pass"]),
            str(counts["warn"]),
            str(counts["fail"])
        )
    
    console.print(table)
    
    # Show advisor fixes if available
    if advisor_fixes:
        console.print("\n[bold]🔧 Advisor Recommendations[/bold]")
        for fix in advisor_fixes[:5]:  # Show top 5
            if isinstance(fix, dict):
                # New evidence-based advisor format
                title = fix.get('title', 'Unknown')
                next_step = fix.get('next_step', 'No action specified')
                console.print(f"• {title}: {next_step}")
            else:
                # Legacy string format
                console.print(f"• {fix}")
        if len(advisor_fixes) > 5:
            console.print(f"... and {len(advisor_fixes) - 5} more (see report.md)")
    
    console.print(f"\n[bold]Reports saved to:[/bold] {output_dir}")
    console.print(f"  • [link=file://{output_dir}/report.md]report.md[/link]")
    console.print(f"  • [link=file://{output_dir}/report.json]report.json[/link]")
    console.print(f"  • [link=file://{output_dir}/support_bundle.tar.gz]support_bundle.tar.gz[/link]")


# Registry management commands
@cli_group.group()
def registry() -> None:
    """Manage service registry and credentials."""
    pass


@cli_group.command()
@click.option(
    "--outputs",
    type=click.Path(path_type=Path, exists=True),
    default=Path.home() / "mediastack-doctor" / "outputs",
    help="Path to outputs directory or specific run directory",
)
def browse(outputs: Path) -> None:
    """Browse previous diagnostic runs interactively."""
    from .utils.viewer import run_browser
    
    try:
        exit_code = run_browser(outputs)
        if exit_code != 0:
            raise SystemExit(exit_code)
    except Exception as e:
        console.print(f"[red]Error browsing reports: {e}[/red]")
        raise SystemExit(1)


@registry.command("set")
@click.argument("service")
@click.option("--url", help="Service URL")
@click.option("--port", type=int, help="Service port")
@click.option("--username", help="Username")
@click.option("--password-secret-ref", help="Password secret reference")
@click.option("--api-key-secret-ref", help="API key secret reference")
@click.option("--token-secret-ref", help="Token secret reference")
@click.option("--metrics-url", help="Metrics URL")
@click.option("--container", help="Container name")
def registry_set(
    service: str,
    url: Optional[str],
    port: Optional[int],
    username: Optional[str],
    password_secret_ref: Optional[str],
    api_key_secret_ref: Optional[str],
    token_secret_ref: Optional[str],
    metrics_url: Optional[str],
    container: Optional[str],
) -> None:
    """Set service configuration in registry."""
    registry = Registry.load()
    
    # Get or create service
    svc = registry.get_service(service)
    if not svc:
        from .registry import ServiceRef
        svc = ServiceRef(name=service)
    
    # Update fields
    if url:
        svc.url = url
    if port:
        svc.port = port
    if username:
        svc.username = username
    if password_secret_ref:
        svc.password_secret_ref = password_secret_ref
    if api_key_secret_ref:
        svc.api_key_secret_ref = api_key_secret_ref
    if token_secret_ref:
        svc.token_secret_ref = token_secret_ref
    if metrics_url:
        svc.metrics_url = metrics_url
    if container:
        svc.container = container
    
    registry.set_service(svc)
    registry.save()
    
    console.print(f"[green]✓[/green] Service '{service}' configured")


@registry.command("get")
@click.argument("service")
@click.option("--show-secrets/--no-show-secrets", default=False)
def registry_get(service: str, show_secrets: bool) -> None:
    """Get service configuration from registry."""
    registry = Registry.load()
    svc = registry.get_service(service)
    
    if not svc:
        console.print(f"[red]✗[/red] Service '{service}' not found")
        return
    
    table = Table(title=f"Service: {service}")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")
    
    for field, value in svc.__dict__.items():
        if value is None:
            continue
        
        if "secret" in field.lower() and not show_secrets:
            value = "****" + str(value)[-4:] if len(str(value)) >= 8 else "****"
        
        table.add_row(field.replace("_", " ").title(), str(value))
    
    console.print(table)


@registry.command("discover")
@click.option("--save/--no-save", default=False)
def registry_discover(save: bool) -> None:
    """Discover services from Docker containers."""
    docker_client = DockerClient()
    registry = Registry.load()
    
    discovered = docker_client.discover_services()
    
    if not discovered:
        console.print("[yellow]No services discovered[/yellow]")
        return
    
    table = Table(title="Discovered Services")
    table.add_column("Service", style="cyan")
    table.add_column("Container", style="white")
    table.add_column("URL", style="green")
    table.add_column("Ports", style="yellow")
    table.add_column("Status", style="magenta")
    
    for service_name, service_info in discovered.items():
        # Check if service already exists in registry
        existing = registry.get_service(service_name)
        status = "🆕 New" if not existing else "🔄 Update" if existing.url != service_info.get("url") else "✅ Current"
        
        table.add_row(
            service_name,
            service_info.get("container", ""),
            service_info.get("url", ""),
            ", ".join(map(str, service_info.get("ports", []))),
            status
        )
    
    console.print(table)
    
    if save:
        updated_count = 0
        for service_name, service_info in discovered.items():
            from .registry import ServiceRef
            svc = ServiceRef(
                name=service_name,
                url=service_info.get("url"),
                container=service_info.get("container")
            )
            registry.set_service(svc)
            updated_count += 1
        
        registry.save()
        console.print(f"[green]✓[/green] {updated_count} services saved to registry")


@registry.command("validate")
def registry_validate() -> None:
    """Validate all services in registry."""
    registry = Registry.load()
    
    services = registry.list_services()
    if not services:
        console.print("[yellow]No services configured in registry[/yellow]")
        return
    
    table = Table(title="Service Validation")
    table.add_column("Service", style="cyan")
    table.add_column("Status", style="white")
    table.add_column("Response", style="green")
    table.add_column("Notes", style="yellow")
    
    import requests
    
    for service_name in services:
        service = registry.get_service(service_name)
        if not service or not service.url:
            table.add_row(service_name, "❌", "No URL", "Service not configured")
            continue
        
        try:
            # Test basic connectivity
            response = requests.get(service.url, timeout=5)
            if response.status_code == 200:
                table.add_row(service_name, "✅", f"HTTP {response.status_code}", "OK")
            elif response.status_code == 401:
                table.add_row(service_name, "⚠️", f"HTTP {response.status_code}", "Auth required")
            else:
                table.add_row(service_name, "⚠️", f"HTTP {response.status_code}", "Unexpected response")
        except requests.exceptions.ConnectionError:
            table.add_row(service_name, "❌", "Connection failed", "Service unreachable")
        except requests.exceptions.Timeout:
            table.add_row(service_name, "⚠️", "Timeout", "Service slow to respond")
        except Exception as e:
            table.add_row(service_name, "❌", "Error", str(e)[:50])
    
    console.print(table)


@registry.command("secret")
@click.argument("action", type=click.Choice(["set", "get", "delete"]))
@click.argument("ref_id")
@click.option("--value", help="Secret value (for set action)")
def registry_secret(action: str, ref_id: str, value: Optional[str]) -> None:
    """Manage secrets in OS keyring."""
    registry = Registry.load()
    
    if action == "set":
        if not value:
            value = click.prompt("Enter secret value", hide_input=True)
        registry.set_secret(ref_id, value)
        console.print(f"[green]✓[/green] Secret '{ref_id}' set")
    
    elif action == "get":
        secret = registry.get_secret(ref_id)
        if secret:
            console.print(f"[green]✓[/green] Secret '{ref_id}': {registry.redact(secret)}")
        else:
            console.print(f"[red]✗[/red] Secret '{ref_id}' not found")
    
    elif action == "delete":
        # Note: keyring doesn't have a delete method in all backends
        console.print(f"[yellow]Deleting secrets not supported in all keyring backends[/yellow]")


def cli_main():
    """Internal CLI main function."""
    cli_group()


def main(argv=None):
    """Main entry point for the CLI."""
    try:
        if argv is None:
            cli_main()
        else:
            # Handle command line arguments when called programmatically
            import sys
            original_argv = sys.argv
            sys.argv = ["mediastack-doctor"] + argv
            try:
                cli_main()
            finally:
                sys.argv = original_argv
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
