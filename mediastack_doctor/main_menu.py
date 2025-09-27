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
        menu_options = [
            ("1", "🔍 Run Full Diagnostics", "Complete system health check"),
            ("2", "📊 Quick System Check", "Fast host and Docker status"),
            ("3", "📁 Browse Previous Reports", "View past diagnostic results"),
            ("4", "⚙️ Configure Services", "Set up service URLs and credentials"),
            ("5", "🔧 Registry Management", "Manage service registry"),
            ("6", "📈 System Statistics", "View detailed system info"),
            ("7", "🌐 Network Benchmarks", "Test network performance"),
            ("8", "🎛️ Settings", "Configure thresholds and options"),
            ("9", "❓ Help", "Show help and documentation"),
            ("0", "🚪 Exit", "Exit MediaStack Doctor")
        ]
        
        if self.console and HAS_RICH:
            menu_table = Table(title="Main Menu", show_header=False, box=None)
            menu_table.add_column("Option", style="bold cyan", width=3)
            menu_table.add_column("Action", style="bold white", width=25)
            menu_table.add_column("Description", style="dim", width=35)
            
            for option, action, description in menu_options:
                menu_table.add_row(option, action, description)
            
            self.console.print(menu_table)
            self.console.print()
            
            choice = Prompt.ask(
                "[bold yellow]Choose an option[/bold yellow]",
                choices=[opt[0] for opt in menu_options],
                default="1"
            )
        else:
            print("Main Menu:")
            for option, action, description in menu_options:
                print(f"  {option}. {action} - {description}")
            print()
            
            while True:
                choice = input("Choose an option (1-9, 0 to exit): ").strip()
                if choice in [opt[0] for opt in menu_options]:
                    break
                print("Invalid choice. Please try again.")
        
        return choice
    
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
        from .cli import run
        from datetime import datetime
        
        # Prepare arguments
        sections = "host,docker" if quick else None
        
        if self.console and HAS_RICH:
            self.console.print(f"\n[bold green]{'Quick' if quick else 'Full'} Diagnostics Starting...[/bold green]")
        else:
            print(f"\n{'Quick' if quick else 'Full'} Diagnostics Starting...")
        
        # Create a mock context for the run function
        class MockContext:
            def __init__(self):
                self.obj = {
                    "output_dir": Path.home() / "mediastack-doctor" / "outputs",
                    "redact": True,
                    "allow_external_checks": False
                }
        
        try:
            # Call the run function directly
            from .cli import run as cli_run
            ctx = MockContext()
            
            # Run diagnostics
            cli_run(
                ctx=ctx,
                qb_url=None, qb_user=None, qb_pass=None,
                plex_token=None, plex_url=None,
                cloudflared_metrics=None, gluetun_host=None,
                nic=None, pcap=None,
                advisor=True, diff=None, sections=sections,
                netbench="skip", deep=False,
                verbose=True, thresholds=None
            )
            
            if self.console and HAS_RICH:
                self.console.print("\n[bold green]✅ Diagnostics completed![/bold green]")
                
                if Confirm.ask("Would you like to browse the results now?", default=True):
                    self.browse_reports()
            else:
                print("\n✅ Diagnostics completed!")
                response = input("Would you like to browse the results now? (Y/n): ").strip().lower()
                if response in ['', 'y', 'yes']:
                    self.browse_reports()
                    
        except Exception as e:
            if self.console and HAS_RICH:
                self.console.print(f"[red]❌ Diagnostics failed: {e}[/red]")
            else:
                print(f"❌ Diagnostics failed: {e}")
    
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
            
            # Show current thresholds
            cpu_thresholds = self.thresholds.get("cpu", {})
            settings_table.add_row("CPU Warning", f"{cpu_thresholds.get('warn', 80)}%")
            settings_table.add_row("CPU Critical", f"{cpu_thresholds.get('fail', 90)}%")
            
            temp_thresholds = self.thresholds.get("temp_c", {})
            settings_table.add_row("Temperature Warning", f"{temp_thresholds.get('warn', 85)}°C")
            settings_table.add_row("Temperature Critical", f"{temp_thresholds.get('fail', 92)}°C")
            
            self.console.print(settings_table)
            
            if Confirm.ask("Would you like to modify thresholds?", default=False):
                self._modify_thresholds()
        else:
            print("\n🎛️ Settings\n")
            
            cpu_thresholds = self.thresholds.get("cpu", {})
            temp_thresholds = self.thresholds.get("temp_c", {})
            
            print(f"CPU Warning: {cpu_thresholds.get('warn', 80)}%")
            print(f"CPU Critical: {cpu_thresholds.get('fail', 90)}%")
            print(f"Temperature Warning: {temp_thresholds.get('warn', 85)}°C")
            print(f"Temperature Critical: {temp_thresholds.get('fail', 92)}°C")
            
            response = input("Would you like to modify thresholds? (y/N): ").strip().lower()
            if response in ['y', 'yes']:
                self._modify_thresholds()
    
    def _modify_thresholds(self):
        """Modify threshold settings."""
        # This is a simplified version - in a full implementation,
        # you'd want to save custom thresholds to a file
        if self.console and HAS_RICH:
            self.console.print("[dim]Threshold modification coming in a future update...[/dim]")
        else:
            print("Threshold modification coming in a future update...")
    
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
                    self.run_diagnostics(quick=True)
                
                elif choice == "3":
                    self.browse_reports()
                
                elif choice == "4":
                    self.configure_services()
                
                elif choice == "5":
                    # Registry management - could call existing CLI commands
                    if self.console and HAS_RICH:
                        self.console.print("[dim]Use 'mediastack-doctor registry' commands for advanced registry management[/dim]")
                    else:
                        print("Use 'mediastack-doctor registry' commands for advanced registry management")
                
                elif choice == "6":
                    self.show_system_stats()
                
                elif choice == "7":
                    if self.console and HAS_RICH:
                        self.console.print("[dim]Network benchmarks coming in a future update...[/dim]")
                    else:
                        print("Network benchmarks coming in a future update...")
                    input("Press Enter to continue...")
                
                elif choice == "8":
                    self.show_settings()
                
                elif choice == "9":
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
