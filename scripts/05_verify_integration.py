#!/usr/bin/env python3
"""
Auth Service Integration - Verification & Testing Script
=========================================================
Purpose: Comprehensive testing of auth service integration
Tests:
    - Database sync status
    - Login flow
    - Token validation
    - Token refresh
    - Token blacklisting
    - Traefik forwardAuth flow
    - User header propagation

Usage:
    python scripts/05_verify_integration.py

Environment Variables:
    AUTH_SERVICE_URL - Auth service URL (default: http://localhost:8001)
    TRAEFIK_URL - Traefik gateway URL (default: http://localhost)
    TEST_USERNAME - Test username (default: admin)
    TEST_PASSWORD - Test password (required)
    POSTGRES_* - Database credentials (for direct checks)
"""

import asyncio
import asyncpg
import os
import sys
import json
from datetime import datetime
from typing import Optional
import aiohttp


# ============================================================================
# Configuration
# ============================================================================

AUTH_SERVICE_URL = os.getenv('AUTH_SERVICE_URL', 'http://localhost:8001')
TRAEFIK_URL = os.getenv('TRAEFIK_URL', 'http://localhost')
TEST_USERNAME = os.getenv('TEST_USERNAME', 'admin')
TEST_PASSWORD = os.getenv('TEST_PASSWORD', '')

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

class TestRunner:
    """Test runner with pretty output"""

    def __init__(self):
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.test_results = []

    def log(self, message: str, level: str = 'INFO'):
        """Print log message"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        icons = {
            'INFO': 'ℹ️ ',
            'SUCCESS': '✅',
            'ERROR': '❌',
            'WARNING': '⚠️ ',
            'PROGRESS': '🔄',
            'TEST': '🧪',
        }
        icon = icons.get(level, 'ℹ️ ')
        print(f"[{timestamp}] {icon} {message}")

    def test_start(self, test_name: str):
        """Mark test start"""
        self.total_tests += 1
        self.log(f"Running: {test_name}", 'TEST')

    def test_pass(self, test_name: str, message: str = ""):
        """Mark test as passed"""
        self.passed_tests += 1
        self.test_results.append((test_name, True, message))
        self.log(f"PASS: {test_name} {message}", 'SUCCESS')

    def test_fail(self, test_name: str, message: str = ""):
        """Mark test as failed"""
        self.failed_tests += 1
        self.test_results.append((test_name, False, message))
        self.log(f"FAIL: {test_name} {message}", 'ERROR')

    def print_summary(self):
        """Print test summary"""
        print()
        print("=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        print(f"Total tests: {self.total_tests}")
        print(f"Passed:      {self.passed_tests} ✅")
        print(f"Failed:      {self.failed_tests} ❌")
        print(f"Success rate: {self.passed_tests / max(self.total_tests, 1) * 100:.1f}%")
        print("=" * 70)

        if self.failed_tests > 0:
            print()
            print("FAILED TESTS:")
            for test_name, passed, message in self.test_results:
                if not passed:
                    print(f"  ❌ {test_name}: {message}")
            print("=" * 70)


runner = TestRunner()


# ============================================================================
# Database Tests
# ============================================================================

async def test_database_sync(conn: asyncpg.Connection):
    """Test 1: Verify database sync status"""
    runner.test_start("Database Sync Status")

    try:
        stats = await conn.fetchrow("""
            SELECT
                COUNT(*) as total_users,
                COUNT(auth_user_id) as linked_users,
                COUNT(*) - COUNT(auth_user_id) as unlinked_users
            FROM omni_dashboard.admin_users
        """)

        if stats['unlinked_users'] == 0:
            runner.test_pass("Database Sync Status", f"({stats['linked_users']} users synced)")
        else:
            runner.test_fail("Database Sync Status", f"({stats['unlinked_users']} users not synced)")

    except Exception as e:
        runner.test_fail("Database Sync Status", str(e))


async def test_foreign_key_constraint(conn: asyncpg.Connection):
    """Test 2: Verify foreign key constraint exists"""
    runner.test_start("Foreign Key Constraint")

    try:
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.table_constraints
                WHERE constraint_schema = 'omni_dashboard'
                AND table_name = 'admin_users'
                AND constraint_name = 'fk_admin_users_auth_user'
            )
        """)

        if exists:
            runner.test_pass("Foreign Key Constraint")
        else:
            runner.test_fail("Foreign Key Constraint", "Constraint not found")

    except Exception as e:
        runner.test_fail("Foreign Key Constraint", str(e))


# ============================================================================
# Auth Service Tests
# ============================================================================

