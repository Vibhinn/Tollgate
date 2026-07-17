import sys
from pathlib import Path

from cryptography.fernet import Fernet

from ..ui import console
from ..steps import guardrail, download_model, services, admin_setup, providers, rate_limiting, finalize

def run_setup() -> None:
    from ..ui.console import print_banner
    print_banner()

    config: dict = {}
    try:
        config = guardrail.run(config)
        config["_fernet_key"] = Fernet.generate_key()

        config = download_model.run(config)
        config = services.run(config)
        config = admin_setup.run(config)
        config = providers.run(config)
        config = rate_limiting.run(config)
        config = finalize.run(config)

    except KeyboardInterrupt:
        Path(".tollgate.key.tmp").unlink(missing_ok=True)
        Path("config.yaml.tmp").unlink(missing_ok=True)
        console.print("\n\n  [bold yellow]Setup cancelled — no files were written.[/bold yellow]\n")
        sys.exit(0)
