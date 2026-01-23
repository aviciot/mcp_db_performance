"""
/validate Endpoint for Traefik forwardAuth
===========================================
This endpoint is called by Traefik to validate JWT tokens before forwarding requests.

Add this endpoint to your auth_service/main.py
"""

from fastapi import HTTPException, Header, Response
from typing import Optional
import jwt


@app.get("/validate")
async def validate(
    response: Response,
    authorization: Optional[str] = Header(None)
):
    """
    Validate JWT token (called by Traefik forwardAuth)

    Flow:
    1. Extract Bearer token from Authorization header
    2. Verify JWT signature and expiry
    3. Check if token is blacklisted
    4. Load user data from database (or cache)
    5. Return user info in response headers

    Headers returned:
        X-User-Id: User ID from auth_service.users
        X-User-Email: User email
        X-User-Role: User role (admin, developer, viewer)
        X-User-Permissions: Comma-separated permissions

    Returns:
        200 OK: Token valid (with user headers)
        401 Unauthorized: Token invalid, expired, or blacklisted

    Note:
        Traefik will read the response headers and forward them to the backend service.
        The backend can then use X-User-* headers for authorization decisions.
    """
    # Step 1: Extract Bearer token
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header"
        )

    token = extract_bearer_token(authorization)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format (expected: Bearer <token>)"
        )

    # Step 2: Validate token
    pool = await get_db()

    try:
        async with pool.acquire() as conn:
            # Get Redis client (optional, for caching)
            redis_client = await get_redis()

            # Validate token and load user data
            user_data = await validate_token_with_cache(token, conn, redis_client)

            # Step 3: Add user info to response headers
            response.headers["X-User-Id"] = str(user_data['user_id'])
            response.headers["X-User-Email"] = user_data['email']
            response.headers["X-User-Role"] = user_data['role']
            response.headers["X-User-Permissions"] = ",".join(user_data['permissions'])

            # Optional: Add username
            response.headers["X-User-Username"] = user_data['username']

            return {
                "valid": True,
                "user_id": user_data['user_id'],
                "username": user_data['username'],
                "role": user_data['role']
            }

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")

    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

    except ValueError as e:
        # Token blacklisted or user not found
        raise HTTPException(status_code=401, detail=str(e))

    except Exception as e:
        # Unexpected error
        print(f"❌ Validation error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# /refresh Endpoint (for token renewal)
# ============================================================================

from pydantic import BaseModel


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    expires_in: int


@app.post("/refresh", response_model=RefreshResponse)
async def refresh(request: RefreshRequest):
    """
    Refresh access token using refresh token

    Flow:
    1. Verify refresh token (signature, expiry)
    2. Check if refresh token is in user_sessions table
    3. Generate new access token
    4. (Optional) Rotate refresh token for security

    Returns:
        RefreshResponse: New access token

    Raises:
        401: Invalid or expired refresh token
    """
    pool = await get_db()

    try:
        # Step 1: Verify refresh token
        payload = verify_refresh_token(request.refresh_token)
        user_id = int(payload['sub'])

        async with pool.acquire() as conn:
            # Step 2: Check if refresh token is in user_sessions
            token_hash = hash_token(request.refresh_token)

            session = await conn.fetchrow("""
                SELECT user_id, expires_at
                FROM auth_service.user_sessions
                WHERE refresh_token_hash = $1
                AND expires_at > NOW()
            """, token_hash)

            if not session:
                raise HTTPException(
                    status_code=401,
                    detail="Refresh token not found or expired"
                )

            # Step 3: Load user data
            user = await conn.fetchrow("""
                SELECT
                    u.id,
                    u.username,
                    u.email,
                    u.role,
                    u.active,
                    r.permissions
                FROM auth_service.users u
                LEFT JOIN auth_service.roles r ON r.name = u.role
                WHERE u.id = $1
            """, user_id)

            if not user or not user['active']:
                raise HTTPException(status_code=401, detail="User not found or disabled")

            # Step 4: Generate new access token
            access_token = generate_access_token(
                user_id=user['id'],
                username=user['username'],
                email=user['email'],
                role=user['role'],
                permissions=user['permissions'] or []
            )

            # Optional: Rotate refresh token (security best practice)
            # new_refresh_token = generate_refresh_token(user_id)
            # await conn.execute("""
            #     UPDATE auth_service.user_sessions
            #     SET refresh_token_hash = $1, updated_at = NOW()
            #     WHERE refresh_token_hash = $2
            # """, hash_token(new_refresh_token), token_hash)

            return RefreshResponse(
                access_token=access_token,
                expires_in=ACCESS_TOKEN_EXPIRY_SECONDS
            )

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token has expired")

    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid refresh token: {str(e)}")

    except HTTPException:
        raise

    except Exception as e:
        print(f"❌ Refresh error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# /logout Endpoint (blacklist token)
# ============================================================================

@app.post("/logout")
async def logout(authorization: Optional[str] = Header(None)):
    """
    Logout user by blacklisting their access token

    Flow:
    1. Extract Bearer token from Authorization header
    2. Verify token (get expiry time)
    3. Add token to blacklisted_tokens table
    4. Delete refresh token from user_sessions
    5. Add to Redis blacklist cache

    Returns:
        200 OK: Token blacklisted successfully
        401 Unauthorized: Invalid token
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = extract_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")

    pool = await get_db()

    try:
        # Step 1: Verify token (to get expiry time)
        payload = verify_access_token(token)
        user_id = int(payload['sub'])
        expires_at_timestamp = payload['exp']

        async with pool.acquire() as conn:
            # Step 2: Blacklist the access token
            token_hash = hash_token(token)

            await conn.execute("""
                INSERT INTO auth_service.blacklisted_tokens (
                    token_hash,
                    user_id,
                    expires_at,
                    created_at
                )
                VALUES ($1, $2, to_timestamp($3), NOW())
                ON CONFLICT (token_hash) DO NOTHING
            """, token_hash, user_id, expires_at_timestamp)

            # Step 3: Delete all refresh tokens for this user (logout from all devices)
            await conn.execute("""
                DELETE FROM auth_service.user_sessions
                WHERE user_id = $1
            """, user_id)

            # Step 4: Add to Redis blacklist cache
            redis_client = await get_redis()
            if redis_client:
                await redis_client.sadd("blacklisted_tokens", token_hash)
                await redis_client.expire("blacklisted_tokens", 3600)  # 1 hour TTL

            return {
                "message": "Logged out successfully",
                "user_id": user_id
            }

    except jwt.InvalidTokenError as e:
        # Token already invalid - that's fine
        return {"message": "Token was already invalid"}

    except Exception as e:
        print(f"❌ Logout error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# Redis Client (Optional, for caching)
# ============================================================================

_redis_client = None


async def get_redis():
    """Get or create Redis client"""
    global _redis_client

    if _redis_client is None:
        try:
            import aioredis
            import os

            redis_host = os.getenv('REDIS_HOST', 'localhost')
            redis_port = int(os.getenv('REDIS_PORT', '6379'))

            _redis_client = await aioredis.create_redis_pool(
                f'redis://{redis_host}:{redis_port}',
                encoding='utf-8'
            )
            print("✅ Redis connected")

        except ImportError:
            print("⚠️  aioredis not installed, caching disabled")
            return None
        except Exception as e:
            print(f"⚠️  Redis connection failed: {e}")
            return None

    return _redis_client
