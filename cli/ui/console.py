from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

console = Console()

_BANNER = """\
[bold cyan]
 ████████╗ ██████╗ ██╗     ██╗      ██████╗  █████╗ ████████╗███████╗
    ██╔══╝██╔═══██╗██║     ██║     ██╔════╝ ██╔══██╗╚══██╔══╝██╔════╝
    ██║   ██║   ██║██║     ██║     ██║  ███╗███████║   ██║   █████╗
    ██║   ██║   ██║██║     ██║     ██║   ██║██╔══██║   ██║   ██╔══╝
    ██║   ╚██████╔╝███████╗███████╗╚██████╔╝██║  ██║   ██║   ███████╗
    ╚═╝    ╚═════╝ ╚══════╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚══════╝
[/bold cyan]"""


def print_banner() -> None:
    console.clear()
    console.print(_BANNER)
    console.print(
        Panel(
            "[bold white]LLM API Gateway  ·  Setup Wizard[/bold white]\n"
            "[dim]Configure your Tollgate instance in minutes[/dim]",
            style="cyan",
            padding=(1, 4),
            expand=False,
        )
    )
    console.print()


def step_header(number: int, title: str, total: int = 6) -> None:
    console.print()
    console.print(
        Rule(
            f"[bold cyan]Step {number}/{total}[/bold cyan]  [bold white]{title}[/bold white]",
            style="cyan dim",
        )
    )
    console.print()


def success(msg: str) -> None:
    console.print(f"  [bold green]✓[/bold green]  {msg}")


def warn(msg: str) -> None:
    console.print(f"  [bold yellow]⚠[/bold yellow]  {msg}")


def error(msg: str) -> None:
    console.print(f"  [bold red]✗[/bold red]  {msg}")


def info(msg: str) -> None:
    console.print(f"  [dim cyan]→[/dim cyan]  {msg}")
