"""Tests for registry functionality."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from mediastack_doctor.registry import Registry, ServiceRef


class TestRegistry:
    """Test registry functionality."""
    
    def test_registry_creation(self):
        """Test registry creation."""
        registry = Registry()
        assert registry._data["version"] == 1
        assert registry._data["services"] == {}
        assert registry._data["secrets"] == []
    
    def test_service_ref_creation(self):
        """Test service reference creation."""
        service = ServiceRef(
            name="test_service",
            url="http://test:8080",
            port=8080,
            username="admin"
        )
        
        assert service.name == "test_service"
        assert service.url == "http://test:8080"
        assert service.port == 8080
        assert service.username == "admin"
    
    def test_registry_persistence(self):
        """Test registry save/load functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "test_registry.yml"
            
            # Create registry
            registry = Registry()
            service = ServiceRef(name="test", url="http://test:8080")
            registry.set_service(service)
            
            # Mock the registry path
            with patch('mediastack_doctor.registry.REGISTRY_PATH', registry_path):
                registry.save()
                
                # Load registry
                loaded_registry = Registry.load()
                
                assert loaded_registry._data["version"] == 1
                assert "test" in loaded_registry._data["services"]
                assert loaded_registry._data["services"]["test"]["url"] == "http://test:8080"
    
    def test_redaction(self):
        """Test secret redaction."""
        registry = Registry()
        
        # Test redaction of secrets
        assert registry.redact("secret123") == "****123"
        assert registry.redact("short") == "****"
        assert registry.redact("") == ""
        assert registry.redact(None) is None
    
    def test_to_redacted_dict(self):
        """Test redacted dictionary conversion."""
        registry = Registry()
        
        # Add a service with secret reference
        service = ServiceRef(
            name="test",
            url="http://test:8080",
            api_key_secret_ref="test_key"
        )
        registry.set_service(service)
        
        # Mock secret retrieval
        with patch.object(registry, 'get_secret', return_value="secret123"):
            redacted = registry.to_redacted_dict()
            
            assert redacted["services"]["test"]["url"] == "http://test:8080"
            assert redacted["services"]["test"]["api_key_secret_ref"] == "****123"
    
    def test_service_validation(self):
        """Test service validation."""
        registry = Registry()
        
        # Valid service
        valid_service = ServiceRef(
            name="valid",
            url="http://valid:8080",
            auth_type="basic",
            username="admin",
            password_secret_ref="password"
        )
        registry.set_service(valid_service)
        
        validation = registry.validate_service("valid")
        assert validation["valid"] is True
        assert len(validation["errors"]) == 0
        
        # Invalid service (no URL)
        invalid_service = ServiceRef(name="invalid")
        registry.set_service(invalid_service)
        
        validation = registry.validate_service("invalid")
        assert validation["valid"] is False
        assert "No URL configured" in validation["errors"]
    
    def test_list_services(self):
        """Test service listing."""
        registry = Registry()
        
        # Add services
        service1 = ServiceRef(name="service1", url="http://service1:8080")
        service2 = ServiceRef(name="service2", url="http://service2:8080")
        
        registry.set_service(service1)
        registry.set_service(service2)
        
        services = registry.list_services()
        assert "service1" in services
        assert "service2" in services
        assert len(services) == 2
    
    def test_remove_service(self):
        """Test service removal."""
        registry = Registry()
        
        # Add service
        service = ServiceRef(name="test", url="http://test:8080")
        registry.set_service(service)
        
        assert "test" in registry.list_services()
        
        # Remove service
        removed = registry.remove_service("test")
        assert removed is True
        assert "test" not in registry.list_services()
        
        # Try to remove non-existent service
        removed = registry.remove_service("nonexistent")
        assert removed is False
