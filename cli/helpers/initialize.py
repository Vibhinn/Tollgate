import secrets
from pathlib import Path
from ..inputs import DATABASE

def generate_config_ini_file():
    config_file_path = Path('config.ini')

    if not config_file_path.exists():
        config_file_path.touch()

def set_encryption_key():
    print("Before we begin, please set your encryption key in order to encrypt your API credentials")
    encryption_key: str = input("Enter your key (press ENTER if you don't have any)")

    if not encryption_key:
        encryption_key = secrets.token_hex(32)



def ask_database_type():
    print("Please input the database type for your application")
    print("============")
    print("Supported databases - SQLite, PostgreSQL, MySQL (default SQLite)")

    database_input = input()
    normalized_input = database_input.upper()

    if normalized_input not in DATABASE:
        raise ValueError("Please select from these 3 only - SQLite, PostgreSQL, MySQL. Type name and press enter (default is SQLite)")


def populate_config_ini_section():
    pass