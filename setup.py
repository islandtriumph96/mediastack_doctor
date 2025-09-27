#!/usr/bin/env python3
"""Setup script for MediaStack Doctor."""

from setuptools import setup, find_packages

setup(
    name="mediastack-doctor",
    version="0.1.0",
    description="Diagnostics CLI for Docker+VPN+Plex/Arr stacks",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "rich",
        "psutil", 
        "requests",
        "PyYAML",
        "Jinja2",
        "keyring",
        "docker"
    ],
    entry_points={
        "console_scripts": [
            "mediastack-doctor=mediastack_doctor.cli:main",
        ],
    },
)
