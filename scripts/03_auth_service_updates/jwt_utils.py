"""
JWT Token Generation and Validation Utilities
==============================================
Add these functions to your auth_service code.

Dependencies:
    pip install pyjwt
"""

import jwt
import os
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional


# ============================================================================
# Configuration
# ============================================================================

JWT_SECRET = os.getenv('JWT_SECRET', 'your-super-secret-jwt-key-256-bit-change-this')
JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
ACCESS_TOKEN_EXPIRY_SECONDS = int(os.getenv('ACCESS_TOKEN_EXPIRY_SECONDS', '3600'))  # 1 hour
REFRESH_TOKEN_EXPIRY_SECONDS = int(os.getenv('REFRESH_TOKEN_EXPIRY_SECONDS', '604800'))  # 7 days


# CRITICAL: Validate JWT_SECRET in production
if JWT_SECRET == 'your-super-secret-jwt-key-256-bit-change-this':
    raise ValueError(
        "CRITICAL: Change JWT_SECRET in production! "
        "Generate with: openssl rand -hex 32"
    )


# ============================================================================
# Token Generation
# ============================================================================

def generate_access_token(
    user_id: int,
    username: str,
    email: str,
    role: str,
    permissions: List[str]
) -> str:
    """
    Generate short-lived access token (JWT)

    Args:
        user_id: User ID from auth_service.users
        username: Username
        email: User email
        role: User role (admin, developer, viewer)
        permissions: List of permissions (e.g., ["mcp:read", "mcp:write"])

    Returns:
        JWT access token (valid for 1 hour)
    """
    now = datetime.utcnow()
    expiry = now + timedelta(seconds=ACCESS_TOKEN_EXPIRY_SECONDS)

    payload = {
        # Standard JWT claims
        "sub": str(user_id),  # Subject (user ID)
        "iat": int(now.timestamp()),  # Issued at
        "exp": int(expiry.timestamp()),  # Expiry
        "jti": hashlib.sha256(f"{user_id}{now.timestamp()}".encode()).hexdigest()[:16],  # JWT ID

        # Custom claims
        "username": username,
        "email": email,
        "role": role,
        "permissions": permissions,
    }

    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token


def generate_refresh_token(user_id: int) -> str:
    """
    Generate long-lived refresh token (JWT)

    Args:
        user_id: User ID from auth_service.users

    Returns:
        JWT refresh token (valid for 7 days)
    """
    now = datetime.utcnow()
    expiry = now + timedelta(seconds=REFRESH_TOKEN_EXPIRY_SECONDS)

    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(expiry.timestamp()),
        "type": "refresh",  # Identify as refresh token
    }

    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token


# ============================================================================
# Token Validation
# ============================================================================

def verify_access_token(token: str) -> Dict:
    """
    Verify and decode access token

    Args:
        token: JWT access token

    Returns:
        Decoded payload (dict)

    Raises:
        jwt.ExpiredSignatureError: Token expired
        jwt.InvalidTokenError: Invalid token
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

        # Verify it's not a refresh token
        if payload.get('type') == 'refresh':
            raise jwt.InvalidTokenError("Cannot use refresh token as access token")

        return payload

    except jwt.ExpiredSignatureError:
        raise jwt.ExpiredSignatureError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise jwt.InvalidTokenError(f"Invalid token: {str(e)}")


def verify_refresh_token(token: str) -> Dict:
    """
    Verify and decode refresh token

    Args:
        token: JWT refresh token

    Returns:
        Decoded payload (dict)

    Raises:
        jwt.ExpiredSignatureError: Token expired
        jwt.InvalidTokenError: Invalid token
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

        # Verify it's a refresh token
        if payload.get('type') != 'refresh':
            raise jwt.InvalidTokenError("Not a refresh token")

        return payload

    except jwt.ExpiredSignatureError:
        raise jwt.ExpiredSignatureError("Refresh token has expired")
    except jwt.InvalidTokenError as e:
        raise jwt.InvalidTokenError(f"Invalid refresh token: {str(e)}")


