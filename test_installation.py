#!/usr/bin/env python3
"""Test MediaStack Doctor installation and basic functionality."""

import sys
from pathlib import Path

def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...")
    
    try:
        import docker
        print("✓ docker")
    except ImportError as e:
        print(f"✗ docker: {e}")
        return False
    
    try:
        import psutil
        print("✓ psutil")
    except ImportError as e:
        print(f"✗ psutil: {e}")
        return False
    
    try:
        import rich
        print("✓ rich")
    except ImportError as e:
        print(f"✗ rich: {e}")
        return False
    
    try:
        import requests
        print("✓ requests")
    except ImportError as e:
        print(f"✗ requests: {e}")
        return False
    
    try:
        import yaml
        print("✓ pyyaml")
    except ImportError as e:
        print(f"✗ pyyaml: {e}")
        return False
    
    try:
        import jinja2
        print("✓ jinja2")
    except ImportError as e:
        print(f"✗ jinja2: {e}")
        return False
    
    try:
        import keyring
        print("✓ keyring")
    except ImportError as e:
        print(f"✗ keyring: {e}")
        return False
    
    try:
        import click
        print("✓ click")
    except ImportError as e:
        print(f"✗ click: {e}")
        return False
    
    return True

def test_mediastack_doctor():
    """Test MediaStack Doctor modules."""
    print("\nTesting MediaStack Doctor modules...")
    
    try:
        from mediastack_doctor import __version__
        print(f"✓ mediastack_doctor v{__version__}")
    except ImportError as e:
        print(f"✗ mediastack_doctor: {e}")
        return False
    
    try:
        from mediastack_doctor.registry import Registry
        print("✓ registry module")
    except ImportError as e:
        print(f"✗ registry: {e}")
        return False
    
    try:
        from mediastack_doctor.utils.docker_client import DockerClient
        print("✓ docker_client module")
    except ImportError as e:
        print(f"✗ docker_client: {e}")
        return False
    
    try:
        from mediastack_doctor.checks import host, docker_topology, gluetun
        print("✓ check modules")
    except ImportError as e:
        print(f"✗ check modules: {e}")
        return False
    
    return True

def test_registry():
    """Test registry functionality."""
    print("\nTesting registry functionality...")
    
    try:
        from mediastack_doctor.registry import Registry, ServiceRef
        
        # Test registry creation
        registry = Registry()
        print("✓ Registry creation")
        
        # Test service reference
        service = ServiceRef(name="test", url="http://test:8080")
        registry.set_service(service)
        print("✓ Service reference")
        
        # Test registry loading/saving
        registry.save()
        loaded_registry = Registry.load()
        print("✓ Registry persistence")
        
        return True
    except Exception as e:
        print(f"✗ Registry test failed: {e}")
        return False

def test_docker_client():
    """Test Docker client functionality."""
    print("\nTesting Docker client...")
    
    try:
        from mediastack_doctor.utils.docker_client import DockerClient
        
        client = DockerClient()
        print("✓ DockerClient creation")
        
        # Test container listing (may fail if Docker not available)
        try:
            containers = client.list_containers()
            print(f"✓ Container listing ({len(containers)} containers)")
        except Exception as e:
            print(f"⚠ Container listing failed (expected if Docker not available): {e}")
        
        return True
    except Exception as e:
        print(f"✗ Docker client test failed: {e}")
        return False

def test_checks():
    """Test check modules."""
    print("\nTesting check modules...")
    
    try:
        from mediastack_doctor.checks import host
        from mediastack_doctor.registry import Registry
        
        registry = Registry()
        checks = host.run_checks(registry)
        print(f"✓ Host checks ({len(checks)} checks)")
        
        return True
    except Exception as e:
        print(f"✗ Check modules test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("MediaStack Doctor - Installation Test")
    print("=" * 40)
    
    all_passed = True
    
    # Test imports
    if not test_imports():
        all_passed = False
    
    # Test MediaStack Doctor modules
    if not test_mediastack_doctor():
        all_passed = False
    
    # Test registry
    if not test_registry():
        all_passed = False
    
    # Test Docker client
    if not test_docker_client():
        all_passed = False
    
    # Test checks
    if not test_checks():
        all_passed = False
    
    print("\n" + "=" * 40)
    if all_passed:
        print("✓ All tests passed! MediaStack Doctor is ready to use.")
        print("\nNext steps:")
        print("1. Run: mediastack-doctor registry discover --save")
        print("2. Configure service credentials")
        print("3. Run: mediastack-doctor diagnose")
        return 0
    else:
        print("✗ Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
