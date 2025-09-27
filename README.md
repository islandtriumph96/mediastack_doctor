# MediaStack Doctor

A comprehensive diagnostics tool for self-hosted media stacks running on Pop!_OS with Docker. MediaStack Doctor audits your entire stack including Docker containers, Gluetun/PIA VPN, Plex, Cloudflared, Arr services, qBittorrent, SABnzbd, system health, and more.

## Features

- **🔍 Comprehensive Diagnostics**: Checks host system, Docker topology, VPN connectivity, and all media services
- **🔐 Secure Credential Management**: Uses OS keyring for secure storage of API keys and tokens
- **📊 Rich Reporting**: Generates detailed Markdown and JSON reports with actionable recommendations
- **🛡️ Privacy-First**: Offline by default, with optional external checks for port-forward testing
- **🔧 Service Registry**: Persistent configuration for service URLs, ports, and credentials
- **📦 Support Bundles**: Creates sanitized support bundles with logs and configuration
- **🎯 Advisor Mode**: Provides copy-pasteable fixes and Docker Compose snippets for common issues
- **📈 Report Diffing**: Compare diagnostic runs to track changes and improvements over time
- **🔍 Deep Checks**: Advanced path parity analysis and Cloudflared route validation
- **⚡ Selective Testing**: Run specific diagnostic sections to focus on particular areas

## Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd mediastack-doctor

# Install dependencies
pip install -e .

# Or install with pipx for isolated installation
pipx install .
```

### Basic Usage

```bash
# Run diagnostics
mediastack-doctor run

# Run with advisor mode for actionable fixes
mediastack-doctor run --advisor

# Run specific sections only
mediastack-doctor run --sections host,docker,gluetun

# Compare with previous run
mediastack-doctor run --diff last

# Run with external checks (port-forward testing)
mediastack-doctor run --allow-external-checks

# View results
ls ~/mediastack-doctor/outputs/
```

### Service Registry Setup

```bash
# Discover services from Docker
mediastack-doctor registry discover --save

# Configure service credentials
mediastack-doctor registry set qbittorrent --url http://192.168.1.50:8081 --username admin --password-secret-ref qb_password
mediastack-doctor registry secret set qb_password

# Configure API keys
mediastack-doctor registry set radarr --url http://radarr:7878 --api-key-secret-ref radarr_apikey
mediastack-doctor registry secret set radarr_apikey

# Validate all services
mediastack-doctor registry validate
```

## Architecture

### Service Registry

The service registry stores connection information for all services:

```yaml
version: 1
services:
  qbittorrent:
    url: "http://192.168.1.50:8081"
    port: 8081
    auth: basic
    username: "admin"
    password_secret_ref: "qb_password"
  radarr:
    url: "http://radarr:7878"
    api_key_secret_ref: "radarr_apikey"
  # ... more services
secrets:
  - id: "radarr_apikey"
  - id: "qb_password"
```

### Diagnostic Categories

1. **Host & Filesystems**
   - CPU, RAM, and swap usage
   - Disk space and mount status
   - Network interfaces and connections
   - System logs and thermal status

2. **Docker Topology**
   - Container health and status
   - Network configuration
   - Volume mounts and path consistency
   - Port collisions and image updates

3. **Gluetun / PIA**
   - VPN connection status
   - Port-forward functionality
   - Firewall rules and DNS configuration
   - Server region and protocol

4. **qBittorrent (inside Gluetun)**
   - WebUI connectivity
   - API authentication
   - Configuration and path consistency
   - Network integration with Gluetun

5. **Arr Stack (Radarr, Sonarr, Prowlarr)**
   - API connectivity
   - Download client integration
   - Indexer synchronization
   - Path consistency across services

6. **SABnzbd**
   - API connectivity
   - Queue and configuration status
   - Directory setup

7. **Plex**
   - Server connectivity
   - Library configuration
   - Remote access status

8. **Cloudflared**
   - Tunnel health
   - Metrics endpoint
   - DNS configuration

9. **Overseerr**
   - API connectivity
   - Service connections
   - Integration status

## Configuration

### Environment Variables

```bash
# Override registry settings
export QB_URL="http://192.168.1.50:8081"
export QB_USER="admin"
export QB_PASS="password"
export PLEX_TOKEN="your-plex-token"
```

### CLI Options

```bash
# Basic diagnostics
mediastack-doctor run

# With specific options
mediastack-doctor run \
  --qb-url http://192.168.1.50:8081 \
  --qb-user admin \
  --qb-pass password \
  --plex-token your-token \
  --output-dir ~/reports \
  --allow-external-checks \
  --nic eth0 \
  --advisor \
  --sections host,docker,gluetun,qbittorrent

# Registry management
mediastack-doctor registry set <service> --url <url> --api-key-secret-ref <ref>
mediastack-doctor registry get <service>
mediastack-doctor registry discover --save
mediastack-doctor registry validate

