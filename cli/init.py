import click
from .helpers import run_initialization_setup, change_configuration


@click.group()
def cli():
    pass

@cli.command()
def init():
    run_initialization_setup()

@cli.command()
def change():
    change_configuration()


