# server/history_tracker.py
# Query execution history tracking with SQLite

import sqlite3
import hashlib
import re
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("history_tracker")

# Database location
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "query_history.db"


def init_db():
    """Initialize the SQLite database with schema."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS executions (
            fingerprint TEXT NOT NULL,
            db_name TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            plan_hash TEXT,
            cost INTEGER,
            table_stats TEXT,
            plan_operations TEXT
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_lookup 
        ON executions(fingerprint, db_name, timestamp DESC)
    """)
    conn.commit()
    conn.close()
    logger.info(f"📁 History database initialized at {DB_PATH}")


def normalize_and_hash(sql: str) -> str:
    """
    Normalize SQL query and return MD5 hash fingerprint.
    Replaces literals with placeholders so structurally identical queries match.
    
    Examples:
        WHERE id IN (12345, 67890) → WHERE id IN (:N, :N)
        WHERE name = 'John' → WHERE name = :S
    """
    if not sql:
        return ""
    
    # Strip trailing semicolons first (common difference between runs)
    sql = sql.rstrip(';').strip()
    
    # Normalize: replace numbers and strings with placeholders
    normalized = re.sub(r'\b\d+\b', ':N', sql)  # Numbers
    normalized = re.sub(r"'[^']*'", ':S', normalized)  # Strings
    normalized = re.sub(r'\s+', ' ', normalized).strip().upper()  # Whitespace
    
    # Debug logging
    fingerprint = hashlib.md5(normalized.encode()).hexdigest()
    logger.debug(f"🔑 Normalized SQL: {normalized[:100]}...")
    logger.debug(f"🔑 Fingerprint: {fingerprint}")
    
    # Hash for compact storage
    return fingerprint


def store_history(fingerprint: str, db_name: str, plan_hash: str, cost: int, 
                  table_stats: dict, plan_operations: list):
    """
    Store query execution record in history.
    
    Args:
        fingerprint: MD5 hash of normalized query
        db_name: Database name
        plan_hash: Oracle plan_hash_value
        cost: Optimizer cost
        table_stats: Dict of {table_name: num_rows}
        plan_operations: List of key operations like ["INDEX RANGE SCAN", "HASH JOIN"]
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT INTO executions VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            fingerprint,
            db_name,
            datetime.now().isoformat(),
            plan_hash or "unknown",
            cost,
            json.dumps(table_stats),
            json.dumps(plan_operations)
        ))
        conn.commit()
        conn.close()
        logger.info(f"💾 Stored execution: fingerprint={fingerprint[:8]}..., cost={cost}")
    except Exception as e:
        logger.warning(f"⚠️  Failed to store history: {e}")


def get_recent_history(fingerprint: str, db_name: str, days: int = 30) -> list:
    """
    Fetch recent execution history for a query fingerprint.
    
    Returns:
        List of dicts with timestamp, plan_hash, cost, table_stats, plan_operations
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute("""
            SELECT timestamp, plan_hash, cost, table_stats, plan_operations
            FROM executions
            WHERE fingerprint = ? AND db_name = ?
              AND timestamp >= datetime('now', '-' || ? || ' days')
            ORDER BY timestamp DESC
            LIMIT 10
        """, (fingerprint, db_name, days))
        
        rows = []
        for r in cur.fetchall():
            rows.append({
                "timestamp": r[0],
                "plan_hash": r[1],
                "cost": r[2],
                "table_stats": json.loads(r[3]) if r[3] else {},
                "plan_operations": json.loads(r[4]) if r[4] else []
            })
        
        conn.close()
        logger.info(f"📊 Found {len(rows)} historical executions for fingerprint {fingerprint[:8]}...")
        return rows
    
    except Exception as e:
        logger.warning(f"⚠️  Failed to fetch history: {e}")
        return []


def compare_with_history(history: list, current_facts: dict) -> dict:
    """
    Compare current execution with historical data.
    
    Returns:
        Dict with status, message, and metrics about performance change
    """
    if not history:
        return {
            "status": "new_query",
            "message": "First time analyzing this query structure"
        }
    
    last = history[0]  # Most recent execution
    current_plan = current_facts.get("plan_details", [])
    
    if not current_plan:
        return {"status": "no_plan", "message": "No execution plan available"}
    
    current_plan_hash = current_plan[0].get("plan_hash_value", "unknown")
    current_cost = current_plan[0].get("cost", 0)
    
    # Extract key operations from current plan
    current_operations = [
        f"{step.get('operation', '')} {step.get('options', '')}".strip()
        for step in current_plan[:5]  # Top 5 operations
    ]
    
    # Same plan hash = optimizer using same strategy
    if last["plan_hash"] == current_plan_hash:
        if current_cost == 0 or last["cost"] == 0:
            return {
                "status": "stable",
                "message": "Plan unchanged (cost data unavailable)"
            }
        
        cost_change_pct = ((current_cost - last["cost"]) / last["cost"]) * 100
        
        if abs(cost_change_pct) < 10:
            return {
                "status": "stable",
                "cost_change_pct": round(cost_change_pct, 1),
                "message": "✅ Performance stable - consistent with previous execution"
            }
        else:
            # Check if table sizes changed
            current_tables = {t["table_name"]: t["num_rows"] for t in current_facts.get("table_stats", [])}
            table_growth = []
            
            for table, old_rows in last["table_stats"].items():
                new_rows = current_tables.get(table, old_rows)
                if new_rows != old_rows and old_rows > 0:
                    growth_pct = ((new_rows - old_rows) / old_rows) * 100
                    table_growth.append(f"{table}: {growth_pct:+.0f}%")
            
            return {
                "status": "data_growth",
                "cost_change_pct": round(cost_change_pct, 1),
                "table_growth": table_growth,
                "message": f"⚠️  Cost changed {cost_change_pct:+.0f}% - likely due to data growth: {', '.join(table_growth)}"
            }
    
    # Different plan = optimizer changed strategy
    else:
        if current_cost == 0 or last["cost"] == 0:
            return {
                "status": "plan_changed",
                "old_plan_hash": last["plan_hash"],
                "new_plan_hash": current_plan_hash,
                "message": "⚠️  Execution plan changed (cost comparison unavailable)"
            }
        
        is_better = current_cost < last["cost"]
        cost_change_pct = ((current_cost - last["cost"]) / last["cost"]) * 100
        
        # Detect significant operation changes
        old_ops = last["plan_operations"]
        operation_changes = []
        
        if any("FULL" in op for op in current_operations) and not any("FULL" in op for op in old_ops):
            operation_changes.append("Added FULL TABLE SCAN")
        if any("INDEX" in op for op in current_operations) and not any("INDEX" in op for op in old_ops):
            operation_changes.append("Now using INDEX")
        
        return {
            "status": "plan_changed",
            "improved": is_better,
            "cost_change_pct": round(cost_change_pct, 1),
            "old_plan_hash": last["plan_hash"],
            "new_plan_hash": current_plan_hash,
            "operation_changes": operation_changes,
            "message": (
                f"✅ Plan improved {abs(cost_change_pct):.0f}%! Optimizer found better strategy."
                if is_better else
                f"⚠️  Plan regressed {abs(cost_change_pct):.0f}%! Review optimizer statistics. Changes: {', '.join(operation_changes) if operation_changes else 'Unknown'}"
            )
        }


# Initialize database on module import
init_db()
