"""Robust thresholds loading and validation."""

from __future__ import annotations
from typing import Any, Dict, Union
import os
import yaml


DEFAULT_THRESHOLDS: Dict[str, Any] = {
    "cpu": {"warn": 80.0, "fail": 90.0},
    "temp_c": {"warn": 85.0, "fail": 92.0},
    "disk_pct": {"warn": 85.0, "fail": 95.0},
    "memory": {"warn": 85.0, "fail": 95.0},
    "network": {"warn": 100.0, "fail": 500.0},
}


class ThresholdsError(Exception):
    """Exception raised when thresholds are invalid or malformed."""
    pass


def load_thresholds(input_: Union[None, str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Load and validate thresholds from various input types.
    
    Args:
        input_: Can be:
            - None: Use defaults
            - str: Path to YAML file
            - dict: Direct threshold configuration
    
    Returns:
        Dict with validated thresholds structure
        
    Raises:
        ThresholdsError: If input is invalid or malformed
    """
    base = {}
    for domain, values in DEFAULT_THRESHOLDS.items():
        base[domain] = values.copy()

    if input_ is None:
        return base

    data: Dict[str, Any]
    if isinstance(input_, dict):
        data = input_
    elif isinstance(input_, str):
        path = os.path.expanduser(input_)
        if not os.path.exists(path):
            raise ThresholdsError(f"Thresholds file not found: {path}")
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw_data = yaml.safe_load(f)
                if raw_data is None:
                    raise ThresholdsError(f"Thresholds file is empty: {path}")
                if not isinstance(raw_data, dict):
                    raise ThresholdsError(f"Thresholds file must contain a YAML mapping, got {type(raw_data)}")
                data = raw_data
        except yaml.YAMLError as e:
            raise ThresholdsError(f"Failed to parse thresholds YAML from {path}: {e}") from e
        except Exception as e:
            raise ThresholdsError(f"Failed to read thresholds file {path}: {e}") from e
    else:
        raise ThresholdsError(f"Unsupported thresholds input type: {type(input_)}. Expected None, str, or dict.")

    # Validate and merge with defaults
    def normalize_number(val: Any, key_path: str) -> float:
        """Convert value to float with helpful error messages."""
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            val = val.strip()
            if not val:
                raise ThresholdsError(f"Threshold '{key_path}' is empty")
            try:
                return float(val)
            except ValueError:
                raise ThresholdsError(f"Threshold '{key_path}' must be a number; got '{val}'")
        raise ThresholdsError(f"Threshold '{key_path}' must be numeric; got {type(val).__name__}")

    # Process each domain in the input data
    for domain, bundle in data.items():
        if not isinstance(bundle, dict):
            raise ThresholdsError(f"Threshold domain '{domain}' must be a mapping with 'warn' and 'fail' keys, got {type(bundle).__name__}")
        
        # Initialize domain if not in base
        if domain not in base:
            base[domain] = {}
        
        # Process warn and fail levels
        for level in ("warn", "fail"):
            if level in bundle:
                try:
                    base[domain][level] = normalize_number(bundle[level], f"{domain}.{level}")
                except ThresholdsError:
                    raise
                except Exception as e:
                    raise ThresholdsError(f"Error processing threshold '{domain}.{level}': {e}") from e

    # Validate that all domains have both warn and fail
    for domain, bundle in base.items():
        if "warn" not in bundle or "fail" not in bundle:
            raise ThresholdsError(f"Domain '{domain}' is missing required 'warn' or 'fail' thresholds")
        
        # Sanity check: fail should be >= warn
        warn_val = float(bundle["warn"])
        fail_val = float(bundle["fail"])
        if fail_val <= warn_val:
            raise ThresholdsError(f"Invalid thresholds for '{domain}': fail ({fail_val}) must be greater than warn ({warn_val})")

    return base


def get_flat_thresholds(thresholds: Dict[str, Any]) -> Dict[str, float]:
    """
    Convert nested thresholds dict to flat dict for template use.
    
    Args:
        thresholds: Nested thresholds dict
        
    Returns:
        Flat dict with keys like 'cpu_warn', 'cpu_fail', etc.
    """
    flat = {}
    for domain, values in thresholds.items():
        if isinstance(values, dict):
            for level, value in values.items():
                if isinstance(value, (int, float)):
                    flat[f"{domain}_{level}"] = float(value)
    return flat


def get_threshold_value(thresholds: Dict[str, Any], domain: str, level: str, default: float = 0.0) -> float:
    """
    Safely get a threshold value with fallback.
    
    Args:
        thresholds: Thresholds dict
        domain: Domain name (e.g., 'cpu', 'temp_c')
        level: Level name ('warn' or 'fail')
        default: Default value if not found
        
    Returns:
        Threshold value as float
    """
    try:
        domain_data = thresholds.get(domain, {})
        if isinstance(domain_data, dict):
            value = domain_data.get(level, default)
            return float(value) if isinstance(value, (int, float)) else default
        return default
    except (TypeError, ValueError):
        return default


def validate_thresholds_dict(thresholds: Any) -> bool:
    """
    Check if a value is a valid thresholds dict.
    
    Args:
        thresholds: Value to check
        
    Returns:
        True if valid thresholds dict
    """
    if not isinstance(thresholds, dict):
        return False
    
    # Check that it has the expected structure
    for domain, values in thresholds.items():
        if not isinstance(values, dict):
            return False
        if "warn" not in values or "fail" not in values:
            return False
        if not isinstance(values["warn"], (int, float)) or not isinstance(values["fail"], (int, float)):
            return False
    
    return True
