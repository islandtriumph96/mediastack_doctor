"""Diff utilities for comparing diagnostic runs."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def diff_runs(prev_run_dir: Path, current_run_dir: Path) -> Optional[str]:
    """Compare two diagnostic runs and return a diff summary."""
    try:
        # Load previous run manifest
        prev_manifest = _load_run_manifest(prev_run_dir)
        if not prev_manifest:
            return None
        
        # Load current run manifest
        current_manifest = _load_run_manifest(current_run_dir)
        if not current_manifest:
            return None
        
        # Compare checks
        changes = _compare_checks(prev_manifest.get("checks", {}), current_manifest.get("checks", {}))
        
        if not changes:
            return None
        
        # Format changes
        return _format_changes(changes)
    
    except Exception as e:
        return f"Error comparing runs: {e}"


def _load_run_manifest(run_dir: Path) -> Optional[Dict[str, Any]]:
    """Load run manifest from directory."""
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.exists():
        return None
    
    try:
        with open(manifest_path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _compare_checks(prev_checks: Dict[str, Any], current_checks: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Compare checks between two runs."""
    changes = []
    
    # Get all check IDs
    all_check_ids = set(prev_checks.keys()) | set(current_checks.keys())
    
    for check_id in all_check_ids:
        prev_check = prev_checks.get(check_id)
        current_check = current_checks.get(check_id)
        
        if not prev_check and current_check:
            # New check
            changes.append({
                "type": "new",
                "check_id": check_id,
                "title": current_check.get("title", "Unknown"),
                "severity": current_check.get("severity", "info"),
            })
        elif prev_check and not current_check:
            # Removed check
            changes.append({
                "type": "removed",
                "check_id": check_id,
                "title": prev_check.get("title", "Unknown"),
                "severity": prev_check.get("severity", "info"),
            })
        elif prev_check and current_check:
            # Check exists in both, compare
            prev_severity = prev_check.get("severity", "info")
            current_severity = current_check.get("severity", "info")
            
            if prev_severity != current_severity:
                changes.append({
                    "type": "severity_change",
                    "check_id": check_id,
                    "title": current_check.get("title", "Unknown"),
                    "prev_severity": prev_severity,
                    "current_severity": current_severity,
                })
            
            # Check if evidence changed significantly
            prev_evidence = prev_check.get("evidence", "")
            current_evidence = current_check.get("evidence", "")
            
            if prev_evidence != current_evidence and _is_significant_change(prev_evidence, current_evidence):
                changes.append({
                    "type": "evidence_change",
                    "check_id": check_id,
                    "title": current_check.get("title", "Unknown"),
                    "prev_evidence": prev_evidence,
                    "current_evidence": current_evidence,
                })
    
    return changes


def _is_significant_change(prev_evidence: str, current_evidence: str) -> bool:
    """Determine if evidence change is significant enough to report."""
    # Skip if both are empty
    if not prev_evidence and not current_evidence:
        return False
    
    # Skip if only whitespace differences
    if prev_evidence.strip() == current_evidence.strip():
        return False
    
    # Skip if both contain similar numbers (e.g., "23.4%" vs "23.5%")
    import re
    prev_numbers = re.findall(r'\d+\.?\d*', prev_evidence)
    current_numbers = re.findall(r'\d+\.?\d*', current_evidence)
    
    if prev_numbers and current_numbers and len(prev_numbers) == len(current_numbers):
        # Check if numbers are very close
        try:
            prev_vals = [float(n) for n in prev_numbers]
            current_vals = [float(n) for n in current_numbers]
            
            # If all numbers are within 5% of each other, consider it insignificant
            significant = False
            for p, c in zip(prev_vals, current_vals):
                if p > 0 and abs(p - c) / p > 0.05:  # 5% threshold
                    significant = True
                    break
            
            if not significant:
                return False
        except ValueError:
            pass  # Not all numbers, continue with normal comparison
    
    return True


def _format_changes(changes: List[Dict[str, Any]]) -> str:
    """Format changes into a readable summary."""
    if not changes:
        return "No significant changes detected."
    
    output = []
    
    # Group changes by type
    new_checks = [c for c in changes if c["type"] == "new"]
    removed_checks = [c for c in changes if c["type"] == "removed"]
    severity_changes = [c for c in changes if c["type"] == "severity_change"]
    evidence_changes = [c for c in changes if c["type"] == "evidence_change"]
    
    # New checks
    if new_checks:
        output.append("🆕 **New Checks:**")
        for change in new_checks:
            severity_icon = _get_severity_icon(change["severity"])
            output.append(f"  {severity_icon} {change['check_id']}: {change['title']}")
        output.append("")
    
    # Removed checks
    if removed_checks:
        output.append("🗑️ **Removed Checks:**")
        for change in removed_checks:
            severity_icon = _get_severity_icon(change["severity"])
            output.append(f"  {severity_icon} {change['check_id']}: {change['title']}")
        output.append("")
    
    # Severity changes
    if severity_changes:
        output.append("📊 **Severity Changes:**")
        for change in severity_changes:
            prev_icon = _get_severity_icon(change["prev_severity"])
            current_icon = _get_severity_icon(change["current_severity"])
            output.append(f"  {prev_icon} → {current_icon} {change['check_id']}: {change['title']}")
        output.append("")
    
    # Evidence changes
    if evidence_changes:
        output.append("📝 **Evidence Changes:**")
        for change in evidence_changes:
            output.append(f"  🔄 {change['check_id']}: {change['title']}")
            if len(change['prev_evidence']) > 100:
                prev_short = change['prev_evidence'][:100] + "..."
            else:
                prev_short = change['prev_evidence']
            
            if len(change['current_evidence']) > 100:
                current_short = change['current_evidence'][:100] + "..."
            else:
                current_short = change['current_evidence']
            
            output.append(f"    Before: {prev_short}")
            output.append(f"    After:  {current_short}")
        output.append("")
    
    return "\n".join(output)


def _get_severity_icon(severity: str) -> str:
    """Get icon for severity level."""
    icons = {
        "info": "✅",
        "warn": "⚠️",
        "fail": "❌",
    }
    return icons.get(severity, "❓")


def save_run_manifest(run_dir: Path, timestamp: str, checks: List[Dict[str, Any]]) -> None:
    """Save run manifest for future diffing."""
    manifest = {
        "timestamp": timestamp,
        "checks": {}
    }
    
    # Create simplified check data for diffing
    for check in checks:
        check_id = check.get("id", "")
        if check_id:
            manifest["checks"][check_id] = {
                "title": check.get("title", ""),
                "severity": check.get("severity", "info"),
                "evidence": check.get("evidence", ""),
                "category": check.get("category", ""),
            }
    
    # Save manifest
    manifest_path = run_dir / "run_manifest.json"
    try:
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
    except OSError as e:
        print(f"Warning: Could not save run manifest: {e}")


def get_last_run_id(output_dir: Path) -> Optional[str]:
    """Get the ID of the most recent run."""
    run_dirs = [d for d in output_dir.iterdir() if d.is_dir()]
    if not run_dirs:
        return None
    
    # Sort by directory name (timestamp) and return the latest
    latest_run = max(run_dirs, key=lambda d: d.name)
    return latest_run.name
