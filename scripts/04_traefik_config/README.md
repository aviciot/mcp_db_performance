# Traefik Configuration for Auth Integration

This directory contains Traefik configuration updates to integrate forwardAuth with auth_service.

## Files

- `middlewares.yml` - forwardAuth middleware configuration
- `routers.yml` - Router configurations (omni2-hub + auth-service)
- `services.yml` - Service definitions
- `docker-compose.yml` - Updated docker-compose with auth_service

## Integration Steps

### 1. Backup existing Traefik config

```bash
cd mcp-gateway/config/traefik/dynamic
cp middlewares.yml middlewares.yml.backup
cp routers.yml routers.yml.backup
cp services.yml services.yml.backup
```

### 2. Update configuration files

Copy the contents from this directory to your Traefik dynamic config:

```bash
# Copy to mcp-gateway/config/traefik/dynamic/
cp scripts/04_traefik_config/middlewares.yml mcp-gateway/config/traefik/dynamic/
cp scripts/04_traefik_config/routers.yml mcp-gateway/config/traefik/dynamic/
cp scripts/04_traefik_config/services.yml mcp-gateway/config/traefik/dynamic/
```

**OR** manually merge the changes (see sections marked with `# AUTH INTEGRATION`)

### 3. Add auth_service to docker-compose

Update your `mcp-gateway/docker-compose.yml` to include auth_service:

```yaml
services:
  auth_service:
    build: ../auth_service
    container_name: auth_service
    environment:
      POSTGRES_HOST: postgres
      POSTGRES_PORT: 5432
      POSTGRES_DB: omni
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      JWT_SECRET: ${JWT_SECRET}
      REDIS_HOST: redis
      REDIS_PORT: 6379
    ports:
      - "8001:8001"
    networks:
      - traefik-network
    depends_on:
      - postgres
      - redis
```

### 4. Restart Traefik

```bash
cd mcp-gateway
docker-compose restart traefik

# Check logs
docker-compose logs -f traefik
```

### 5. Test the integration

```bash
# Test 1: Login to get JWT token
curl -X POST http://localhost/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}'

# Save the access_token from response

# Test 2: Try accessing omni2-mcp without token (should fail)
curl -v http://localhost/omni2-mcp/health

# Expected: 401 Unauthorized

# Test 3: Try with valid token (should succeed)
curl -v http://localhost/omni2-mcp/health \
  -H "Authorization: Bearer <access_token>"

# Expected: 200 OK (or 404 if endpoint doesn't exist)
```

## Configuration Overview

### forwardAuth Middleware

The `auth-service-validate` middleware tells Traefik to:
1. Intercept requests to protected routes
2. Forward the Authorization header to `auth_service /validate`
3. If validation succeeds (200 OK), forward the request with user headers
4. If validation fails (401), return 401 to client

**User headers forwarded:**
- `X-User-Id` - User ID from auth_service.users
- `X-User-Email` - User email
- `X-User-Role` - User role (admin, developer, viewer)
- `X-User-Permissions` - Comma-separated permissions
- `X-User-Username` - Username

### Router Configuration

**auth-service-router:**
- Path: `/auth/*`
- No authentication required (allows login)
- Strips `/auth` prefix before forwarding

**omni2-hub-router:**
- Path: `/omni2-mcp/*`
- **With authentication** (uses `mcp-authenticated` middleware chain)
- Forwards user headers to omni2-hub

### Middleware Chain

The `mcp-authenticated` middleware chain applies these middlewares in order:

1. **auth-service-validate** - Validate JWT token (forwardAuth)
2. **strip-mcp-prefix** - Strip `/omni2-mcp` prefix
3. **sse-headers** - Add SSE headers (for MCP streaming)
4. **rate-limit-default** - Apply rate limiting

## Troubleshooting

### 401 Unauthorized when using valid token

**Check:**
1. Is auth_service running? `docker-compose ps auth_service`
2. Can Traefik reach auth_service? `docker-compose logs traefik`
3. Is JWT_SECRET the same in auth_service and Traefik? (Check .env files)
4. Is the token expired? (Check `exp` claim in JWT)

**Debug:**
```bash
# Test auth_service directly (bypass Traefik)
curl -X GET http://localhost:8001/validate \
  -H "Authorization: Bearer <token>"

# Should return 200 OK with X-User-* headers
```

### Headers not forwarded to backend

**Check:**
1. Verify `authResponseHeaders` in middlewares.yml includes all required headers
2. Check backend service logs - are headers present?
3. Use `curl -v` to inspect response headers from /validate

**Fix:**
```yaml
# In middlewares.yml
authResponseHeaders:
  - "X-User-Id"
  - "X-User-Email"
  - "X-User-Role"
  - "X-User-Permissions"
  - "X-User-Username"  # Add any missing headers
```

### SSE streaming broken

**Check:**
1. Is `X-Accel-Buffering: no` header present?
2. Is proxy buffering disabled in Traefik?

**Fix:**
```yaml
# In middlewares.yml
sse-headers:
  headers:
    customResponseHeaders:
      Cache-Control: "no-cache"
      Connection: "keep-alive"
      X-Accel-Buffering: "no"
```

### Rate limiting too aggressive

**Adjust:**
```yaml
# In middlewares.yml
rate-limit-default:
  rateLimit:
    average: 100  # Increase from 10 to 100 req/sec
    burst: 200    # Increase from 20 to 200
```

## Rollback

If something goes wrong, rollback to backup configs:

```bash
cd mcp-gateway/config/traefik/dynamic
cp middlewares.yml.backup middlewares.yml
cp routers.yml.backup routers.yml
cp services.yml.backup services.yml

# Restart Traefik
docker-compose restart traefik
```

## Next Steps

After configuring Traefik:

1. Test all flows (login, validate, refresh, logout)
2. Run verification script: `python scripts/05_verify_integration.py`
3. Update omni2-admin frontend to use new auth flow
4. Monitor logs for errors
5. Deploy to production
