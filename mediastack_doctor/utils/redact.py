"""Text redaction utilities for sensitive information."""

import re
from typing import Any, Dict, List, Union


class Redactor:
    """Redact sensitive information from text and data structures."""
    
    def __init__(self) -> None:
        """Initialize redactor with common patterns."""
        # Common patterns for sensitive data
        self.patterns = [
            # API keys and tokens
            (r'(?i)(api[_-]?key|token|secret|password|passwd|pwd)\s*[:=]\s*["\']?([a-zA-Z0-9+/=]{20,})["\']?', r'\1=****'),
            (r'(?i)(bearer|authorization)\s+([a-zA-Z0-9+/=]{20,})', r'\1 ****'),
            
            # URLs with credentials
            (r'(https?://)([^:]+):([^@]+)@([^\s]+)', r'\1****:****@\4'),
            
            # IP addresses (optional - can be disabled)
            # (r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b', r'***.***.***.***'),
            
            # Email addresses
            (r'\b([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b', r'****@\2'),
            
            # Credit card numbers
            (r'\b(\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4})\b', r'****-****-****-****'),
            
            # Phone numbers
            (r'\b(\+?1?[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b', r'****-****-****'),
            
            # Common file paths that might contain usernames
            (r'/home/([^/\s]+)/', r'/home/****/'),
            (r'/Users/([^/\s]+)/', r'/Users/****/'),
        ]
        
        # Compile patterns for better performance
        self.compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), replacement)
            for pattern, replacement in self.patterns
        ]
    
    def redact_text(self, text: str) -> str:
        """Redact sensitive information from text."""
        if not text:
            return text
        
        redacted = text
        for pattern, replacement in self.compiled_patterns:
            redacted = pattern.sub(replacement, redacted)
        
        return redacted
    
    def redact_dict(self, data: Any) -> Any:
        """Recursively redact sensitive information from dictionary."""
        if isinstance(data, dict):
            return {key: self.redact_dict(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self.redact_dict(item) for item in data]
        elif isinstance(data, str):
            return self.redact_text(data)
        else:
            return data
    
    def redact_url(self, url: str) -> str:
        """Redact credentials from URL."""
        if not url:
            return url
        
        # Remove credentials from URL
        redacted = re.sub(
            r'(https?://)([^:]+):([^@]+)@([^\s]+)',
            r'\1****:****@\4',
            url,
            flags=re.IGNORECASE
        )
        
        return redacted
    
    def redact_secret(self, secret: str, show_last: int = 4) -> str:
        """Redact secret value, showing only last N characters."""
        if not secret:
            return secret
        
        if len(secret) <= show_last:
            return "****"
        
        return "****" + secret[-show_last:]
    
    def redact_email(self, email: str) -> str:
        """Redact email address."""
        if not email or "@" not in email:
            return email
        
        local, domain = email.split("@", 1)
        if len(local) <= 2:
            return "****@" + domain
        
        return local[:2] + "****@" + domain
    
    def redact_ip(self, ip: str) -> str:
        """Redact IP address."""
        if not ip:
            return ip
        
        # Simple IP redaction - replace last octet
        parts = ip.split(".")
        if len(parts) == 4:
            return ".".join(parts[:3]) + ".***"
        
        return "***.***.***.***"
    
    def redact_file_path(self, path: str) -> str:
        """Redact sensitive parts of file paths."""
        if not path:
            return path
        
        # Redact home directory usernames
        redacted = re.sub(r'/home/([^/\s]+)/', r'/home/****/', path)
        redacted = re.sub(r'/Users/([^/\s]+)/', r'/Users/****/', redacted)
        
        return redacted
    
    def is_sensitive_key(self, key: str) -> bool:
        """Check if a key name indicates sensitive data."""
        sensitive_keywords = [
            "password", "passwd", "pwd", "secret", "token", "key", "auth",
            "credential", "api_key", "access_token", "refresh_token",
            "private_key", "certificate", "cert", "ssl", "tls"
        ]
        
        key_lower = key.lower()
        return any(keyword in key_lower for keyword in sensitive_keywords)
    
    def redact_sensitive_values(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Redact values for keys that indicate sensitive data."""
        redacted = {}
        
        for key, value in data.items():
            if self.is_sensitive_key(key) and isinstance(value, str):
                redacted[key] = self.redact_secret(value)
            elif isinstance(value, dict):
                redacted[key] = self.redact_sensitive_values(value)
            elif isinstance(value, list):
                redacted[key] = [
                    self.redact_sensitive_values(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                redacted[key] = value
        
        return redacted
