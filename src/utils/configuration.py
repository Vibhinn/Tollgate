from configparser import ConfigParser

from src.utils.types import CONFIGURATION_OPTIONS, CONFIGURATION_SECTIONS

class Config:
    def __init__(self):
        self.config_parser = ConfigParser()
        self.config_parser.read("config.ini")

    def get_config(self, section: CONFIGURATION_SECTIONS, option: CONFIGURATION_OPTIONS):
        return self.config_parser.get(section=section, option=option)

