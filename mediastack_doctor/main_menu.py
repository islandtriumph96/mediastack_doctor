"""Interactive main menu interface for MediaStack Doctor."""

import sys
from pathlib import Path
from typing import Optional, Dict, Any

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt, Confirm
    from rich.text import Text
    from rich.align import Align
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    Console = None

from .registry import Registry
from .utils.docker_client import DockerClient
from .utils.thresholds import load_thresholds, DEFAULT_THRESHOLDS


class MainMenu:
    """Interactive main menu for MediaStack Doctor."""
    
    def __init__(self):
        self.console = Console() if HAS_RICH else None
        self.registry = Registry.load()
        self.docker_client = None
        self.thresholds = DEFAULT_THRESHOLDS

        # Try to initialize Docker client
        try:
            self.docker_client = DockerClient()
        except Exception:
            self.docker_client = None

        # Check for missing credentials (will be called from run() when interactive)

    def _check_missing_credentials(self):
        """Check for missing service credentials and prompt for them."""
        services = self.registry._data.get("services", {})
        missing_creds = []

        for service_name, service_data in services.items():
            url = service_data.get("url")
            if not url:
                continue

            # Check qBittorrent credentials
            if service_name == "qbittorrent":
                username = service_data.get("username")
                password_ref = service_data.get("password_secret_ref")
                password = self.registry.get_secret(password_ref) if password_ref else None

                if not username or not password:
                    missing_creds.append({
                        "service": service_name,
                        "type": "username/password",
                        "details": "qBittorrent WebUI authentication"
                    })

            # Check Arr service API keys
            elif service_name in ["radarr", "sonarr", "prowlarr"]:
                api_key_ref = service_data.get("api_key_secret_ref")
                api_key = self.registry.get_secret(api_key_ref) if api_key_ref else None

                if not api_key:
                    missing_creds.append({
                        "service": service_name,
                        "type": "API key",
                        "details": f"{service_name.title()} API authentication"
                    })

            # Check Plex token
            elif service_name == "plex":
                token_ref = service_data.get("token_secret_ref")
                token = self.registry.get_secret(token_ref) if token_ref else None

                if not token:
                    missing_creds.append({
                        "service": service_name,
                        "type": "authentication token",
                        "details": "Plex server authentication"
                    })

        # Show missing credentials warning
        if missing_creds and self.console and HAS_RICH:
            self.console.print("\n[yellow]⚠️ Missing Service Credentials[/yellow]")
            self.console.print("[dim]Some services are configured but missing authentication:[/dim]\n")

            creds_table = Table(show_header=True)
            creds_table.add_column("Service", style="cyan")
            creds_table.add_column("Missing", style="white")
            creds_table.add_column("Details", style="dim")

            for cred in missing_creds:
                creds_table.add_row(
                    cred["service"],
                    cred["type"],
                    cred["details"]
                )

            self.console.print(creds_table)
            self.console.print()

            if Confirm.ask("Would you like to configure missing credentials now?", default=True):
                self._prompt_for_missing_credentials(missing_creds)

        elif missing_creds:
            print("\n⚠️ Missing Service Credentials")
            print("Some services are configured but missing authentication:\n")
            for cred in missing_creds:
                print(f"  {cred['service']}: Missing {cred['type']} ({cred['details']})")

            response = input("Would you like to configure missing credentials now? (Y/n): ").strip().lower()
            if response in ['', 'y', 'yes']:
                self._prompt_for_missing_credentials(missing_creds)

    def _prompt_for_missing_credentials(self, missing_creds):
        """Prompt user to enter missing credentials."""
        for cred in missing_creds:
            service_name = cred["service"]
            cred_type = cred["type"]

            if self.console and HAS_RICH:
                self.console.print(f"\n[bold cyan]🔑 Setting up {service_name.title()} credentials[/bold cyan]")
            else:
                print(f"\n🔑 Setting up {service_name.title()} credentials")

            # Get existing service
            existing_svc = self.registry.get_service(service_name)

            if service_name == "qbittorrent":
                # Prompt for username/password
                if self.console and HAS_RICH:
                    username = Prompt.ask("qBittorrent username", default=existing_svc.username if existing_svc else "admin")
                    password = Prompt.ask("qBittorrent password", password=True)
                else:
                    default_username = existing_svc.username if existing_svc else "admin"
                    username = input(f"qBittorrent username (default: {default_username}): ").strip() or default_username
                    import getpass
                    password = getpass.getpass("qBittorrent password: ")

                if password:
                    # Store password securely
                    secret_ref = f"{service_name}_password"
                    self.registry.set_secret(secret_ref, password)

                    # Update service with username and secret ref
                    from .registry import ServiceRef
                    svc = ServiceRef(
                        name=service_name,
                        url=existing_svc.url if existing_svc else f"http://localhost:8080",
                        username=username,
                        password_secret_ref=secret_ref
                    )
                    self.registry.set_service(svc)
                    self.registry.save()

                    if self.console and HAS_RICH:
                        self.console.print(f"[green]✅ qBittorrent credentials saved[/green]")
                    else:
                        print(f"✅ qBittorrent credentials saved")

            elif service_name in ["radarr", "sonarr", "prowlarr"]:
                # Prompt for API key
                if self.console and HAS_RICH:
                    self.console.print(f"[dim]Get API key from {service_name.title()} Settings > General > Security[/dim]")
                    api_key = Prompt.ask(f"{service_name.title()} API key", password=True)
                else:
                    print(f"Get API key from {service_name.title()} Settings > General > Security")
                    import getpass
                    api_key = getpass.getpass(f"{service_name.title()} API key: ")

                if api_key:
                    # Store API key securely
                    secret_ref = f"{service_name}_api_key"
                    self.registry.set_secret(secret_ref, api_key)

                    # Update service with API key ref
                    from .registry import ServiceRef
                    svc = ServiceRef(
                        name=service_name,
                        url=existing_svc.url if existing_svc else f"http://localhost:{self._get_default_port(service_name)}",
                        api_key_secret_ref=secret_ref
                    )
                    self.registry.set_service(svc)
                    self.registry.save()

                    if self.console and HAS_RICH:
                        self.console.print(f"[green]✅ {service_name.title()} API key saved[/green]")
                    else:
                        print(f"✅ {service_name.title()} API key saved")

            elif service_name == "plex":
                # Prompt for Plex token
                if self.console and HAS_RICH:
                    self.console.print("[dim]Get Plex token from https://plex.tv/claim[/dim]")
                    plex_token = Prompt.ask("Plex authentication token", password=True)
                else:
                    print("Get Plex token from https://plex.tv/claim")
                    import getpass
                    plex_token = getpass.getpass("Plex authentication token: ")

                if plex_token:
                    # Store token securely
                    secret_ref = f"{service_name}_token"
                    self.registry.set_secret(secret_ref, plex_token)

                    # Update service with token ref
                    from .registry import ServiceRef
                    svc = ServiceRef(
                        name=service_name,
                        url=existing_svc.url if existing_svc else "http://localhost:32400",
                        token_secret_ref=secret_ref
                    )
                    self.registry.set_service(svc)
                    self.registry.save()

                    if self.console and HAS_RICH:
                        self.console.print(f"[green]✅ Plex token saved[/green]")
                    else:
                        print(f"✅ Plex token saved")

    def show_banner(self):
        """Display the main banner."""
        if self.console and HAS_RICH:
            banner_text = Text()
            banner_text.append("🏥 MediaStack Doctor 🏥", style="bold blue")
            banner_text.append("\n")
            banner_text.append("Comprehensive Diagnostics for Self-Hosted Media Stacks", style="dim")
            
            banner_panel = Panel(
                Align.center(banner_text),
                style="blue",
                padding=(1, 2)
            )
            self.console.print("\n")
            self.console.print(banner_panel)
            self.console.print("\n")
        else:
            print("\n" + "="*60)
            print("🏥 MediaStack Doctor 🏥")
            print("Comprehensive Diagnostics for Self-Hosted Media Stacks")
            print("="*60 + "\n")
    
    def show_system_status(self):
        """Show quick system status."""
        if self.console and HAS_RICH:
            status_table = Table(title="System Status", show_header=True, header_style="bold magenta")
            status_table.add_column("Component", style="cyan")
            status_table.add_column("Status", style="white")
            
            # Docker status
            docker_status = "✅ Connected" if self.docker_client else "❌ Not Available"
            status_table.add_row("Docker", docker_status)
            
            # Registry status
            services_count = len(self.registry._data.get("services", {}))
            registry_status = f"✅ {services_count} services" if services_count > 0 else "⚠️ No services configured"
            status_table.add_row("Registry", registry_status)
            
            # Thresholds status
            thresholds_status = "✅ Default thresholds loaded"
            status_table.add_row("Thresholds", thresholds_status)
            
            self.console.print(status_table)
            self.console.print()
        else:
            print("System Status:")
            print(f"  Docker: {'Connected' if self.docker_client else 'Not Available'}")
            services_count = len(self.registry._data.get("services", {}))
            print(f"  Registry: {services_count} services configured")
            print(f"  Thresholds: Default loaded")
            print()
    
    def show_main_menu(self) -> str:
        """Show the main menu and get user choice."""
        from .utils.menu_navigation import create_menu
        
        menu_options = [
            ("1", "🔍 Run Full Diagnostics", "Complete system health check"),
            ("2", "📊 Quick System Check", "Fast host and Docker status"),
            ("3", "📁 Browse Previous Reports", "View past diagnostic results"),
            ("4", "⚙️ Configure Services", "Set up service URLs and credentials"),
            ("5", "🔧 Registry Management", "Manage service registry"),
            ("6", "📈 System Statistics", "View detailed system info"),
            ("7", "🩺 Troubleshoot Service", "Create diagnostic snapshot for a specific service"),
            ("8", "🌐 Network Benchmarks", "Test network performance"),
            ("9", "🎛️ Settings", "Configure thresholds and options"),
            ("10", "❓ Help", "Show help and documentation"),
            ("0", "🚪 Exit", "Exit MediaStack Doctor")
        ]
        
        return create_menu("Main Menu", menu_options, self.console)
    
    def check_configuration(self) -> bool:
        """Check if basic configuration is present."""
        services = self.registry._data.get("services", {})
        
        if not services:
            if self.console and HAS_RICH:
                self.console.print("[yellow]⚠️ No services configured in registry[/yellow]")
                self.console.print("[dim]Some diagnostics may not work without service configuration.[/dim]")
                
                if Confirm.ask("Would you like to configure services now?", default=True):
                    return False  # Redirect to configuration
            else:
                print("⚠️ No services configured in registry")
                print("Some diagnostics may not work without service configuration.")
                
                response = input("Would you like to configure services now? (Y/n): ").strip().lower()
                if response in ['', 'y', 'yes']:
                    return False  # Redirect to configuration
        
        return True  # Configuration OK
    
    def run_diagnostics(self, quick: bool = False):
        """Run diagnostics with the current configuration."""
        from .utils.diagnostics_runner import run_diagnostics_impl
        from pathlib import Path

        output_dir = Path.home() / "mediastack-doctor" / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Run diagnostics using the shared implementation
            result = run_diagnostics_impl(
                registry=self.registry,
                docker_client=self.docker_client,
                output_dir=output_dir,
                advisor=True,
                quick=quick,
                verbose=True,
                sections=None if not quick else "host,docker",
                thresholds=self.thresholds,
                redact=True,
                allow_external_checks=False
            )

            # Show results
            summary = result["summary"]
            run_dir = result["run_dir"]

            if self.console and HAS_RICH:
                self.console.print("\n[bold green]✅ Diagnostics completed![/bold green]")
                self.console.print(f"[blue]Reports saved to: {run_dir}[/blue]")

                # Show summary
                from rich.table import Table
                summary_table = Table(title="Diagnostics Summary", show_header=True)
                summary_table.add_column("Metric", style="cyan")
                summary_table.add_column("Value", style="white")

                summary_table.add_row("Total Checks", str(summary["total"]))
                summary_table.add_row("Passed", f"[green]{summary['passed']}[/green]")
                summary_table.add_row("Warnings", f"[yellow]{summary['warnings']}[/yellow]")
                summary_table.add_row("Failed", f"[red]{summary['failed']}[/red]")
                summary_table.add_row("Success Rate", f"{summary['success_rate']:.1f}%")

                self.console.print(summary_table)

                if Confirm.ask("Would you like to browse the results now?", default=True):
                    self.browse_reports()
            else:
                print("\n✅ Diagnostics completed!")
                print(f"Reports saved to: {run_dir}")
                print(f"Summary: {summary['passed']} passed, {summary['warnings']} warnings, {summary['failed']} failed")
                response = input("Would you like to browse the results now? (Y/n): ").strip().lower()
                if response in ['', 'y', 'yes']:
                    self.browse_reports()

        except Exception as e:
            if self.console and HAS_RICH:
                self.console.print(f"[red]❌ Diagnostics failed: {e}[/red]")
            else:
                print(f"❌ Diagnostics failed: {e}")

            input("Press Enter to continue...")

    def quick_system_check(self):
        """Run a quick system check (host + docker sections)."""
        from .utils.diagnostics_runner import run_diagnostics_impl
        from pathlib import Path

        output_dir = Path.home() / "mediastack-doctor" / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Run quick diagnostics
            result = run_diagnostics_impl(
                registry=self.registry,
                docker_client=self.docker_client,
                output_dir=output_dir,
                advisor=True,
                quick=True,
                verbose=False,  # Less verbose for quick check
                sections="host,docker",
                thresholds=self.thresholds,
                redact=True,
                allow_external_checks=False
            )

            # Show enhanced summary with explanations
            summary = result["summary"]
            all_checks = result["checks"]

            if self.console and HAS_RICH:
                summary_table = Table(title="Quick System Check Results", show_header=True)
                summary_table.add_column("Category", style="cyan")
                summary_table.add_column("Passed", style="green")
                summary_table.add_column("Warnings", style="yellow")
                summary_table.add_column("Failed", style="red")

                categories = {}
                for check in all_checks:
                    cat = check.get("category", "Unknown")
                    if cat not in categories:
                        categories[cat] = {"pass": 0, "warn": 0, "fail": 0}

                    severity = check.get("severity", "info")
                    if severity == "info":
                        categories[cat]["pass"] += 1
                    elif severity == "warn":
                        categories[cat]["warn"] += 1
                    elif severity == "fail":
                        categories[cat]["fail"] += 1

                for category, counts in categories.items():
                    summary_table.add_row(
                        category,
                        str(counts["pass"]),
                        str(counts["warn"]),
                        str(counts["fail"])
                    )

                self.console.print("\n")
                self.console.print(summary_table)

                # Show top issues with enhanced explanations
                failed_checks = [c for c in all_checks if c.get("severity") == "fail"][:3]
                warn_checks = [c for c in all_checks if c.get("severity") == "warn"][:3]

                if failed_checks or warn_checks:
                    self.console.print("\n[bold yellow]Top Issues Found:[/bold yellow]")

                    for check in failed_checks + warn_checks:
                        severity_icon = "❌" if check.get("severity") == "fail" else "⚠️"
                        title = check.get('title', 'Unknown')
                        evidence = check.get('evidence', '')

                        self.console.print(f"  {severity_icon} [bold]{title}[/bold]")
                        self.console.print(f"    [dim]Evidence: {evidence}[/dim]")

                        # Enhanced explanations
                        if "Missing Expected Services" in title:
                            self.console.print(f"    [yellow]💡 Some containers may be down - try: docker-compose up -d[/yellow]")
                        elif "CPU Usage" in title:
                            self.console.print(f"    [yellow]💡 High CPU usage detected - check for runaway processes[/yellow]")
                        elif "Disk Usage" in title:
                            self.console.print(f"    [yellow]💡 Low disk space - consider cleanup or expansion[/yellow]")
                        elif "Container Status" in title:
                            self.console.print(f"    [yellow]💡 Container issue - check logs with: docker logs {title.split(' - ')[1] if ' - ' in title else 'container'}[/yellow]")

                # Check for serious issues
                serious_issues = summary["failed"] > 5 or (summary["failed"] > 0 and "CPU" in str([c.get("title") for c in failed_checks]))

                if serious_issues:
                    self.console.print("\n[bold red]⚠️ Serious issues detected![/bold red]")
                    if Confirm.ask("Would you like to run full diagnostics for detailed analysis?", default=True):
                        self.run_diagnostics(quick=False)
                        return

                self.console.print("\n[bold blue]💡 For detailed analysis, use 'Run Full Diagnostics'[/bold blue]")
            else:
                print("\nQuick System Check Results:")
                categories = {}
                for check in all_checks:
                    cat = check.get("category", "Unknown")
                    if cat not in categories:
                        categories[cat] = {"pass": 0, "warn": 0, "fail": 0}

                    severity = check.get("severity", "info")
                    if severity == "info":
                        categories[cat]["pass"] += 1
                    elif severity == "warn":
                        categories[cat]["warn"] += 1
                    elif severity == "fail":
                        categories[cat]["fail"] += 1

                for category, counts in categories.items():
                    print(f"  {category}: {counts['pass']} passed, {counts['warn']} warnings, {counts['fail']} failed")

                # Show top issues
                failed_checks = [c for c in all_checks if c.get("severity") == "fail"][:3]
                warn_checks = [c for c in all_checks if c.get("severity") == "warn"][:3]

                if failed_checks or warn_checks:
                    print("\nTop Issues Found:")
                    for check in failed_checks + warn_checks:
                        severity_icon = "❌" if check.get("severity") == "fail" else "⚠️"
                        title = check.get('title', 'Unknown')
                        evidence = check.get('evidence', '')
                        print(f"  {severity_icon} {title}")
                        print(f"    Evidence: {evidence}")

                print("\n💡 For detailed analysis, use 'Run Full Diagnostics'")

            input("\nPress Enter to continue...")

        except Exception as e:
            if self.console and HAS_RICH:
                self.console.print(f"[red]❌ Quick check failed: {e}[/red]")
            else:
                print(f"❌ Quick check failed: {e}")

            input("Press Enter to continue...")

    def registry_management(self):
        """Interactive registry management submenu."""
        from .utils.menu_navigation import create_menu
        
        while True:
            # Show current services first
            if self.console and HAS_RICH:
                self.console.print("\n[bold cyan]🔧 Registry Management[/bold cyan]\n")

                registry_table = Table(title="Current Services", show_header=True)
                registry_table.add_column("Service", style="cyan")
                registry_table.add_column("URL", style="white")
                registry_table.add_column("Auth", style="green")

                services = self.registry._data.get("services", {})
                if services:
                    for name, svc_data in services.items():
                        url = svc_data.get("url", "Not configured")
                        
                        # Check authentication status
                        auth_status = "❌ No auth"
                        if svc_data.get("api_key_secret_ref"):
                            auth_status = "🔑 API key"
                        elif svc_data.get("password_secret_ref"):
                            auth_status = "🔒 Password"
                        elif svc_data.get("token_secret_ref"):
                            auth_status = "🎫 Token"
                        elif name in ["overseerr", "filebrowser"]:
                            auth_status = "✅ Optional"
                        
                        registry_table.add_row(name, url, auth_status)
                else:
                    registry_table.add_row("No services configured", "", "")

                self.console.print(registry_table)
                self.console.print()
            else:
                print("\n🔧 Registry Management\n")
                services = self.registry._data.get("services", {})
                print("Current Services:")
                if services:
                    for name, svc_data in services.items():
                        url = svc_data.get("url", "Not configured")
                        print(f"  {name}: {url}")
                else:
                    print("  No services configured")
                print()

            menu_options = [
                ("1", "📋 List Services", "View all configured services"),
                ("2", "➕ Add/Edit Service", "Add or modify a service configuration"),
                ("3", "🔍 Discover Services", "Auto-discover services from Docker containers"),
                ("4", "🔑 Manage Secrets", "View and manage stored credentials"),
                ("5", "🔗 Test Connectivity", "Test connectivity to configured services"),
                ("6", "🗑️ Remove Service", "Remove a service from registry"),
                ("0", "⬅️ Back to Main Menu", "Return to main menu")
            ]

            choice = create_menu("Registry Management Menu", menu_options, self.console)

            if choice == "0":
                break
            elif choice == "1":
                self._list_services()
            elif choice == "2":
                self._add_edit_service()
            elif choice == "3":
                self._discover_services()
            elif choice == "4":
                self._manage_secrets()
            elif choice == "5":
                self._test_connectivity()
            elif choice == "6":
                self._remove_service()

    def _list_services(self):
        """List all configured services."""
        services = self.registry._data.get("services", {})

        if not services:
            if self.console and HAS_RICH:
                self.console.print("[yellow]No services configured.[/yellow]")
            else:
                print("No services configured.")
            return

        if self.console and HAS_RICH:
            services_table = Table(title="Configured Services", show_header=True)
            services_table.add_column("Service", style="cyan")
            services_table.add_column("URL", style="white")
            services_table.add_column("Container", style="dim")

            for name, svc_data in services.items():
                url = svc_data.get("url", "Not configured")
                container = svc_data.get("container", "Not set")
                services_table.add_row(name, url, container)

            self.console.print("\n")
            self.console.print(services_table)
        else:
            print("\nConfigured Services:")
            for name, svc_data in services.items():
                url = svc_data.get("url", "Not configured")
                container = svc_data.get("container", "Not set")
                print(f"  {name}: {url} (container: {container})")

        input("\nPress Enter to continue...")

    def _add_edit_service(self):
        """Add or edit a service configuration."""
        from .utils.menu_navigation import create_menu
        
        service_options = [
            ("qbittorrent", "🌊 qBittorrent", "Torrent download client"),
            ("radarr", "🎬 Radarr", "Movie collection manager"),
            ("sonarr", "📺 Sonarr", "TV series collection manager"),
            ("prowlarr", "🔍 Prowlarr", "Indexer manager"),
            ("plex", "🎭 Plex", "Media server"),
            ("overseerr", "📋 Overseerr", "Media request management"),
            ("0", "⬅️ Back", "Return to registry menu")
        ]
        
        service_name = create_menu("Select Service to Configure", service_options, self.console)
        
        if service_name == "0":
            return

        # Get existing service or create new
        existing_svc = self.registry.get_service(service_name)

        if self.console and HAS_RICH:
            url = Prompt.ask(
                "Enter service URL",
                default=existing_svc.url if existing_svc else f"http://localhost:{self._get_default_port(service_name)}"
            )
        else:
            existing_svc = self.registry.get_service(service_name)
            default_url = existing_svc.url if existing_svc else f"http://localhost:{self._get_default_port(service_name)}"
            url = input(f"Enter service URL (default: {default_url}): ").strip()
            if not url:
                url = default_url

        # Create service reference
        from .registry import ServiceRef
        svc = ServiceRef(name=service_name, url=url)

        # Save service
        self.registry.set_service(svc)
        self.registry.save()

        if self.console and HAS_RICH:
            self.console.print(f"[green]✅ Service '{service_name}' saved[/green]")
        else:
            print(f"✅ Service '{service_name}' saved")

        input("Press Enter to continue...")

    def _get_default_port(self, service_name: str) -> int:
        """Get default port for a service."""
        ports = {
            "qbittorrent": 8080,
            "radarr": 7878,
            "sonarr": 8989,
            "prowlarr": 9696,
            "plex": 32400,
            "overseerr": 5055
        }
        return ports.get(service_name, 8080)

    def _discover_services(self):
        """Discover services from Docker containers."""
        self._auto_discover_services()
        input("Press Enter to continue...")

    def _manage_secrets(self):
        """Manage stored secrets."""
        secrets = self.registry._data.get("secrets", [])

        if not secrets:
            if self.console and HAS_RICH:
                self.console.print("[yellow]No secrets stored.[/yellow]")
            else:
                print("No secrets stored.")
            input("Press Enter to continue...")
            return

        if self.console and HAS_RICH:
            secrets_table = Table(title="Stored Secrets", show_header=True)
            secrets_table.add_column("Secret ID", style="cyan")
            secrets_table.add_column("Status", style="white")

            for secret_id in secrets:
                status = "✅ Stored" if self.registry.get_secret(secret_id) else "❌ Missing"
                secrets_table.add_row(secret_id, status)

            self.console.print("\n")
            self.console.print(secrets_table)
        else:
            print("\nStored Secrets:")
            for secret_id in secrets:
                status = "✅ Stored" if self.registry.get_secret(secret_id) else "❌ Missing"
                print(f"  {secret_id}: {status}")

        input("\nPress Enter to continue...")

    def _test_connectivity(self):
        """Test connectivity to configured services."""
        services = self.registry._data.get("services", {})

        if not services:
            if self.console and HAS_RICH:
                self.console.print("[yellow]No services configured for connectivity testing.[/yellow]")
            else:
                print("No services configured for connectivity testing.")
            input("Press Enter to continue...")
            return

        if self.console and HAS_RICH:
            conn_table = Table(title="Connectivity Test Results", show_header=True)
            conn_table.add_column("Service", style="cyan")
            conn_table.add_column("Status", style="white")
            conn_table.add_column("Response", style="dim")

            for name, svc_data in services.items():
                url = svc_data.get("url")
                if url:
                    try:
                        import requests
                        response = requests.head(url, timeout=5)
                        status = "✅ Connected" if response.status_code < 400 else f"❌ HTTP {response.status_code}"
                        conn_table.add_row(name, status, f"HTTP {response.status_code}")
                    except Exception as e:
                        conn_table.add_row(name, "❌ Failed", str(e))
                else:
                    conn_table.add_row(name, "⚠️ No URL", "Service URL not configured")

            self.console.print("\n")
            self.console.print(conn_table)
        else:
            print("\nConnectivity Test Results:")
            for name, svc_data in services.items():
                url = svc_data.get("url")
                if url:
                    try:
                        import requests
                        response = requests.head(url, timeout=5)
                        status = "✅ Connected" if response.status_code < 400 else f"❌ HTTP {response.status_code}"
                        print(f"  {name}: {status} (HTTP {response.status_code})")
                    except Exception as e:
                        print(f"  {name}: ❌ Failed ({e})")
                else:
                    print(f"  {name}: ⚠️ No URL configured")

        input("\nPress Enter to continue...")

    def _remove_service(self):
        """Remove a service from the registry."""
        services = self.registry._data.get("services", {})
        
        if not services:
            if self.console and HAS_RICH:
                self.console.print("[yellow]No services to remove.[/yellow]")
            else:
                print("No services to remove.")
            input("Press Enter to continue...")
            return

        # Select service to remove
        service_names = list(services.keys())
        
        from .utils.menu_navigation import create_menu
        
        # Create service removal menu
        service_options = [(name, f"🗑️ {name}", f"Remove {name} from registry") for name in service_names]
        service_options.append(("0", "⬅️ Back", "Return to registry menu"))
        
        service_name = create_menu("Select Service to Remove", service_options, self.console)
        
        if service_name == "0":
            return
        
        # Confirm removal
        if self.console and HAS_RICH:
            self.console.print(f"[yellow]⚠️ This will remove '{service_name}' from the registry.[/yellow]")
            self.console.print(f"[yellow]Associated secrets will remain in keyring.[/yellow]")
            
            if Confirm.ask(f"Are you sure you want to remove '{service_name}'?", default=False):
                del self.registry._data["services"][service_name]
                self.registry.save()
                self.console.print(f"[green]✅ Service '{service_name}' removed[/green]")
            else:
                self.console.print("[blue]Removal cancelled[/blue]")
        else:
            print(f"⚠️ This will remove '{service_name}' from the registry.")
            print(f"Associated secrets will remain in keyring.")
            
            response = input(f"Are you sure you want to remove '{service_name}'? (y/N): ").strip().lower()
            if response in ['y', 'yes']:
                del self.registry._data["services"][service_name]
                self.registry.save()
                print(f"✅ Service '{service_name}' removed")
            else:
                print("Removal cancelled")
        
        input("\nPress Enter to continue...")

    def troubleshoot_service(self):
        """Create a diagnostic snapshot for a specific service."""
        from .troubleshooter import ServiceTroubleshooter
        from pathlib import Path

        # Available services
        services = [
            ("qbittorrent", "qBittorrent"),
            ("radarr", "Radarr"),
            ("sonarr", "Sonarr"),
            ("prowlarr", "Prowlarr"),
            ("plex", "Plex Media Server"),
            ("overseerr", "Overseerr"),
            ("sabnzbd", "SABnzbd"),
            ("gluetun", "Gluetun VPN"),
        ]

        from .utils.menu_navigation import create_menu
        
        service_choice = create_menu("Select Service to Troubleshoot", 
                                   [(key, f"🩺 {name}", f"Create snapshot for {name}") for key, name in services] + 
                                   [("0", "⬅️ Back", "Return to main menu")], 
                                   self.console)
        
        if service_choice == "0":
            return
            
        service_key = service_choice

        try:
            troubleshooter = ServiceTroubleshooter(self.registry, self.docker_client)
            snapshot_path = troubleshooter.create_snapshot(service_key)

            if self.console and HAS_RICH:
                self.console.print(f"\n[bold green]✅ Service snapshot created![/bold green]")
                self.console.print(f"[blue]Snapshot saved to: {snapshot_path}[/blue]")
                self.console.print(f"\n[bold yellow]💡 Share this snapshot file with support for detailed analysis[/bold yellow]")
            else:
                print(f"\n✅ Service snapshot created!")
                print(f"Snapshot saved to: {snapshot_path}")
                print(f"\n💡 Share this snapshot file with support for detailed analysis")

            input("\nPress Enter to continue...")

        except Exception as e:
            if self.console and HAS_RICH:
                self.console.print(f"[red]❌ Troubleshooting failed: {e}[/red]")
            else:
                print(f"❌ Troubleshooting failed: {e}")
            input("\nPress Enter to continue...")

    def browse_reports(self):
        """Browse previous diagnostic reports."""
        from .utils.viewer import run_browser
        
        outputs_path = Path.home() / "mediastack-doctor" / "outputs"
        
        if not outputs_path.exists():
            if self.console and HAS_RICH:
                self.console.print("[yellow]No previous reports found.[/yellow]")
                self.console.print("[dim]Run diagnostics first to generate reports.[/dim]")
            else:
                print("No previous reports found.")
                print("Run diagnostics first to generate reports.")
            return
        
        try:
            if self.console and HAS_RICH:
                self.console.print("\n[bold blue]Opening report browser...[/bold blue]")
            else:
                print("\nOpening report browser...")
                
            run_browser(outputs_path)
        except Exception as e:
            if self.console and HAS_RICH:
                self.console.print(f"[red]Error browsing reports: {e}[/red]")
            else:
                print(f"Error browsing reports: {e}")
    
    def configure_services(self):
        """Interactive service configuration."""
        if self.console and HAS_RICH:
            self.console.print("\n[bold cyan]🔧 Service Configuration[/bold cyan]")
            self.console.print("[dim]Let's set up your media stack services...[/dim]\n")
        else:
            print("\n🔧 Service Configuration")
            print("Let's set up your media stack services...\n")
        
        # Auto-discovery first
        if self.docker_client:
            if self.console and HAS_RICH:
                if Confirm.ask("Would you like to auto-discover services from Docker containers?", default=True):
                    self._auto_discover_services()
            else:
                response = input("Would you like to auto-discover services from Docker containers? (Y/n): ").strip().lower()
                if response in ['', 'y', 'yes']:
                    self._auto_discover_services()
        
        # Manual configuration for key services
        key_services = [
            ("qbittorrent", "qBittorrent", "8080", True),  # needs_auth
            ("radarr", "Radarr", "7878", True),
            ("sonarr", "Sonarr", "8989", True),
            ("prowlarr", "Prowlarr", "9696", True),
            ("plex", "Plex Media Server", "32400", True),
            ("overseerr", "Overseerr", "5055", False),
        ]
        
        for service_key, service_name, default_port, needs_auth in key_services:
            self._configure_service(service_key, service_name, default_port, needs_auth)
        
        if self.console and HAS_RICH:
            self.console.print("\n[bold green]✅ Service configuration completed![/bold green]")
        else:
            print("\n✅ Service configuration completed!")
    
    def _auto_discover_services(self):
        """Auto-discover services from Docker containers."""
        try:
            discovered = self.docker_client.discover_services()
            
            if discovered:
                if self.console and HAS_RICH:
                    self.console.print(f"[green]Found {len(discovered)} services![/green]")
                else:
                    print(f"Found {len(discovered)} services!")
                
                # Save discovered services
                from .registry import ServiceRef
                for service_name, service_info in discovered.items():
                    svc = ServiceRef(
                        name=service_name,
                        url=service_info.get("url"),
                        container=service_info.get("container")
                    )
                    self.registry.set_service(svc)
                
                self.registry.save()
            else:
                if self.console and HAS_RICH:
                    self.console.print("[yellow]No services auto-discovered.[/yellow]")
                else:
                    print("No services auto-discovered.")
                    
        except Exception as e:
            if self.console and HAS_RICH:
                self.console.print(f"[red]Auto-discovery failed: {e}[/red]")
            else:
                print(f"Auto-discovery failed: {e}")
    
    def _configure_service(self, service_key: str, service_name: str, default_port: str, needs_auth: bool):
        """Configure a specific service."""
        existing = self.registry.get_service(service_key)
        
        if existing and existing.url:
            if self.console and HAS_RICH:
                current_url = existing.url
                self.console.print(f"[dim]{service_name} is already configured: {current_url}[/dim]")
                if not Confirm.ask(f"Reconfigure {service_name}?", default=False):
                    return
            else:
                current_url = existing.url
                print(f"{service_name} is already configured: {current_url}")
                response = input(f"Reconfigure {service_name}? (y/N): ").strip().lower()
                if response not in ['y', 'yes']:
                    return
        
        # Get URL
        if self.console and HAS_RICH:
            url = Prompt.ask(
                f"Enter {service_name} URL",
                default=f"http://localhost:{default_port}"
            )
        else:
            url = input(f"Enter {service_name} URL (default: http://localhost:{default_port}): ").strip()
            if not url:
                url = f"http://localhost:{default_port}"
        
        # Create service reference
        from .registry import ServiceRef
        svc = ServiceRef(name=service_key, url=url)
        
        # Get authentication if needed
        if needs_auth:
            self._configure_service_auth(service_key, service_name, svc)
        
        # Save service
        self.registry.set_service(svc)
        self.registry.save()
        
        if self.console and HAS_RICH:
            self.console.print(f"[green]✅ {service_name} configured[/green]")
        else:
            print(f"✅ {service_name} configured")
    
    def _configure_service_auth(self, service_key: str, service_name: str, svc):
        """Configure authentication for a service."""
        if service_key == "qbittorrent":
            # qBittorrent uses username/password
            if self.console and HAS_RICH:
                username = Prompt.ask(f"{service_name} username", default="admin")
                if Confirm.ask(f"Set password for {service_name}?", default=True):
                    password = Prompt.ask(f"{service_name} password", password=True)
                    if password:
                        secret_ref = f"{service_key}_password"
                        self.registry.set_secret(secret_ref, password)
                        svc.password_secret_ref = secret_ref
            else:
                username = input(f"{service_name} username (default: admin): ").strip() or "admin"
                response = input(f"Set password for {service_name}? (Y/n): ").strip().lower()
                if response in ['', 'y', 'yes']:
                    import getpass
                    password = getpass.getpass(f"{service_name} password: ")
                    if password:
                        secret_ref = f"{service_key}_password"
                        self.registry.set_secret(secret_ref, password)
                        svc.password_secret_ref = secret_ref
            
            svc.username = username
            
        else:
            # Arr services use API keys
            if self.console and HAS_RICH:
                if Confirm.ask(f"Set API key for {service_name}?", default=True):
                    self.console.print(f"[dim]Get API key from {service_name} Settings > General > Security[/dim]")
                    api_key = Prompt.ask(f"{service_name} API key", password=True)
                    if api_key:
                        secret_ref = f"{service_key}_api_key"
                        self.registry.set_secret(secret_ref, api_key)
                        svc.api_key_secret_ref = secret_ref
            else:
                response = input(f"Set API key for {service_name}? (Y/n): ").strip().lower()
                if response in ['', 'y', 'yes']:
                    print(f"Get API key from {service_name} Settings > General > Security")
                    import getpass
                    api_key = getpass.getpass(f"{service_name} API key: ")
                    if api_key:
                        secret_ref = f"{service_key}_api_key"
                        self.registry.set_secret(secret_ref, api_key)
                        svc.api_key_secret_ref = secret_ref

    def network_benchmarks(self):
        """Network performance testing."""
        if self.console and HAS_RICH:
            self.console.print("\n[bold cyan]🌐 Network Benchmarks[/bold cyan]\n")
            
            # Check for speedtest-cli
            import subprocess
            try:
                subprocess.run(["which", "speedtest-cli"], check=True, capture_output=True)
                speedtest_available = True
            except subprocess.CalledProcessError:
                speedtest_available = False
            
            if speedtest_available:
                if Confirm.ask("Run WAN speed test? (requires speedtest-cli)", default=False):
                    try:
                        self.console.print("[blue]Running WAN speed test...[/blue]")
                        result = subprocess.run(
                            ["speedtest-cli", "--simple"], 
                            capture_output=True, text=True, timeout=60
                        )
                        
                        if result.returncode == 0:
                            self.console.print("[green]WAN Speed Test Results:[/green]")
                            self.console.print(result.stdout)
                        else:
                            self.console.print(f"[red]Speed test failed: {result.stderr}[/red]")
                    except Exception as e:
                        self.console.print(f"[red]Speed test error: {e}[/red]")
            else:
                self.console.print("[yellow]speedtest-cli not available[/yellow]")
                self.console.print("[dim]Install with: sudo apt install speedtest-cli[/dim]")
            
            # Basic ping test
            if Confirm.ask("Run basic connectivity test?", default=True):
                targets = ["8.8.8.8", "1.1.1.1", "google.com"]
                
                ping_table = Table(title="Ping Test Results", show_header=True)
                ping_table.add_column("Target", style="cyan")
                ping_table.add_column("Status", style="white")
                ping_table.add_column("Latency", style="green")
                
                for target in targets:
                    try:
                        result = subprocess.run(
                            ["ping", "-c", "3", target],
                            capture_output=True, text=True, timeout=15
                        )
                        
                        if result.returncode == 0:
                            # Extract average latency
                            output = result.stdout
                            if "avg" in output:
                                latency_line = [line for line in output.split('\n') if 'avg' in line]
                                if latency_line:
                                    latency = latency_line[0].split('/')[-2] + "ms"
                                else:
                                    latency = "Success"
                            else:
                                latency = "Success"
                            ping_table.add_row(target, "✅ Reachable", latency)
                        else:
                            ping_table.add_row(target, "❌ Failed", "N/A")
                    except Exception:
                        ping_table.add_row(target, "❌ Error", "N/A")
                
                self.console.print(ping_table)
        else:
            print("\n🌐 Network Benchmarks")
            print("Network benchmarks require rich interface for best experience.")
            print("Use: pip install rich")
        
        input("\nPress Enter to continue...")
    
    def show_system_stats(self):
        """Show detailed system statistics."""
        import psutil
        from datetime import datetime
        
        if self.console and HAS_RICH:
            self.console.print("\n[bold cyan]📊 System Statistics[/bold cyan]\n")
            
            # System info table
            system_table = Table(title="System Information", show_header=True)
            system_table.add_column("Metric", style="cyan")
            system_table.add_column("Value", style="white")
            
            # CPU info
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            system_table.add_row("CPU Usage", f"{cpu_percent:.1f}%")
            system_table.add_row("CPU Cores", str(cpu_count))
            
            # Memory info
            memory = psutil.virtual_memory()
            system_table.add_row("Memory Usage", f"{memory.percent:.1f}% ({memory.used / (1024**3):.1f}GB / {memory.total / (1024**3):.1f}GB)")
            
            # Disk info
            disk = psutil.disk_usage('/')
            system_table.add_row("Root Disk", f"{disk.percent:.1f}% ({disk.used / (1024**3):.1f}GB / {disk.total / (1024**3):.1f}GB)")
            
            # Uptime
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            system_table.add_row("Uptime", str(uptime).split('.')[0])
            
            self.console.print(system_table)
            
            # Docker info if available
            if self.docker_client:
                containers = self.docker_client.list_containers()
                docker_table = Table(title="Docker Containers", show_header=True)
                docker_table.add_column("Name", style="cyan")
                docker_table.add_column("Status", style="white")
                docker_table.add_column("Image", style="dim")
                
                for container in containers[:10]:  # Show first 10
                    status_color = "green" if container["status"].startswith("Up") else "red"
                    docker_table.add_row(
                        container["name"],
                        f"[{status_color}]{container['status']}[/{status_color}]",
                        container.get("image", "unknown")
                    )
                
                self.console.print("\n")
                self.console.print(docker_table)
        else:
            print("\n📊 System Statistics\n")
            
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            print(f"CPU Usage: {cpu_percent:.1f}% ({cpu_count} cores)")
            print(f"Memory: {memory.percent:.1f}% ({memory.used / (1024**3):.1f}GB / {memory.total / (1024**3):.1f}GB)")
            print(f"Root Disk: {disk.percent:.1f}% ({disk.used / (1024**3):.1f}GB / {disk.total / (1024**3):.1f}GB)")
            
            if self.docker_client:
                containers = self.docker_client.list_containers()
                print(f"\nDocker Containers: {len(containers)} total")
                for container in containers[:5]:  # Show first 5
                    print(f"  {container['name']}: {container['status']}")
        
        input("\nPress Enter to continue...")
    
    def show_settings(self):
        """Show and modify settings."""
        if self.console and HAS_RICH:
            self.console.print("\n[bold cyan]🎛️ Settings[/bold cyan]\n")
            
            settings_table = Table(title="Current Settings", show_header=True)
            settings_table.add_column("Setting", style="cyan")
            settings_table.add_column("Value", style="white")
            settings_table.add_column("Description", style="dim")
            
            # Show current thresholds
            cpu_thresholds = self.thresholds.get("cpu", {})
            settings_table.add_row("CPU Warning", f"{cpu_thresholds.get('warn', 80)}%", "Warning threshold for CPU usage")
            settings_table.add_row("CPU Critical", f"{cpu_thresholds.get('fail', 90)}%", "Critical threshold for CPU usage")
            
            temp_thresholds = self.thresholds.get("temp_c", {})
            settings_table.add_row("Temperature Warning", f"{temp_thresholds.get('warn', 85)}°C", "Warning threshold for temperature")
            settings_table.add_row("Temperature Critical", f"{temp_thresholds.get('fail', 92)}°C", "Critical threshold for temperature")
            
            disk_thresholds = self.thresholds.get("disk_pct", {})
            settings_table.add_row("Disk Warning", f"{disk_thresholds.get('warn', 85)}%", "Warning threshold for disk usage")
            settings_table.add_row("Disk Critical", f"{disk_thresholds.get('fail', 95)}%", "Critical threshold for disk usage")
            
            self.console.print(settings_table)
            self.console.print()
            
            self.console.print("[bold yellow]📝 Threshold Configuration[/bold yellow]")
            self.console.print("[dim]To modify thresholds, edit the 'thresholds.yml' file in your project directory.[/dim]")
            self.console.print("[dim]Then run diagnostics with: --thresholds ./thresholds.yml[/dim]")
            self.console.print()
            
            # Show example thresholds.yml
            example_yaml = """[bold]Example thresholds.yml:[/bold]
[dim]```yaml
cpu:
  warn: 75.0
  fail: 85.0
temp_c:
  warn: 80.0
  fail: 90.0
disk_pct:
  warn: 80.0
  fail: 90.0
```[/dim]"""
            self.console.print(example_yaml)
            
        else:
            print("\n🎛️ Settings\n")
            
            cpu_thresholds = self.thresholds.get("cpu", {})
            temp_thresholds = self.thresholds.get("temp_c", {})
            disk_thresholds = self.thresholds.get("disk_pct", {})
            
            print("Current Thresholds:")
            print(f"  CPU Warning: {cpu_thresholds.get('warn', 80)}%")
            print(f"  CPU Critical: {cpu_thresholds.get('fail', 90)}%")
            print(f"  Temperature Warning: {temp_thresholds.get('warn', 85)}°C")
            print(f"  Temperature Critical: {temp_thresholds.get('fail', 92)}°C")
            print(f"  Disk Warning: {disk_thresholds.get('warn', 85)}%")
            print(f"  Disk Critical: {disk_thresholds.get('fail', 95)}%")
            print()
            
            print("To modify thresholds, edit the 'thresholds.yml' file in your project directory.")
            print("Then run diagnostics with: --thresholds ./thresholds.yml")
        
        input("\nPress Enter to continue...")

    def show_system_stats(self):
        """Show detailed system statistics."""
        import psutil
        from datetime import datetime

        if self.console and HAS_RICH:
            self.console.print("\n[bold cyan]📊 System Statistics[/bold cyan]\n")

            # System info table
            system_table = Table(title="System Information", show_header=True)
            system_table.add_column("Metric", style="cyan")
            system_table.add_column("Value", style="white")

            # CPU info
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            system_table.add_row("CPU Usage", f"{cpu_percent:.1f}%")
            system_table.add_row("CPU Cores", str(cpu_count))

            # Memory info
            memory = psutil.virtual_memory()
            system_table.add_row("Memory Usage", f"{memory.percent:.1f}% ({memory.used / (1024**3):.1f}GB / {memory.total / (1024**3):.1f}GB)")

            # Disk info
            disk = psutil.disk_usage('/')
            system_table.add_row("Root Disk", f"{disk.percent:.1f}% ({disk.used / (1024**3):.1f}GB / {disk.total / (1024**3):.1f}GB)")

            # Uptime
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            system_table.add_row("Uptime", str(uptime).split('.')[0])

            self.console.print(system_table)

            # Docker info if available
            if self.docker_client:
                containers = self.docker_client.list_containers()
                docker_table = Table(title="Docker Containers", show_header=True)
                docker_table.add_column("Name", style="cyan")
                docker_table.add_column("Status", style="white")
                docker_table.add_column("Image", style="dim")

                for container in containers[:10]:  # Show first 10
                    status_color = "green" if container["status"].startswith("Up") else "red"
                    docker_table.add_row(
                        container["name"],
                        f"[{status_color}]{container['status']}[/{status_color}]",
                        container.get("image", "unknown")
                    )

                self.console.print("\n")
                self.console.print(docker_table)
        else:
            print("\n📊 System Statistics\n")

            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            print(f"CPU Usage: {cpu_percent:.1f}% ({cpu_count} cores)")
            print(f"Memory: {memory.percent:.1f}% ({memory.used / (1024**3):.1f}GB / {memory.total / (1024**3):.1f}GB)")
            print(f"Root Disk: {disk.percent:.1f}% ({disk.used / (1024**3):.1f}GB / {disk.total / (1024**3):.1f}GB)")

            if self.docker_client:
                containers = self.docker_client.list_containers()
                print(f"\nDocker Containers: {len(containers)} total")
                for container in containers[:5]:  # Show first 5
                    print(f"  {container['name']}: {container['status']}")

        input("\nPress Enter to continue...")
    
    def show_help(self):
        """Show help information."""
        help_text = """
🏥 MediaStack Doctor Help

MAIN FEATURES:
• Full Diagnostics: Comprehensive health check of your entire media stack
• Quick Check: Fast system and Docker status check  
• Browse Reports: View previous diagnostic results interactively
• Service Config: Set up URLs, API keys, and credentials for your services
• System Stats: View detailed system performance information

GETTING STARTED:
1. Start with "Configure Services" to set up your media stack services
2. Run "Full Diagnostics" to get a complete health assessment
3. Use "Browse Reports" to explore the results and get actionable advice

SERVICE SETUP:
• qBittorrent: Needs username/password for API access
• Radarr/Sonarr/Prowlarr: Need API keys from Settings > General > Security  
• Plex: Needs authentication token for remote access checks
• Overseerr: Usually works without authentication

TIPS:
• Use auto-discovery to find Docker containers automatically
• Custom thresholds can be set for CPU, temperature, and disk usage
• Reports include specific commands to reproduce and fix issues
• The registry stores credentials securely using your OS keyring

For more help, check the generated reports or visit the GitHub repository.
        """
        
        if self.console and HAS_RICH:
            help_panel = Panel(
                help_text.strip(),
                title="Help & Documentation",
                style="blue"
            )
            self.console.print(help_panel)
        else:
            print(help_text)
        
        input("\nPress Enter to continue...")
    
    def run(self):
        """Main menu loop."""
        if not HAS_RICH:
            print("Note: Install 'rich' for enhanced display: pip install rich")
            print()

        # Check for missing credentials on first run
        self._check_missing_credentials()

        while True:
            try:
                self.show_banner()
                self.show_system_status()

                choice = self.show_main_menu()
                
                if choice == "0":
                    if self.console and HAS_RICH:
                        self.console.print("\n[bold blue]Thanks for using MediaStack Doctor! 👋[/bold blue]\n")
                    else:
                        print("\nThanks for using MediaStack Doctor! 👋\n")
                    break
                
                elif choice == "1":
                    if self.check_configuration():
                        self.run_diagnostics(quick=False)
                    else:
                        self.configure_services()
                
                elif choice == "2":
                    self.quick_system_check()
                
                elif choice == "3":
                    self.browse_reports()
                
                elif choice == "4":
                    self.configure_services()
                
                elif choice == "5":
                    self.registry_management()
                
                elif choice == "6":
                    self.show_system_stats()

                elif choice == "7":
                    self.troubleshoot_service()

                elif choice == "8":
                    self.network_benchmarks()

                elif choice == "9":
                    self.show_settings()

                elif choice == "10":
                    self.show_help()
                
                # Clear screen between menu iterations
                if self.console and HAS_RICH:
                    self.console.clear()
                else:
                    print("\n" * 2)  # Simple spacing for non-rich terminals
                    
            except KeyboardInterrupt:
                if self.console and HAS_RICH:
                    self.console.print("\n\n[yellow]Interrupted by user. Goodbye! 👋[/yellow]\n")
                else:
                    print("\n\nInterrupted by user. Goodbye! 👋\n")
                break
            except Exception as e:
                if self.console and HAS_RICH:
                    self.console.print(f"\n[red]An error occurred: {e}[/red]")
                    self.console.print("[dim]Press Enter to continue...[/dim]")
                else:
                    print(f"\nAn error occurred: {e}")
                    print("Press Enter to continue...")
                input()


def main():
    """Entry point for the main menu."""
    menu = MainMenu()
    menu.run()


if __name__ == "__main__":
    main()
