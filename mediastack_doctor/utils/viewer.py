"""Interactive viewer for MediaStack Doctor reports."""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

# Graceful rich import
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.prompt import Prompt, IntPrompt, Confirm
    from rich.text import Text
    from rich.columns import Columns
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    Console = None
    Table = None
    Panel = None
    Prompt = None
    IntPrompt = None
    Text = None
    Columns = None


def load_report_data(report_path: Path) -> Optional[Dict[str, Any]]:
    """Load report data from JSON file."""
    try:
        with open(report_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, PermissionError) as e:
        return None


def load_markdown_report(report_path: Path) -> Optional[str]:
    """Load markdown report content."""
    try:
        with open(report_path, 'r') as f:
            return f.read()
    except (FileNotFoundError, PermissionError):
        return None


def truncate_text(text: str, max_length: int = 120) -> str:
    """Truncate text to max_length with ellipsis."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."


def show_summary(data: Dict[str, Any], console: Optional[Console] = None) -> None:
    """Show diagnostic summary."""
    summary = data.get("summary", {})
    
    if console and HAS_RICH:
        table = Table(title="Diagnostic Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Total Checks", str(summary.get("total", 0)))
        table.add_row("Passed", str(summary.get("passed", 0)))
        table.add_row("Warnings", str(summary.get("warnings", 0)))
        table.add_row("Failed", str(summary.get("failed", 0)))
        table.add_row("Success Rate", f"{summary.get('success_rate', 0):.1f}%")
        
        console.print(table)
    else:
        print("\n=== Diagnostic Summary ===")
        print(f"Total Checks: {summary.get('total', 0)}")
        print(f"Passed: {summary.get('passed', 0)}")
        print(f"Warnings: {summary.get('warnings', 0)}")
        print(f"Failed: {summary.get('failed', 0)}")
        print(f"Success Rate: {summary.get('success_rate', 0):.1f}%")


def _compute_stats(items):
    """Compute statistics for a list of checks."""
    stats = {"total": 0, "passed": 0, "warnings": 0, "failed": 0}
    for check in items:
        stats["total"] += 1
        severity = (check.get("severity") or "").lower()
        if severity in ("pass", "ok", "success", "info"):
            stats["passed"] += 1
        elif severity in ("warn", "warning"):
            stats["warnings"] += 1
        elif severity in ("fail", "error", "fatal"):
            stats["failed"] += 1
    return stats

def show_categories(data: Dict[str, Any], console: Optional[Console] = None) -> None:
    """Show checks by category."""
    categories = data.get("categories", {})
    
    if console and HAS_RICH:
        table = Table(title="Checks by Category")
        table.add_column("Category", style="cyan")
        table.add_column("Total", style="white")
        table.add_column("Passed", style="green")
        table.add_column("Warnings", style="yellow")
        table.add_column("Failed", style="red")
        
        for category, payload in categories.items():
            # Handle both new format (with stats) and old format (direct list)
            if isinstance(payload, dict) and "stats" in payload:
                # New format with pre-computed stats
                stats = payload["stats"]
                table.add_row(
                    category,
                    str(stats.get("total", 0)),
                    str(stats.get("passed", 0)),
                    str(stats.get("warnings", 0)),
                    str(stats.get("failed", 0))
                )
            else:
                # Old format - compute stats from checks
                checks = payload if isinstance(payload, list) else payload.get("checks", [])
                stats = _compute_stats(checks)
                table.add_row(
                    category,
                    str(stats["total"]),
                    str(stats["passed"]),
                    str(stats["warnings"]),
                    str(stats["failed"])
                )
        
        console.print(table)
    else:
        print("\n=== Checks by Category ===")
        for category, payload in categories.items():
            # Handle both new format (with stats) and old format (direct list)
            if isinstance(payload, dict) and "stats" in payload:
                # New format with pre-computed stats
                stats = payload["stats"]
                print(f"{category}: {stats.get('total', 0)} total "
                      f"({stats.get('passed', 0)}✅ {stats.get('warnings', 0)}⚠️ {stats.get('failed', 0)}❌)")
            else:
                # Old format - compute stats from checks
                checks = payload if isinstance(payload, list) else payload.get("checks", [])
                stats = _compute_stats(checks)
                print(f"{category}: {stats['total']} total "
                      f"({stats['passed']}✅ {stats['warnings']}⚠️ {stats['failed']}❌)")


def show_warn_fail_only(data: Dict[str, Any], console: Optional[Console] = None) -> None:
    """Show only WARN and FAIL checks."""
    checks = data.get("checks", [])
    warn_fail_checks = [c for c in checks if c.get("severity") in ["warn", "fail"]]
    
    if not warn_fail_checks:
        if console and HAS_RICH:
            console.print("[green]No warnings or failures found![/green]")
        else:
            print("No warnings or failures found!")
        return
    
    if console and HAS_RICH:
        table = Table(title="Warnings and Failures")
        table.add_column("ID", style="cyan")
        table.add_column("Category", style="white")
        table.add_column("Title", style="yellow")
        table.add_column("Severity", style="red")
        table.add_column("Evidence", style="white")
        
        for check in warn_fail_checks:
            severity_style = "red" if check.get("severity") == "fail" else "yellow"
            table.add_row(
                check.get("id", "N/A"),
                check.get("category", "Unknown"),
                check.get("title", "Unknown"),
                f"[{severity_style}]{check.get('severity', 'unknown').upper()}[/{severity_style}]",
                truncate_text(check.get("evidence", ""))
            )
        
        console.print(table)
    else:
        print("\n=== Warnings and Failures ===")
        for check in warn_fail_checks:
            severity = check.get("severity", "unknown").upper()
            print(f"{check.get('id', 'N/A')} [{severity}] {check.get('title', 'Unknown')}")
            print(f"  Evidence: {truncate_text(check.get('evidence', ''))}")


def show_check_details(check_id: str, data: Dict[str, Any], console: Optional[Console] = None, verbose: bool = False) -> None:
    """Show detailed information for a specific check."""
    checks = data.get("checks", [])
    check = next((c for c in checks if c.get("id") == check_id), None)
    
    if not check:
        if console and HAS_RICH:
            console.print(f"[red]Check '{check_id}' not found[/red]")
        else:
            print(f"Check '{check_id}' not found")
        return
    
    if console and HAS_RICH:
        # Create detailed panel
        content = f"""
