import yaml
import os
import logging
import sys

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "config/settings.yaml")

class Config:
    def __init__(self):
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            self._raw = yaml.safe_load(f)

        # Read server section
        server = self._raw.get("server", {})
        self.server_name = server.get("name", "performance_mcp")
        self.server_port = server.get("port", 8300)
        
        # Authentication configuration
        auth_config = server.get("authentication", {})
        self.auth_enabled = auth_config.get("enabled", False)
        self.api_keys = {
            key_config["key"]: key_config["name"] 
            for key_config in auth_config.get("api_keys", [])
        }

        # Logging configuration
        log_config = self._raw.get("logging", {})
        self.log_level = log_config.get("level", "INFO").upper()
        self.show_tool_calls = log_config.get("show_tool_calls", True)
        self.show_sql_queries = log_config.get("show_sql_queries", False)
        
        # DEBUG: Force print to stderr to see in Docker logs
        sys.stderr.write(f"[CONFIG-DEBUG] show_sql_queries = {self.show_sql_queries}\n")
        sys.stderr.flush()

        # Oracle analysis configuration
        oracle_analysis = self._raw.get("oracle_analysis", {})
        self.output_preset = oracle_analysis.get("output_preset", "standard").lower()

        # Performance monitoring configuration
        self.performance_monitoring = self._raw.get("performance_monitoring", {})

        # Database presets
        self.database_presets = self._raw.get("database_presets", {})

                # Startup configuration
        startup_config = self._raw.get("startup", {})
        self.check_db_connections = startup_config.get("check_db_connections", False)
        
        # PostgreSQL cache configuration
        pg_config = self._raw.get("postgresql_cache", {})
        self.postgresql_cache = {
            "host": pg_config.get("host", "pg"),
            "port": pg_config.get("port", 5432),
            "database": pg_config.get("database", "omni"),
            "user": pg_config.get("user", "omni"),
            "password": pg_config.get("password", "postgres"),
            "schema": pg_config.get("schema", "mcp_performance"),
            "pool": pg_config.get("pool", {"min_size": 1, "max_size": 10}),
            "cache_ttl": pg_config.get("cache_ttl", {
                "table_knowledge": 7,
                "relationships": 7,
                "query_explanations": 30
            }),
            "error_handling": pg_config.get("error_handling", {
                "log_all_errors": True,
                "raise_on_connection_failure": False,
                "retry_attempts": 3,
                "retry_delay_seconds": 1
            })
                }

    def get_db_preset(self, name):
        if name not in self.database_presets:
            raise KeyError(f"DB preset '{name}' is not defined in settings.yaml")
        return self.database_presets[name]
    
    def get_postgresql_config(self):
        """Get PostgreSQL cache configuration with environment variable overrides."""
        config = self.postgresql_cache.copy()

        # Allow environment variable overrides
        config["host"] = os.getenv("KNOWLEDGE_DB_HOST", config["host"])
        config["port"] = int(os.getenv("KNOWLEDGE_DB_PORT", config["port"]))
        config["database"] = os.getenv("KNOWLEDGE_DB_NAME", config["database"])
        config["user"] = os.getenv("KNOWLEDGE_DB_USER", config["user"])
        config["password"] = os.getenv("KNOWLEDGE_DB_PASSWORD", config["password"])
        config["schema"] = os.getenv("KNOWLEDGE_DB_SCHEMA", config["schema"])

        return config

    def is_feedback_enabled(self):
        """Check if feedback system is enabled."""
        feedback_config = self._raw.get("feedback", {})
        return feedback_config.get("enabled", False)

config = Config()
