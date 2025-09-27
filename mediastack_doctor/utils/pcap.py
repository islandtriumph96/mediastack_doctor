"""Packet capture utilities for network analysis."""

import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional


def capture_top_talkers(
    duration: int = 8,
    interface: Optional[str] = None,
    output_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """Capture network traffic and analyze top talkers."""
    
    # Check if tcpdump is available
    try:
        result = subprocess.run(
            ["tcpdump", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            return {
                "available": False,
                "reason": "tcpdump not available",
                "top_flows": [],
                "summary": "tcpdump not installed"
            }
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {
            "available": False,
            "reason": "tcpdump not available",
            "top_flows": [],
            "summary": "tcpdump not installed"
        }
    
    # Determine interface
    if not interface:
        interface = _get_default_interface()
    
    if not interface:
        return {
            "available": False,
            "reason": "No suitable network interface found",
            "top_flows": [],
            "summary": "No network interface available"
        }
    
    # Create temporary pcap file
    with tempfile.NamedTemporaryFile(suffix=".pcap", delete=False) as pcap_file:
        pcap_path = pcap_file.name
    
    try:
        # Run tcpdump
        cmd = [
            "tcpdump",
            "-i", interface,
            "-w", pcap_path,
            "-c", "1000",  # Limit to 1000 packets
            "-s", "0",     # Capture full packets
            "ip",          # Only IP traffic
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=duration + 5
        )
        
        if result.returncode != 0 and "packets captured" not in result.stderr:
            return {
                "available": False,
                "reason": f"tcpdump failed: {result.stderr.strip()}",
                "top_flows": [],
                "summary": "tcpdump capture failed"
            }
        
        # Analyze the pcap file
        top_flows = _analyze_pcap_file(pcap_path)
        
        # Clean up
        Path(pcap_path).unlink(missing_ok=True)
        
        return {
            "available": True,
            "interface": interface,
            "duration": duration,
            "top_flows": top_flows,
            "summary": f"Captured {len(top_flows)} top flows on {interface}"
        }
    
    except subprocess.TimeoutExpired:
        # Clean up on timeout
        Path(pcap_path).unlink(missing_ok=True)
        return {
            "available": False,
            "reason": "tcpdump timed out",
            "top_flows": [],
            "summary": "Capture timed out"
        }
    except Exception as e:
        # Clean up on error
        Path(pcap_path).unlink(missing_ok=True)
        return {
            "available": False,
            "reason": f"Capture error: {e}",
            "top_flows": [],
            "summary": "Capture failed"
        }


def _get_default_interface() -> Optional[str]:
    """Get the default network interface."""
    try:
        # Try to get the default route interface
        result = subprocess.run(
            ["ip", "route", "show", "default"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'default via' in line:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == 'dev' and i + 1 < len(parts):
                            return parts[i + 1]
        
        # Fallback: get first active interface
        result = subprocess.run(
            ["ip", "link", "show"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if ': ' in line and 'state UP' in line:
                    interface = line.split(':')[1].strip()
                    if interface and not interface.startswith('lo'):
                        return interface
        
        return None
    
    except Exception:
        return None


def _analyze_pcap_file(pcap_path: str) -> List[Dict[str, Any]]:
    """Analyze pcap file to find top talkers."""
    try:
        # Use tcpdump to extract flow information
        cmd = [
            "tcpdump",
            "-r", pcap_path,
            "-n",  # Don't resolve hostnames
            "-q",  # Quiet mode
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            return []
        
        # Parse tcpdump output to extract flows
        flows = {}
        
        for line in result.stdout.split('\n'):
            if not line.strip():
                continue
            
            # Extract source and destination from tcpdump output
            # Format: timestamp src > dst: flags seq ack win options length
            try:
                parts = line.split()
                if len(parts) < 4:
                    continue
                
                # Find the '>' which separates src and dst
                arrow_idx = -1
                for i, part in enumerate(parts):
                    if part == '>':
                        arrow_idx = i
                        break
                
                if arrow_idx == -1 or arrow_idx < 1 or arrow_idx + 1 >= len(parts):
                    continue
                
                src = parts[arrow_idx - 1]
                dst = parts[arrow_idx + 1]
                
                # Remove port numbers for aggregation
                src_ip = src.split(':')[0] if ':' in src else src
                dst_ip = dst.split(':')[0] if ':' in dst else dst
                
                # Create flow key (bidirectional)
                flow_key = tuple(sorted([src_ip, dst_ip]))
                
                # Extract packet length (last number in the line)
                length = 0
                for part in reversed(parts):
                    if part.isdigit():
                        length = int(part)
                        break
                
                if flow_key not in flows:
                    flows[flow_key] = {
                        "src": src_ip,
                        "dst": dst_ip,
                        "packets": 0,
                        "bytes": 0
                    }
                
                flows[flow_key]["packets"] += 1
                flows[flow_key]["bytes"] += length
            
            except (ValueError, IndexError):
                continue
        
        # Sort by bytes and return top 5
        sorted_flows = sorted(
            flows.values(),
            key=lambda x: x["bytes"],
            reverse=True
        )
        
        return sorted_flows[:5]
    
    except Exception:
        return []


def get_top_ports(pcap_path: str) -> List[Dict[str, Any]]:
    """Get top ports from pcap file."""
    try:
        # Use tcpdump to extract port information
        cmd = [
            "tcpdump",
            "-r", pcap_path,
            "-n",  # Don't resolve hostnames
            "-q",  # Quiet mode
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            return []
        
        # Parse tcpdump output to extract ports
        ports = {}
        
        for line in result.stdout.split('\n'):
            if not line.strip():
                continue
            
            try:
                parts = line.split()
                if len(parts) < 4:
                    continue
                
                # Find the '>' which separates src and dst
                arrow_idx = -1
                for i, part in enumerate(parts):
                    if part == '>':
                        arrow_idx = i
                        break
                
                if arrow_idx == -1 or arrow_idx < 1 or arrow_idx + 1 >= len(parts):
                    continue
                
                src = parts[arrow_idx - 1]
                dst = parts[arrow_idx + 1]
                
                # Extract ports
                src_port = None
                dst_port = None
                
                if ':' in src:
                    src_port = src.split(':')[1]
                if ':' in dst:
                    dst_port = dst.split(':')[1]
                
                # Count both source and destination ports
                for port in [src_port, dst_port]:
                    if port and port.isdigit():
                        port_num = int(port)
                        if port_num not in ports:
                            ports[port_num] = {"port": port_num, "packets": 0}
                        ports[port_num]["packets"] += 1
            
            except (ValueError, IndexError):
                continue
        
        # Sort by packet count and return top 5
        sorted_ports = sorted(
            ports.values(),
            key=lambda x: x["packets"],
            reverse=True
        )
        
        return sorted_ports[:5]
    
    except Exception:
        return []