[bold]ID:[/bold] {check.get('id', 'N/A')}
[bold]Category:[/bold] {check.get('category', 'Unknown')}
[bold]Title:[/bold] {check.get('title', 'Unknown')}
[bold]Severity:[/bold] {check.get('severity', 'unknown').upper()}

[bold]Evidence:[/bold]
{check.get('evidence', 'Not available')}

[bold]Why it matters:[/bold]
{check.get('why_it_matters', 'Not available')}

[bold]Suggested fix:[/bold]
{check.get('suggested_fix', 'Not available')}
"""
        
        # Add verbose details if requested
        if verbose and check.get("severity") in ["warn", "fail"]:
            content += "\n[bold]Verbose Details:[/bold]\n"
            
            # Container evidence
            if check.get("container_evidence"):
                container_evidence = check["container_evidence"]
                content += f"""
[bold]Container Details:[/bold]
  Status: {container_evidence.get('status', 'N/A')}
  Health: {container_evidence.get('health_status', 'N/A')}
  Restart Count: {container_evidence.get('restart_count', 'N/A')}
  Exit Code: {container_evidence.get('exit_code', 'N/A')}
  Ports: {', '.join(container_evidence.get('ports', [])) or 'None'}
  Networks: {', '.join(container_evidence.get('networks', [])) or 'None'}
  Volumes: {', '.join(container_evidence.get('volumes', [])) or 'None'}
