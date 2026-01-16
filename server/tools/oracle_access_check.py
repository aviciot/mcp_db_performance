"""
Oracle Access Check Tool - Check access to data dictionary views and system tables
"""

import logging
from mcp_app import mcp
import db_connector

logger = logging.getLogger(__name__)


@mcp.tool(
    name="check_oracle_access",
    description=(
        "🔍 [ORACLE ONLY] Check database user permissions and access to Oracle data dictionary views.\n\n"
        "Returns a report showing:\n"
        "- What ALL_* views are accessible (tables, indexes, constraints, etc.)\n"
        "- What DBA_* views are accessible (storage, segments)\n"
        "- What V$* views are accessible (optimizer parameters)\n"
        "- Impact on analysis quality (HIGH/MEDIUM/LOW)\n"
        "- Recommendations for missing permissions\n\n"
        "Use this to understand why certain analysis features may be unavailable."
    ),
)
def check_oracle_access(db_name: str):
    """
    Check Oracle user access to data dictionary and performance views.
    
    Args:
        db_name: Name of Oracle database from settings.yaml
    
    Returns:
        Dict with access report and recommendations
    """
    logger.info(f"🔍 Checking Oracle access for database: {db_name}")
    
    try:
        conn = db_connector.connect(db_name)
        cur = conn.cursor()
        
        access_report = {}
        recommendations = []
        impact_score = 0  # 0-10, higher = more capabilities
        
        # Check 1: ALL_TABLES (critical for table stats)
        try:
            cur.execute("SELECT COUNT(*) FROM ALL_TABLES WHERE ROWNUM <= 1")
            cur.fetchone()
            access_report["ALL_TABLES"] = "✓ Accessible"
            impact_score += 2
        except Exception as e:
            access_report["ALL_TABLES"] = f"✗ No access: {str(e)}"
            recommendations.append("CRITICAL: Grant SELECT on ALL_TABLES for basic table statistics")
        
        # Check 2: ALL_INDEXES (critical for index info)
        try:
            cur.execute("SELECT COUNT(*) FROM ALL_INDEXES WHERE ROWNUM <= 1")
            cur.fetchone()
            access_report["ALL_INDEXES"] = "✓ Accessible"
            impact_score += 2
        except Exception as e:
            access_report["ALL_INDEXES"] = f"✗ No access: {str(e)}"
            recommendations.append("CRITICAL: Grant SELECT on ALL_INDEXES for index analysis")
        
        # Check 3: ALL_IND_COLUMNS (important for index column details)
        try:
            cur.execute("SELECT COUNT(*) FROM ALL_IND_COLUMNS WHERE ROWNUM <= 1")
            cur.fetchone()
            access_report["ALL_IND_COLUMNS"] = "✓ Accessible"
            impact_score += 1
        except Exception as e:
            access_report["ALL_IND_COLUMNS"] = f"✗ No access: {str(e)}"
            recommendations.append("Grant SELECT on ALL_IND_COLUMNS for detailed index composition")
        
        # Check 4: ALL_CONSTRAINTS (helpful for constraint analysis)
        try:
            cur.execute("SELECT COUNT(*) FROM ALL_CONSTRAINTS WHERE ROWNUM <= 1")
            cur.fetchone()
            access_report["ALL_CONSTRAINTS"] = "✓ Accessible"
            impact_score += 1
        except Exception as e:
            access_report["ALL_CONSTRAINTS"] = f"✗ No access: {str(e)}"
            recommendations.append("Grant SELECT on ALL_CONSTRAINTS for constraint metadata")
        
        # Check 5: ALL_TAB_COLUMNS (helpful for column statistics)
        try:
            cur.execute("SELECT COUNT(*) FROM ALL_TAB_COLUMNS WHERE ROWNUM <= 1")
            cur.fetchone()
            access_report["ALL_TAB_COLUMNS"] = "✓ Accessible"
            impact_score += 1
        except Exception as e:
            access_report["ALL_TAB_COLUMNS"] = f"✗ No access: {str(e)}"
            recommendations.append("Grant SELECT on ALL_TAB_COLUMNS for column statistics")
        
        # Check 6: ALL_TAB_PARTITIONS (helpful for partition info)
        try:
            cur.execute("SELECT COUNT(*) FROM ALL_TAB_PARTITIONS WHERE ROWNUM <= 1")
            cur.fetchone()
            access_report["ALL_TAB_PARTITIONS"] = "✓ Accessible"
            impact_score += 0.5
        except Exception as e:
            access_report["ALL_TAB_PARTITIONS"] = f"✗ No access: {str(e)}"
            recommendations.append("Grant SELECT on ALL_TAB_PARTITIONS for partition analysis")
        
        # Check 7: DBA_SEGMENTS (important for storage analysis - requires DBA role)
        try:
            cur.execute("SELECT COUNT(*) FROM DBA_SEGMENTS WHERE ROWNUM <= 1")
            cur.fetchone()
            access_report["DBA_SEGMENTS"] = "✓ Accessible"
            impact_score += 1.5
        except Exception as e:
            access_report["DBA_SEGMENTS"] = f"✗ No access: {str(e)}"
            recommendations.append("Grant SELECT on DBA_SEGMENTS (or SELECT_CATALOG_ROLE) for storage analysis")
        
        # Check 8: V$PARAMETER (helpful for optimizer settings)
        try:
            cur.execute("SELECT COUNT(*) FROM V$PARAMETER WHERE ROWNUM <= 1")
            cur.fetchone()
            access_report["V$PARAMETER"] = "✓ Accessible"
            impact_score += 1
        except Exception as e:
            access_report["V$PARAMETER"] = f"✗ No access: {str(e)}"
            recommendations.append("Grant SELECT on V$PARAMETER for optimizer parameter analysis")
        
        # Check 9: Can create EXPLAIN PLAN table?
        try:
            # Check if PLAN_TABLE exists or can be accessed
            cur.execute("SELECT COUNT(*) FROM PLAN_TABLE WHERE ROWNUM <= 1")
            cur.fetchone()
            access_report["EXPLAIN PLAN"] = "✓ Can execute (PLAN_TABLE exists)"
            impact_score += 1
        except Exception as e:
            # Try to create it
            try:
                cur.execute("@?/rdbms/admin/utlxplan.sql")
                access_report["EXPLAIN PLAN"] = "✓ Can execute (PLAN_TABLE created)"
                impact_score += 1
            except:
                access_report["EXPLAIN PLAN"] = f"✗ Cannot create PLAN_TABLE: {str(e)}"
                recommendations.append("CRITICAL: Run @?/rdbms/admin/utlxplan.sql to create PLAN_TABLE")
        
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
                "execution_plan": "✓" if "EXPLAIN PLAN" in access_report and "✓" in access_report["EXPLAIN PLAN"] else "✗",
                "table_statistics": "✓" if "ALL_TABLES" in access_report and "✓" in access_report["ALL_TABLES"] else "✗",
                "index_metadata": "✓" if "ALL_INDEXES" in access_report and "✓" in access_report["ALL_INDEXES"] else "✗",
                "index_composition": "✓" if "ALL_IND_COLUMNS" in access_report and "✓" in access_report["ALL_IND_COLUMNS"] else "✗",
                "constraint_analysis": "✓" if "ALL_CONSTRAINTS" in access_report and "✓" in access_report["ALL_CONSTRAINTS"] else "✗",
                "column_statistics": "✓" if "ALL_TAB_COLUMNS" in access_report and "✓" in access_report["ALL_TAB_COLUMNS"] else "✗",
                "partition_info": "✓" if "ALL_TAB_PARTITIONS" in access_report and "✓" in access_report["ALL_TAB_PARTITIONS"] else "✗",
                "storage_analysis": "✓" if "DBA_SEGMENTS" in access_report and "✓" in access_report["DBA_SEGMENTS"] else "✗",
                "optimizer_params": "✓" if "V$PARAMETER" in access_report and "✓" in access_report["V$PARAMETER"] else "✗",
            }
        }
        
        cur.close()
        conn.close()
        
        return {
            "access_report": summary,
            "prompt": f"Oracle access check complete. Impact: {impact_level} | Confidence: {confidence} | Score: {impact_score}/10"
        }
        
    except Exception as e:
        logger.error(f"Error checking Oracle access: {e}")
        return {
            "error": f"Failed to check access: {str(e)}",
            "prompt": f"Could not connect to Oracle database '{db_name}' to check access"
        }
