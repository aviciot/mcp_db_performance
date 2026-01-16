# server/knowledge_db.py
"""
Knowledge Database Connector (Async)

Manages PostgreSQL connection for the business logic knowledge base using asyncpg.
Handles caching of table metadata, relationships, and query explanations.

Fixes applied:
- Renamed class to KnowledgeDB for clarity
- Added comprehensive error handling with clear logging
- Made TTLs configurable via config
- Added connection retry logic
- Added graceful degradation when PostgreSQL is unavailable
"""

import os
import json
import hashlib
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from config import config

try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    logging.warning("asyncpg not available - PostgreSQL cache will be disabled")

logger = logging.getLogger("knowledge_db")


class KnowledgeDBError(Exception):
    """Custom exception for Knowledge DB errors."""
    pass


class KnowledgeDB:
    """
    Knowledge database connector for caching business context.
    
    Uses PostgreSQL to store:
    - Table metadata and inferred business meaning
    - Relationships between tables
    - Cached query explanations
    - Domain glossary terms
    
    Features:
    - Configurable TTL settings
    - Comprehensive error handling
    - Connection retry logic
    - Graceful degradation when PostgreSQL unavailable
    """
    
    def __init__(self, schema: str = None):
        if not ASYNCPG_AVAILABLE:
            logger.error("❌ asyncpg not available - PostgreSQL cache disabled")
            self.pool = None
            self._enabled = False
            self.config = None
            return
            
        # Get configuration from config.py
        try:
            self.config = config.get_postgresql_config()
        except Exception as e:
            logger.error(f"❌ Failed to load PostgreSQL config: {e}")
            self.pool = None
            self._enabled = False
            self.config = None
            return
        
        # Schema support for multi-MCP deployment
        self.schema = schema or self.config["schema"]
        
        # Connection state
        self.pool = None
        self._enabled = False
        self._connection_attempts = 0
        self._last_connection_error = None
        
        # Cache TTL settings from config
        self.ttl_days = self.config["cache_ttl"]
        
        logger.info(f"📦 Knowledge DB initialized with schema: {self.schema}")
        logger.info(f"🔧 Cache TTLs: tables={self.ttl_days['table_knowledge']}d, "
                   f"relationships={self.ttl_days['relationships']}d, "
                   f"queries={self.ttl_days['query_explanations']}d")

    async def connect(self, retry: bool = True):
        """Establish connection pool to PostgreSQL knowledge database."""
        logger.debug(f"[DEBUG] Entered KnowledgeDB.connect() (attempts={self._connection_attempts}, enabled={self._enabled})")
        if not ASYNCPG_AVAILABLE:
            logger.error("❌ asyncpg not available - cannot connect to PostgreSQL")
            self._enabled = False
            return False
            
        self._connection_attempts += 1
        
        host = self.config["host"]
        port = self.config["port"]
        database = self.config["database"]
        user = self.config["user"]
        password = self.config["password"]
        
        logger.info(f"🔗 Connecting to PostgreSQL (attempt {self._connection_attempts}): {user}@{host}:{port}/{database}")
        
        try:
            self.pool = await asyncpg.create_pool(
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
                min_size=self.config["pool"]["min_size"],
                max_size=self.config["pool"]["max_size"],
                server_settings={
                    'application_name': f'mcp_performance_server_{self.schema}',
                    'search_path': f'{self.schema},public'
                }
            )
            
            # Test connection with a simple query
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            
            self._enabled = True
            self._last_connection_error = None
            logger.info(f"✅ Knowledge DB connected successfully to {host}:{port}/{database} (schema: {self.schema})")
            logger.info(f"   🔗 Pool: {self.pool}, Enabled: {self.is_enabled}")
            return True
            
        except Exception as e:
            self._enabled = False
            self.pool = None
            self._last_connection_error = str(e)
            
            error_msg = f"❌ Failed to connect to Knowledge DB (attempt {self._connection_attempts}): {e}"
            
            if self.config["error_handling"]["log_all_errors"]:
                logger.error(error_msg, exc_info=True)
            else:
                logger.error(error_msg)
            
            # Retry logic
            if retry and self._connection_attempts < self.config["error_handling"]["retry_attempts"]:
                delay = self.config["error_handling"]["retry_delay_seconds"]
                logger.info(f"🔄 Retrying connection in {delay} seconds...")
                await asyncio.sleep(delay)
                return await self.connect(retry=True)
            
            # Final failure - decide whether to raise or degrade gracefully
            if self.config["error_handling"]["raise_on_connection_failure"]:
                raise KnowledgeDBError(f"Failed to connect after {self._connection_attempts} attempts: {e}")
            else:
                logger.warning(f"⚠️  PostgreSQL cache unavailable - continuing without cache (graceful degradation)")
                return False
    
    @property
    def is_enabled(self) -> bool:
        """Check if knowledge DB is available."""
        return self._enabled and self.pool is not None
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get detailed connection status for diagnostics."""
        return {
            "enabled": self._enabled,
            "pool_exists": self.pool is not None,
            "config_loaded": self.config is not None,
            "connection_attempts": self._connection_attempts,
            "last_error": self._last_connection_error,
            "schema": self.schema,
            "host": self.config.get("host") if self.config else None,
            "port": self.config.get("port") if self.config else None,
            "database": self.config.get("database") if self.config else None
        }
    
    # ========================================
    # Database Helper Methods
    # ========================================
    
    async def fetchrow(self, query, *args):
        """Execute query and return single row."""
        if not self.is_enabled:
            print("[KnowledgeDBAsync] fetchrow: DB not enabled!")
            raise RuntimeError("KnowledgeDBAsync is not enabled (no DB connection)")
        try:
            async with self.pool.acquire() as conn:
                logger.debug(f"[DB] fetchrow: pool={self.pool}, conn={conn}, query={query}, args={args}")
                result = await conn.fetchrow(query, *args)
                logger.debug(f"[DB] fetchrow result: {result}")
                return result
        except Exception as e:
            print(f"[KnowledgeDBAsync] fetchrow ERROR: {e}\n  Query: {query}\n  Args: {args}\n  DB: {self.schema}")
            logger.error(f"[KnowledgeDBAsync] fetchrow ERROR: {e}", exc_info=True)
            raise

    async def fetch(self, query, *args):
        """Execute query and return all rows."""
        if not self.is_enabled:
            print("[KnowledgeDBAsync] fetch: DB not enabled!")
            raise RuntimeError("KnowledgeDBAsync is not enabled (no DB connection)")
        try:
            async with self.pool.acquire() as conn:
                logger.debug(f"[DB] fetch: pool={self.pool}, conn={conn}, query={query}, args={args}")
                result = await conn.fetch(query, *args)
                logger.debug(f"[DB] fetch result: {result}")
                return result
        except Exception as e:
            print(f"[KnowledgeDBAsync] fetch ERROR: {e}\n  Query: {query}\n  Args: {args}\n  DB: {self.schema}")
            logger.error(f"[KnowledgeDBAsync] fetch ERROR: {e}", exc_info=True)
            raise

    async def fetchval(self, query, *args):
        """Execute query and return single value."""
        if not self.is_enabled:
            print("[KnowledgeDBAsync] fetchval: DB not enabled!")
            raise RuntimeError("KnowledgeDBAsync is not enabled (no DB connection)")
        try:
            async with self.pool.acquire() as conn:
                logger.debug(f"[DB] fetchval: pool={self.pool}, conn={conn}, query={query}, args={args}")
                result = await conn.fetchval(query, *args)
                logger.debug(f"[DB] fetchval result: {result}")
                return result
        except Exception as e:
            print(f"[KnowledgeDBAsync] fetchval ERROR: {e}\n  Query: {query}\n  Args: {args}\n  DB: {self.schema}")
            logger.error(f"[KnowledgeDBAsync] fetchval ERROR: {e}", exc_info=True)
            raise

    async def execute(self, query, *args):
        """Execute query (INSERT/UPDATE/DELETE)."""
        if not self.is_enabled:
            print("[KnowledgeDBAsync] execute: DB not enabled!")
            raise RuntimeError("KnowledgeDBAsync is not enabled (no DB connection)")
        try:
            async with self.pool.acquire() as conn:
                logger.debug(f"[DB] execute: pool={self.pool}, conn={conn}, query={query}, args={args}")
                result = await conn.execute(query, *args)
                logger.debug(f"[DB] execute result: {result}")
                return result
        except Exception as e:
            print(f"[KnowledgeDBAsync] execute ERROR: {e}\n  Query: {query}\n  Args: {args}\n  DB: {self.schema}")
            logger.error(f"[KnowledgeDBAsync] execute ERROR: {e}", exc_info=True)
            raise
    
    # Legacy sync cursor logic removed
    
    # ========================================
    # Table Knowledge
    # ========================================
    
    async def get_table_knowledge(self, db_name: str, owner: str, table_name: str) -> Optional[Dict[str, Any]]:
        """
        Get cached table knowledge (async).
        Returns None if not cached or cache is stale.
        """
        if not self.is_enabled:
            logger.debug(f"🔌 [POSTGRESQL READ] Knowledge DB not enabled, skipping cache lookup")
            logger.debug(f"   🔍 Status: {self.get_connection_status()}")
            return None
            
        logger.info(f"💾 [POSTGRESQL READ] Looking up from {self.config['host']}:{self.config['port']}/{self.config['database']}")
        logger.info(f"💾 [POSTGRESQL READ] Target: {self.schema}.table_knowledge")
        logger.info(f"💾 [POSTGRESQL READ] Query: db={db_name}, owner={owner.upper()}, table={table_name.upper()}")
        
        lookup_query = f"""
            SELECT * FROM {self.schema}.table_knowledge
            WHERE db_name = $1 AND owner = $2 AND table_name = $3
              AND last_refreshed > NOW() - INTERVAL '7 days'
            """
        
        logger.debug(f"💾 [POSTGRESQL READ] SQL: {lookup_query}")
        
        row = await self.fetchrow(lookup_query, db_name, owner.upper(), table_name.upper())
        
        if row:
            logger.info(f"✅ [POSTGRESQL READ] CACHE HIT: Found {owner}.{table_name} (refreshed: {row.get('last_refreshed', 'unknown')})")
            result = dict(row)
            # Parse JSON fields
            if result.get('columns'):
                try:
                    result['columns'] = json.loads(result['columns']) if isinstance(result['columns'], str) else result['columns']
                except:
                    result['columns'] = []
            return result
        else:
            logger.info(f"❌ [POSTGRESQL READ] CACHE MISS: No entry for {owner}.{table_name}")
            
            # Debug: Show what IS in the table
            debug_query = f"SELECT db_name, owner, table_name, last_refreshed FROM {self.schema}.table_knowledge LIMIT 5"
            debug_rows = await self.fetch(debug_query)
            logger.debug(f"🔍 [POSTGRESQL DEBUG] Current table contents: {[dict(r) for r in debug_rows]}")
            
            return None

    async def get_tables_knowledge_batch(self, db_name: str, tables: List[Tuple[str, str]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
        """Get cached knowledge for multiple tables at once (async) - OPTIMIZED.
        Returns dict mapping (owner, table) to knowledge dict.
        """
        if not self.is_enabled or not tables:
            return {}

        # Performance optimization: batch processing
        owners = [owner.upper() for owner, _ in tables]
        table_names = [table.upper() for _, table in tables]

        # Enhanced query with better indexing hints
        rows = await self.fetch(
            f"""
                SELECT * FROM {self.schema}.table_knowledge
                WHERE db_name = $1
                  AND last_refreshed > NOW() - INTERVAL '7 days'
                  AND owner = ANY($2::text[])
                  AND table_name = ANY($3::text[])
                ORDER BY refresh_count DESC  -- Most frequently used first
                """, db_name, owners, table_names
        )

        result = {}
        for row in rows:
            key = (row['owner'], row['table_name'])
            row_dict = dict(row)
            # Parse JSON fields efficiently
            if row_dict.get('columns') and isinstance(row_dict['columns'], str):
                try:
                    row_dict['columns'] = json.loads(row_dict['columns'])
                except (json.JSONDecodeError, TypeError):
                    row_dict['columns'] = []
            result[key] = row_dict

        logger.info(f"\U0001F4E6 Batch lookup: {len(result)}/{len(tables)} tables found in cache")
        return result
    
    async def save_tables_knowledge_batch(self, table_data: List[Dict]) -> int:
        """Save multiple table knowledge entries in a single transaction - HIGH PERFORMANCE."""
        if not self.is_enabled or not table_data:
            return 0
            
        logger.info(f"💾 [BATCH SAVE] Saving {len(table_data)} tables in single transaction...")
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    saved_count = 0
                    insert_query = f"""
                        INSERT INTO {self.schema}.table_knowledge (
                            db_name, owner, table_name, oracle_comment, num_rows,
                            is_partitioned, partition_type, partition_key_columns,
                            columns, primary_key_columns,
                            inferred_entity_type, inferred_domain,
                            business_description, business_purpose, confidence_score
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15
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
                            refresh_count = COALESCE(table_knowledge.refresh_count, 0) + 1
                    """
                    
                    for data in table_data:
                        await conn.execute(
                            insert_query,
                            data.get('db_name'), data.get('owner', '').upper(), data.get('table_name', '').upper(),
                            data.get('oracle_comment'), data.get('num_rows'),
                            data.get('is_partitioned', False), data.get('partition_type'), data.get('partition_key_columns'),
                            json.dumps(data.get('columns', [])), data.get('primary_key_columns'),
                            data.get('inferred_entity_type'), data.get('inferred_domain'),
                            data.get('business_description'), data.get('business_purpose'), data.get('confidence_score', 0.5)
                        )
                        saved_count += 1
                    
                    logger.info(f"✅ [BATCH SAVE] Successfully saved {saved_count} tables in transaction")
                    return saved_count
                    
        except Exception as e:
            logger.error(f"❌ [BATCH SAVE] Failed to save batch: {e}", exc_info=True)
            return 0
    
    async def save_table_knowledge(
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
        # Validate required parameters
        if not db_name or not owner or not table_name:
            logger.error(f"❌ [POSTGRESQL WRITE] Invalid parameters: db_name={db_name}, owner={owner}, table_name={table_name}")
            return False

        if not self.is_enabled:
            logger.warning(f"🔌 [POSTGRESQL WRITE] Knowledge DB not enabled, skipping save for {owner}.{table_name}")
            logger.warning(f"   🔍 Connection status: {self.get_connection_status()}")
            return False

        try:
            # Log the actual parameters being saved
            logger.info(f"💾 [POSTGRESQL WRITE] Saving to {self.config['host']}:{self.config['port']}/{self.config['database']}")
            logger.info(f"💾 [POSTGRESQL WRITE] Target: {self.schema}.table_knowledge")
            logger.info(f"💾 [POSTGRESQL WRITE] Data: db={db_name}, owner={owner.upper()}, table={table_name.upper()}")
            logger.info(f"💾 [POSTGRESQL WRITE] Entity: {inferred_entity_type}, Domain: {inferred_domain}")
            
            insert_query = f"""
                INSERT INTO {self.schema}.table_knowledge (
                    db_name, owner, table_name, oracle_comment, num_rows,
                    is_partitioned, partition_type, partition_key_columns,
                    columns, primary_key_columns,
                    inferred_entity_type, inferred_domain,
                    business_description, business_purpose, confidence_score
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15
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
                    refresh_count = COALESCE(table_knowledge.refresh_count, 0) + 1
                """
            
            logger.debug(f"💾 [POSTGRESQL WRITE] Executing SQL: {insert_query[:200]}...")
            
            result = await self.execute(
                insert_query,
                db_name, owner.upper(), table_name.upper(), oracle_comment, num_rows,
                is_partitioned, partition_type, partition_key_columns,
                json.dumps(columns) if columns else json.dumps([]), primary_key_columns,
                inferred_entity_type, inferred_domain,
                business_description, business_purpose, confidence_score
            )
            
            logger.info(f"✅ [POSTGRESQL WRITE] INSERT result: {result}")
            logger.info(f"✅ [POSTGRESQL WRITE] Successfully saved {owner}.{table_name} to cache")
            
            # Verify the save worked by reading it back
            verify_query = f"SELECT db_name, owner, table_name FROM {self.schema}.table_knowledge WHERE db_name = $1 AND owner = $2 AND table_name = $3"
            verify_result = await self.fetchrow(verify_query, db_name, owner.upper(), table_name.upper())
            
            if verify_result:
                logger.info(f"✅ [POSTGRESQL VERIFY] Confirmed saved: {dict(verify_result)}")
            else:
                logger.error(f"❌ [POSTGRESQL VERIFY] FAILED - No data found after save!")
                
            return True
            
        except KnowledgeDBError as e:
            logger.error(f"❌ [POSTGRESQL ERROR] KnowledgeDB Error saving {owner}.{table_name}: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ [POSTGRESQL ERROR] Failed to save {owner}.{table_name}: {e}", exc_info=True)
            logger.error(f"❌ [POSTGRESQL ERROR] Connection: {self.config['host']}:{self.config['port']}/{self.config['database']}")
            logger.error(f"❌ [POSTGRESQL ERROR] Schema: {self.schema}")
            logger.error(f"❌ [POSTGRESQL ERROR] Pool status: enabled={self.is_enabled}, pool={self.pool is not None}")
            return False  # Graceful degradation
    
    # ========================================
    # Relationship Knowledge
    # ========================================
    
    async def get_relationships_for_table(
        self,
        db_name: str,
        owner: str,
        table_name: str
    ) -> List[Dict[str, Any]]:
        if not self.is_enabled:
            return []
        rows = await self.fetch(
            f"""
            SELECT * FROM {self.schema}.relationship_knowledge
            WHERE db_name = $1
              AND last_refreshed > NOW() - INTERVAL '7 days'
              AND (
                (from_owner = $2 AND from_table = $3)
                OR (to_owner = $2 AND to_table = $3)
              )
            """,
            db_name, owner.upper(), table_name.upper()
        )
        return [dict(row) for row in rows]
    
    async def get_outgoing_relationships(
        self,
        db_name: str,
        owner: str,
        table_name: str
    ) -> List[Dict[str, Any]]:
        if not self.is_enabled:
            return []
        rows = await self.fetch(
            f"""
            SELECT * FROM {self.schema}.relationship_knowledge
            WHERE db_name = $1
              AND from_owner = $2 AND from_table = $3
              AND last_refreshed > NOW() - INTERVAL '7 days'
            """,
            db_name, owner.upper(), table_name.upper()
        )
        return [dict(row) for row in rows]
    
    async def save_relationship(
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
        if not self.is_enabled:
            return False
        await self.execute(
            f"""
            INSERT INTO {self.schema}.relationship_knowledge (
                db_name, from_owner, from_table, from_columns,
                to_owner, to_table, to_columns,
                relationship_type, constraint_name, cardinality,
                is_lookup, business_meaning, relationship_role
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13
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
            """,
            db_name, from_owner.upper(), from_table.upper(), from_columns,
            to_owner.upper(), to_table.upper(), to_columns,
            relationship_type, constraint_name, cardinality,
            is_lookup, business_meaning, relationship_role
        )
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
    
    async def get_query_explanation(
        self,
        db_name: str,
        sql_text: str
    ) -> Optional[Dict[str, Any]]:
        if not self.is_enabled:
            return None
        fingerprint = self.hash_sql(sql_text)
        row = await self.fetchrow(
            f"""
            UPDATE {self.schema}.query_explanations
            SET hit_count = hit_count + 1,
                last_accessed = NOW()
            WHERE sql_fingerprint = $1 AND db_name = $2
              AND created_at > NOW() - INTERVAL '30 days'
            RETURNING *
            """,
            fingerprint, db_name
        )
        if row:
            logger.info(f"📦 Cache HIT for query explanation (hits: {row['hit_count']})")
            return dict(row)
        return None
    
    async def save_query_explanation(
        self,
        db_name: str,
        sql_text: str,
        business_explanation: str,
        tables_involved: List[Dict[str, str]],
        query_purpose: Optional[str] = None,
        data_flow_description: Optional[str] = None,
        domain_tags: Optional[List[str]] = None
    ) -> bool:
        if not self.is_enabled:
            return False
        fingerprint = self.hash_sql(sql_text)
        normalized = ' '.join(sql_text.lower().split())
        await self.execute(
            f"""
            INSERT INTO {self.schema}.query_explanations (
                sql_fingerprint, db_name, sql_text, sql_normalized,
                tables_involved, business_explanation,
                query_purpose, data_flow_description, domain_tags
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9
            )
            ON CONFLICT (sql_fingerprint, db_name) DO UPDATE SET
                business_explanation = EXCLUDED.business_explanation,
                query_purpose = EXCLUDED.query_purpose,
                data_flow_description = EXCLUDED.data_flow_description,
                domain_tags = EXCLUDED.domain_tags,
                last_accessed = NOW(),
                hit_count = query_explanations.hit_count + 1
            """,
            fingerprint, db_name, sql_text, normalized,
            json.dumps(tables_involved), business_explanation,
            query_purpose, data_flow_description, domain_tags
        )
        logger.info(f"💾 Cached query explanation (fingerprint: {fingerprint})")
        return True
    
    # ========================================
    # Domain Glossary
    # ========================================
    
    async def add_domain_term(
        self,
        term: str,
        domain: str,
        definition: str,
        examples: Optional[List[str]] = None,
        related_terms: Optional[List[str]] = None,
        example_tables: Optional[List[str]] = None,
        example_columns: Optional[List[str]] = None
    ) -> bool:
        if not self.is_enabled:
            return False
        await self.execute(
            f"""
            INSERT INTO {self.schema}.domain_glossary (
                term, domain, definition, examples,
                related_terms, example_tables, example_columns
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (term, domain) DO UPDATE SET
                definition = EXCLUDED.definition,
                examples = COALESCE(EXCLUDED.examples, domain_glossary.examples),
                related_terms = COALESCE(EXCLUDED.related_terms, domain_glossary.related_terms),
                example_tables = COALESCE(EXCLUDED.example_tables, domain_glossary.example_tables),
                example_columns = COALESCE(EXCLUDED.example_columns, domain_glossary.example_columns),
                occurrence_count = domain_glossary.occurrence_count + 1
            """,
            term.lower(), domain.lower(), definition,
            examples, related_terms, example_tables, example_columns
        )
        return True
    
    async def get_domain_terms(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get domain glossary terms (async)."""
        if not self.is_enabled:
            return []
        if domain:
            rows = await self.fetch(
                """
                SELECT * FROM {self.schema}.domain_glossary
                WHERE domain = $1
                ORDER BY occurrence_count DESC
                """,
                domain.lower()
            )
        else:
            rows = await self.fetch(
                """
                SELECT * FROM {self.schema}.domain_glossary
                ORDER BY domain, occurrence_count DESC
                """
            )
        return [dict(row) for row in rows]
    
    # ========================================
    # Discovery Logging
    # ========================================
    
    async def log_discovery(
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
        if not self.is_enabled:
            return False
        await self.execute(
            f"""
            INSERT INTO {self.schema}.discovery_log (
                operation_type, db_name,
                tables_discovered, relationships_discovered,
                cache_hits, cache_misses,
                duration_ms, oracle_queries_executed,
                success, error_message
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            operation_type, db_name,
            tables_discovered, relationships_discovered,
            cache_hits, cache_misses,
            duration_ms, oracle_queries_executed,
            success, error_message
        )
        return True
    
    # ========================================
    # Admin Documentation (Table Overrides)
    # ========================================
    
    async def set_table_documentation(
        self,
        db_name: str,
        owner: str,
        table_name: str,
        business_description: str,
        business_purpose: Optional[str] = None,
        domain: Optional[str] = None,
        entity_type: Optional[str] = None
    ) -> bool:
        if not self.is_enabled:
            return False
        await self.execute(
            f"""
            INSERT INTO {self.schema}.table_knowledge (
                db_name, owner, table_name,
                business_description, business_purpose,
                inferred_domain, inferred_entity_type,
                confidence_score
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, 1.0)
            ON CONFLICT (db_name, owner, table_name) DO UPDATE SET
                business_description = EXCLUDED.business_description,
                business_purpose = COALESCE(EXCLUDED.business_purpose, table_knowledge.business_purpose),
                inferred_domain = COALESCE(EXCLUDED.inferred_domain, table_knowledge.inferred_domain),
                inferred_entity_type = COALESCE(EXCLUDED.inferred_entity_type, table_knowledge.inferred_entity_type),
                confidence_score = 1.0,
                last_refreshed = NOW()
            """,
            db_name, owner.upper(), table_name.upper(),
            business_description, business_purpose,
            domain, entity_type
        )
        logger.info(f"📝 Admin set documentation for {owner}.{table_name}")
        return True
    
    async def get_admin_documentation(
        self,
        db_name: str,
        owner: str,
        table_name: str
    ) -> Optional[Dict[str, Any]]:
        if not self.is_enabled:
            return None
        row = await self.fetchrow(
            """
            SELECT business_description, business_purpose, 
                   inferred_domain, inferred_entity_type
            FROM {self.schema}.table_knowledge
            WHERE db_name = $1 AND owner = $2 AND table_name = $3
              AND business_description IS NOT NULL
              AND confidence_score >= 1.0
            """,
            db_name, owner.upper(), table_name.upper()
        )
        if row:
            return {
                "description": row["business_description"],
                "purpose": row["business_purpose"],
                "domain": row["inferred_domain"],
                "entity_type": row["inferred_entity_type"],
                "is_admin_provided": True
            }
        return None
    
    async def list_documented_tables(self, db_name: Optional[str] = None) -> List[Dict[str, str]]:
        """List all tables that have admin-provided documentation (async)."""
        if not self.is_enabled:
            return []
        if db_name:
            rows = await self.fetch(
                """
                SELECT db_name, owner, table_name, business_description
                FROM {self.schema}.table_knowledge
                WHERE db_name = $1
                  AND business_description IS NOT NULL
                  AND confidence_score >= 1.0
                ORDER BY owner, table_name
                """,
                db_name
            )
        else:
            rows = await self.fetch(
                """
                SELECT db_name, owner, table_name, business_description
                FROM {self.schema}.table_knowledge
                WHERE business_description IS NOT NULL
                  AND confidence_score >= 1.0
                ORDER BY db_name, owner, table_name
                """
            )
        return [dict(row) for row in rows]
    
    # ========================================
    # Utility Methods
    # ========================================
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about cached knowledge (async)."""
        if not self.is_enabled:
            return {"enabled": False}
        stats = {"enabled": True}
        # Table knowledge stats
        row = await self.fetchrow(f"SELECT COUNT(*) as count FROM {self.schema}.table_knowledge")
        stats["tables_cached"] = row["count"] if row else 0
        # Relationship stats
        row = await self.fetchrow(f"SELECT COUNT(*) as count FROM {self.schema}.relationship_knowledge")
        stats["relationships_cached"] = row["count"] if row else 0
        # Query explanation stats
        row = await self.fetchrow(f"SELECT COUNT(*) as count, SUM(hit_count) as total_hits FROM {self.schema}.query_explanations")
        stats["queries_cached"] = row["count"] if row else 0
        stats["total_cache_hits"] = row["total_hits"] if row and row["total_hits"] is not None else 0
        # Domain terms
        row = await self.fetchrow(f"SELECT COUNT(*) as count FROM {self.schema}.domain_glossary")
        stats["domain_terms"] = row["count"] if row else 0
        return stats
    
    async def warm_cache_on_startup(self, top_n: int = 100) -> Dict[str, int]:
        """Pre-warm cache with most frequently accessed tables for faster startup."""
        if not self.is_enabled:
            logger.warning("📦 Cache warming skipped - Knowledge DB not enabled")
            return {"warmed": 0, "relationships_warmed": 0}
            
        logger.info(f"🔥 Starting cache warming - loading top {top_n} most accessed tables...")
        
        try:
            # Get most frequently refreshed tables (indicates high usage)
            warm_query = f"""
                SELECT db_name, owner, table_name, refresh_count, last_refreshed,
                       inferred_entity_type, inferred_domain
                FROM {self.schema}.table_knowledge 
                WHERE last_refreshed > NOW() - INTERVAL '30 days'
                ORDER BY refresh_count DESC, last_refreshed DESC
                LIMIT $1
            """
            
            warm_rows = await self.fetch(warm_query, top_n)
            
            logger.info(f"🔥 Found {len(warm_rows)} tables to warm in cache")
            
            # Warm relationships for these tables
            relationship_count = 0
            for row in warm_rows:
                relationships = await self.get_relationships_for_table(
                    row['db_name'], row['owner'], row['table_name']
                )
                relationship_count += len(relationships)
            
            logger.info(f"✅ Cache warming complete: {len(warm_rows)} tables, {relationship_count} relationships")
            
            return {
                "warmed": len(warm_rows),
                "relationships_warmed": relationship_count,
                "top_domains": list(set([r['inferred_domain'] for r in warm_rows if r['inferred_domain']])),
                "top_entity_types": list(set([r['inferred_entity_type'] for r in warm_rows if r['inferred_entity_type']]))
            }
            
        except Exception as e:
            logger.error(f"❌ Cache warming failed: {e}")
            return {"warmed": 0, "relationships_warmed": 0, "error": str(e)}
    
    async def close(self):
        """Close async database pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            self._enabled = False
            logger.info("🔌 Knowledge DB async pool closed")


    async def _delayed_connect(self):
        """Delayed connection for auto-connect during initialization."""
        try:
            await asyncio.sleep(0.1)  # Small delay to let initialization complete
            success = await self.connect(retry=True)
            if success:
                logger.info("✅ Auto-connection successful during startup")
            else:
                logger.warning("⚠️  Auto-connection failed during startup")
        except Exception as e:
            logger.error(f"❌ Auto-connection error during startup: {e}")
    
    async def init(self):
        """Initialize the knowledge database connection (force connection)."""
        logger.info("🚀 Explicitly initializing Knowledge DB connection...")
        success = await self.connect(retry=True)
        if success:
            logger.info(f"✅ Knowledge DB initialization complete - connection established")
            logger.info(f"   📊 Connection details: {self.get_connection_status()}")
            
            # Start background health monitoring
            asyncio.create_task(self._health_monitor())
            logger.info("   💓 Background health monitoring started")
        else:
            logger.error(f"❌ Knowledge DB initialization FAILED")
            logger.error(f"   🔍 Connection status: {self.get_connection_status()}")
        return success
    
    async def _health_monitor(self):
        """Background task to monitor connection health and auto-recovery."""
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                if self.is_enabled:
                    # Quick health check
                    await self.fetchval("SELECT 1")
                    logger.debug("💚 Connection health check: OK")
                else:
                    logger.warning("💔 Connection health check: FAILED - attempting reconnection")
                    await self.connect(retry=True)
            except Exception as e:
                logger.warning(f"💔 Connection health check failed: {e} - attempting reconnection")
                try:
                    await self.connect(retry=True)
                except Exception as reconnect_error:
                    logger.error(f"❌ Auto-reconnection failed: {reconnect_error}")
                    await asyncio.sleep(60)  # Wait longer before next attempt


# ========================================
# Global Instance Management
# ========================================

# Global instance
_knowledge_db: Optional[KnowledgeDB] = None

def get_knowledge_db(schema: str = None) -> KnowledgeDB:
    """Get or create the global knowledge DB instance."""
    global _knowledge_db
    if _knowledge_db is None:
        try:
            _knowledge_db = KnowledgeDB(schema=schema)
            logger.info("📦 Knowledge DB instance created successfully")
        except Exception as e:
            logger.error(f"❌ Failed to create Knowledge DB instance: {e}")
            # Create a disabled instance for graceful degradation
            _knowledge_db = KnowledgeDB.__new__(KnowledgeDB)
            _knowledge_db._enabled = False
            _knowledge_db.pool = None
            _knowledge_db.schema = schema or "mcp_performance"
            _knowledge_db.config = None
    return _knowledge_db


async def cleanup_knowledge_db():
    """Cleanup function for application shutdown."""
    global _knowledge_db
    if _knowledge_db:
        logger.info("🧹 Cleaning up Knowledge DB connection...")
        await _knowledge_db.close()
        _knowledge_db = None
        logger.info("✅ Knowledge DB cleanup complete")