# Compare runs
mediastack-doctor run --diff last
mediastack-doctor run --diff 20240101_120000
```

## Output

### Reports

MediaStack Doctor generates three types of output:

1. **`report.md`** - Human-readable Markdown report with:
   - Executive summary with pass/warn/fail counts
   - Critical issues requiring immediate attention
   - Detailed findings for each diagnostic category
   - System information and recommendations

2. **`report.json`** - Machine-readable JSON with:
   - Structured diagnostic results
   - System information
   - Service registry (redacted)
   - Timestamps and metadata

3. **`support_bundle.tar.gz`** - Support bundle containing:
   - Report files
   - System logs (journalctl)
   - Docker container logs
   - Registry configuration (redacted)

### Example Report Structure

```markdown
# MediaStack Doctor Report

## Executive Summary
| Metric | Value |
|--------|-------|
| Total Checks | 45 |
| Passed | 38 ✅ |
| Warnings | 5 ⚠️ |
| Failed | 2 ❌ |
| Success Rate | 84.4% |

## 🚨 Critical Issues
- **qBittorrent WebUI Connectivity** (Q5)
  - *Evidence:* Cannot connect to http://192.168.1.50:8081
  - *Impact:* qBittorrent is not reachable
  - *Fix:* Check container status, network configuration, and firewall rules

## Detailed Results
### Host & Filesystems
#### ✅ CPU Usage (H1)
**Evidence:** CPU usage is 23.4%
**Why it matters:** CPU usage is within normal range
```

## Advanced Features

### Advisor Mode

The advisor mode provides actionable fixes for common issues:

```bash
# Run with advisor mode
mediastack-doctor run --advisor
```

The advisor will provide:
- **Copy-pasteable fixes** for failed and warning checks
- **Docker Compose snippets** for configuration issues
- **Environment variable examples** for service configuration
- **Network and firewall recommendations**

### Report Diffing

Compare diagnostic runs to track improvements:

```bash
# Compare with the last run
mediastack-doctor run --diff last

# Compare with a specific run
mediastack-doctor run --diff 20240101_120000
```

Diff reports show:
- **New checks** that were added
- **Removed checks** that are no longer relevant
- **Severity changes** (fail → warn → info)
- **Evidence changes** with significant differences

### Deep Checks

#### Path Parity Analysis (A6)
Automatically detects path inconsistencies across services:
- Identifies `/downloads` vs `/data` mismatches
- Validates consistent volume mounts
- Suggests Docker Compose configurations
- Warns about common path issues

#### Cloudflared Routes (C3)
Validates tunnel configuration and backend connectivity:
- Lists active tunnel routes
- Tests backend service accessibility
- Warns about Plex routing through Cloudflare
- Provides Zero-Trust authentication recommendations

### Selective Testing

Run only specific diagnostic sections:

```bash
# Test only host system
mediastack-doctor run --sections host

# Test Docker and VPN
mediastack-doctor run --sections docker,gluetun

# Test media services
mediastack-doctor run --sections qbittorrent,arr,plex
```

Available sections: `host`, `docker`, `gluetun`, `qbittorrent`, `arr`, `sabnzbd`, `plex`, `cloudflared`, `overseerr`

## Troubleshooting

### Common Issues

1. **Docker Connection Failed**
   ```bash
   # Check Docker daemon
   sudo systemctl status docker
   
   # Test Docker access
   docker ps
   ```

2. **Service Not Found**
   ```bash
   # Discover services
   mediastack-doctor registry discover
   
   # Check container names
   docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"
   ```

3. **API Authentication Failed**
   ```bash
   # Check API key
   mediastack-doctor registry get <service> --show-secrets
   
   # Update API key
   mediastack-doctor registry secret set <ref>
   ```

4. **Permission Denied**
   ```bash
   # Check file permissions
   ls -la ~/.mediastack-doctor/
   
   # Fix permissions
   chmod 600 ~/.mediastack-doctor/registry.yml
   ```

### Logs and Debugging

```bash
# Check container logs
docker logs <container_name>

# Check system logs
journalctl -u docker -f

# Run with verbose output
mediastack-doctor diagnose --output-dir ~/debug
```

## Security

- **Credential Storage**: All sensitive data is stored in OS keyring (GNOME Keyring, macOS Keychain, Windows Credential Manager)
- **Redaction**: All output is automatically redacted to remove sensitive information
- **Offline by Default**: No external network calls unless explicitly enabled
- **Read-Only**: Never modifies system configuration or data

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the support bundle
3. Open an issue on GitHub
4. Check container logs: `docker logs <container_name>`

---

*MediaStack Doctor v0.1.0 - Comprehensive diagnostics for self-hosted media stacks*
