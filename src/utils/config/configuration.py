from configparser import ConfigParser

class Config:
    def __init__(self):
        self.config_parser = ConfigParser()
        self.config_parser.read("config.ini")

    def get_config(self, section, option):
        return self.config_parser.get(section=section, option=option)

