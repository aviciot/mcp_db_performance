import yaml
import os

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "config/settings.yaml")

class Config:
    def __init__(self):
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            self._raw = yaml.safe_load(f)

        # Read server section
        server = self._raw.get("server", {})
        self.server_name = server.get("name", "oracle_performance_mcp")
        self.server_port = server.get("port", 8300)

        # Database presets
        self.database_presets = self._raw.get("database_presets", {})

    def get_db_preset(self, name):
        if name not in self.database_presets:
            raise KeyError(f"DB preset '{name}' is not defined in settings.yaml")
        return self.database_presets[name]

config = Config()
