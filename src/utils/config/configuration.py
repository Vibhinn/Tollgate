from configparser import ConfigParser
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import CONFIGURATION_OPTIONS, CONFIGURATION_SECTIONS


class Config:
    def __init__(self):
        self.config_parser = ConfigParser()
        self.config_parser.read("config.ini")

    def get_config(self, section: "CONFIGURATION_SECTIONS", option: "CONFIGURATION_OPTIONS") -> str:
        value = self.config_parser.get(section=section, option=option)
        if value.startswith("gAAAA"):
            from ..crypto import decrypt_value
            return decrypt_value(value)
        return value
