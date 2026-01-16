# server/tools/help_tools.py
"""
Interactive help tool for Performance MCP Server
Reads from knowledge_base/ markdown files
"""

import os
from pathlib import Path
from mcp_app import mcp
from config import config


# Get path to knowledge_base directory
KNOWLEDGE_BASE_DIR = Path(__file__).parent.parent / "knowledge_base"


def read_knowledge_file(filename: str) -> str:
    """Read markdown file from knowledge_base directory"""
    filepath = KNOWLEDGE_BASE_DIR / filename
    if filepath.exists():
        return filepath.read_text(encoding='utf-8')
    return f"File not found: {filename}"


@mcp.tool(
    name="get_knowledge_base_content",
    description=(
        "📚 Get documentation from Performance MCP knowledge base.\n\n"
        "Access comprehensive documentation including workflows, architecture diagrams, "
        "tool references, and troubleshooting guides.\n\n"
        "**Available Topics:**\n"
        "• `overview` - What this MCP does, when to use it\n"
        "• `workflows` - Step-by-step guides (slow query analysis, plan comparison, etc.)\n"
        "• `architecture` - How it works internally (includes Mermaid diagrams!)\n"
        "• `troubleshooting` - Common errors and solutions\n"
        "• `tool:check_oracle_access` - Verify Oracle permissions\n"
        "• `tool:check_mysql_access` - Verify MySQL permissions\n"
        "• `tool:analyze_oracle_query` - Main Oracle analysis tool\n\n"
        "**Use this when:** User asks how to use MCP, needs workflow guidance, wants to see diagrams, troubleshooting errors"
    ),
)
def get_knowledge_base_content(topic: str = "overview"):
    """
    Get documentation from Performance MCP knowledge base.
    
    Args:
        topic: Documentation topic or tool name
            - overview, workflows, architecture, troubleshooting
            - tool:check_oracle_access, tool:analyze_oracle_query, etc.
    
    Returns:
        Markdown content including Mermaid diagrams
    """
    
    # Map topics to files
    topic_map = {
        "overview": "overview.md",
        "workflows": "workflows.md",
        "architecture": "architecture.md",
        "troubleshooting": "troubleshooting.md",
        "summary": "SUMMARY.md",
        
        # Tool-specific docs
        "tool:check_oracle_access": "tools/check_oracle_access.md",
        "tool:check_mysql_access": "tools/check_mysql_access.md",
        "tool:analyze_oracle_query": "tools/analyze_oracle_query.md",
        
        # Aliases for common questions
        "slow query": "workflows.md",
        "permissions": "workflows.md",
        "preset": "architecture.md",
        "error": "troubleshooting.md",
        "diagram": "architecture.md",
    }
    
    topic_lower = topic.lower()
    
    # Direct match
    if topic_lower in topic_map:
        filename = topic_map[topic_lower]
        content = read_knowledge_file(filename)
        return {
            "topic": topic,
            "source": f"knowledge_base/{filename}",
            "content": content,
            "note": "This documentation includes Mermaid diagrams that render in compatible viewers"
        }
    
    # Keyword search in topic
    for keyword, filename in topic_map.items():
        if keyword in topic_lower:
            content = read_knowledge_file(filename)
            return {
                "topic": topic,
                "matched_keyword": keyword,
                "source": f"knowledge_base/{filename}",
                "content": content
            }
    
    # Default: return overview + available topics
    return {
        "error": f"Topic '{topic}' not found",
        "available_topics": list(topic_map.keys()),
        "suggestion": "Try: get_knowledge_base_content(topic='overview') for introduction",
        "note": "You can also request specific tool documentation with 'tool:tool_name'"
    }


@mcp.tool(
    name="list_knowledge_base_topics",
    description=(
        "📑 List all available documentation topics in the knowledge base.\n\n"
        "Returns organized list of available documentation with descriptions."
    ),
)
def list_knowledge_base_topics():
    """List all available knowledge base topics"""
    
    return {
        "knowledge_base_location": str(KNOWLEDGE_BASE_DIR),
        "core_documentation": {
            "overview": {
                "file": "overview.md",
                "description": "MCP purpose, capabilities, when to use, what it does/doesn't do"
            },
            "workflows": {
                "file": "workflows.md",
                "description": "7 step-by-step guides: slow query analysis, plan comparison, permission checks, etc.",
                "includes": "Complete workflows from start to finish"
            },
            "architecture": {
                "file": "architecture.md",
                "description": "How MCP works internally, preset impact, data flow",
                "includes": "Mermaid diagrams showing system architecture and data flow"
            },
            "troubleshooting": {
                "file": "troubleshooting.md",
                "description": "Common errors and solutions",
                "includes": "ORA-00942, connection issues, permission errors, stale statistics, etc."
            }
        },
        "tool_documentation": {
            "check_oracle_access": {
                "file": "tools/check_oracle_access.md",
                "description": "Verify Oracle permissions and data dictionary access",
                "use_topic": "tool:check_oracle_access"
            },
            "check_mysql_access": {
                "file": "tools/check_mysql_access.md",
                "description": "Verify MySQL permissions and performance_schema access",
                "use_topic": "tool:check_mysql_access"
            },
            "analyze_oracle_query": {
                "file": "tools/analyze_oracle_query.md",
                "description": "Main Oracle query analysis tool with preset explanations",
                "use_topic": "tool:analyze_oracle_query"
            }
        },
        "usage_examples": [
            "get_knowledge_base_content(topic='overview')",
            "get_knowledge_base_content(topic='workflows')",
            "get_knowledge_base_content(topic='architecture')  # Includes diagrams!",
            "get_knowledge_base_content(topic='tool:check_oracle_access')",
            "get_knowledge_base_content(topic='slow query')  # Smart search"
        ],
        "note": "All documentation includes examples, diagrams, and real-world scenarios"
    }


# Keep old function name for backward compatibility
@mcp.tool(
    name="get_mcp_help",
    description=(
        "📚 Legacy help function - redirects to knowledge base.\n\n"
        "**Deprecated:** Use get_knowledge_base_content() instead for full documentation.\n\n"
        "This function now returns a summary and points to the knowledge base."
    ),
)
def get_mcp_help(topic: str = "overview"):
    """
    Legacy help function - provides summary and redirects to knowledge base
    
    Args:
        topic: Help topic (kept for backward compatibility)
    
    Returns:
        Summary with pointer to knowledge base
    """
    
    return {
        "mcp_name": "Performance MCP Server",
        "version": "2.0",
        "purpose": "SQL query performance analysis without execution",
        "message": "✨ Full documentation now available in knowledge base!",
        
        "redirect": {
            "use_tool": "get_knowledge_base_content",
            "examples": [
                "get_knowledge_base_content(topic='overview')",
                "get_knowledge_base_content(topic='workflows')",
                "get_knowledge_base_content(topic='troubleshooting')",
                "get_knowledge_base_content(topic='tool:check_oracle_access')"
            ]
        },
        
        "quick_start": {
            "most_used_tool": "analyze_oracle_query",
            "typical_workflow": [
                "1. User provides slow Oracle query",
                "2. Call analyze_oracle_query(db_name='prod', sql_text='...')",
                "3. Review execution plan for expensive operations",
                "4. Suggest optimization (index, query rewrite)",
                "5. Use compare_oracle_query_plans to verify improvement"
            ],
            "get_detailed_help": "Call get_knowledge_base_content() for comprehensive docs"
        }
    }

