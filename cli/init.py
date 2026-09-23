import click
from .helpers import run_initialization_setup, print_configuration, change_configuration


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


