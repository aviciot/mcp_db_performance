# Auth Service Integration - Implementation Plan

> **Status**: Ready for Execution
> **Approach**: Hybrid Architecture (Separate Schemas + FK Linkage)
> **Estimated Time**: 1-2 hours
> **Rollback**: Fully reversible

---

## Executive Summary

We'll integrate auth_service with omni2-admin using a **hybrid approach** that:

✅ **Keeps both schemas separate** (auth_service + omni_dashboard)
✅ **Links via foreign key** (auth_user_id in omni_dashboard.admin_users)
✅ **Preserves all existing data** (zero data loss)
✅ **Uses JWT authentication** through Traefik forwardAuth
✅ **Syncs users lazily** at login time (no bulk migration needed)

**Architecture:**
```
┌─────────────────────┐         ┌──────────────────────┐
│  auth_service       │         │  omni_dashboard      │
│  (Authentication)   │         │  (Business Logic)    │
├─────────────────────┤         ├──────────────────────┤
│ • users             │◄────┐   │ • admin_users        │
│ • roles             │     │   │   - auth_user_id (FK)│
│ • user_sessions     │     └───┤ • mcp_configs        │
│ • blacklisted_tokens│         │ • usage_logs         │
│ • auth_audit        │         │ • teams              │
└─────────────────────┘         └──────────────────────┘
```

---

## Implementation Steps

### Phase 1: Database Migration (5 minutes)

**What we're doing:**
- Add `auth_user_id` column to `omni_dashboard.admin_users`
- Create foreign key constraint for referential integrity
- Add index for query performance

**Script:** `scripts/01_database_migration.sql`

**Risk:** LOW - Non-breaking change (adds nullable column)

**Rollback:**
```sql
ALTER TABLE omni_dashboard.admin_users DROP COLUMN auth_user_id;
```

---

### Phase 2: Sync Existing Users (10 minutes)

**What we're doing:**
- Create `auth_service.users` records for all existing `omni_dashboard.admin_users`
- Link them via `auth_user_id` foreign key
- One-time sync script (idempotent, safe to re-run)

**Script:** `scripts/02_sync_users.py`

**What it does:**
1. Reads all users from `omni_dashboard.admin_users` where `auth_user_id IS NULL`
2. Creates matching records in `auth_service.users`
3. Updates `admin_users.auth_user_id` with the new auth user ID
4. Logs all operations for audit trail

**Risk:** LOW - Read existing data, create new records, no deletions

**Verification:**
```sql
-- Check sync status
SELECT
    COUNT(*) as total_admin_users,
    COUNT(auth_user_id) as linked_users,
    COUNT(*) - COUNT(auth_user_id) as unlinked_users
FROM omni_dashboard.admin_users;
```

---

### Phase 3: Update auth_service Login (20 minutes)

**What we're doing:**
- Modify `/login` endpoint to authenticate against `omni_dashboard.admin_users`
- Auto-create/link `auth_service.users` records if missing (lazy sync)
- Generate JWT tokens (access + refresh)
- Store session in `auth_service.user_sessions`

**Files to modify:**
- `auth_service/main.py` (update `/login` endpoint)
- `auth_service/auth.py` (add JWT generation functions)

**Script:** `scripts/03_auth_service_updates/`

**Risk:** MEDIUM - Changes auth flow, but preserves backward compatibility

**Testing:**
```bash
# Test login
curl -X POST http://localhost:8001/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}'

# Should return:
# { "access_token": "eyJ...", "refresh_token": "eyJ...", "expires_in": 3600 }
```

---

### Phase 4: Configure Traefik forwardAuth (15 minutes)

**What we're doing:**
- Add `auth-service-validate` middleware (forwardAuth)
- Configure auth_service `/validate` endpoint
- Update omni2-hub router to use authentication
- Add user headers (X-User-Id, X-User-Role, etc.)

**Files to modify:**
- `mcp-gateway/config/traefik/dynamic/middlewares.yml`
- `mcp-gateway/config/traefik/dynamic/routers.yml`
- `mcp-gateway/config/traefik/dynamic/services.yml`

**Script:** `scripts/04_traefik_config/`

**Risk:** MEDIUM - Changes request flow, but easy to rollback

**Testing:**
```bash
# Get JWT token first
TOKEN=$(curl -X POST http://localhost:8001/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}' | jq -r '.access_token')

# Test authenticated request
curl -X GET http://localhost/omni2-mcp/health \
  -H "Authorization: Bearer $TOKEN"

# Should return 200 OK with omni2-hub response
```

---

### Phase 5: Verification & Testing (10 minutes)

**What we're doing:**
- Run comprehensive test suite
- Verify all flows work end-to-end
- Check database consistency
- Test error scenarios

