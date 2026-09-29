import os
import sys
from pathlib import Path

import click

from .helpers import run_initialization_setup, print_configuration, change_configuration
from .ui import error
from src.utils.config import Config

_APP_DIR = os.environ.get("TOLLGATE_APP_DIR", ".")


@click.group()
def cli():
    pass #need to keep tis empty

@cli.command()
def init():
    run_initialization_setup()

@cli.command()
@click.option("--change", "change_mode", is_flag=True, help="Interactively change a specific setting.")
def config(change_mode: bool):
    if change_mode:
        change_configuration()
    else:
        print_configuration()

@cli.command()
def start():
    if not Path("config.yaml").exists():
        error("No config.yaml found. Run: tollgate init")
        sys.exit(1)

    try:
        Config()
    except Exception as e:
        error(f"config.yaml could not be loaded: {e}")
        sys.exit(1)

    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=13000, app_dir=_APP_DIR)


