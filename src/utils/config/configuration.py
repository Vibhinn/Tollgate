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

    def get_config(
        self,
        section: CONFIGURATION_SECTIONS,
        option: CONFIGURATION_OPTIONS,
        sub_section: CONFIGURATION_SUB_SECTIONS | list[str] = None,
    ) -> str:
        value = self._data[section]
        if sub_section:
            path = sub_section if isinstance(sub_section, list) else [sub_section]
            for key in path:
                value = value[key]
        value = value[option]

        if value.startswith("gAAAA"):
            from ..crypto import decrypt_value
            return decrypt_value(value)
        return value
