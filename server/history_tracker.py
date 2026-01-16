# server/history_tracker_postgres.py
# Query execution history tracking with PostgreSQL (migrated from SQLite)

import os
import hashlib
import re
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import asyncpg
from knowledge_db import get_knowledge_db

logger = logging.getLogger("history_tracker_postgres")
logger.info("[history_tracker_postgres.py] Script started. PID: %s", os.getpid())


class QueryHistoryTracker:
    """
    Query execution history tracking using PostgreSQL.
    Migrated from SQLite history_tracker.py to use unified storage.
    """
    
    def __init__(self, schema: str = None):
        self.schema = schema or os.getenv("KNOWLEDGE_DB_SCHEMA", "mcp_performance")
        self.mcp_instance_id = os.getenv("MCP_INSTANCE_ID", "performance_mcp")
        self.knowledge_db = get_knowledge_db(schema=self.schema)
        logger.info(f"Query History Tracker initialized: schema={self.schema}, instance_id={self.mcp_instance_id}")
    
    async def ensure_connected(self):
        """Ensure PostgreSQL connection is available."""
        if not self.knowledge_db.is_enabled:
            print(f"[QueryHistoryTracker] Connecting to Postgres for schema={self.schema}")
            try:
                await self.knowledge_db.connect()
            except Exception as e:
                print(f"[QueryHistoryTracker] ERROR connecting to Postgres: {e} (schema={self.schema})")
                logger.error(f"[QueryHistoryTracker] ERROR connecting to Postgres: {e}", exc_info=True)
    
    def normalize_and_hash(self, sql: str) -> str:
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
        
        return fingerprint
    
    async def store_history(
        self,
        fingerprint: str,
        db_name: str,
        plan_hash: Optional[str],
        cost: int,
        table_stats: Dict[str, Any],
        plan_operations: List[str],
        sql_sample: Optional[str] = None,
        execution_time_ms: Optional[int] = None,
        buffer_gets: Optional[int] = None,
        physical_reads: Optional[int] = None
    ):
        """
        Store query execution record in PostgreSQL history.
        """
        try:
            await self.ensure_connected()
            # Truncate SQL sample for storage
            if sql_sample and len(sql_sample) > 500:
                sql_sample = sql_sample[:500] + "..."
            print(f"[QueryHistoryTracker] Storing history for fingerprint={fingerprint[:8]}..., db={db_name}, schema={self.schema}")
            await self.knowledge_db.execute(
                f"""
                INSERT INTO {self.schema}.query_execution_history (
                    fingerprint, db_name, mcp_instance_id, executed_at,
                    plan_hash, optimizer_cost, table_stats, plan_operations,
                    execution_time_ms, buffer_gets, physical_reads, sql_text_sample
                ) VALUES (
                    $1, $2, $3, NOW(), $4, $5, $6, $7, $8, $9, $10, $11
                )
                """,
                fingerprint,
                db_name,
                self.mcp_instance_id,
                plan_hash or "unknown",
                cost,
                json.dumps(table_stats),
                json.dumps(plan_operations),
                execution_time_ms,
                buffer_gets,
                physical_reads,
                sql_sample
            )
            logger.info(f"💾 Stored execution history: fingerprint={fingerprint[:8]}..., cost={cost}, db={db_name}")
        except Exception as e:
            print(f"[QueryHistoryTracker] ERROR storing history: {e}\n  DB: {self.schema}\n  fingerprint={fingerprint[:8]}..., db={db_name}")
            logger.warning(f"⚠️  Failed to store history: {e}")
    
    async def get_recent_history(
        self,
        fingerprint: str,
        db_name: str,
        days: int = 30,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent execution history for a query fingerprint.
        """
        try:
            await self.ensure_connected()
            print(f"[QueryHistoryTracker] Fetching recent history for fingerprint={fingerprint[:8]}..., db={db_name}, schema={self.schema}")
            rows = await self.knowledge_db.fetch(
                f"""
                SELECT 
                    executed_at, plan_hash, optimizer_cost, table_stats, plan_operations,
                    execution_time_ms, buffer_gets, physical_reads,
                    was_regression, cost_change_pct, plan_changed
                FROM {self.schema}.query_execution_history
                WHERE fingerprint = $1 AND db_name = $2 AND mcp_instance_id = $3
                  AND executed_at >= NOW() - INTERVAL '{days} days'
                ORDER BY executed_at DESC
                LIMIT $4
                """,
                fingerprint, db_name, self.mcp_instance_id, limit
            )
            result = []
            for row in rows:
                history_entry = {
                    "timestamp": row["executed_at"].isoformat() if row["executed_at"] else None,
                    "plan_hash": row["plan_hash"],
                    "cost": row["optimizer_cost"] or 0,
                    "table_stats": json.loads(row["table_stats"]) if row["table_stats"] else {},
                    "plan_operations": json.loads(row["plan_operations"]) if row["plan_operations"] else [],
                    "execution_time_ms": row["execution_time_ms"],
                    "buffer_gets": row["buffer_gets"],
                    "physical_reads": row["physical_reads"],
                    "was_regression": row["was_regression"],
                    "cost_change_pct": row["cost_change_pct"],
                    "plan_changed": row["plan_changed"]
                }
                result.append(history_entry)
            logger.info(f"📊 Found {len(result)} historical executions for fingerprint {fingerprint[:8]}... in last {days} days")
            return result
        except Exception as e:
            print(f"[QueryHistoryTracker] ERROR fetching history: {e}\n  DB: {self.schema}\n  fingerprint={fingerprint[:8]}..., db={db_name}")
            logger.warning(f"⚠️  Failed to fetch history: {e}")
            return []
    
    async def compare_with_history(
        self,
        history: List[Dict[str, Any]],
        current_facts: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compare current execution with historical data and update regression tracking.
        
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
                await self._update_regression_tracking(
                    current_facts.get("fingerprint", ""),
                    current_facts.get("db_name", ""),
                    was_regression=False,
                    cost_change_pct=cost_change_pct,
                    plan_changed=False
                )
                
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
                
                is_regression = cost_change_pct > 0
                await self._update_regression_tracking(
                    current_facts.get("fingerprint", ""),
                    current_facts.get("db_name", ""),
                    was_regression=is_regression,
                    cost_change_pct=cost_change_pct,
                    plan_changed=False
                )
                
                return {
                    "status": "data_growth" if table_growth else "cost_change",
                    "cost_change_pct": round(cost_change_pct, 1),
                    "table_growth": table_growth,
                    "is_regression": is_regression,
                    "message": f"⚠️  Cost changed {cost_change_pct:+.0f}% - likely due to data growth: {', '.join(table_growth)}" if table_growth else f"⚠️  Cost changed {cost_change_pct:+.0f}% - performance {'regressed' if is_regression else 'improved'}"
                }
        
        # Different plan = optimizer changed strategy
        else:
            if current_cost == 0 or last["cost"] == 0:
                await self._update_regression_tracking(
                    current_facts.get("fingerprint", ""),
                    current_facts.get("db_name", ""),
                    was_regression=False,  # Can't determine without cost
                    cost_change_pct=None,
                    plan_changed=True
                )
                
                return {
                    "status": "plan_changed",
                    "old_plan_hash": last["plan_hash"],
                    "new_plan_hash": current_plan_hash,
                    "message": "⚠️  Execution plan changed (cost comparison unavailable)"
                }
            
            is_better = current_cost < last["cost"]
            cost_change_pct = ((current_cost - last["cost"]) / last["cost"]) * 100
            
            await self._update_regression_tracking(
                current_facts.get("fingerprint", ""),
                current_facts.get("db_name", ""),
                was_regression=not is_better,
                cost_change_pct=cost_change_pct,
                plan_changed=True
            )
            
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
                "is_regression": not is_better,
                "message": (
                    f"✅ Plan improved {abs(cost_change_pct):.0f}%! Optimizer found better strategy."
                    if is_better else
                    f"⚠️  Plan regressed {abs(cost_change_pct):.0f}%! Review optimizer statistics. Changes: {', '.join(operation_changes) if operation_changes else 'Unknown'}"
                )
            }
    
    async def _update_regression_tracking(
        self,
        fingerprint: str,
        db_name: str,
        was_regression: bool,
        cost_change_pct: Optional[float],
        plan_changed: bool
    ):
        """Update the latest execution record with regression analysis results."""
        try:
            await self.knowledge_db.execute(
                f"""
                UPDATE {self.schema}.query_execution_history
                SET 
                    was_regression = $1,
                    cost_change_pct = $2,
                    plan_changed = $3
                WHERE fingerprint = $4 
                  AND db_name = $5 
                  AND mcp_instance_id = $6
                  AND executed_at = (
                      SELECT MAX(executed_at) 
                      FROM {self.schema}.query_execution_history 
                      WHERE fingerprint = $4 AND db_name = $5 AND mcp_instance_id = $6
                  )
                """,
                was_regression,
                cost_change_pct,
                plan_changed,
                fingerprint,
                db_name,
                self.mcp_instance_id
            )
        except Exception as e:
            logger.warning(f"⚠️  Failed to update regression tracking: {e}")
    
    async def get_query_summary(self, fingerprint: str, db_name: str) -> Optional[Dict[str, Any]]:
        """Get aggregated performance summary for a query fingerprint."""
        try:
            await self.ensure_connected()
            
            row = await self.knowledge_db.fetchrow(
                f"""
                SELECT 
                    total_executions, avg_cost, min_cost, max_cost,
                    last_executed, latest_plan_hash, cost_trend, plan_stability_pct,
                    first_seen
                FROM {self.schema}.query_performance_summary
                WHERE fingerprint = $1 AND db_name = $2 AND mcp_instance_id = $3
                """,
                fingerprint, db_name, self.mcp_instance_id
            )
            
            if row:
                return {
                    "total_executions": row["total_executions"],
                    "avg_cost": row["avg_cost"],
                    "min_cost": row["min_cost"],
                    "max_cost": row["max_cost"],
                    "last_executed": row["last_executed"].isoformat() if row["last_executed"] else None,
                    "latest_plan_hash": row["latest_plan_hash"],
                    "cost_trend": row["cost_trend"],
                    "plan_stability_pct": row["plan_stability_pct"],
                    "first_seen": row["first_seen"].isoformat() if row["first_seen"] else None
                }
            
            return None
            
        except Exception as e:
            logger.warning(f"⚠️  Failed to get query summary: {e}")
            return None
    
    async def get_regression_count(self, db_name: str, days: int = 7) -> Dict[str, int]:
        """Get count of queries with performance regressions in the last N days."""
        try:
            await self.ensure_connected()
            
            row = await self.knowledge_db.fetchrow(
                f"""
                SELECT 
                    COUNT(*) as total_regressions,
                    COUNT(DISTINCT fingerprint) as unique_queries_regressed
                FROM {self.schema}.query_execution_history
                WHERE db_name = $1 
                  AND mcp_instance_id = $2
                  AND was_regression = TRUE
                  AND executed_at >= NOW() - INTERVAL '{days} days'
                """,
                db_name, self.mcp_instance_id
            )
            
            return {
                "total_regressions": row["total_regressions"] if row else 0,
                "unique_queries_regressed": row["unique_queries_regressed"] if row else 0,
                "period_days": days
            }
            
        except Exception as e:
            logger.warning(f"⚠️  Failed to get regression count: {e}")
            return {"total_regressions": 0, "unique_queries_regressed": 0, "period_days": days}


# Global instance
_query_history_tracker: Optional[QueryHistoryTracker] = None

def get_query_history_tracker(schema: str = None) -> QueryHistoryTracker:
    """Get or create the global query history tracker instance."""
    global _query_history_tracker
    if _query_history_tracker is None:
        _query_history_tracker = QueryHistoryTracker(schema=schema)
    return _query_history_tracker


# Legacy compatibility functions (async versions)
async def init_db():
    """Initialize the PostgreSQL query history tables (compatibility function)."""
    tracker = get_query_history_tracker()
    await tracker.ensure_connected()
    logger.info(f"📁 Query history database initialized in PostgreSQL schema: {tracker.schema}")

def normalize_and_hash(sql: str) -> str:
    """Legacy compatibility function."""
    tracker = get_query_history_tracker()
    return tracker.normalize_and_hash(sql)

async def store_history(fingerprint: str, db_name: str, plan_hash: str, cost: int, 
                  table_stats: dict, plan_operations: list):
    """Legacy compatibility function."""
    tracker = get_query_history_tracker()
    await tracker.store_history(fingerprint, db_name, plan_hash, cost, table_stats, plan_operations)

async def get_recent_history(fingerprint: str, db_name: str, days: int = 30) -> list:
    """Legacy compatibility function."""
    tracker = get_query_history_tracker()
    return await tracker.get_recent_history(fingerprint, db_name, days)

async def compare_with_history(history: list, current_facts: dict) -> dict:
    """Legacy compatibility function."""
    tracker = get_query_history_tracker()
    return await tracker.compare_with_history(history, current_facts)