# ============================================================================
# Token Utilities
# ============================================================================

def hash_token(token: str) -> str:
    """
    Hash token for database storage

    Args:
        token: JWT token

    Returns:
        SHA-256 hash of token
    """
    return hashlib.sha256(token.encode()).hexdigest()


def extract_bearer_token(authorization_header: Optional[str]) -> Optional[str]:
    """
    Extract JWT token from Authorization header

    Args:
        authorization_header: HTTP Authorization header value

    Returns:
        JWT token (without "Bearer " prefix) or None

    Example:
        >>> extract_bearer_token("Bearer eyJhbGc...")
        "eyJhbGc..."
    """
    if not authorization_header:
        return None

    if not authorization_header.startswith("Bearer "):
        return None

    return authorization_header[7:]  # Remove "Bearer " prefix


# ============================================================================
# Token Validation for /validate Endpoint
# ============================================================================

async def validate_token_with_cache(
    token: str,
    conn,  # Database connection
    redis_client=None  # Optional Redis client for caching
) -> Dict:
    """
    Validate JWT token and load user data (with optional caching)

    Args:
        token: JWT access token
        conn: Database connection
        redis_client: Optional Redis client for caching

    Returns:
        User data dict with keys: user_id, username, email, role, permissions

    Raises:
        jwt.ExpiredSignatureError: Token expired
        jwt.InvalidTokenError: Invalid token
        ValueError: Token blacklisted or user not found
    """
    # Step 1: Verify JWT signature and expiry
    payload = verify_access_token(token)
    user_id = int(payload['sub'])

    # Step 2: Check if token is blacklisted (Redis cache first)
    token_hash = hash_token(token)

    if redis_client:
        # Fast check: Is token in Redis blacklist?
        is_blacklisted = await redis_client.sismember("blacklisted_tokens", token_hash)
        if is_blacklisted:
            raise ValueError("Token has been revoked")

    # Fallback: Check database
    is_blacklisted_db = await conn.fetchval("""
        SELECT EXISTS (
            SELECT 1 FROM auth_service.blacklisted_tokens
            WHERE token_hash = $1 AND expires_at > NOW()
        )
    """, token_hash)

    if is_blacklisted_db:
        # Add to Redis cache for faster future checks
        if redis_client:
            await redis_client.sadd("blacklisted_tokens", token_hash)
            await redis_client.expire("blacklisted_tokens", 3600)  # 1 hour TTL
        raise ValueError("Token has been revoked")

    # Step 3: Load user data (with caching)
    user_cache_key = f"user:{user_id}"

    if redis_client:
        # Try to get from cache
        import json
        cached_user = await redis_client.get(user_cache_key)
        if cached_user:
            return json.loads(cached_user)

    # Load from database
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

    if not user:
        raise ValueError("User not found")

    if not user['active']:
        raise ValueError("User account is disabled")

    user_data = {
        "user_id": user['id'],
        "username": user['username'],
        "email": user['email'],
        "role": user['role'],
        "permissions": user['permissions'] or [],
    }

    # Cache for 5 minutes
    if redis_client:
        import json
        await redis_client.setex(
            user_cache_key,
            300,  # 5 minutes
            json.dumps(user_data)
        )

    return user_data


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example: Generate tokens
    access_token = generate_access_token(
        user_id=1,
        username="john.doe",
        email="john@example.com",
        role="developer",
        permissions=["mcp:read", "mcp:write", "omni2:read"]
    )

    refresh_token = generate_refresh_token(user_id=1)

    print("Access Token:")
    print(access_token)
    print()

    print("Refresh Token:")
    print(refresh_token)
    print()

    # Example: Verify tokens
    try:
        payload = verify_access_token(access_token)
        print("Access Token Payload:")
        print(payload)
    except jwt.InvalidTokenError as e:
        print(f"Invalid token: {e}")
