# Auth Service Code Updates

This directory contains the updated auth_service code to integrate with omni_dashboard.admin_users.

## Files

- `login_endpoint.py` - Updated /login endpoint implementation
- `jwt_utils.py` - JWT token generation and validation functions
- `.env.example` - Required environment variables

## Integration Steps

### 1. Update auth_service/main.py

Replace the existing `/login` endpoint with the implementation from `login_endpoint.py`.

**Location:** `auth_service/main.py`

**What changes:**
- `/login` now authenticates against `omni_dashboard.admin_users`
- Auto-creates/links `auth_service.users` records (lazy sync)
- Generates JWT tokens (access + refresh)
- Stores session in `auth_service.user_sessions`
- Updates `last_login` in both tables

### 2. Add JWT utilities

Copy functions from `jwt_utils.py` to your auth_service code (or create a new file).

**Functions provided:**
- `generate_access_token()` - Create short-lived access token (1 hour)
- `generate_refresh_token()` - Create long-lived refresh token (7 days)
- `verify_access_token()` - Validate and decode access token
- `verify_refresh_token()` - Validate and decode refresh token
- `hash_token()` - Hash tokens for database storage

### 3. Add /validate endpoint

This endpoint is called by Traefik forwardAuth to validate JWT tokens.

**What it does:**
1. Extracts Bearer token from Authorization header
2. Validates JWT signature and expiry
3. Checks if token is blacklisted
4. Loads user data from database (or cache)
5. Returns user info in response headers

**Response headers:**
- `X-User-Id` - User ID from auth_service.users
- `X-User-Email` - User email
- `X-User-Role` - User role (admin, developer, viewer)
- `X-User-Permissions` - Comma-separated permissions

### 4. Update environment variables

Copy `.env.example` to `auth_service/.env` and fill in values.

**Required variables:**
```bash
# JWT Configuration
JWT_SECRET=your-256-bit-secret-key-change-this-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRY_SECONDS=3600        # 1 hour
REFRESH_TOKEN_EXPIRY_SECONDS=604800     # 7 days

# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=omni
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-password

# Redis (optional, for caching)
REDIS_HOST=localhost
REDIS_PORT=6379
```

### 5. Install dependencies

```bash
cd auth_service
pip install pyjwt bcrypt asyncpg redis
```

### 6. Test locally

```bash
# Start auth_service
python main.py

# Test login
curl -X POST http://localhost:8001/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}'

# Should return:
# {
#   "access_token": "eyJhbGc...",
#   "refresh_token": "eyJhbGc...",
#   "token_type": "bearer",
#   "expires_in": 3600
# }

# Test validate
curl -X GET http://localhost:8001/validate \
  -H "Authorization: Bearer <access_token>"

# Should return 200 OK with X-User-* headers
```

## Security Notes

1. **NEVER commit .env files to git**
   - Add `.env` to `.gitignore`
   - Use `.env.example` for templates

2. **Use strong JWT_SECRET**
   - Generate: `openssl rand -hex 32`
   - Minimum 256 bits
   - Change in production!

3. **Enable HTTPS in production**
   - JWT tokens should only be sent over HTTPS
   - Configure Traefik with TLS certificates

4. **Token expiry**
   - Access tokens: Short-lived (1 hour)
   - Refresh tokens: Long-lived (7 days)
   - Implement token rotation for refresh tokens

5. **Rate limiting**
   - Add rate limiting to /login endpoint
   - Prevent brute force attacks
   - Use Redis for distributed rate limiting

## Troubleshooting

### Login fails with "Invalid credentials"
- Check that omni_dashboard.admin_users has the user
- Verify password_hash format (bcrypt)
- Check database connection

### Token validation fails
- Verify JWT_SECRET matches across services
- Check token expiry (not expired?)
- Check if token is blacklisted

### Headers not forwarded by Traefik
- Verify `authResponseHeaders` in Traefik config
- Check that auth_service /validate returns headers
- Use `curl -v` to inspect headers

## Next Steps

After updating auth_service code:

1. Test locally (see "Test locally" section above)
2. Deploy to development environment
3. Run verification tests: `python scripts/05_verify_integration.py`
4. Configure Traefik (scripts/04_traefik_config/)
5. Deploy to production
