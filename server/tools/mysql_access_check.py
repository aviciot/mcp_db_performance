"""
MySQL Access Check Tool - Check access to information_schema and performance_schema tables
"""

import logging
from mcp_app import mcp
import mysql_connector

logger = logging.getLogger(__name__)


@mcp.tool(
    name="check_mysql_access",
    description=(
        "🔍 [MYSQL ONLY] Check database user permissions and access to MySQL metadata tables.\n\n"
        "Returns a report showing:\n"
        "- What information_schema tables are accessible\n"
        "- What performance_schema tables are accessible\n"
        "- Impact on analysis quality (HIGH/MEDIUM/LOW)\n"
        "- Recommendations for missing permissions\n\n"
        "Use this to understand why certain analysis features may be unavailable."
    ),
)
def check_mysql_access(db_name: str):
    """
    Check MySQL user access to metadata and performance schema tables.
    
    Args:
        db_name: Name of MySQL database from settings.yaml
    
    Returns:
        Dict with access report and recommendations
    """
    logger.info(f"🔍 Checking MySQL access for database: {db_name}")
    
    try:
        conn = mysql_connector.connect(db_name)
        cur = conn.cursor()
        
        access_report = {}
        recommendations = []
        impact_score = 0  # 0-10, higher = more capabilities
        
        # Check 1: information_schema.TABLES (critical for table stats)
        try:
            cur.execute("SELECT COUNT(*) FROM information_schema.TABLES LIMIT 1")
            cur.fetchone()
            access_report["information_schema.TABLES"] = "✓ Accessible"
            impact_score += 3
        except Exception as e:
            access_report["information_schema.TABLES"] = f"✗ No access: {str(e)}"
            recommendations.append("CRITICAL: Grant SELECT on information_schema.TABLES for basic table statistics")
        
        # Check 2: information_schema.STATISTICS (critical for index info)
        try:
            cur.execute("SELECT COUNT(*) FROM information_schema.STATISTICS LIMIT 1")
            cur.fetchone()
            access_report["information_schema.STATISTICS"] = "✓ Accessible"
            impact_score += 3
        except Exception as e:
            access_report["information_schema.STATISTICS"] = f"✗ No access: {str(e)}"
            recommendations.append("CRITICAL: Grant SELECT on information_schema.STATISTICS for index analysis")
        
        # Check 3: information_schema.COLUMNS (helpful for column stats)
        try:
            cur.execute("SELECT COUNT(*) FROM information_schema.COLUMNS LIMIT 1")
            cur.fetchone()
            access_report["information_schema.COLUMNS"] = "✓ Accessible"
            impact_score += 1
        except Exception as e:
            access_report["information_schema.COLUMNS"] = f"✗ No access: {str(e)}"
            recommendations.append("Grant SELECT on information_schema.COLUMNS for detailed column metadata")
        
        # Check 4: performance_schema.table_io_waits_summary_by_index_usage (for index usage stats)
        try:
            cur.execute("SELECT COUNT(*) FROM performance_schema.table_io_waits_summary_by_index_usage LIMIT 1")
            cur.fetchone()
            access_report["performance_schema.table_io_waits"] = "✓ Accessible"
            impact_score += 2
        except Exception as e:
            access_report["performance_schema.table_io_waits"] = f"✗ No access: {str(e)}"
            recommendations.append("Grant SELECT on performance_schema.* for index usage statistics")
        
        # Check 5: Can run EXPLAIN?
        try:
            cur.execute("EXPLAIN SELECT 1")
            cur.fetchall()
            access_report["EXPLAIN"] = "✓ Can execute"
            impact_score += 1
        except Exception as e:
            access_report["EXPLAIN"] = f"✗ Cannot execute: {str(e)}"
            recommendations.append("CRITICAL: User must have SELECT privilege to run EXPLAIN")
        
        # Determine overall impact
        if impact_score >= 9:
            impact_level = "HIGH - Full analysis capabilities"
            confidence = "HIGH"
        elif impact_score >= 6:
            impact_level = "MEDIUM - Core analysis available, some features limited"
            confidence = "MEDIUM"
        else:
            impact_level = "LOW - Limited analysis capabilities"
            confidence = "LOW"
        
        # Build summary
        summary = {
            "database": db_name,
            "access_checks": access_report,
            "impact_score": f"{impact_score}/10",
            "impact_level": impact_level,
            "confidence": confidence,
            "recommendations": recommendations if recommendations else ["No additional permissions needed - full access available"],
            "analysis_capabilities": {
                "execution_plan": "✓" if "EXPLAIN" in access_report and "✓" in access_report["EXPLAIN"] else "✗",
                "table_statistics": "✓" if "information_schema.TABLES" in access_report and "✓" in access_report["information_schema.TABLES"] else "✗",
                "index_metadata": "✓" if "information_schema.STATISTICS" in access_report and "✓" in access_report["information_schema.STATISTICS"] else "✗",
                "index_usage_stats": "✓" if "performance_schema.table_io_waits" in access_report and "✓" in access_report["performance_schema.table_io_waits"] else "✗",
            }
        }
        
        cur.close()
        conn.close()
        
        return {
            "access_report": summary,
            "prompt": f"MySQL access check complete. Impact: {impact_level} | Confidence: {confidence} | Score: {impact_score}/10"
        }
        
    except Exception as e:
        logger.error(f"Error checking MySQL access: {e}")
        return {
            "error": f"Failed to check access: {str(e)}",
            "prompt": f"Could not connect to MySQL database '{db_name}' to check access"
        }
