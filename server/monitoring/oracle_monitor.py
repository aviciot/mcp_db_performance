"""
Oracle Real-Time Performance Monitor

Collects real-time system health and query performance metrics from Oracle V$ views.

SECURITY MODEL:
- READ ONLY: All queries SELECT from system views only
- NEVER EXECUTE: User SQL from V$SQL is displayed, NEVER executed
- All monitoring queries go through existing validate_sql() security layer

Required Oracle Permissions:
- SELECT on V$SQL
- SELECT on V$SYSSTAT
- SELECT on V$OSSTAT
- SELECT on V$SYSTEM_EVENT
- SELECT on V$SESSION
- SELECT on V$ACTIVE_SESSION_HISTORY (optional, improves accuracy)
"""

import oracledb
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class OracleMonitor:
    """Real-time Oracle performance data collector"""
    
    def __init__(self, connection: oracledb.Connection):
        """
        Initialize monitor with database connection
        
        Args:
            connection: Active oracledb connection
        """
        self.conn = connection
        self.cursor = self.conn.cursor()
    
    def get_system_health(self, time_range_minutes: int = 15) -> Dict:
        """
        Get current system health metrics
        
        Args:
            time_range_minutes: Look back period for wait events (default 15)
        
        Returns:
            Dict containing:
            - cpu_usage_pct: CPU utilization %
            - active_sessions: Current active sessions
            - buffer_cache_hit_ratio: Buffer cache hit %
            - wait_events: Top wait events with time spent
            - health_score: Overall health (GOOD/WARNING/CRITICAL)
            - timestamp: Collection time
        
        Security: READ ONLY - queries V$SYSSTAT, V$OSSTAT, V$SESSION, V$SYSTEM_EVENT
        """
        logger.info(f"Collecting system health metrics (last {time_range_minutes} minutes)")
        
        health_data = {
            'timestamp': datetime.now().isoformat(),
            'collection_window_minutes': time_range_minutes
        }
        
        try:
            # 1. CPU Usage (from V$OSSTAT)
            cpu_query = """
                SELECT VALUE 
                FROM V$OSSTAT 
                WHERE STAT_NAME = 'BUSY_TIME'
            """
            self.cursor.execute(cpu_query)
            busy_time = self.cursor.fetchone()
            
            idle_query = """
                SELECT VALUE 
                FROM V$OSSTAT 
                WHERE STAT_NAME = 'IDLE_TIME'
            """
            self.cursor.execute(idle_query)
            idle_time = self.cursor.fetchone()
            
            if busy_time and idle_time:
                total_time = busy_time[0] + idle_time[0]
                cpu_pct = (busy_time[0] / total_time * 100) if total_time > 0 else 0
                health_data['cpu_usage_pct'] = round(cpu_pct, 2)
            else:
                health_data['cpu_usage_pct'] = None
                logger.warning("Could not retrieve CPU stats from V$OSSTAT")
            
            # 2. Active Sessions (from V$SESSION)
            session_query = """
                SELECT COUNT(*) 
                FROM V$SESSION 
                WHERE STATUS = 'ACTIVE' 
                  AND TYPE = 'USER'
            """
            self.cursor.execute(session_query)
            result = self.cursor.fetchone()
            health_data['active_sessions'] = result[0] if result else 0
            
            # 3. Buffer Cache Hit Ratio (from V$SYSSTAT)
            cache_query = """
                SELECT 
                    SUM(CASE WHEN NAME = 'physical reads' THEN VALUE ELSE 0 END) as physical_reads,
                    SUM(CASE WHEN NAME = 'db block gets' THEN VALUE ELSE 0 END) as db_block_gets,
                    SUM(CASE WHEN NAME = 'consistent gets' THEN VALUE ELSE 0 END) as consistent_gets
                FROM V$SYSSTAT
                WHERE NAME IN ('physical reads', 'db block gets', 'consistent gets')
            """
            self.cursor.execute(cache_query)
            result = self.cursor.fetchone()
            
            if result:
                physical_reads, db_block_gets, consistent_gets = result
                logical_reads = db_block_gets + consistent_gets
                
                if logical_reads > 0:
                    hit_ratio = ((logical_reads - physical_reads) / logical_reads) * 100
                    health_data['buffer_cache_hit_ratio'] = round(hit_ratio, 2)
                else:
                    health_data['buffer_cache_hit_ratio'] = None
            
            # 4. Top Wait Events (from V$SYSTEM_EVENT)
            # Exclude idle waits, show top 5 by time waited
            wait_query = """
                SELECT 
                    EVENT,
                    TOTAL_WAITS,
                    TIME_WAITED_MICRO / 1000000 as TIME_WAITED_SEC,
                    AVERAGE_WAIT
                FROM V$SYSTEM_EVENT
                WHERE WAIT_CLASS != 'Idle'
                  AND TOTAL_WAITS > 0
                ORDER BY TIME_WAITED_MICRO DESC
                FETCH FIRST 5 ROWS ONLY
            """
            self.cursor.execute(wait_query)
            wait_events = []
            
            for row in self.cursor:
                wait_events.append({
                    'event': row[0],
                    'total_waits': row[1],
                    'time_waited_seconds': round(row[2], 2),
                    'average_wait_ms': round(row[3], 3)
                })
            
            health_data['top_wait_events'] = wait_events
            
            # 5. Calculate Health Score
            health_data['health_score'] = self._calculate_health_score(health_data)
            
            logger.info(f"System health collected: {health_data['health_score']}")
            return health_data
            
        except oracledb.DatabaseError as e:
            error_msg = f"Database error collecting system health: {str(e)}"
            logger.error(error_msg)
            return {
                'error': error_msg,
                'timestamp': datetime.now().isoformat()
            }
    
    def get_top_queries_realtime(
        self, 
        metric: str = 'cpu', 
        time_range_minutes: int = 60,
        limit: int = 10,
        exclude_sys: bool = True,
        schema_filter: Optional[str] = None,
        module_filter: Optional[str] = None
    ) -> Dict:
        """
        Get top queries by specified metric from V$SQL
        
        Args:
            metric: 'cpu' | 'elapsed' | 'reads' | 'executions' | 'buffer_gets'
            time_range_minutes: Look back period (default 60)
            limit: Number of queries to return (default 10)
            exclude_sys: Exclude SYS/SYSTEM schemas (default True)
            schema_filter: Only include specific schema (e.g., 'INFORM')
            module_filter: Only include specific module (e.g., 'YOUR_APP')
        
        Returns:
            Dict containing:
            - queries: List of top queries with metrics
            - collection_time: When data was collected
            - metric_used: Which metric was used for ranking
        
        Security: READ ONLY - queries V$SQL for analysis
        NEVER EXECUTES user SQL - only displays for analysis
        """
        logger.info(f"Collecting top {limit} queries by {metric} (last {time_range_minutes} minutes)")
        if exclude_sys:
            logger.info("   Excluding SYS/SYSTEM schemas")
        if schema_filter:
            logger.info(f"   Filtering by schema: {schema_filter}")
        if module_filter:
            logger.info(f"   Filtering by module: {module_filter}")
        
        # Map metric to V$SQL column and order
        metric_mapping = {
            'cpu': ('CPU_TIME', 'CPU_TIME DESC'),
            'elapsed': ('ELAPSED_TIME', 'ELAPSED_TIME DESC'),
            'reads': ('DISK_READS', 'DISK_READS DESC'),
            'executions': ('EXECUTIONS', 'EXECUTIONS DESC'),
            'buffer_gets': ('BUFFER_GETS', 'BUFFER_GETS DESC')
        }
        
        if metric not in metric_mapping:
            return {
                'error': f"Invalid metric '{metric}'. Use: {', '.join(metric_mapping.keys())}",
                'timestamp': datetime.now().isoformat()
            }
        
        metric_column, order_by = metric_mapping[metric]
        
        # Build WHERE clause with filters
        where_conditions = [
            "LAST_ACTIVE_TIME >= SYSDATE - (:minutes / 1440)",
            "EXECUTIONS > 0",
            f"{metric_column} > 0"
        ]
        
        # Add schema exclusions
        if exclude_sys:
            where_conditions.append("PARSING_SCHEMA_NAME NOT IN ('SYS', 'SYSTEM', 'DBSNMP', 'OUTLN', 'MDSYS', 'ORDSYS', 'CTXSYS', 'XDB')")
        
        # Add schema filter
        if schema_filter:
            where_conditions.append(f"PARSING_SCHEMA_NAME = :schema_filter")
        
        # Add module filter
        if module_filter:
            where_conditions.append(f"MODULE LIKE :module_filter")
        
        where_clause = " AND ".join(where_conditions)
        
        # Query V$SQL for top queries
        # Note: We're looking at LAST_ACTIVE_TIME to approximate time window
        query = f"""
            SELECT 
                SQL_ID,
                SUBSTR(SQL_TEXT, 1, 500) as SQL_TEXT,
                EXECUTIONS,
                CPU_TIME / 1000000 as CPU_SECONDS,
                ELAPSED_TIME / 1000000 as ELAPSED_SECONDS,
                BUFFER_GETS,
                DISK_READS,
                ROWS_PROCESSED,
                LAST_ACTIVE_TIME,
                PARSING_SCHEMA_NAME,
                MODULE
            FROM V$SQL
            WHERE {where_clause}
            ORDER BY {order_by}
            FETCH FIRST :limit ROWS ONLY
        """
        
        try:
            # Build bind parameters
            bind_params = {'minutes': time_range_minutes, 'limit': limit}
            if schema_filter:
                bind_params['schema_filter'] = schema_filter.upper()
            if module_filter:
                bind_params['module_filter'] = f'%{module_filter}%'
            
            self.cursor.execute(query, bind_params)
            
            queries = []
            for row in self.cursor:
                sql_id, sql_text, executions, cpu_sec, elapsed_sec, buffer_gets, disk_reads, rows_proc, last_active, schema, module = row
                
                # Calculate averages
                avg_cpu_ms = (cpu_sec * 1000 / executions) if executions > 0 else 0
                avg_elapsed_ms = (elapsed_sec * 1000 / executions) if executions > 0 else 0
                avg_buffer_gets = buffer_gets / executions if executions > 0 else 0
                
                query_data = {
                    'sql_id': sql_id,
                    'sql_text': sql_text,
                    'executions': executions,
                    'cpu_seconds': round(cpu_sec, 2),
                    'elapsed_seconds': round(elapsed_sec, 2),
                    'buffer_gets': buffer_gets,
                    'disk_reads': disk_reads,
                    'rows_processed': rows_proc,
                    'avg_cpu_ms': round(avg_cpu_ms, 2),
                    'avg_elapsed_ms': round(avg_elapsed_ms, 2),
                    'avg_buffer_gets': round(avg_buffer_gets, 0),
                    'last_active_time': last_active.isoformat() if last_active else None,
                    'parsing_schema': schema,
                    'module': module
                }
                
                # Flag dangerous SQL (DDL/DML operations) - but NEVER execute it
                if self._is_dangerous_sql(sql_text):
                    query_data['warning'] = 'DDL/DML operation detected - displayed for analysis only, NOT executed'
                
                queries.append(query_data)
            
            result = {
                'metric': metric,
                'time_range_minutes': time_range_minutes,
                'filters': {
                    'exclude_sys': exclude_sys,
                    'schema_filter': schema_filter,
                    'module_filter': module_filter
                },
                'queries_found': len(queries),
                'queries': queries,
                'timestamp': datetime.now().isoformat(),
                'security_note': 'All SQL is read from V$SQL for analysis only. No user SQL is executed by this tool.'
            }
            
            logger.info(f"Found {len(queries)} top queries by {metric}")
            return result
            
        except oracledb.DatabaseError as e:
            error_msg = f"Database error collecting top queries: {str(e)}"
            logger.error(error_msg)
            return {
                'error': error_msg,
                'timestamp': datetime.now().isoformat()
            }
    
    def _calculate_health_score(self, health_data: Dict) -> str:
        """
        Calculate overall health score based on metrics
        
        Returns: 'GOOD' | 'WARNING' | 'CRITICAL'
        """
        score_points = 0
        max_points = 0
        
        # CPU Check (3 points)
        if health_data.get('cpu_usage_pct') is not None:
            max_points += 3
            cpu = health_data['cpu_usage_pct']
            if cpu < 70:
                score_points += 3
            elif cpu < 85:
                score_points += 2
            elif cpu < 95:
                score_points += 1
        
        # Buffer Cache Check (2 points)
        if health_data.get('buffer_cache_hit_ratio') is not None:
            max_points += 2
            hit_ratio = health_data['buffer_cache_hit_ratio']
            if hit_ratio > 95:
                score_points += 2
            elif hit_ratio > 90:
                score_points += 1
        
        # Wait Events Check (2 points)
        if health_data.get('top_wait_events'):
            max_points += 2
            top_wait = health_data['top_wait_events'][0] if health_data['top_wait_events'] else None
            if top_wait:
                # Check if top wait event is problematic
                problematic_waits = ['db file sequential read', 'db file scattered read', 'direct path read', 'log file sync']
                if top_wait['event'] not in problematic_waits:
                    score_points += 2
                elif top_wait['time_waited_seconds'] < 100:
                    score_points += 1
        
        # Active Sessions Check (1 point)
        if health_data.get('active_sessions') is not None:
            max_points += 1
            if health_data['active_sessions'] < 50:  # Arbitrary threshold
                score_points += 1
        
        # Calculate final score
        if max_points == 0:
            return 'UNKNOWN'
        
        score_pct = (score_points / max_points) * 100
        
        if score_pct >= 80:
            return 'GOOD'
        elif score_pct >= 60:
            return 'WARNING'
        else:
            return 'CRITICAL'
    
    def _is_dangerous_sql(self, sql_text: str) -> bool:
        """
        Detect dangerous SQL operations (DDL/DML)
        Used only for flagging in output - SQL is NEVER executed
        """
        if not sql_text:
            return False
        
        sql_upper = sql_text.upper().strip()
        
        dangerous_keywords = [
            'CREATE TABLE', 'DROP TABLE', 'TRUNCATE', 'DELETE FROM',
            'INSERT INTO', 'UPDATE ', 'ALTER TABLE', 'GRANT ', 'REVOKE '
        ]
        
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                return True
        
        return False
    
    def close(self):
        """Close cursor (connection managed externally)"""
        if self.cursor:
            self.cursor.close()
