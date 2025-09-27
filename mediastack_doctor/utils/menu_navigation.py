"""Arrow key navigation for menus."""

import sys
import termios
import tty
from typing import List, Tuple, Optional

try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    Console = None


class ArrowMenu:
    """Menu with arrow key navigation."""
    
    def __init__(self, title: str, options: List[Tuple[str, str, str]], console: Optional[Console] = None):
        """
        Initialize menu.
        
        Args:
            title: Menu title
            options: List of (key, action, description) tuples
            console: Rich console instance
        """
        self.title = title
        self.options = options
        self.console = console
        self.selected_index = 0
        
    def show_menu(self) -> str:
        """Show menu and handle navigation. Returns selected option key."""
        if not HAS_RICH or not self.console:
            return self._fallback_menu()
        
        # Check if we're in a terminal that supports arrow keys
        if not sys.stdin.isatty():
            return self._fallback_menu()
        
        try:
            return self._arrow_menu()
        except Exception:
            # Fallback to typed menu if arrow keys don't work
            return self._fallback_menu()
    
    def _arrow_menu(self) -> str:
        """Menu with arrow key navigation."""
        while True:
            # Clear screen and show menu
            self.console.clear()
            self._render_menu()
            
            # Get key input
            key = self._get_key()
            
            if key == 'up':
                self.selected_index = (self.selected_index - 1) % len(self.options)
            elif key == 'down':
                self.selected_index = (self.selected_index + 1) % len(self.options)
            elif key == 'enter':
                return self.options[self.selected_index][0]
            elif key == 'escape' or key == 'q':
                # Return exit option if available, otherwise first option
                exit_options = [opt for opt in self.options if opt[0] in ['0', 'exit', 'back']]
                return exit_options[0][0] if exit_options else self.options[0][0]
    
    def _render_menu(self):
        """Render the menu with current selection highlighted."""
        if self.console and HAS_RICH:
            # Show title
            self.console.print(f"\n[bold blue]{self.title}[/bold blue]\n")
            
            # Create menu table
            menu_table = Table(show_header=False, box=None, padding=(0, 1))
            menu_table.add_column("Selector", style="bold cyan", width=3)
            menu_table.add_column("Action", style="bold white", width=25)
            menu_table.add_column("Description", style="dim", width=35)
            
            for i, (key, action, description) in enumerate(self.options):
                if i == self.selected_index:
                    # Highlight selected option
                    menu_table.add_row(
                        "►",
                        f"[reverse]{action}[/reverse]",
                        f"[reverse]{description}[/reverse]"
                    )
                else:
                    menu_table.add_row("", action, description)
            
            self.console.print(menu_table)
            self.console.print("\n[dim]Use ↑↓ arrows to navigate, Enter to select, Esc/Q to go back[/dim]")
    
    def _fallback_menu(self) -> str:
        """Fallback menu with typed input."""
        if self.console and HAS_RICH:
            menu_table = Table(title=self.title, show_header=False, box=None)
            menu_table.add_column("Option", style="bold cyan", width=3)
            menu_table.add_column("Action", style="bold white", width=25)
            menu_table.add_column("Description", style="dim", width=35)
            
            for key, action, description in self.options:
                menu_table.add_row(key, action, description)
            
            self.console.print(menu_table)
            self.console.print()
            
            from rich.prompt import Prompt
            choice = Prompt.ask(
                "[bold yellow]Choose an option[/bold yellow]",
                choices=[opt[0] for opt in self.options],
                default=self.options[0][0]
            )
        else:
            print(f"\n{self.title}:")
            for key, action, description in self.options:
                print(f"  {key}. {action} - {description}")
            print()
            
            while True:
                choice = input(f"Choose an option ({'/'.join([opt[0] for opt in self.options])}): ").strip()
                if choice in [opt[0] for opt in self.options]:
                    break
                print("Invalid choice. Please try again.")
        
        return choice
    
    def _get_key(self) -> str:
        """Get a single keypress."""
        try:
            # Save terminal settings
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            
            try:
                # Set terminal to raw mode
                tty.setraw(sys.stdin.fileno())
                
                # Read key
                ch = sys.stdin.read(1)
                
                # Handle escape sequences (arrow keys)
                if ch == '\x1b':
                    ch += sys.stdin.read(2)
                    if ch == '\x1b[A':
                        return 'up'
                    elif ch == '\x1b[B':
                        return 'down'
                    elif ch == '\x1b[C':
                        return 'right'
                    elif ch == '\x1b[D':
                        return 'left'
                    else:
                        return 'escape'
                elif ch == '\r' or ch == '\n':
                    return 'enter'
                elif ch == '\x1b':
                    return 'escape'
                elif ch == 'q' or ch == 'Q':
                    return 'q'
                elif ch == '\x03':  # Ctrl+C
                    raise KeyboardInterrupt
                else:
                    return ch
                    
            finally:
                # Restore terminal settings
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                
        except Exception:
            # Fallback for non-terminal environments
            return 'enter'


def create_menu(title: str, options: List[Tuple[str, str, str]], console: Optional[Console] = None) -> str:
    """
    Create and show a menu with arrow key navigation.
    
    Args:
        title: Menu title
        options: List of (key, action, description) tuples
        console: Rich console instance
        
    Returns:
        Selected option key
    """
    menu = ArrowMenu(title, options, console)
    return menu.show_menu()
