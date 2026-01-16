"""
Performance Snapshot Manager

Manages historical storage of system health and query performance snapshots to SQLite.

SECURITY:
- Stores only metadata and statistics - no sensitive data
- Automatic cleanup of old snapshots based on retention policy
- Read-only queries against snapshot history

Database: Extends existing query_history.db with new tables
Tables:
- system_health_snapshots: System metrics over time
- query_performance_snapshots: Top query metrics over time
"""

import sqlite3
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class SnapshotManager:
    """Manages historical performance snapshots in SQLite"""
    
    def __init__(self, db_path: str = "query_history.db"):
        """
        Initialize snapshot manager
        
        Args:
            db_path: Path to SQLite database (default: query_history.db)
        """
        self.db_path = db_path
        self._ensure_schema()
    
    def _ensure_schema(self):
        """Create tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # System Health Snapshots Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_health_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    db_name TEXT NOT NULL,
                    snapshot_time DATETIME NOT NULL,
                    cpu_usage_pct REAL,
                    active_sessions INTEGER,
                    buffer_cache_hit_ratio REAL,
                    top_wait_event TEXT,
                    top_wait_time_seconds REAL,
                    health_score TEXT,
                    metadata TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(db_name, snapshot_time)
                )
            """)
            
            # Index for time-based queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_health_db_time 
                ON system_health_snapshots(db_name, snapshot_time DESC)
            """)
            
            # Query Performance Snapshots Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS query_performance_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    db_name TEXT NOT NULL,
                    snapshot_time DATETIME NOT NULL,
                    sql_id TEXT NOT NULL,
                    sql_text TEXT,
                    executions INTEGER,
                    cpu_seconds REAL,
                    elapsed_seconds REAL,
                    buffer_gets INTEGER,
                    disk_reads INTEGER,
                    rows_processed INTEGER,
                    avg_cpu_ms REAL,
                    avg_elapsed_ms REAL,
                    parsing_schema TEXT,
                    metric_rank INTEGER,
                    metric_type TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(db_name, snapshot_time, sql_id)
                )
            """)
            
            # Index for queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_query_perf_db_time 
                ON query_performance_snapshots(db_name, snapshot_time DESC)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_query_perf_sql_id 
                ON query_performance_snapshots(sql_id)
            """)
            
            conn.commit()
            logger.info("Snapshot schema ensured in database")
            
        except sqlite3.Error as e:
            logger.error(f"Error creating snapshot schema: {e}")
            raise
        finally:
            conn.close()
    
    def save_health_snapshot(self, db_name: str, health_data: Dict) -> bool:
        """
        Save system health snapshot
        
        Args:
            db_name: Database identifier
            health_data: Health metrics from OracleMonitor.get_system_health()
        
        Returns:
            True if saved successfully
        """
        if 'error' in health_data:
            logger.warning(f"Skipping health snapshot with error: {health_data['error']}")
            return False
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            snapshot_time = datetime.fromisoformat(health_data['timestamp'])
            
            # Extract top wait event
            top_wait_event = None
            top_wait_time = None
            if health_data.get('top_wait_events'):
                top_wait = health_data['top_wait_events'][0]
                top_wait_event = top_wait['event']
                top_wait_time = top_wait['time_waited_seconds']
            
            # Store full wait events in metadata
            metadata = {
                'collection_window_minutes': health_data.get('collection_window_minutes'),
                'wait_events': health_data.get('top_wait_events', [])
            }
            
            cursor.execute("""
                INSERT OR REPLACE INTO system_health_snapshots 
                (db_name, snapshot_time, cpu_usage_pct, active_sessions, 
                 buffer_cache_hit_ratio, top_wait_event, top_wait_time_seconds, 
                 health_score, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                db_name,
                snapshot_time,
                health_data.get('cpu_usage_pct'),
                health_data.get('active_sessions'),
                health_data.get('buffer_cache_hit_ratio'),
                top_wait_event,
                top_wait_time,
                health_data.get('health_score'),
                json.dumps(metadata)
            ))
            
            conn.commit()
            logger.info(f"Saved health snapshot for {db_name} at {snapshot_time}")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Error saving health snapshot: {e}")
            return False
        finally:
            conn.close()
    
    def save_query_snapshots(
        self, 
        db_name: str, 
        snapshot_time: datetime,
        queries: List[Dict],
        metric_type: str
    ) -> int:
        """
        Save query performance snapshots
        
        Args:
            db_name: Database identifier
            snapshot_time: When snapshot was taken
            queries: List of queries from OracleMonitor.get_top_queries_realtime()
            metric_type: Metric used for ranking (cpu, elapsed, etc.)
        
        Returns:
            Number of queries saved
        """
        if not queries:
            return 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        saved_count = 0
        
        try:
            for rank, query in enumerate(queries, 1):
                cursor.execute("""
                    INSERT OR REPLACE INTO query_performance_snapshots
                    (db_name, snapshot_time, sql_id, sql_text, executions,
                     cpu_seconds, elapsed_seconds, buffer_gets, disk_reads,
                     rows_processed, avg_cpu_ms, avg_elapsed_ms, parsing_schema,
                     metric_rank, metric_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    db_name,
                    snapshot_time,
                    query['sql_id'],
                    query['sql_text'],
                    query['executions'],
                    query['cpu_seconds'],
                    query['elapsed_seconds'],
                    query['buffer_gets'],
                    query['disk_reads'],
                    query['rows_processed'],
                    query['avg_cpu_ms'],
                    query['avg_elapsed_ms'],
                    query['parsing_schema'],
                    rank,
                    metric_type
                ))
                saved_count += 1
            
            conn.commit()
            logger.info(f"Saved {saved_count} query snapshots for {db_name}")
            return saved_count
            
        except sqlite3.Error as e:
            logger.error(f"Error saving query snapshots: {e}")
            return saved_count
        finally:
            conn.close()
    
    def get_health_history(
        self, 
        db_name: str, 
        hours: int = 24
    ) -> List[Dict]:
        """
        Get system health history for time-series analysis
        
        Args:
            db_name: Database identifier
            hours: Hours of history to retrieve
        
        Returns:
            List of health snapshots ordered by time
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            cursor.execute("""
                SELECT 
                    snapshot_time,
                    cpu_usage_pct,
                    active_sessions,
                    buffer_cache_hit_ratio,
                    top_wait_event,
                    top_wait_time_seconds,
                    health_score,
                    metadata
                FROM system_health_snapshots
                WHERE db_name = ?
                  AND snapshot_time >= ?
                ORDER BY snapshot_time ASC
            """, (db_name, cutoff_time))
            
            history = []
            for row in cursor:
                history.append({
                    'timestamp': row[0],
                    'cpu_usage_pct': row[1],
                    'active_sessions': row[2],
                    'buffer_cache_hit_ratio': row[3],
                    'top_wait_event': row[4],
                    'top_wait_time_seconds': row[5],
                    'health_score': row[6],
                    'metadata': json.loads(row[7]) if row[7] else {}
                })
            
            logger.info(f"Retrieved {len(history)} health snapshots for {db_name}")
            return history
            
        except sqlite3.Error as e:
            logger.error(f"Error retrieving health history: {e}")
            return []
        finally:
            conn.close()
    
    def get_query_trends(
        self,
        db_name: str,
        sql_id: Optional[str] = None,
        hours: int = 24,
        metric_type: Optional[str] = None
    ) -> List[Dict]:
        """
        Get query performance trends
        
        Args:
            db_name: Database identifier
            sql_id: Specific SQL ID (optional, returns all if None)
            hours: Hours of history to retrieve
            metric_type: Filter by metric type (optional)
        
        Returns:
            List of query snapshots ordered by time
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            query = """
                SELECT 
                    snapshot_time,
                    sql_id,
                    sql_text,
                    executions,
                    cpu_seconds,
                    elapsed_seconds,
                    buffer_gets,
                    disk_reads,
                    avg_cpu_ms,
                    avg_elapsed_ms,
                    metric_rank,
                    metric_type
                FROM query_performance_snapshots
                WHERE db_name = ?
                  AND snapshot_time >= ?
            """
            params = [db_name, cutoff_time]
            
            if sql_id:
                query += " AND sql_id = ?"
                params.append(sql_id)
            
            if metric_type:
                query += " AND metric_type = ?"
                params.append(metric_type)
            
            query += " ORDER BY snapshot_time ASC, metric_rank ASC"
            
            cursor.execute(query, params)
            
            trends = []
            for row in cursor:
                trends.append({
                    'timestamp': row[0],
                    'sql_id': row[1],
                    'sql_text': row[2],
                    'executions': row[3],
                    'cpu_seconds': row[4],
                    'elapsed_seconds': row[5],
                    'buffer_gets': row[6],
                    'disk_reads': row[7],
                    'avg_cpu_ms': row[8],
                    'avg_elapsed_ms': row[9],
                    'metric_rank': row[10],
                    'metric_type': row[11]
                })
            
            logger.info(f"Retrieved {len(trends)} query trend snapshots for {db_name}")
            return trends
            
        except sqlite3.Error as e:
            logger.error(f"Error retrieving query trends: {e}")
            return []
        finally:
            conn.close()
    
    def cleanup_old_snapshots(self, retention_days: int = 30) -> Tuple[int, int]:
        """
        Delete snapshots older than retention period
        
        Args:
            retention_days: Number of days to keep (default 30)
        
        Returns:
            Tuple of (health_deleted, query_deleted) counts
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cutoff_time = datetime.now() - timedelta(days=retention_days)
            
            cursor.execute("""
                DELETE FROM system_health_snapshots
                WHERE snapshot_time < ?
            """, (cutoff_time,))
            health_deleted = cursor.rowcount
            
            cursor.execute("""
                DELETE FROM query_performance_snapshots
                WHERE snapshot_time < ?
            """, (cutoff_time,))
            query_deleted = cursor.rowcount
            
            conn.commit()
            logger.info(f"Cleaned up {health_deleted} health + {query_deleted} query snapshots older than {retention_days} days")
            return (health_deleted, query_deleted)
            
        except sqlite3.Error as e:
            logger.error(f"Error cleaning up snapshots: {e}")
            return (0, 0)
        finally:
            conn.close()
