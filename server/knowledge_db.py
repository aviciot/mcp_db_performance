# server/knowledge_db.py
"""
Knowledge Database Connector

Manages PostgreSQL connection for the business logic knowledge base.
Handles caching of table metadata, relationships, and query explanations.
"""

import os
import json
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from contextlib import contextmanager

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor, Json
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

logger = logging.getLogger("knowledge_db")


class KnowledgeDB:
    """
    Knowledge database connector for caching business context.
    
    Uses PostgreSQL to store:
    - Table metadata and inferred business meaning
    - Relationships between tables
    - Cached query explanations
    - Domain glossary terms
    """
    
    # Cache TTL settings (in days)
    TABLE_CACHE_TTL_DAYS = 7
    RELATIONSHIP_CACHE_TTL_DAYS = 7
    QUERY_CACHE_TTL_DAYS = 30
    
    def __init__(self):
        """Initialize knowledge DB connection."""
        self._conn = None
        self._enabled = False
        
        # Connection settings from environment or defaults
        self.host = os.getenv("KNOWLEDGE_DB_HOST", "postgres")
        self.port = int(os.getenv("KNOWLEDGE_DB_PORT", "5432"))
        self.database = os.getenv("KNOWLEDGE_DB_NAME", "omni")
        self.user = os.getenv("KNOWLEDGE_DB_USER", "postgres")
        self.password = os.getenv("KNOWLEDGE_DB_PASSWORD", "postgres")
        
        if not PSYCOPG2_AVAILABLE:
            logger.warning("⚠️ psycopg2 not installed - knowledge caching disabled")
            return
            
        self._try_connect()
    
    def _try_connect(self) -> bool:
        """Try to establish database connection."""
        try:
            self._conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                connect_timeout=5
            )
            self._conn.autocommit = False
            self._enabled = True
            logger.info(f"✅ Connected to knowledge DB at {self.host}:{self.port}/{self.database}")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Cannot connect to knowledge DB: {e} - caching disabled")
            self._enabled = False
            return False
    
    @property
    def is_enabled(self) -> bool:
        """Check if knowledge DB is available."""
        return self._enabled and self._conn is not None
    
    @contextmanager
    def _cursor(self):
        """Get a database cursor with auto-commit handling."""
        if not self.is_enabled:
            yield None
            return
            
        try:
            cur = self._conn.cursor(cursor_factory=RealDictCursor)
            yield cur
            self._conn.commit()
        except Exception as e:
            self._conn.rollback()
            logger.error(f"❌ Knowledge DB error: {e}")
            raise
        finally:
            if cur:
                cur.close()
    
    # ========================================
    # Table Knowledge
    # ========================================
    
    def get_table_knowledge(
        self, 
        db_name: str, 
        owner: str, 
        table_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached table knowledge.
        
        Returns None if not cached or cache is stale.
        """
        if not self.is_enabled:
            logger.debug(f"🔌 Knowledge DB not enabled, skipping cache lookup")
            return None
            
        with self._cursor() as cur:
            if cur is None:
                logger.warning(f"⚠️ No database cursor available")
                return None
                
            cur.execute("""
                SELECT * FROM table_knowledge
                WHERE db_name = %s AND owner = %s AND table_name = %s
                  AND last_refreshed > NOW() - INTERVAL '%s days'
            """, (db_name, owner.upper(), table_name.upper(), self.TABLE_CACHE_TTL_DAYS))
            
            row = cur.fetchone()
            if row:
                logger.info(f"💾 PostgreSQL cache: Found {owner}.{table_name} (refreshed: {row.get('last_refreshed', 'unknown')})")
                return dict(row)
            else:
                logger.debug(f"💾 PostgreSQL cache: No entry for {owner}.{table_name}")
                return None
    
    def get_tables_knowledge_batch(
        self, 
        db_name: str, 
        tables: List[Tuple[str, str]]
    ) -> Dict[Tuple[str, str], Dict[str, Any]]:
        """
        Get cached knowledge for multiple tables at once.
        
        Args:
            db_name: Database name
            tables: List of (owner, table_name) tuples
            
        Returns:
            Dict mapping (owner, table) to knowledge dict
        """
        if not self.is_enabled or not tables:
            return {}
            
        with self._cursor() as cur:
            if cur is None:
                return {}
            
            # Build query for batch lookup
            conditions = []
            params = [db_name, self.TABLE_CACHE_TTL_DAYS]
            
            for i, (owner, table) in enumerate(tables):
                conditions.append(f"(owner = %s AND table_name = %s)")
                params.extend([owner.upper(), table.upper()])
            
            cur.execute(f"""
                SELECT * FROM table_knowledge
                WHERE db_name = %s
                  AND last_refreshed > NOW() - INTERVAL '%s days'
                  AND ({' OR '.join(conditions)})
            """, params)
            
            result = {}
            for row in cur.fetchall():
                key = (row['owner'], row['table_name'])
                result[key] = dict(row)
            
            return result
    
    def save_table_knowledge(
        self,
        db_name: str,
        owner: str,
        table_name: str,
        oracle_comment: Optional[str] = None,
        num_rows: Optional[int] = None,
        is_partitioned: bool = False,
        partition_type: Optional[str] = None,
        partition_key_columns: Optional[List[str]] = None,
        columns: Optional[List[Dict]] = None,
        primary_key_columns: Optional[List[str]] = None,
        inferred_entity_type: Optional[str] = None,
        inferred_domain: Optional[str] = None,
        business_description: Optional[str] = None,
        business_purpose: Optional[str] = None,
        confidence_score: float = 0.5
    ) -> bool:
        """Save or update table knowledge."""
        if not self.is_enabled:
            return False
            
        with self._cursor() as cur:
            if cur is None:
                return False
                
            cur.execute("""
                INSERT INTO table_knowledge (
                    db_name, owner, table_name, oracle_comment, num_rows,
                    is_partitioned, partition_type, partition_key_columns,
                    columns, primary_key_columns,
                    inferred_entity_type, inferred_domain,
                    business_description, business_purpose, confidence_score
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (db_name, owner, table_name) DO UPDATE SET
                    oracle_comment = EXCLUDED.oracle_comment,
                    num_rows = EXCLUDED.num_rows,
                    is_partitioned = EXCLUDED.is_partitioned,
                    partition_type = EXCLUDED.partition_type,
                    partition_key_columns = EXCLUDED.partition_key_columns,
                    columns = EXCLUDED.columns,
                    primary_key_columns = EXCLUDED.primary_key_columns,
                    inferred_entity_type = COALESCE(EXCLUDED.inferred_entity_type, table_knowledge.inferred_entity_type),
                    inferred_domain = COALESCE(EXCLUDED.inferred_domain, table_knowledge.inferred_domain),
                    business_description = COALESCE(EXCLUDED.business_description, table_knowledge.business_description),
                    business_purpose = COALESCE(EXCLUDED.business_purpose, table_knowledge.business_purpose),
                    confidence_score = EXCLUDED.confidence_score,
                    last_refreshed = NOW(),
                    refresh_count = table_knowledge.refresh_count + 1
            """, (
                db_name, owner.upper(), table_name.upper(), oracle_comment, num_rows,
                is_partitioned, partition_type, partition_key_columns,
                Json(columns) if columns else Json([]), primary_key_columns,
                inferred_entity_type, inferred_domain,
                business_description, business_purpose, confidence_score
            ))
            
            logger.debug(f"💾 Saved table knowledge: {owner}.{table_name}")
            return True
    
    # ========================================
    # Relationship Knowledge
    # ========================================
    
    def get_relationships_for_table(
        self,
        db_name: str,
        owner: str,
        table_name: str
    ) -> List[Dict[str, Any]]:
        """Get all relationships where this table is involved (from or to)."""
        if not self.is_enabled:
            return []
            
        with self._cursor() as cur:
            if cur is None:
                return []
                
            cur.execute("""
                SELECT * FROM relationship_knowledge
                WHERE db_name = %s
                  AND last_refreshed > NOW() - INTERVAL '%s days'
                  AND (
                    (from_owner = %s AND from_table = %s)
                    OR (to_owner = %s AND to_table = %s)
                  )
            """, (
                db_name, self.RELATIONSHIP_CACHE_TTL_DAYS,
                owner.upper(), table_name.upper(),
                owner.upper(), table_name.upper()
            ))
            
            return [dict(row) for row in cur.fetchall()]
    
    def get_outgoing_relationships(
        self,
        db_name: str,
        owner: str,
        table_name: str
    ) -> List[Dict[str, Any]]:
        """Get relationships where this table has FKs to other tables."""
        if not self.is_enabled:
            return []
            
        with self._cursor() as cur:
            if cur is None:
                return []
                
            cur.execute("""
                SELECT * FROM relationship_knowledge
                WHERE db_name = %s
                  AND from_owner = %s AND from_table = %s
                  AND last_refreshed > NOW() - INTERVAL '%s days'
            """, (db_name, owner.upper(), table_name.upper(), self.RELATIONSHIP_CACHE_TTL_DAYS))
            
            return [dict(row) for row in cur.fetchall()]
    
    def save_relationship(
        self,
        db_name: str,
        from_owner: str,
        from_table: str,
        from_columns: List[str],
        to_owner: str,
        to_table: str,
        to_columns: List[str],
        relationship_type: str = "FK",
        constraint_name: Optional[str] = None,
        cardinality: Optional[str] = None,
        is_lookup: bool = False,
        business_meaning: Optional[str] = None,
        relationship_role: Optional[str] = None
    ) -> bool:
        """Save or update relationship knowledge."""
        if not self.is_enabled:
            return False
            
        with self._cursor() as cur:
            if cur is None:
                return False
                
            cur.execute("""
                INSERT INTO relationship_knowledge (
                    db_name, from_owner, from_table, from_columns,
                    to_owner, to_table, to_columns,
                    relationship_type, constraint_name, cardinality,
                    is_lookup, business_meaning, relationship_role
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (db_name, from_owner, from_table, to_owner, to_table, from_columns) 
                DO UPDATE SET
                    to_columns = EXCLUDED.to_columns,
                    relationship_type = EXCLUDED.relationship_type,
                    constraint_name = EXCLUDED.constraint_name,
                    cardinality = EXCLUDED.cardinality,
                    is_lookup = EXCLUDED.is_lookup,
                    business_meaning = COALESCE(EXCLUDED.business_meaning, relationship_knowledge.business_meaning),
                    relationship_role = COALESCE(EXCLUDED.relationship_role, relationship_knowledge.relationship_role),
                    last_refreshed = NOW()
            """, (
                db_name, from_owner.upper(), from_table.upper(), from_columns,
                to_owner.upper(), to_table.upper(), to_columns,
                relationship_type, constraint_name, cardinality,
                is_lookup, business_meaning, relationship_role
            ))
            
            logger.debug(f"💾 Saved relationship: {from_owner}.{from_table} -> {to_owner}.{to_table}")
            return True
    
    # ========================================
    # Query Explanation Cache
    # ========================================
    
    @staticmethod
    def hash_sql(sql_text: str) -> str:
        """Generate fingerprint hash for SQL query."""
        # Normalize: lowercase, collapse whitespace, remove trailing semicolon
        normalized = ' '.join(sql_text.lower().split())
        if normalized.endswith(';'):
            normalized = normalized[:-1]
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]
    
    def get_query_explanation(
        self,
        db_name: str,
        sql_text: str
    ) -> Optional[Dict[str, Any]]:
        """Get cached explanation for a query."""
        if not self.is_enabled:
            return None
            
        fingerprint = self.hash_sql(sql_text)
        
        with self._cursor() as cur:
            if cur is None:
                return None
                
            cur.execute("""
                UPDATE query_explanations
                SET hit_count = hit_count + 1,
                    last_accessed = NOW()
                WHERE sql_fingerprint = %s AND db_name = %s
                  AND created_at > NOW() - INTERVAL '%s days'
                RETURNING *
            """, (fingerprint, db_name, self.QUERY_CACHE_TTL_DAYS))
            
            row = cur.fetchone()
            if row:
                logger.info(f"📦 Cache HIT for query explanation (hits: {row['hit_count']})")
                return dict(row)
            return None
    
    def save_query_explanation(
        self,
        db_name: str,
        sql_text: str,
        business_explanation: str,
        tables_involved: List[Dict[str, str]],
        query_purpose: Optional[str] = None,
        data_flow_description: Optional[str] = None,
        domain_tags: Optional[List[str]] = None
    ) -> bool:
        """Save query explanation to cache."""
        if not self.is_enabled:
            return False
            
        fingerprint = self.hash_sql(sql_text)
        normalized = ' '.join(sql_text.lower().split())
        
        with self._cursor() as cur:
            if cur is None:
                return False
                
            cur.execute("""
                INSERT INTO query_explanations (
                    sql_fingerprint, db_name, sql_text, sql_normalized,
                    tables_involved, business_explanation,
                    query_purpose, data_flow_description, domain_tags
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (sql_fingerprint, db_name) DO UPDATE SET
                    business_explanation = EXCLUDED.business_explanation,
                    query_purpose = EXCLUDED.query_purpose,
                    data_flow_description = EXCLUDED.data_flow_description,
                    domain_tags = EXCLUDED.domain_tags,
                    last_accessed = NOW(),
                    hit_count = query_explanations.hit_count + 1
            """, (
                fingerprint, db_name, sql_text, normalized,
                Json(tables_involved), business_explanation,
                query_purpose, data_flow_description, domain_tags
            ))
            
            logger.info(f"💾 Cached query explanation (fingerprint: {fingerprint})")
            return True
    
    # ========================================
    # Domain Glossary
    # ========================================
    
    def add_domain_term(
        self,
        term: str,
        domain: str,
        definition: str,
        examples: Optional[List[str]] = None,
        related_terms: Optional[List[str]] = None,
        example_tables: Optional[List[str]] = None,
        example_columns: Optional[List[str]] = None
    ) -> bool:
        """Add or update a domain term."""
        if not self.is_enabled:
            return False
            
        with self._cursor() as cur:
            if cur is None:
                return False
                
            cur.execute("""
                INSERT INTO domain_glossary (
                    term, domain, definition, examples,
                    related_terms, example_tables, example_columns
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (term, domain) DO UPDATE SET
                    definition = EXCLUDED.definition,
                    examples = COALESCE(EXCLUDED.examples, domain_glossary.examples),
                    related_terms = COALESCE(EXCLUDED.related_terms, domain_glossary.related_terms),
                    example_tables = COALESCE(EXCLUDED.example_tables, domain_glossary.example_tables),
                    example_columns = COALESCE(EXCLUDED.example_columns, domain_glossary.example_columns),
                    occurrence_count = domain_glossary.occurrence_count + 1
            """, (
                term.lower(), domain.lower(), definition,
                examples, related_terms, example_tables, example_columns
            ))
            return True
    
    def get_domain_terms(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get domain glossary terms."""
        if not self.is_enabled:
            return []
            
        with self._cursor() as cur:
            if cur is None:
                return []
                
            if domain:
                cur.execute("""
                    SELECT * FROM domain_glossary
                    WHERE domain = %s
                    ORDER BY occurrence_count DESC
                """, (domain.lower(),))
            else:
                cur.execute("""
                    SELECT * FROM domain_glossary
                    ORDER BY domain, occurrence_count DESC
                """)
            
            return [dict(row) for row in cur.fetchall()]
    
    # ========================================
    # Discovery Logging
    # ========================================
    
    def log_discovery(
        self,
        operation_type: str,
        db_name: str,
        tables_discovered: int = 0,
        relationships_discovered: int = 0,
        cache_hits: int = 0,
        cache_misses: int = 0,
        duration_ms: Optional[int] = None,
        oracle_queries_executed: int = 0,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> bool:
        """Log a discovery operation."""
        if not self.is_enabled:
            return False
            
        with self._cursor() as cur:
            if cur is None:
                return False
                
            cur.execute("""
                INSERT INTO discovery_log (
                    operation_type, db_name,
                    tables_discovered, relationships_discovered,
                    cache_hits, cache_misses,
                    duration_ms, oracle_queries_executed,
                    success, error_message
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                operation_type, db_name,
                tables_discovered, relationships_discovered,
                cache_hits, cache_misses,
                duration_ms, oracle_queries_executed,
                success, error_message
            ))
            return True
    
    # ========================================
    # Admin Documentation (Table Overrides)
    # ========================================
    
    def set_table_documentation(
        self,
        db_name: str,
        owner: str,
        table_name: str,
        business_description: str,
        business_purpose: Optional[str] = None,
        domain: Optional[str] = None,
        entity_type: Optional[str] = None
    ) -> bool:
        """
        Admin function: Set business documentation for a table.
        
        This overrides auto-inferred values with admin-provided documentation.
        """
        if not self.is_enabled:
            return False
            
        with self._cursor() as cur:
            if cur is None:
                return False
            
            # Update existing or insert new
            cur.execute("""
                INSERT INTO table_knowledge (
                    db_name, owner, table_name,
                    business_description, business_purpose,
                    inferred_domain, inferred_entity_type,
                    confidence_score
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 1.0)
                ON CONFLICT (db_name, owner, table_name) DO UPDATE SET
                    business_description = EXCLUDED.business_description,
                    business_purpose = COALESCE(EXCLUDED.business_purpose, table_knowledge.business_purpose),
                    inferred_domain = COALESCE(EXCLUDED.inferred_domain, table_knowledge.inferred_domain),
                    inferred_entity_type = COALESCE(EXCLUDED.inferred_entity_type, table_knowledge.inferred_entity_type),
                    confidence_score = 1.0,
                    last_refreshed = NOW()
            """, (
                db_name, owner.upper(), table_name.upper(),
                business_description, business_purpose,
                domain, entity_type
            ))
            
            logger.info(f"📝 Admin set documentation for {owner}.{table_name}")
            return True
    
    def get_admin_documentation(
        self,
        db_name: str,
        owner: str,
        table_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get admin-provided documentation for a table.
        
        Returns None if no admin documentation exists.
        """
        if not self.is_enabled:
            return None
            
        with self._cursor() as cur:
            if cur is None:
                return None
            
            cur.execute("""
                SELECT business_description, business_purpose, 
                       inferred_domain, inferred_entity_type
                FROM table_knowledge
                WHERE db_name = %s AND owner = %s AND table_name = %s
                  AND business_description IS NOT NULL
                  AND confidence_score >= 1.0
            """, (db_name, owner.upper(), table_name.upper()))
            
            row = cur.fetchone()
            if row:
                return {
                    "description": row["business_description"],
                    "purpose": row["business_purpose"],
                    "domain": row["inferred_domain"],
                    "entity_type": row["inferred_entity_type"],
                    "is_admin_provided": True
                }
            return None
    
    def list_documented_tables(self, db_name: Optional[str] = None) -> List[Dict[str, str]]:
        """List all tables that have admin-provided documentation."""
        if not self.is_enabled:
            return []
            
        with self._cursor() as cur:
            if cur is None:
                return []
            
            if db_name:
                cur.execute("""
                    SELECT db_name, owner, table_name, business_description
                    FROM table_knowledge
                    WHERE db_name = %s
                      AND business_description IS NOT NULL
                      AND confidence_score >= 1.0
                    ORDER BY owner, table_name
                """, (db_name,))
            else:
                cur.execute("""
                    SELECT db_name, owner, table_name, business_description
                    FROM table_knowledge
                    WHERE business_description IS NOT NULL
                      AND confidence_score >= 1.0
                    ORDER BY db_name, owner, table_name
                """)
            
            return [dict(row) for row in cur.fetchall()]
    
    # ========================================
    # Utility Methods
    # ========================================
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about cached knowledge."""
        if not self.is_enabled:
            return {"enabled": False}
            
        with self._cursor() as cur:
            if cur is None:
                return {"enabled": False}
            
            stats = {"enabled": True}
            
            # Table knowledge stats
            cur.execute("SELECT COUNT(*) as count FROM table_knowledge")
            stats["tables_cached"] = cur.fetchone()["count"]
            
            # Relationship stats
            cur.execute("SELECT COUNT(*) as count FROM relationship_knowledge")
            stats["relationships_cached"] = cur.fetchone()["count"]
            
            # Query explanation stats
            cur.execute("""
                SELECT COUNT(*) as count, SUM(hit_count) as total_hits
                FROM query_explanations
            """)
            row = cur.fetchone()
            stats["queries_cached"] = row["count"]
            stats["total_cache_hits"] = row["total_hits"] or 0
            
            # Domain terms
            cur.execute("SELECT COUNT(*) as count FROM domain_glossary")
            stats["domain_terms"] = cur.fetchone()["count"]
            
            return stats
    
    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
            self._enabled = False
            logger.info("🔌 Knowledge DB connection closed")


# Global instance
_knowledge_db: Optional[KnowledgeDB] = None


def get_knowledge_db() -> KnowledgeDB:
    """Get or create the global knowledge DB instance."""
    global _knowledge_db
    if _knowledge_db is None:
        _knowledge_db = KnowledgeDB()
    return _knowledge_db