"""
                
                if container_evidence.get("log_errors"):
                    content += "\n[bold]Recent Log Errors:[/bold]\n"
                    for error in container_evidence["log_errors"]:
                        content += f"  [red]{error}[/red]\n"
            
            # Reproduce commands
            content += "\n[bold]Reproduce Commands:[/bold]\n"
            check_id_val = check.get("id", "")
            if check_id_val.startswith("H1"):
                content += "  [dim]top -H -o %CPU[/dim]\n"
                content += "  [dim]ps aux --sort=-%cpu | head -10[/dim]\n"
            elif check_id_val.startswith("H16"):
                content += "  [dim]sensors[/dim]\n"
                content += "  [dim]cat /sys/class/thermal/thermal_zone*/temp[/dim]\n"
            elif check_id_val.startswith("D2"):
                container_name = check.get("title", "").split(" - ")[1] if " - " in check.get("title", "") else "container"
                content += f"  [dim]docker inspect {container_name} --format '{{json .State}}' | jq .[/dim]\n"
                content += f"  [dim]docker logs {container_name} --tail 50[/dim]\n"
            else:
                content += f"  [dim]# Check {check.get('title', 'Unknown')}[/dim]\n"
                content += f"  [dim]# Evidence: {check.get('evidence', 'N/A')}[/dim]\n"
        
        severity_color = "red" if check.get("severity") == "fail" else "yellow" if check.get("severity") == "warn" else "green"
        panel = Panel(content, title=f"Check Details: {check_id}", border_style=severity_color)
        console.print(panel)
    else:
        print(f"\n=== Check Details: {check_id} ===")
        print(f"ID: {check.get('id', 'N/A')}")
        print(f"Category: {check.get('category', 'Unknown')}")
        print(f"Title: {check.get('title', 'Unknown')}")
        print(f"Severity: {check.get('severity', 'unknown').upper()}")
        print(f"\nEvidence: {check.get('evidence', 'Not available')}")
        print(f"\nWhy it matters: {check.get('why_it_matters', 'Not available')}")
        print(f"\nSuggested fix: {check.get('suggested_fix', 'Not available')}")
        
        # Show verbose details if requested
        if verbose and check.get("severity") in ["warn", "fail"]:
            print(f"\nVerbose Details:")
            
            # Container evidence
            if check.get("container_evidence"):
                container_evidence = check["container_evidence"]
                print(f"Container Details:")
                print(f"  Status: {container_evidence.get('status', 'N/A')}")
                print(f"  Health: {container_evidence.get('health_status', 'N/A')}")
                print(f"  Restart Count: {container_evidence.get('restart_count', 'N/A')}")
                print(f"  Exit Code: {container_evidence.get('exit_code', 'N/A')}")
                print(f"  Ports: {', '.join(container_evidence.get('ports', [])) or 'None'}")
                print(f"  Networks: {', '.join(container_evidence.get('networks', [])) or 'None'}")
                print(f"  Volumes: {', '.join(container_evidence.get('volumes', [])) or 'None'}")
                
                if container_evidence.get("log_errors"):
                    print(f"Recent Log Errors:")
                    for error in container_evidence["log_errors"]:
                        print(f"  {error}")
            
            # Reproduce commands
            print(f"\nReproduce Commands:")
            check_id_val = check.get("id", "")
            if check_id_val.startswith("H1"):
                print("  top -H -o %CPU")
                print("  ps aux --sort=-%cpu | head -10")
            elif check_id_val.startswith("H16"):
                print("  sensors")
                print("  cat /sys/class/thermal/thermal_zone*/temp")
            elif check_id_val.startswith("D2"):
                container_name = check.get("title", "").split(" - ")[1] if " - " in check.get("title", "") else "container"
                print(f"  docker inspect {container_name} --format '{{json .State}}' | jq .")
                print(f"  docker logs {container_name} --tail 50")
            else:
                print(f"  # Check {check.get('title', 'Unknown')}")
                print(f"  # Evidence: {check.get('evidence', 'N/A')}")


def show_advisor_recommendations(data: Dict[str, Any], console: Optional[Console] = None) -> None:
    """Show advisor recommendations."""
    recommendations = data.get("advisor_fixes", [])
    
    if not recommendations:
        if console and HAS_RICH:
            console.print("[green]No advisor recommendations available[/green]")
        else:
            print("No advisor recommendations available")
        return
    
    if console and HAS_RICH:
        console.print("\n[bold]Advisor Recommendations[/bold]")
        for i, rec in enumerate(recommendations, 1):
            console.print(f"{i}. {rec}")
    else:
        print("\n=== Advisor Recommendations ===")
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec}")


def search_checks(keyword: str, data: Dict[str, Any], console: Optional[Console] = None) -> None:
    """Search checks by keyword."""
    checks = data.get("checks", [])
    keyword_lower = keyword.lower()
    
    matching_checks = []
    for check in checks:
        searchable_text = " ".join([
            check.get("title", ""),
            check.get("evidence", ""),
            check.get("why_it_matters", ""),
            check.get("suggested_fix", "")
        ]).lower()
        
        if keyword_lower in searchable_text:
            matching_checks.append(check)
    
    if not matching_checks:
        if console and HAS_RICH:
            console.print(f"[yellow]No checks found matching '{keyword}'[/yellow]")
        else:
            print(f"No checks found matching '{keyword}'")
        return
    
    if console and HAS_RICH:
        table = Table(title=f"Search Results for '{keyword}'")
        table.add_column("ID", style="cyan")
        table.add_column("Title", style="white")
        table.add_column("Severity", style="white")
        table.add_column("Evidence", style="white")
        
        for check in matching_checks:
            severity_style = "red" if check.get("severity") == "fail" else "yellow" if check.get("severity") == "warn" else "green"
            table.add_row(
                check.get("id", "N/A"),
                check.get("title", "Unknown"),
                f"[{severity_style}]{check.get('severity', 'unknown').upper()}[/{severity_style}]",
                truncate_text(check.get("evidence", ""))
            )
        
        console.print(table)
    else:
        print(f"\n=== Search Results for '{keyword}' ===")
        for check in matching_checks:
            severity = check.get("severity", "unknown").upper()
            print(f"{check.get('id', 'N/A')} [{severity}] {check.get('title', 'Unknown')}")
            print(f"  Evidence: {truncate_text(check.get('evidence', ''))}")


def list_available_runs(outputs_dir: Path) -> List[Path]:
    """List available run directories."""
    if not outputs_dir.exists():
        return []
    
    runs = []
    for item in outputs_dir.iterdir():
        if item.is_dir() and (item / "report.json").exists():
            runs.append(item)
    
    # Sort by modification time (newest first)
    runs.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return runs


def run_browser(outputs_path: Path) -> int:
    """Run the interactive browser."""
    console = Console() if HAS_RICH else None
    
    # Determine if we're looking at a specific run or outputs directory
    if outputs_path.is_file() and outputs_path.name == "report.json":
        # Specific report file
        report_path = outputs_path
        run_dir = report_path.parent
    elif outputs_path.is_dir() and (outputs_path / "report.json").exists():
        # Specific run directory
        report_path = outputs_path / "report.json"
        run_dir = outputs_path
    elif outputs_path.is_dir():
        # Outputs directory - need to select a run
        available_runs = list_available_runs(outputs_path)
        if not available_runs:
            if console and HAS_RICH:
                console.print(f"[yellow]No diagnostic runs found in {outputs_path}[/yellow]")
                console.print("[blue]Run 'mediastack-doctor run' to create your first diagnostic report[/blue]")
            else:
                print(f"No diagnostic runs found in {outputs_path}")
                print("Run 'mediastack-doctor run' to create your first diagnostic report")
            return 0
        
        # Show available runs and let user select with arrow navigation
        from ..utils.menu_navigation import create_menu
        
        # Create run selection menu
        run_options = []
        for i, run in enumerate(available_runs[:10], 1):  # Show latest 10
            run_options.append((str(i), f"📊 {run.name}", f"View diagnostic run from {run.name}"))
        run_options.append(("0", "⬅️ Exit", "Exit report browser"))
        
        try:
            choice = create_menu(f"Select Diagnostic Run from {outputs_path.name}", run_options, console)
            
            if choice == "0":
                return 0
            
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(available_runs):
                selected_run = available_runs[choice_idx]
                report_path = selected_run / "report.json"
                run_dir = selected_run
            else:
                if console and HAS_RICH:
                    console.print("[red]Invalid selection[/red]")
                else:
                    print("Invalid selection")
                return 1
        except (KeyboardInterrupt, EOFError):
            return 0
    else:
        if console and HAS_RICH:
            console.print(f"[red]Invalid path: {outputs_path}[/red]")
            console.print("[blue]Please provide a path to a report.json file, run directory, or outputs directory[/blue]")
        else:
            print(f"Invalid path: {outputs_path}")
            print("Please provide a path to a report.json file, run directory, or outputs directory")
        return 1
    
    # Load report data
    data = load_report_data(report_path)
    if not data:
        if console and HAS_RICH:
            console.print(f"[red]Could not load report from {report_path}[/red]")
        else:
            print(f"Could not load report from {report_path}")
        return 1
    
    # Main menu loop
    while True:
        from ..utils.menu_navigation import create_menu
        
        # Show current run info
        if console and HAS_RICH:
            console.print(f"\n[bold blue]📊 Report Browser[/bold blue]")
            console.print(f"[dim]Viewing: {run_dir.name}[/dim]\n")
        else:
            print(f"\n📊 Report Browser")
            print(f"Viewing: {run_dir.name}\n")
        
        browser_options = [
            ("1", "📋 Summary", "View diagnostic summary"),
            ("2", "📁 Browse Categories", "Explore checks by category"),
            ("3", "⚠️ Show WARN/FAIL Only", "View only issues that need attention"),
            ("4", "🔍 View Specific Check", "Look up a check by ID"),
            ("5", "🔧 Advisor Recommendations", "View actionable fixes"),
            ("6", "🔎 Search Checks", "Search checks by keyword"),
            ("7", "🔄 Switch Run", "Select a different diagnostic run"),
            ("8", "🚪 Exit", "Exit report browser")
        ]
        
        try:
            choice = create_menu("Report Browser Menu", browser_options, console)
        except (KeyboardInterrupt, EOFError):
            return 0
        
        if choice == "1":
            show_summary(data, console)
        elif choice == "2":
            show_categories(data, console)
        elif choice == "3":
            show_warn_fail_only(data, console)
        elif choice == "4":
            if console and HAS_RICH:
                check_id = Prompt.ask("Enter check ID")
                verbose = Confirm.ask("Show verbose details?", default=False)
            else:
                check_id = input("Enter check ID: ").strip()
                verbose_input = input("Show verbose details? (y/N): ").strip().lower()
                verbose = verbose_input in ['y', 'yes']
            show_check_details(check_id, data, console, verbose)
        elif choice == "5":
            show_advisor_recommendations(data, console)
        elif choice == "6":
            if console and HAS_RICH:
                keyword = Prompt.ask("Enter search keyword")
            else:
                keyword = input("Enter search keyword: ").strip()
            search_checks(keyword, data, console)
        elif choice == "7":
            # Switch run - restart browser with outputs directory
            return run_browser(outputs_path.parent if outputs_path.name == "report.json" else outputs_path)
        elif choice == "8":
            return 0
        else:
            if console and HAS_RICH:
                console.print("[red]Invalid choice[/red]")
            else:
                print("Invalid choice")
        
        if console and HAS_RICH:
            Prompt.ask("\nPress Enter to continue", default="")
        else:
            input("\nPress Enter to continue...")
    
    return 0
