#!/usr/bin/env python3
"""Example usage of MediaStack Doctor."""

import subprocess
import sys
from pathlib import Path

def main():
    """Demonstrate MediaStack Doctor usage."""
    print("MediaStack Doctor - Example Usage")
    print("=" * 40)
    
    # Check if mediastack-doctor is installed
    try:
        result = subprocess.run(["mediastack-doctor", "--version"], 
                              capture_output=True, text=True, check=True)
        print(f"✓ MediaStack Doctor installed: {result.stdout.strip()}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("✗ MediaStack Doctor not found. Please install it first:")
        print("  pip install -e .")
        return 1
    
    print("\n1. Discovering services from Docker...")
    try:
        result = subprocess.run(["mediastack-doctor", "registry", "discover"], 
                              capture_output=True, text=True, check=True)
        print("✓ Service discovery completed")
        if result.stdout:
            print("Discovered services:")
            print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"⚠ Service discovery failed: {e}")
    
    print("\n2. Running diagnostics...")
    try:
        result = subprocess.run([
            "mediastack-doctor", "diagnose",
            "--output-dir", "./example_output"
        ], capture_output=True, text=True, check=True)
        print("✓ Diagnostics completed")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"✗ Diagnostics failed: {e}")
        print(f"Error output: {e.stderr}")
        return 1
    
    print("\n3. Checking output files...")
    output_dir = Path("./example_output")
    if output_dir.exists():
        for file_path in output_dir.rglob("*"):
            if file_path.is_file():
                size = file_path.stat().st_size
                print(f"✓ {file_path.relative_to(output_dir)} ({size} bytes)")
    else:
        print("⚠ No output directory found")
    
    print("\n4. Example registry commands:")
    print("  # Set qBittorrent configuration")
    print("  mediastack-doctor registry set qbittorrent --url http://localhost:8081 --username admin --password-secret-ref qb_password")
    print("  mediastack-doctor registry secret set qb_password")
    print()
    print("  # Set Radarr configuration")
    print("  mediastack-doctor registry set radarr --url http://localhost:7878 --api-key-secret-ref radarr_apikey")
    print("  mediastack-doctor registry secret set radarr_apikey")
    print()
    print("  # View configuration")
    print("  mediastack-doctor registry get qbittorrent")
    print("  mediastack-doctor registry validate")
    
    print("\n✓ Example usage completed!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
