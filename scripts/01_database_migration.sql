-- ============================================================================
-- Auth Service Integration - Database Migration
-- ============================================================================
-- Purpose: Add foreign key linkage from omni_dashboard.admin_users to auth_service.users
-- Risk: LOW (adds nullable column, non-breaking change)
-- Rollback: ALTER TABLE omni_dashboard.admin_users DROP COLUMN auth_user_id;
-- ============================================================================

-- Prerequisites check
DO $$
BEGIN
    -- Verify auth_service.users table exists
    IF NOT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_schema = 'auth_service' AND table_name = 'users'
    ) THEN
        RAISE EXCEPTION 'auth_service.users table does not exist! Please deploy auth_service first.';
    END IF;

    -- Verify omni_dashboard.admin_users table exists
    IF NOT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_schema = 'omni_dashboard' AND table_name = 'admin_users'
    ) THEN
        RAISE EXCEPTION 'omni_dashboard.admin_users table does not exist!';
    END IF;

    RAISE NOTICE '✅ Prerequisites check passed';
END $$;

-- ============================================================================
-- Step 1: Add auth_user_id column
-- ============================================================================

-- Check if column already exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM information_schema.columns
        WHERE table_schema = 'omni_dashboard'
        AND table_name = 'admin_users'
        AND column_name = 'auth_user_id'
    ) THEN
        -- Add the column
        ALTER TABLE omni_dashboard.admin_users
        ADD COLUMN auth_user_id INTEGER;

        RAISE NOTICE '✅ Added auth_user_id column to omni_dashboard.admin_users';
    ELSE
        RAISE NOTICE 'ℹ️  auth_user_id column already exists';
    END IF;
END $$;

-- ============================================================================
-- Step 2: Add foreign key constraint
-- ============================================================================

-- Check if constraint already exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM information_schema.table_constraints
        WHERE constraint_schema = 'omni_dashboard'
        AND table_name = 'admin_users'
        AND constraint_name = 'fk_admin_users_auth_user'
    ) THEN
        -- Add foreign key constraint
        ALTER TABLE omni_dashboard.admin_users
        ADD CONSTRAINT fk_admin_users_auth_user
        FOREIGN KEY (auth_user_id)
        REFERENCES auth_service.users(id)
        ON DELETE SET NULL;  -- If auth user deleted, set to NULL (not CASCADE)

        RAISE NOTICE '✅ Added foreign key constraint: fk_admin_users_auth_user';
    ELSE
        RAISE NOTICE 'ℹ️  Foreign key constraint already exists';
    END IF;
END $$;

-- ============================================================================
-- Step 3: Add index for performance
-- ============================================================================

-- Check if index already exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_indexes
        WHERE schemaname = 'omni_dashboard'
        AND tablename = 'admin_users'
        AND indexname = 'idx_admin_users_auth_user_id'
    ) THEN
        -- Create index
        CREATE INDEX idx_admin_users_auth_user_id
        ON omni_dashboard.admin_users(auth_user_id);

        RAISE NOTICE '✅ Created index: idx_admin_users_auth_user_id';
    ELSE
        RAISE NOTICE 'ℹ️  Index already exists';
    END IF;
END $$;

-- ============================================================================
-- Step 4: Verification
-- ============================================================================

-- Display current sync status
DO $$
DECLARE
    total_users INTEGER;
    linked_users INTEGER;
    unlinked_users INTEGER;
BEGIN
    SELECT
        COUNT(*) INTO total_users
    FROM omni_dashboard.admin_users;

    SELECT
        COUNT(*) INTO linked_users
    FROM omni_dashboard.admin_users
    WHERE auth_user_id IS NOT NULL;

    unlinked_users := total_users - linked_users;

    RAISE NOTICE '';
    RAISE NOTICE '======================================';
    RAISE NOTICE 'Migration Complete!';
    RAISE NOTICE '======================================';
    RAISE NOTICE 'Total admin users: %', total_users;
    RAISE NOTICE 'Linked to auth_service: %', linked_users;
    RAISE NOTICE 'Not yet linked: %', unlinked_users;
    RAISE NOTICE '';
    RAISE NOTICE 'Next step: Run scripts/02_sync_users.py';
    RAISE NOTICE '======================================';
END $$;

-- Display schema info
\d omni_dashboard.admin_users
