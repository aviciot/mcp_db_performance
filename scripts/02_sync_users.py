#!/usr/bin/env python3
"""
Auth Service Integration - User Sync Script
============================================
Purpose: Sync existing omni_dashboard.admin_users to auth_service.users
Risk: LOW (creates new records, no deletions)
Idempotent: Safe to run multiple times (skips already synced users)

Usage:
    python scripts/02_sync_users.py

Environment Variables:
    POSTGRES_HOST - PostgreSQL host (default: localhost)
    POSTGRES_PORT - PostgreSQL port (default: 5432)
    POSTGRES_DB - Database name (default: omni)
    POSTGRES_USER - Database user (default: postgres)
    POSTGRES_PASSWORD - Database password (required)
"""

import asyncio
import asyncpg
import os
import sys
from datetime import datetime
from typing import Optional


# ============================================================================
# Configuration
# ============================================================================

DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', '5432')),
    'database': os.getenv('POSTGRES_DB', 'omni'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', ''),
}


# ============================================================================
# Helper Functions
# ============================================================================

def log(message: str, level: str = 'INFO'):
    """Pretty print log messages"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    icons = {
        'INFO': 'ℹ️ ',
        'SUCCESS': '✅',
        'ERROR': '❌',
        'WARNING': '⚠️ ',
        'PROGRESS': '🔄',
    }
    icon = icons.get(level, 'ℹ️ ')
    print(f"[{timestamp}] {icon} {message}")


async def verify_prerequisites(conn: asyncpg.Connection) -> bool:
    """Verify database schemas and tables exist"""
    log("Verifying prerequisites...", 'PROGRESS')

    # Check auth_service.users table
    auth_users_exists = await conn.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'auth_service' AND table_name = 'users'
        )
    """)

    if not auth_users_exists:
        log("auth_service.users table does not exist!", 'ERROR')
        log("Please deploy auth_service first", 'ERROR')
        return False

    # Check omni_dashboard.admin_users table
    admin_users_exists = await conn.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'omni_dashboard' AND table_name = 'admin_users'
        )
    """)

    if not admin_users_exists:
        log("omni_dashboard.admin_users table does not exist!", 'ERROR')
        return False

    # Check if auth_user_id column exists
    auth_user_id_exists = await conn.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_schema = 'omni_dashboard'
            AND table_name = 'admin_users'
            AND column_name = 'auth_user_id'
        )
    """)

    if not auth_user_id_exists:
        log("auth_user_id column missing in omni_dashboard.admin_users!", 'ERROR')
        log("Please run scripts/01_database_migration.sql first", 'ERROR')
        return False

    log("Prerequisites check passed", 'SUCCESS')
    return True


async def get_unlinked_users(conn: asyncpg.Connection) -> list:
    """Get all admin users that haven't been linked to auth_service yet"""
    users = await conn.fetch("""
        SELECT
            id,
            email,
            username,
            full_name,
            password_hash,
            role,
            is_active,
            created_at
        FROM omni_dashboard.admin_users
        WHERE auth_user_id IS NULL
        ORDER BY created_at ASC
    """)
    return users


async def check_existing_auth_user(
    conn: asyncpg.Connection,
    username: str,
    email: str
) -> Optional[int]:
    """Check if auth_service.users already has a user with this username/email"""
    result = await conn.fetchrow("""
        SELECT id FROM auth_service.users
        WHERE username = $1 OR email = $2
        LIMIT 1
    """, username, email)

    return result['id'] if result else None


async def create_auth_user(
    conn: asyncpg.Connection,
    admin_user: dict
) -> int:
    """Create new auth_service.users record"""
    auth_user_id = await conn.fetchval("""
        INSERT INTO auth_service.users (
            username,
            email,
            name,
            role,
            active,
            created_at,
            updated_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id
    """,
        admin_user['username'],
        admin_user['email'],
        admin_user['full_name'] or admin_user['username'],
        admin_user['role'],
        admin_user['is_active'],
        admin_user['created_at'],
        datetime.utcnow()
    )
    return auth_user_id