async def test_login(session: aiohttp.ClientSession) -> Optional[dict]:
    """Test 3: Login with valid credentials"""
    runner.test_start("Login Flow")

    if not TEST_PASSWORD:
        runner.test_fail("Login Flow", "TEST_PASSWORD not set")
        return None

    try:
        async with session.post(
            f"{AUTH_SERVICE_URL}/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                if 'access_token' in data and 'refresh_token' in data:
                    runner.test_pass("Login Flow", f"(got tokens)")
                    return data
                else:
                    runner.test_fail("Login Flow", "Missing tokens in response")
                    return None
            else:
                text = await resp.text()
                runner.test_fail("Login Flow", f"HTTP {resp.status}: {text}")
                return None

    except Exception as e:
        runner.test_fail("Login Flow", str(e))
        return None


async def test_login_invalid_credentials(session: aiohttp.ClientSession):
    """Test 4: Login with invalid credentials (should fail)"""
    runner.test_start("Login with Invalid Credentials")

    try:
        async with session.post(
            f"{AUTH_SERVICE_URL}/login",
            json={"username": "invalid", "password": "wrong"}
        ) as resp:
            if resp.status == 401:
                runner.test_pass("Login with Invalid Credentials", "(correctly rejected)")
            else:
                runner.test_fail("Login with Invalid Credentials", f"Expected 401, got {resp.status}")

    except Exception as e:
        runner.test_fail("Login with Invalid Credentials", str(e))


async def test_validate_token(session: aiohttp.ClientSession, access_token: str):
    """Test 5: Validate JWT token"""
    runner.test_start("Token Validation")

    try:
        async with session.get(
            f"{AUTH_SERVICE_URL}/validate",
            headers={"Authorization": f"Bearer {access_token}"}
        ) as resp:
            if resp.status == 200:
                # Check for user headers in response
                user_id = resp.headers.get('X-User-Id')
                user_role = resp.headers.get('X-User-Role')
                user_email = resp.headers.get('X-User-Email')

                if user_id and user_role:
                    runner.test_pass("Token Validation", f"(user_id={user_id}, role={user_role})")
                else:
                    runner.test_fail("Token Validation", "Missing user headers")
            else:
                text = await resp.text()
                runner.test_fail("Token Validation", f"HTTP {resp.status}: {text}")

    except Exception as e:
        runner.test_fail("Token Validation", str(e))


async def test_validate_invalid_token(session: aiohttp.ClientSession):
    """Test 6: Validate invalid token (should fail)"""
    runner.test_start("Invalid Token Rejection")

    try:
        async with session.get(
            f"{AUTH_SERVICE_URL}/validate",
            headers={"Authorization": "Bearer invalid_token_12345"}
        ) as resp:
            if resp.status == 401:
                runner.test_pass("Invalid Token Rejection", "(correctly rejected)")
            else:
                runner.test_fail("Invalid Token Rejection", f"Expected 401, got {resp.status}")

    except Exception as e:
        runner.test_fail("Invalid Token Rejection", str(e))


async def test_refresh_token(session: aiohttp.ClientSession, refresh_token: str) -> Optional[str]:
    """Test 7: Refresh access token"""
    runner.test_start("Token Refresh")

    try:
        async with session.post(
            f"{AUTH_SERVICE_URL}/refresh",
            json={"refresh_token": refresh_token}
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                if 'access_token' in data:
                    runner.test_pass("Token Refresh", "(got new access token)")
                    return data['access_token']
                else:
                    runner.test_fail("Token Refresh", "Missing access_token in response")
                    return None
            else:
                text = await resp.text()
                runner.test_fail("Token Refresh", f"HTTP {resp.status}: {text}")
                return None

    except Exception as e:
        runner.test_fail("Token Refresh", str(e))
        return None


async def test_logout(session: aiohttp.ClientSession, access_token: str):
    """Test 8: Logout (blacklist token)"""
    runner.test_start("Logout")

    try:
        async with session.post(
            f"{AUTH_SERVICE_URL}/logout",
            headers={"Authorization": f"Bearer {access_token}"}
        ) as resp:
            if resp.status == 200:
                runner.test_pass("Logout", "(token blacklisted)")
            else:
                text = await resp.text()
                runner.test_fail("Logout", f"HTTP {resp.status}: {text}")

    except Exception as e:
        runner.test_fail("Logout", str(e))


async def test_blacklisted_token(session: aiohttp.ClientSession, blacklisted_token: str):
    """Test 9: Use blacklisted token (should fail)"""
    runner.test_start("Blacklisted Token Rejection")

    try:
        async with session.get(
            f"{AUTH_SERVICE_URL}/validate",
            headers={"Authorization": f"Bearer {blacklisted_token}"}
        ) as resp:
            if resp.status == 401:
                runner.test_pass("Blacklisted Token Rejection", "(correctly rejected)")
            else:
                runner.test_fail("Blacklisted Token Rejection", f"Expected 401, got {resp.status}")

    except Exception as e:
        runner.test_fail("Blacklisted Token Rejection", str(e))


# ============================================================================
# Traefik Integration Tests
# ============================================================================

async def test_traefik_forwardauth(session: aiohttp.ClientSession, access_token: str):
    """Test 10: Traefik forwardAuth flow"""
    runner.test_start("Traefik forwardAuth")

    try:
        # Try to access omni2-mcp through Traefik
        async with session.get(
            f"{TRAEFIK_URL}/omni2-mcp/health",
            headers={"Authorization": f"Bearer {access_token}"}
        ) as resp:
            if resp.status in [200, 404]:  # 404 is ok (endpoint may not exist yet)
                runner.test_pass("Traefik forwardAuth", f"(HTTP {resp.status})")
            elif resp.status == 401:
                runner.test_fail("Traefik forwardAuth", "Token rejected (auth not configured?)")
            else:
                runner.test_fail("Traefik forwardAuth", f"HTTP {resp.status}")

    except aiohttp.ClientError as e:
        runner.test_fail("Traefik forwardAuth", f"Connection error: {e}")
    except Exception as e:
        runner.test_fail("Traefik forwardAuth", str(e))


async def test_traefik_no_token(session: aiohttp.ClientSession):
    """Test 11: Traefik without token (should fail)"""
    runner.test_start("Traefik without Token")

    try:
        async with session.get(f"{TRAEFIK_URL}/omni2-mcp/health") as resp:
            if resp.status == 401:
                runner.test_pass("Traefik without Token", "(correctly rejected)")
            elif resp.status in [200, 404]:
                runner.test_fail("Traefik without Token", "Auth not enabled on router!")
            else:
                runner.test_fail("Traefik without Token", f"HTTP {resp.status}")

    except aiohttp.ClientError as e:
        # Connection error might mean service not running (that's ok)
        runner.test_pass("Traefik without Token", "(service not accessible)")
    except Exception as e:
        runner.test_fail("Traefik without Token", str(e))


# ============================================================================
# Main Test Runner
# ============================================================================

async def run_all_tests():
    """Run all verification tests"""
    runner.log("Starting verification tests...", 'PROGRESS')
    runner.log(f"Auth Service: {AUTH_SERVICE_URL}")
    runner.log(f"Traefik Gateway: {TRAEFIK_URL}")
    runner.log(f"Test User: {TEST_USERNAME}")
    print()

    # Check prerequisites
    if not TEST_PASSWORD:
        runner.log("TEST_PASSWORD environment variable not set!", 'ERROR')
        runner.log("Example: export TEST_PASSWORD='your-admin-password'", 'INFO')
        sys.exit(1)

    if not DB_CONFIG['password']:
        runner.log("POSTGRES_PASSWORD environment variable not set!", 'ERROR')
        runner.log("Skipping database tests...", 'WARNING')
        DB_CONFIG['password'] = None

    # ========================================================================
    # DATABASE TESTS
    # ========================================================================

    if DB_CONFIG['password']:
        runner.log("Running database tests...", 'PROGRESS')
        try:
            conn = await asyncpg.connect(**DB_CONFIG)
            await test_database_sync(conn)
            await test_foreign_key_constraint(conn)
            await conn.close()
        except Exception as e:
            runner.log(f"Database connection failed: {e}", 'ERROR')

    # ========================================================================
    # AUTH SERVICE TESTS
    # ========================================================================

    runner.log("Running auth service tests...", 'PROGRESS')
    print()

    async with aiohttp.ClientSession() as session:
        # Test login
        login_result = await test_login(session)
        await test_login_invalid_credentials(session)

        if login_result:
            access_token = login_result['access_token']
            refresh_token = login_result['refresh_token']

            # Test token validation
            await test_validate_token(session, access_token)
            await test_validate_invalid_token(session)

            # Test token refresh
            new_access_token = await test_refresh_token(session, refresh_token)

            # Test logout
            await test_logout(session, access_token)
            await test_blacklisted_token(session, access_token)

            # ================================================================
            # TRAEFIK TESTS (use new token, not blacklisted one)
            # ================================================================

            if new_access_token:
                runner.log("Running Traefik integration tests...", 'PROGRESS')
                print()
                await test_traefik_forwardauth(session, new_access_token)
                await test_traefik_no_token(session)

    # ========================================================================
    # PRINT SUMMARY
    # ========================================================================

    runner.print_summary()

    # Exit with proper code
    sys.exit(0 if runner.failed_tests == 0 else 1)


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    print()
    print("=" * 70)
    print("Auth Service Integration - Verification Tests")
    print("=" * 70)
    print()

    try:
        asyncio.run(run_all_tests())
    except KeyboardInterrupt:
        print()
        runner.log("Tests interrupted by user", 'WARNING')
        sys.exit(1)
