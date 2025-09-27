"""Service registry with OS keyring integration for secure credential storage."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import keyring
import yaml


REGISTRY_PATH = Path.home() / ".mediastack-doctor" / "registry.yml"


@dataclass
class ServiceRef:
    """Reference to a service with connection details."""
    name: str
    url: Optional[str] = None
    port: Optional[int] = None
    metrics_url: Optional[str] = None
    username: Optional[str] = None
    password_secret_ref: Optional[str] = None
    api_key_secret_ref: Optional[str] = None
    token_secret_ref: Optional[str] = None
    container: Optional[str] = None
    auth_type: Optional[str] = None  # basic, api_key, token, none


class Registry:
    """Service registry with secure credential storage."""
    
    def __init__(self, data: Optional[Dict[str, Any]] = None) -> None:
        """Initialize registry with data."""
        self._data = data or {"version": 1, "services": {}, "secrets": []}
    
    @classmethod
    def load(cls) -> "Registry":
        """Load registry from disk."""
        if REGISTRY_PATH.exists():
            try:
                with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                return cls(data)
            except (yaml.YAMLError, OSError) as e:
                print(f"Warning: Could not load registry: {e}")
                return cls({})
        return cls({})
    
    def save(self) -> None:
        """Save registry to disk."""
        REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
                yaml.safe_dump(self._data, f, sort_keys=False, default_flow_style=False)
        except OSError as e:
            raise RuntimeError(f"Could not save registry: {e}")
    
    def get_service(self, name: str) -> Optional[ServiceRef]:
        """Get service reference by name."""
        raw = self._data.get("services", {}).get(name)
        if not raw:
            return None
        return ServiceRef(name=name, **raw)
    
    def set_service(self, ref: ServiceRef) -> None:
        """Set service reference."""
        service_data = {}
        for key, value in ref.__dict__.items():
            if key != "name" and value is not None:
                service_data[key] = value
        
        self._data.setdefault("services", {})[ref.name] = service_data
    
    def get_secret(self, ref_id: str) -> Optional[str]:
        """Get secret from OS keyring."""
        if not ref_id:
            return None
        try:
            return keyring.get_password("mediastack-doctor", ref_id)
        except Exception as e:
            print(f"Warning: Could not retrieve secret '{ref_id}': {e}")
            return None
    
    def set_secret(self, ref_id: str, value: str) -> None:
        """Set secret in OS keyring."""
        try:
            keyring.set_password("mediastack-doctor", ref_id, value)
            # Track secret references
            secrets = self._data.get("secrets", [])
            if ref_id not in secrets:
                secrets.append(ref_id)
                self._data["secrets"] = secrets
        except Exception as e:
            raise RuntimeError(f"Could not store secret '{ref_id}': {e}")
    
    def redact(self, s: Optional[str]) -> Optional[str]:
        """Redact sensitive string for display."""
        if not s:
            return s
        if len(s) < 8:
            return "****"
        return "****" + s[-4:]
    
    def to_redacted_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with redacted secrets."""
        out = {
            "version": self._data.get("version", 1),
            "services": {},
            "secrets": []
        }
        
        for name, svc in self._data.get("services", {}).items():
            copy = dict(svc)
            for key in ("password_secret_ref", "api_key_secret_ref", "token_secret_ref"):
                if copy.get(key):
                    secret = self.get_secret(copy[key])
                    copy[key] = self.redact(secret)
            out["services"][name] = copy
        
        out["secrets"] = [
            {"id": s["id"] if isinstance(s, dict) else s}
            for s in self._data.get("secrets", [])
        ]
        
        return out
    
    def list_services(self) -> List[str]:
        """List all service names."""
        return list(self._data.get("services", {}).keys())
    
    def remove_service(self, name: str) -> bool:
        """Remove service from registry."""
        services = self._data.get("services", {})
        if name in services:
            del services[name]
            return True
        return False
    
    # Convenience methods for common operations
    def set_service_url(self, name: str, url: str) -> None:
        """Set service URL."""
        svc = self.get_service(name) or ServiceRef(name=name)
        svc.url = url
        self.set_service(svc)
    
    def set_service_username(self, name: str, username: str) -> None:
        """Set service username."""
        svc = self.get_service(name) or ServiceRef(name=name)
        svc.username = username
        self.set_service(svc)
    
    def set_service_metrics_url(self, name: str, metrics_url: str) -> None:
        """Set service metrics URL."""
        svc = self.get_service(name) or ServiceRef(name=name)
        svc.metrics_url = metrics_url
        self.set_service(svc)
    
    def set_service_container(self, name: str, container: str) -> None:
        """Set service container name."""
        svc = self.get_service(name) or ServiceRef(name=name)
        svc.container = container
        self.set_service(svc)
    
    def get_service_credentials(self, name: str) -> Dict[str, Optional[str]]:
        """Get all credentials for a service."""
        svc = self.get_service(name)
        if not svc:
            return {}
        
        creds = {}
        if svc.username:
            creds["username"] = svc.username
        if svc.password_secret_ref:
            creds["password"] = self.get_secret(svc.password_secret_ref)
        if svc.api_key_secret_ref:
            creds["api_key"] = self.get_secret(svc.api_key_secret_ref)
        if svc.token_secret_ref:
            creds["token"] = self.get_secret(svc.token_secret_ref)
        
        return creds
    
    def validate_service(self, name: str) -> Dict[str, Any]:
        """Validate service configuration."""
        svc = self.get_service(name)
        if not svc:
            return {"valid": False, "errors": ["Service not found"]}
        
        errors = []
        warnings = []
        
        if not svc.url:
            errors.append("No URL configured")
        
        if svc.auth_type == "basic" and not svc.username:
            errors.append("Username required for basic auth")
        
        if svc.auth_type == "basic" and not svc.password_secret_ref:
            errors.append("Password secret reference required for basic auth")
        
        if svc.api_key_secret_ref and not self.get_secret(svc.api_key_secret_ref):
            warnings.append("API key secret not found in keyring")
        
        if svc.token_secret_ref and not self.get_secret(svc.token_secret_ref):
            warnings.append("Token secret not found in keyring")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
