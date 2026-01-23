"""
Updated /login endpoint for auth_service
=========================================
Integrates with omni_dashboard.admin_users and auth_service.users

Replace your existing /login endpoint in auth_service/main.py with this implementation.
"""

from fastapi import HTTPException, Request
from pydantic import BaseModel
import bcrypt
from datetime import datetime
from typing import Optional

# ============================================================================
# Request/Response Models
# ============================================================================

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


# ============================================================================
# /login Endpoint
# ============================================================================

@app.post("/login", response_model=TokenPair)
async def login(request: LoginRequest, http_request: Request):
    """
    Login with username/password.

    Flow:
    1. Authenticate against omni_dashboard.admin_users (source of truth for passwords)
    2. Get or create auth_service.users record (lazy sync)
    3. Generate JWT tokens (access + refresh)
    4. Store session in auth_service.user_sessions
    5. Update last_login in both tables
    6. Audit login attempt

    Returns:
        TokenPair: Access token (1 hour) + Refresh token (7 days)

    Raises:
        400: Missing username or password
        401: Invalid credentials
        403: Account is disabled
    """
    if not request.username or not request.password:
        raise HTTPException(status_code=400, detail="username and password required")

    pool = await get_db()

    async with pool.acquire() as conn:
        # ====================================================================
        # Step 1: Authenticate against omni_dashboard.admin_users
        # ====================================================================

        admin_user = await conn.fetchrow("""
            SELECT
                id,
                username,
                email,
                password_hash,
                role,
                is_active,
                auth_user_id,
                full_name,
                created_at
            FROM omni_dashboard.admin_users
            WHERE username = $1
        """, request.username)

        if not admin_user:
            # Audit failed attempt (user not found)
            await audit_login(conn, request.username, None, "user_not_found", http_request)
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Verify password (bcrypt)
        password_valid = bcrypt.checkpw(
            request.password.encode('utf-8'),
            admin_user['password_hash'].encode('utf-8')
        )

        if not password_valid:
            # Audit failed attempt (invalid password)
            await audit_login(
                conn,
                request.username,
                admin_user['id'],
                "invalid_password",
                http_request
            )
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if not admin_user['is_active']:
            # Audit failed attempt (account disabled)
            await audit_login(
                conn,
                request.username,
                admin_user['id'],
                "account_disabled",
                http_request
            )
            raise HTTPException(status_code=403, detail="Account is disabled")

        # ====================================================================
        # Step 2: Get or create auth_service.users record (lazy sync)
        # ====================================================================

        auth_user_id = admin_user['auth_user_id']

        if not auth_user_id:
            # First login after migration - create auth_service.users record
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
                VALUES ($1, $2, $3, $4, true, $5, NOW())
                RETURNING id
            """,
                admin_user['username'],
                admin_user['email'],
                admin_user['full_name'] or admin_user['username'],
                admin_user['role'],
                admin_user['created_at']
            )

            # Link back to omni_dashboard.admin_users
            await conn.execute("""
                UPDATE omni_dashboard.admin_users
                SET auth_user_id = $1
                WHERE id = $2
            """, auth_user_id, admin_user['id'])

            print(f"✅ Created auth_service.users record: {admin_user['username']} → auth_user_id={auth_user_id}")

        # ====================================================================
        # Step 3: Load role permissions
        # ====================================================================

        role_permissions = await conn.fetchrow("""
            SELECT permissions, rate_limit, token_expiry_minutes
            FROM auth_service.roles
            WHERE name = $1
        """, admin_user['role'])

        permissions = role_permissions['permissions'] if role_permissions else []

        # ====================================================================
        # Step 4: Generate JWT tokens
        # ====================================================================

        access_token = generate_access_token(
            user_id=auth_user_id,
            username=admin_user['username'],
            email=admin_user['email'],
            role=admin_user['role'],
            permissions=permissions
        )

        refresh_token = generate_refresh_token(
            user_id=auth_user_id
        )

        # ====================================================================
        # Step 5: Store session in auth_service.user_sessions
        # ====================================================================

        user_agent = http_request.headers.get('User-Agent', 'Unknown')
        ip_address = http_request.client.host if http_request.client else 'Unknown'

        await conn.execute("""
            INSERT INTO auth_service.user_sessions (
                user_id,
                refresh_token_hash,
                device_info,
                ip_address,
                created_at,
                expires_at
            )
            VALUES ($1, $2, $3, $4, NOW(), NOW() + INTERVAL '7 days')
        """,
            auth_user_id,
            hash_token(refresh_token),
            user_agent,
            ip_address
        )

        # ====================================================================
        # Step 6: Update last_login in both tables
        # ====================================================================

        await conn.execute("""
            UPDATE omni_dashboard.admin_users
            SET last_login = NOW()
            WHERE id = $1
        """, admin_user['id'])

        await conn.execute("""
            UPDATE auth_service.users
            SET last_login_at = NOW()
            WHERE id = $1
        """, auth_user_id)

        # ====================================================================
        # Step 7: Audit successful login
        # ====================================================================

        await audit_login(
            conn,
            admin_user['username'],
            admin_user['id'],
            "success",
            http_request
        )

        # ====================================================================
        # Step 8: Return tokens
        # ====================================================================

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=ACCESS_TOKEN_EXPIRY_SECONDS
        )


# ============================================================================
# Helper: Audit Login Attempts
# ============================================================================

async def audit_login(
    conn,
    username: str,
    user_id: Optional[int],
    status: str,
    http_request: Request
):
    """
    Log login attempt to auth_service.auth_audit table

    Args:
        conn: Database connection
        username: Username attempted
        user_id: User ID (if user exists)
        status: success | user_not_found | invalid_password | account_disabled
        http_request: FastAPI request object
    """
    try:
        user_agent = http_request.headers.get('User-Agent', 'Unknown')
        ip_address = http_request.client.host if http_request.client else 'Unknown'

        await conn.execute("""
            INSERT INTO auth_service.auth_audit (
                username,
                user_id,
                action,
                status,
                ip_address,
                user_agent,
                created_at
            )
            VALUES ($1, $2, 'login', $3, $4, $5, NOW())
        """, username, user_id, status, ip_address, user_agent)
    except Exception as e:
        # Don't fail login if audit fails
        print(f"⚠️  Failed to audit login: {e}")


# ============================================================================
# Helper: Get Database Pool
# ============================================================================

async def get_db():
    """Get or create database connection pool"""
    global _db_pool

    if _db_pool is None:
        import asyncpg
        import os

        _db_pool = await asyncpg.create_pool(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=int(os.getenv('POSTGRES_PORT', '5432')),
            database=os.getenv('POSTGRES_DB', 'omni'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', ''),
            min_size=2,
            max_size=10
        )

    return _db_pool


# ============================================================================
# Configuration
# ============================================================================

import os

ACCESS_TOKEN_EXPIRY_SECONDS = int(os.getenv('ACCESS_TOKEN_EXPIRY_SECONDS', '3600'))
REFRESH_TOKEN_EXPIRY_SECONDS = int(os.getenv('REFRESH_TOKEN_EXPIRY_SECONDS', '604800'))

_db_pool = None  # Global database pool
