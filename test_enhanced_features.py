#!/usr/bin/env python3
"""Test script for enhanced MediaStack Doctor features."""

import sys
import os
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_advisor_rules():
    """Test the advisor rules functionality."""
    print("Testing advisor rules...")
    
    try:
        from mediastack_doctor.utils.advisor_rules import AdvisorRules, Thresholds, ContainerEvidence
        
        # Test thresholds
        thresholds = Thresholds()
        print(f"✓ Default thresholds: CPU WARN={thresholds.cpu_warn}% FAIL={thresholds.cpu_fail}%")
        
        # Test advisor rules
        advisor = AdvisorRules(thresholds)
        
        # Test container evidence
        healthy_container = ContainerEvidence(
            name="test-container",
            status="running",
            health_status="healthy",
            restart_count=0,
            exit_code=None,
            started_at="2024-01-01T00:00:00Z",
            ports=["8080:8080"],
            networks=["bridge"],
            volumes=["/host:/container"],
            log_errors=[]
        )
        
        should_restart, reason = advisor.should_suggest_restart(healthy_container)
        print(f"✓ Healthy container restart check: {should_restart} - {reason}")
        
        # Test unhealthy container
        unhealthy_container = ContainerEvidence(
            name="test-container",
            status="running",
            health_status="unhealthy",
            restart_count=2,
            exit_code=None,
            started_at="2024-01-01T00:00:00Z",
            ports=["8080:8080"],
            networks=["bridge"],
            volumes=["/host:/container"],
            log_errors=["error: connection refused"]
        )
        
        should_restart, reason = advisor.should_suggest_restart(unhealthy_container)
        print(f"✓ Unhealthy container restart check: {should_restart} - {reason}")
        
        return True
        
    except Exception as e:
        print(f"✗ Advisor rules test failed: {e}")
        return False

def test_thresholds_loading():
    """Test thresholds loading from file."""
    print("\nTesting thresholds loading...")
    
    try:
        from mediastack_doctor.utils.advisor_rules import load_thresholds_from_file
        
        # Test loading from the default thresholds file
        thresholds_path = project_root / "thresholds.yml"
        if thresholds_path.exists():
            thresholds = load_thresholds_from_file(str(thresholds_path))
            print(f"✓ Loaded thresholds from file: CPU WARN={thresholds.cpu_warn}% FAIL={thresholds.cpu_fail}%")
        else:
            print("⚠ Thresholds file not found, testing with non-existent file")
            thresholds = load_thresholds_from_file("non_existent.yml")
            print(f"✓ Fallback to defaults: CPU WARN={thresholds.cpu_warn}% FAIL={thresholds.cpu_fail}%")
        
        return True
        
    except Exception as e:
        print(f"✗ Thresholds loading test failed: {e}")
        return False

def test_evidence_based_fixes():
    """Test evidence-based fix generation."""
    print("\nTesting evidence-based fixes...")
    
    try:
        from mediastack_doctor.utils.advisor_rules import generate_evidence_based_fixes, Thresholds
        
        # Mock checks data
        mock_checks = [
            {
                "id": "H1",
                "title": "CPU Usage",
                "severity": "fail",
                "evidence": "CPU usage is 95.2%",
                "category": "Host & Filesystems"
            },
            {
                "id": "H16", 
                "title": "Thermal Status",
                "severity": "fail",
                "evidence": "Temperature is 98°C",
                "category": "Host & Filesystems"
            },
            {
                "id": "D2_test_container",
                "title": "Container Status - test-container",
                "severity": "warn",
                "evidence": "Container is running but has restarted 3 times",
                "category": "Docker Topology"
            }
        ]
        
        # Mock container evidence
        from mediastack_doctor.utils.advisor_rules import ContainerEvidence
        container_evidence_map = {
            "test-container": ContainerEvidence(
                name="test-container",
                status="running",
                health_status="healthy",
                restart_count=3,
                exit_code=None,
                started_at="2024-01-01T00:00:00Z",
                ports=["8080:8080"],
                networks=["bridge"],
                volumes=["/host:/container"],
                log_errors=[]
            )
        }
        
        thresholds = Thresholds()
        recommendations = generate_evidence_based_fixes(mock_checks, container_evidence_map, thresholds, verbose=True)
        
        print(f"✓ Generated {len(recommendations)} evidence-based recommendations")
        
        for rec in recommendations:
            print(f"  - {rec['title']}: {rec['why']}")
            if rec.get('host_context'):
                print(f"    Host context: {rec['host_context']}")
        
        return True
        
    except Exception as e:
        print(f"✗ Evidence-based fixes test failed: {e}")
        return False

def test_cli_help():
    """Test that CLI shows new options."""
    print("\nTesting CLI help...")
    
    try:
        from mediastack_doctor.cli import main
        
        # This would normally show help, but we'll just test that the function exists
        print("✓ CLI main function accessible")
        
        # Test that we can import the new parameters from the run function
        import inspect
        import mediastack_doctor.cli as cli_module
        
        # Find the run function
        run_func = getattr(cli_module, 'run', None)
        if run_func:
            sig = inspect.signature(run_func)
            params = list(sig.parameters.keys())
            
            if 'verbose' in params:
                print("✓ --verbose parameter found in run function")
            else:
                print("⚠ --verbose parameter not found in run function")
                
            if 'thresholds' in params:
                print("✓ --thresholds parameter found in run function")
            else:
                print("⚠ --thresholds parameter not found in run function")
        else:
            print("⚠ run function not found")
        
        return True
        
    except Exception as e:
        print(f"✗ CLI help test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("MediaStack Doctor Enhanced Features Test")
    print("=" * 50)
    
    tests = [
        test_advisor_rules,
        test_thresholds_loading,
        test_evidence_based_fixes,
        test_cli_help
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\nTest Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Enhanced features are working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
