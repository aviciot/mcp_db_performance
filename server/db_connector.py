# server/db_connector.py

import os
import oracledb
import logging
from config import config

logger = logging.getLogger("db-check")

# Ensure UTF-8 handling for Oracle Thin mode
os.environ["NLS_LANG"] = ".AL32UTF8"


class OracleConnector:
    def connect(self, preset_name: str):
        p = config.get_db_preset(preset_name)

        # Thin mode → cannot use encoding=
        return oracledb.connect(
            user=p["user"],
            password=p["password"],
            dsn=p["dsn"]
        )

    def test_connection(self, preset_name: str) -> bool:
        try:
            conn = self.connect(preset_name)
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM dual")
            cur.fetchone()
            cur.close()
            conn.close()
            logger.info(f"✅ DB preset '{preset_name}' is reachable.")
            return True
        except Exception as e:
            logger.error(f"❌ DB preset '{preset_name}' unreachable: {e}")
            return False

oracle_connector = OracleConnector()