async def link_users(
    conn: asyncpg.Connection,
    admin_user_id: int,
    auth_user_id: int
):
    """Link omni_dashboard.admin_users to auth_service.users"""
    await conn.execute("""
        UPDATE omni_dashboard.admin_users
        SET auth_user_id = $1
        WHERE id = $2
    """, auth_user_id, admin_user_id)


async def sync_single_user(
    conn: asyncpg.Connection,
    admin_user: dict
) -> tuple[bool, str]:
    """
    Sync a single user from omni_dashboard to auth_service

    Returns:
        (success: bool, message: str)
    """
    try:
        # Check if auth user already exists
        existing_auth_id = await check_existing_auth_user(
            conn,
            admin_user['username'],
            admin_user['email']
        )

        if existing_auth_id:
            # Link existing auth user
            await link_users(conn, admin_user['id'], existing_auth_id)
            return (True, f"Linked to existing auth_user_id={existing_auth_id}")
        else:
            # Create new auth user
            auth_user_id = await create_auth_user(conn, admin_user)
            await link_users(conn, admin_user['id'], auth_user_id)
            return (True, f"Created new auth_user_id={auth_user_id}")

    except Exception as e:
        return (False, f"Error: {str(e)}")


async def print_summary(conn: asyncpg.Connection):
    """Print sync summary statistics"""
    stats = await conn.fetchrow("""
        SELECT
            COUNT(*) as total_users,
            COUNT(auth_user_id) as linked_users,
            COUNT(*) - COUNT(auth_user_id) as unlinked_users
        FROM omni_dashboard.admin_users
    """)

    print()
    print("=" * 60)
    print("SYNC SUMMARY")
    print("=" * 60)
    print(f"Total admin users:      {stats['total_users']}")
    print(f"Linked to auth_service: {stats['linked_users']}")
    print(f"Not yet linked:         {stats['unlinked_users']}")
    print("=" * 60)


# ============================================================================
# Main Sync Function
# ============================================================================

async def sync_users():
    """Main function to sync all users"""
    log("Starting user sync...", 'PROGRESS')
    log(f"Database: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")

    if not DB_CONFIG['password']:
        log("POSTGRES_PASSWORD environment variable not set!", 'ERROR')
        log("Example: export POSTGRES_PASSWORD='your-password'", 'INFO')
        sys.exit(1)

    # Connect to database
    try:
        conn = await asyncpg.connect(**DB_CONFIG)
        log("Database connection established", 'SUCCESS')
    except Exception as e:
        log(f"Failed to connect to database: {e}", 'ERROR')
        sys.exit(1)

    try:
        # Verify prerequisites
        if not await verify_prerequisites(conn):
            sys.exit(1)

        # Get unlinked users
        unlinked_users = await get_unlinked_users(conn)

        if not unlinked_users:
            log("All users are already synced!", 'SUCCESS')
            await print_summary(conn)
            return

        log(f"Found {len(unlinked_users)} users to sync", 'INFO')
        print()

        # Sync each user
        success_count = 0
        error_count = 0

        for i, admin_user in enumerate(unlinked_users, 1):
            username = admin_user['username']
            email = admin_user['email']

            # Use transaction for each user
            async with conn.transaction():
                success, message = await sync_single_user(conn, admin_user)

                if success:
                    log(f"[{i}/{len(unlinked_users)}] {username} ({email}): {message}", 'SUCCESS')
                    success_count += 1
                else:
                    log(f"[{i}/{len(unlinked_users)}] {username} ({email}): {message}", 'ERROR')
                    error_count += 1

        # Print final summary
        print()
        log(f"Sync complete: {success_count} success, {error_count} errors", 'SUCCESS' if error_count == 0 else 'WARNING')
        await print_summary(conn)

        if error_count == 0:
            print()
            log("Next step: Update auth_service code (scripts/03_auth_service_updates/)", 'INFO')

    except Exception as e:
        log(f"Unexpected error: {e}", 'ERROR')
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        await conn.close()
        log("Database connection closed", 'INFO')


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    print()
    print("=" * 60)
    print("Auth Service Integration - User Sync")
    print("=" * 60)
    print()

    try:
        asyncio.run(sync_users())
    except KeyboardInterrupt:
        print()
        log("Sync interrupted by user", 'WARNING')
        sys.exit(1)