**Script:** `scripts/05_verify_integration.py`

**Test Coverage:**
- ✅ Login with valid credentials
- ✅ Login with invalid credentials
- ✅ Token validation
- ✅ Token expiry
- ✅ Token refresh
- ✅ Token blacklisting (logout)
- ✅ Traefik forwardAuth flow
- ✅ User header propagation
- ✅ Database sync status

---

## File Structure

All scripts are ready to execute:

```
scripts/
├── 01_database_migration.sql          # Phase 1: Add FK column
├── 02_sync_users.py                    # Phase 2: Sync existing users
├── 03_auth_service_updates/
│   ├── main.py                         # Updated /login endpoint
│   ├── auth.py                         # JWT generation functions
│   └── README.md                       # Integration instructions
├── 04_traefik_config/
│   ├── middlewares.yml                 # forwardAuth middleware
│   ├── routers.yml                     # Updated routers
│   ├── services.yml                    # Auth service definition
│   └── README.md                       # Traefik setup guide
└── 05_verify_integration.py            # Phase 5: Test everything

```

---

## Execution Order

**IMPORTANT:** Follow this exact order:

1. ✅ **Backup databases** (omni + auth_service schemas)
2. ✅ **Run Phase 1** (database migration)
3. ✅ **Run Phase 2** (sync users)
4. ✅ **Run Phase 3** (update auth_service code)
5. ✅ **Test auth_service** locally (before Traefik)
6. ✅ **Run Phase 4** (configure Traefik)
7. ✅ **Run Phase 5** (verification tests)
8. ✅ **Monitor logs** for errors

---

## Rollback Plan

If something goes wrong, rollback in reverse order:

### Rollback Phase 4 (Traefik)
```bash
# Remove auth middleware from omni2-hub router
# Restart Traefik with old config
docker-compose restart traefik
```

### Rollback Phase 3 (auth_service)
```bash
# Revert auth_service code
git checkout HEAD~1 auth_service/
docker-compose restart auth_service
```

### Rollback Phase 2 (Sync)
```sql
-- Clear auth_user_id links (keeps auth_service.users intact)
UPDATE omni_dashboard.admin_users SET auth_user_id = NULL;
```

### Rollback Phase 1 (Database)
```sql
-- Remove FK column
ALTER TABLE omni_dashboard.admin_users DROP COLUMN auth_user_id;
```

---

## Environment Variables

Before running scripts, ensure these are set:

**auth_service/.env:**
```bash
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=omni
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-password

# JWT Configuration
JWT_SECRET=your-256-bit-secret-key-change-this-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRY_SECONDS=3600        # 1 hour
REFRESH_TOKEN_EXPIRY_SECONDS=604800     # 7 days

# Redis (for token blacklist cache)
REDIS_HOST=localhost
REDIS_PORT=6379

# API Configuration
API_HOST=0.0.0.0
API_PORT=8001
```

**CRITICAL:** Never commit `.env` files! Use `.env.example` templates.

---

## Success Criteria

After implementation, verify:

- [ ] All existing admin users can login
- [ ] JWT tokens are generated correctly
- [ ] `/validate` endpoint returns user info
- [ ] Traefik forwards authenticated requests
- [ ] User headers (X-User-Id, X-User-Role) are present
- [ ] Token refresh works
- [ ] Logout blacklists tokens
- [ ] Invalid tokens are rejected (401)
- [ ] omni_dashboard.admin_users.auth_user_id is populated
- [ ] No errors in auth_service logs
- [ ] No errors in Traefik logs

---

## Timeline

| Phase | Duration | Downtime |
|-------|----------|----------|
| Phase 1: Database Migration | 5 min | None |
| Phase 2: Sync Users | 10 min | None |
| Phase 3: Update auth_service | 20 min | ~2 min |
| Phase 4: Configure Traefik | 15 min | ~1 min |
| Phase 5: Verification | 10 min | None |
| **Total** | **60 min** | **~3 min** |

---

## Next Steps

1. Review this plan with your team
2. Backup databases (PostgreSQL dump)
3. Set environment variables in `auth_service/.env`
4. Run scripts in order (01 → 02 → 03 → 04 → 05)
5. Monitor logs for errors
6. Test end-to-end flows
7. Update frontend to use new auth flow (separate task)

---

## Questions or Issues?

If you encounter any problems during implementation:

1. Check logs: `docker-compose logs auth_service traefik`
2. Verify database state: Run queries in verification section
3. Test auth_service directly (bypass Traefik): `curl http://localhost:8001/login`
4. Rollback if needed (see Rollback Plan above)

---

**Ready to proceed?** Start with Phase 1: Database Migration

Run: `psql -U postgres -d omni -f scripts/01_database_migration.sql`
