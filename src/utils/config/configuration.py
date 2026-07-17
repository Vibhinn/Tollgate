import yaml
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import CONFIGURATION_OPTIONS, CONFIGURATION_SECTIONS, CONFIGURATION_SUB_SECTIONS

class Config:
    def __init__(self):
        with open("config.yaml") as f:
            self._data: dict = yaml.safe_load(f)

    def get_entire_config_section(self, section: CONFIGURATION_SECTIONS) -> dict:
        return self._data.get(section, {})

    def get_config(self, section: CONFIGURATION_SECTIONS, option: CONFIGURATION_OPTIONS, sub_section: CONFIGURATION_SUB_SECTIONS = None) -> str:
        if sub_section:
            value = self._data.get(section)[sub_section][option]
        else:
            value = self._data[section][option]

        if value.startswith("gAAAA"):
            from ..crypto import decrypt_value
            return decrypt_value(value)
        return value
