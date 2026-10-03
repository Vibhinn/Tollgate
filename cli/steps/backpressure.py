from rich.prompt import Prompt

from ..ui import step_header, success, error, info

DEFAULT_MAX_IN_FLIGHT = "50"


def ask_max_in_flight(default: str = DEFAULT_MAX_IN_FLIGHT) -> str:
    while True:
        raw = Prompt.ask(
            f"\n  [bold cyan]Max requests in flight[/bold cyan] [dim](default {default})[/dim]",
            default=default,
        )
        if raw.isdigit() and int(raw) > 0:
            return raw
        error("Enter a positive integer")


def run(config: dict) -> dict:
    step_header(7, "Backpressure", total=8)

    info(
        "Once this many requests are being processed at the same time, new ones get\n"
        "  a 503 with a Retry-After header instead of piling up and timing out.\n"
        "  [dim]Lower it on small boxes or heavy \"smart\" traffic. Tune it with a k6 ramp.[/dim]"
    )

    max_in_flight = ask_max_in_flight()
    config["backpressure"] = {"max_in_flight": max_in_flight}

    success(f"Backpressure set to [bold]{max_in_flight}[/bold] requests in flight")
    return config
