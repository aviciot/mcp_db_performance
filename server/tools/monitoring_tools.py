"""
MCP Tools for Database Performance Monitoring

Provides 3 MCP tools for real-time and historical performance analysis:

1. get_database_health() - Current system health (CPU, sessions, cache, waits)
2. get_top_queries() - Top N queries by metric (cpu/elapsed/reads/executions)
3. get_performance_trends() - Historical time-series with JSON chart data

SECURITY MODEL:
- READ ONLY: All tools query system views only (V$SQL, V$SYSSTAT, etc.)
- NEVER EXECUTE: User SQL from V$SQL is displayed, NEVER executed
- Per-Database Control: Feature toggles in settings.yaml
- Inherits existing validate_sql() security layers

All SQL found in V$SQL is FOR ANALYSIS ONLY - even DDL/DML is never executed.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import logging

from mcp_app import mcp
from db_connector import oracle_connector
from config import config
from monitoring.oracle_monitor import OracleMonitor
from monitoring.snapshot_manager import SnapshotManager

logger = logging.getLogger(__name__)

# Load monitoring configuration
monitoring_config = config.performance_monitoring
db_presets = config.database_presets


def _check_monitoring_enabled(db_name: str, feature: str) -> tuple:
    """
    Check if monitoring feature is enabled for database
    
    Args:
        db_name: Database identifier
        feature: 'allow_system_stats' or 'allow_top_queries'
    
    Returns:
        (is_enabled, error_message)
    """
    db_config = db_presets.get(db_name, {})
    monitoring_settings = db_config.get('performance_monitoring', {})
    
    # Check if performance monitoring is enabled
    if not monitoring_settings.get('enabled', False):
        return False, f"Performance monitoring is DISABLED for database '{db_name}'. Enable in settings.yaml: database_presets.{db_name}.performance_monitoring.enabled = true"
    
    # Check specific feature
    if not monitoring_settings.get(feature, False):
        feature_name = feature.replace('allow_', '').replace('_', ' ')
        return False, f"{feature_name.title()} monitoring is DISABLED for database '{db_name}'. Enable in settings.yaml: database_presets.{db_name}.performance_monitoring.{feature} = true"
    
    return True, None


def _format_output(data: Dict, preset: str = None) -> Dict:
    """
    Format output based on preset (standard/compact/minimal)
    
    Args:
        data: Raw data dictionary
        preset: Output preset (uses config default if None)
    
    Returns:
        Formatted data
    """
    preset = preset or monitoring_config.get('output_preset', 'compact')
    
    if preset == 'minimal':
        # Keep only critical fields
        if 'queries' in data:
            for q in data['queries']:
                q.pop('sql_text', None)
                q.pop('module', None)
                q.pop('rows_processed', None)
        
        if 'top_wait_events' in data:
            data['top_wait_events'] = data['top_wait_events'][:1]  # Only worst
    
    elif preset == 'compact':
        # Truncate SQL text
        if 'queries' in data:
            for q in data['queries']:
                if 'sql_text' in q and q['sql_text']:
                    q['sql_text'] = q['sql_text'][:200] + ('...' if len(q['sql_text']) > 200 else '')
        
        if 'top_wait_events' in data:
            data['top_wait_events'] = data['top_wait_events'][:3]  # Top 3
    
    # 'standard' = no modification, return all data
    
    return data


def _generate_chart_data(history: List[Dict], metric: str) -> Dict:
    """
    Generate JSON chart data for visualization
    
    Args:
        history: List of historical data points
        metric: Metric to chart
    
    Returns:
        Chart data in JSON format compatible with matplotlib/plotly/Chart.js
    """
    if not history:
        return {
            'type': 'line',
            'data': {
                'labels': [],
                'datasets': []
            },
            'note': 'No historical data available'
        }
    
    # Extract timestamps and values
    timestamps = []
    values = []
    
    for point in history:
        timestamps.append(point.get('timestamp', ''))
        
        # Map metric name to data field
        if metric == 'cpu_usage':
            values.append(point.get('cpu_usage_pct'))
        elif metric == 'active_sessions':
            values.append(point.get('active_sessions'))
        elif metric == 'buffer_cache_hit_ratio':
            values.append(point.get('buffer_cache_hit_ratio'))
        elif metric == 'cpu_seconds':
            values.append(point.get('cpu_seconds'))
        elif metric == 'elapsed_seconds':
            values.append(point.get('elapsed_seconds'))
        elif metric == 'avg_cpu_ms':
            values.append(point.get('avg_cpu_ms'))
        else:
            values.append(None)
    
    return {
        'type': 'line',
        'data': {
            'labels': timestamps,
            'datasets': [{
                'label': metric.replace('_', ' ').title(),
                'data': values,
                'borderColor': 'rgb(75, 192, 192)',
                'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                'tension': 0.1
            }]
        },
        'options': {
            'responsive': True,
            'plugins': {
                'title': {
                    'display': True,
                    'text': f'{metric.replace("_", " ").title()} Over Time'
                }
            },
            'scales': {
                'y': {
                    'beginAtZero': False
                }
            }
        }
    }


# ============================================================================
# MCP TOOL 1: get_database_health
# ============================================================================

@mcp.tool(
    name="get_database_health",
    description=(
        "📊 [ORACLE] Get real-time database health metrics including CPU, sessions, cache hit ratio, and wait events.\n\n"
        "⚠️ DATABASE TYPE: This tool is for ORACLE databases only.\n\n"
        "🔍 What this tool does:\n"
        "• Queries Oracle system views (V$OSSTAT, V$SYSSTAT, V$SESSION, V$SYSTEM_EVENT)\n"
        "• Returns current system health snapshot with health score (GOOD/WARNING/CRITICAL)\n"
        "• Optionally saves snapshot to history for trend analysis\n\n"
        "📈 Metrics Provided:\n"
        "• CPU Usage %\n"
        "• Active Sessions\n"
        "• Buffer Cache Hit Ratio\n"
        "• Top 5 Wait Events\n"
        "• Overall Health Score\n\n"
        "🔒 Security:\n"
        "✅ READ ONLY: Queries system views, never executes user SQL\n"
        "✅ Per-database control via performance_monitoring.enabled in settings.yaml\n"
        "✅ Requires: SELECT on V$OSSTAT, V$SYSSTAT, V$SESSION, V$SYSTEM_EVENT\n\n"
        "💡 Example Usage:\n"
        "\"Check health of way4_docker7 database\"\n"
        "\"What's the current system health for way4_docker7?\"\n"
        "\"Show me CPU and wait events for way4_docker7\""
    )
)
def get_database_health(db_name: str, time_range_minutes: int = 15, save_snapshot: bool = True):
    """
    Get real-time database health metrics
    
    Args:
        db_name: Database identifier from settings.yaml
        time_range_minutes: Look-back period for wait events
        save_snapshot: Whether to save to historical storage
    
    Returns:
        Dict with health metrics and optional historical chart data
    """
    logger.info(f"get_database_health called for {db_name}")
    
    # Check if monitoring is enabled
    enabled, error_msg = _check_monitoring_enabled(db_name, 'allow_system_stats')
    if not enabled:
        return {"error": error_msg}
    
    try:
        # Get database connection
        conn = oracle_connector.connect(db_name)
        
        # Collect health metrics
        monitor = OracleMonitor(conn)
        health_data = monitor.get_system_health(time_range_minutes)
        monitor.close()
        conn.close()
        
        # Format output
        health_data = _format_output(health_data)
        
        # Save snapshot if requested
        if save_snapshot and 'error' not in health_data:
            snapshot_mgr = SnapshotManager()
            snapshot_mgr.save_health_snapshot(db_name, health_data)
            health_data['snapshot_saved'] = True
        
        # Add metadata
        health_data['database'] = db_name
        health_data['tool'] = 'get_database_health'
        health_data['security_note'] = 'READ ONLY queries - no user SQL executed'
        
        return health_data
        
    except Exception as e:
        error_msg = f"Error collecting database health: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg, "database": db_name}


# ============================================================================
# MCP TOOL 2: get_top_queries
# ============================================================================

@mcp.tool(
    name="get_top_queries",
    description=(
        "🔍 [ORACLE] Get top N queries by specified metric from V$SQL.\n\n"
        "⚠️ DATABASE TYPE: This tool is for ORACLE databases only.\n\n"
        "🔍 What this tool does:\n"
        "• Queries V$SQL to find most expensive queries by metric\n"
        "• Returns SQL text, execution stats, and performance metrics\n"
        "• **SECURITY: SQL is displayed for analysis ONLY - NEVER executed, even DDL/DML**\n\n"
        "📊 Available Metrics:\n"
        "• cpu: Top queries by CPU consumption\n"
        "• elapsed: Top queries by elapsed time\n"
        "• reads: Top queries by disk reads\n"
        "• executions: Most frequently executed queries\n"
        "• buffer_gets: Top queries by logical reads\n\n"
        "🎯 Filtering Options:\n"
        "• exclude_sys: Exclude SYS/SYSTEM schemas (default: true)\n"
        "• schema_filter: Only show queries from specific schema (e.g., 'INFORM')\n"
        "• module_filter: Only show queries from specific module/application\n"
        "• time_range_minutes: Look back period (default: 60)\n\n"
        "🔒 Security:\n"
        "✅ READ ONLY: Queries V$SQL for analysis\n"
        "✅ NEVER EXECUTE: User SQL is displayed, not executed (even CREATE/DROP/DELETE)\n"
        "✅ Dangerous SQL is flagged with warning but shown for analysis\n"
        "✅ Requires: SELECT on V$SQL\n\n"
        "💡 Example Usage:\n"
        "\"Show me top 10 queries by CPU on way4_docker7\"\n"
        "\"What are the most expensive queries by elapsed time?\"\n"
        "\"Find top 5 queries by disk reads in last hour\"\n"
        "\"Show top queries from INFORM schema only\"\n"
        "\"Which application queries execute most frequently?\""
    )
)
def get_top_queries(
    db_name: str,
    metric: str = 'cpu',
    time_range_minutes: int = 60,
    limit: int = 10,
    save_snapshot: bool = True,
    exclude_sys: bool = True,
    schema_filter: str = None,
    module_filter: str = None
):
    """
    Get top queries by specified metric
    
    Args:
        db_name: Database identifier from settings.yaml
        metric: Ranking metric (cpu/elapsed/reads/executions/buffer_gets)
        time_range_minutes: Look-back period
        limit: Number of queries to return
        save_snapshot: Whether to save to historical storage
        exclude_sys: Exclude SYS/SYSTEM schemas (default True)
        schema_filter: Only include specific schema (e.g., 'INFORM')
        module_filter: Only include specific module/application
    
    Returns:
        Dict with top queries and metrics
        
    Security: SQL from V$SQL is FOR ANALYSIS ONLY - never executed
    """
    logger.info(f"get_top_queries called for {db_name}, metric={metric}, limit={limit}")
    if schema_filter:
        logger.info(f"   Schema filter: {schema_filter}")
    if module_filter:
        logger.info(f"   Module filter: {module_filter}")
    
    # Check if monitoring is enabled
    enabled, error_msg = _check_monitoring_enabled(db_name, 'allow_top_queries')
    if not enabled:
        return {"error": error_msg}
    
    try:
        # Get database connection
        conn = oracle_connector.connect(db_name)
        
        # Collect top queries
        monitor = OracleMonitor(conn)
        query_data = monitor.get_top_queries_realtime(
            metric, 
            time_range_minutes, 
            limit,
            exclude_sys,
            schema_filter,
            module_filter
        )
        monitor.close()
        conn.close()
        
        # Format output
        query_data = _format_output(query_data)
        
        # Save snapshot if requested
        if save_snapshot and 'error' not in query_data and query_data.get('queries'):
            snapshot_mgr = SnapshotManager()
            snapshot_mgr.save_query_snapshots(
                db_name,
                datetime.now(),
                query_data['queries'],
                metric
            )
            query_data['snapshot_saved'] = True
        
        # Add metadata
        query_data['database'] = db_name
        query_data['tool'] = 'get_top_queries'
        
        return query_data
        
    except Exception as e:
        error_msg = f"Error collecting top queries: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg, "database": db_name}


# ============================================================================
# MCP TOOL 3: get_performance_trends
# ============================================================================

@mcp.tool(
    name="get_performance_trends",
    description=(
        "📈 [ORACLE] Get historical performance trends with JSON chart data for visualization.\n\n"
        "⚠️ DATABASE TYPE: This tool is for ORACLE databases only.\n\n"
        "🔍 What this tool does:\n"
        "• Retrieves historical snapshots from SQLite storage\n"
        "• Generates time-series data for trend analysis\n"
        "• Returns JSON chart data compatible with matplotlib/plotly/Chart.js\n\n"
        "📊 Available Metrics:\n"
        "System Health:\n"
        "• cpu_usage: CPU utilization over time\n"
        "• active_sessions: Session count trends\n"
        "• buffer_cache_hit_ratio: Cache efficiency trends\n\n"
        "Query Performance:\n"
        "• cpu_seconds: Query CPU consumption trends\n"
        "• elapsed_seconds: Query elapsed time trends\n"
        "• avg_cpu_ms: Average query CPU trends\n\n"
        "📉 Chart Format:\n"
        "Returns JSON in Chart.js format with labels, datasets, and configuration.\n"
        "Can be visualized with matplotlib, plotly, or any charting library.\n\n"
        "🔒 Security:\n"
        "✅ READ ONLY: Queries historical snapshot tables\n"
        "✅ No live database queries - uses stored snapshots\n\n"
        "💡 Example Usage:\n"
        "\"Show CPU usage trend for way4_docker7 over last 24 hours\"\n"
        "\"What's the buffer cache hit ratio trend for past week?\"\n"
        "\"Chart top query CPU consumption over last 6 hours\""
    )
)
def get_performance_trends(
    db_name: str,
    hours: int = 24,
    metric: str = 'cpu_usage',
    sql_id: Optional[str] = None
):
    """
    Get historical performance trends with chart data
    
    Args:
        db_name: Database identifier from settings.yaml
        hours: Hours of history to retrieve
        metric: Metric to chart
        sql_id: Optional SQL ID for query-specific trends
    
    Returns:
        Dict with historical data and JSON chart
    """
    logger.info(f"get_performance_trends called for {db_name}, metric={metric}, hours={hours}")
    
    # Check if monitoring is enabled (use system_stats for health metrics)
    feature = 'allow_system_stats' if metric in ['cpu_usage', 'active_sessions', 'buffer_cache_hit_ratio'] else 'allow_top_queries'
    enabled, error_msg = _check_monitoring_enabled(db_name, feature)
    if not enabled:
        return {"error": error_msg}
    
    try:
        snapshot_mgr = SnapshotManager()
        
        # Determine if system health or query trend
        if metric in ['cpu_usage', 'active_sessions', 'buffer_cache_hit_ratio']:
            # System health trend
            history = snapshot_mgr.get_health_history(db_name, hours)
            trend_type = 'system_health'
        else:
            # Query performance trend
            history = snapshot_mgr.get_query_trends(db_name, sql_id, hours)
            trend_type = 'query_performance'
        
        # Generate chart data
        chart_format = monitoring_config.get('chart_format', 'json')
        chart_data = None
        
        if chart_format in ['json', 'both']:
            chart_data = _generate_chart_data(history, metric)
        
        result = {
            'database': db_name,
            'metric': metric,
            'hours': hours,
            'data_points': len(history),
            'trend_type': trend_type,
            'history': history,
            'tool': 'get_performance_trends',
            'timestamp': datetime.now().isoformat()
        }
        
        if chart_data:
            result['chart'] = chart_data
            result['chart_note'] = 'JSON format compatible with Chart.js, matplotlib, plotly'
        
        if sql_id:
            result['sql_id'] = sql_id
        
        return result
        
    except Exception as e:
        error_msg = f"Error retrieving performance trends: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg, "database": db_name}
