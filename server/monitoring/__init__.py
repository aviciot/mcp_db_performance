"""
Performance Monitoring Module

This module provides real-time and historical performance monitoring for Oracle databases.

Security Model:
- READ ONLY: All monitoring queries only SELECT from system views (V$SQL, V$SYSSTAT, etc.)
- NEVER EXECUTE: User SQL retrieved from V$SQL is displayed for analysis, NEVER executed
- Inherits Security: Monitoring queries go through existing validate_sql() security layer

Components:
- oracle_monitor.py: Real-time data collection from V$ views
- snapshot_manager.py: Historical snapshot storage to SQLite
- scheduler.py: Background scheduler stub (Phase 2 - disabled by default)
"""

from .oracle_monitor import OracleMonitor
from .snapshot_manager import SnapshotManager

__all__ = ['OracleMonitor', 'SnapshotManager']
