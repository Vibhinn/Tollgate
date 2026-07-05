from rich.prompt import Prompt
from rich.table import Table

from ..ui import console, step_header, success, error, info


def run(config: dict) -> dict:
    step_header(5, "Rate Limiting", total=6)

    info(
        "Tollgate uses a token-bucket limiter per user.\n"
        "  [dim]Burst allows short spikes above the sustained rate.[/dim]"
    )

    while True:
        raw = Prompt.ask("\n  [bold cyan]Sustained requests per second[/bold cyan] [dim](per user)[/dim]")
        if raw.isdigit() and int(raw) > 0:
            rps = int(raw)
            break
        error("Enter a positive integer")

    while True:
        raw = Prompt.ask(
            "  [bold cyan]Burst multiplier[/bold cyan] [dim](seconds of burst capacity, default 5)[/dim]",
            default="5",
        )
        if raw.isdigit() and int(raw) >= 1:
            burst = int(raw)
            break
        error("Enter a positive integer")

    max_tokens = rps * burst
    refill_rate = rps
    time_interval = 1.0

    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 3))
    table.add_column("Setting", style="bold white")
    table.add_column("Value", style="bold green")
    table.add_column("Meaning", style="dim")

    table.add_row("MAX_TOKENS", str(max_tokens), f"bucket capacity ({rps} req/s × {burst}s burst)")
    table.add_row("REFILL_RATE", str(refill_rate), f"tokens added per interval")
    table.add_row("TIME_INTERVAL", "1.0", "refill every second")

    console.print()
    console.print(table)

    config["rate_limiter"] = {
        "MAX_TOKENS": str(max_tokens),
        "REFILL_RATE": str(refill_rate),
        "TIME_INTERVAL": str(time_interval),
    }

    success("Rate limiter configured")
    return config
