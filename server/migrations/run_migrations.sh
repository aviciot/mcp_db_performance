#!/bin/bash
# ============================================================================
# Migration Runner Script
# ============================================================================
# Automatically runs all SQL migrations in order
# Usage:
#   ./run_migrations.sh                    # Run on local PostgreSQL
#   ./run_migrations.sh docker             # Run on Docker container
#   ./run_migrations.sh docker omni_pg_db  # Run on specific container

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_NAME=${DB_NAME:-omni}
DB_USER=${DB_USER:-omni}
DB_PASSWORD=${DB_PASSWORD:-omni}
MIGRATIONS_DIR="$(dirname "$0")"
CONTAINER_NAME=${2:-omni_pg_db}

# Check if running in Docker mode
USE_DOCKER=false
if [ "$1" == "docker" ]; then
    USE_DOCKER=true
    echo -e "${BLUE}Running migrations in Docker mode${NC}"
    echo -e "${BLUE}Container: ${CONTAINER_NAME}${NC}"
else
    echo -e "${BLUE}Running migrations locally${NC}"
    echo -e "${BLUE}Host: ${DB_HOST}:${DB_PORT}${NC}"
fi

echo -e "${BLUE}Database: ${DB_NAME}${NC}"
echo -e "${BLUE}Schema: mcp_performance${NC}"
echo ""

# Function to execute SQL
execute_sql() {
    local sql_file=$1
    local filename=$(basename "$sql_file")

    echo -n -e "${YELLOW}Running migration: ${filename}${NC} ... "

    if [ "$USE_DOCKER" = true ]; then
        # Run in Docker container
        if docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" < "$sql_file" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Success${NC}"
            return 0
        else
            echo -e "${RED}✗ Failed${NC}"
            echo -e "${RED}Error running $filename${NC}"
            docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" < "$sql_file"
            return 1
        fi
    else
        # Run locally
        if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$sql_file" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Success${NC}"
            return 0
        else
            echo -e "${RED}✗ Failed${NC}"
            echo -e "${RED}Error running $filename${NC}"
            PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$sql_file"
            return 1
        fi
    fi
}

# Check if Docker container exists (if Docker mode)
if [ "$USE_DOCKER" = true ]; then
    if ! docker ps | grep -q "$CONTAINER_NAME"; then
        echo -e "${RED}Error: Docker container '$CONTAINER_NAME' is not running${NC}"
        echo ""
        echo "Available containers:"
        docker ps --format "table {{.Names}}\t{{.Status}}"
        exit 1
    fi
fi

# Check if psql is available (if local mode)
if [ "$USE_DOCKER" = false ]; then
    if ! command -v psql &> /dev/null; then
        echo -e "${RED}Error: psql command not found${NC}"
        echo "Please install PostgreSQL client or use Docker mode: ./run_migrations.sh docker"
        exit 1
    fi
fi

# Find all SQL migration files
migration_files=$(find "$MIGRATIONS_DIR" -maxdepth 1 -name "*.sql" -type f | sort)

if [ -z "$migration_files" ]; then
    echo -e "${YELLOW}No migration files found in $MIGRATIONS_DIR${NC}"
    exit 0
fi

# Count migrations
total=$(echo "$migration_files" | wc -l)
echo -e "${BLUE}Found $total migration(s) to run${NC}"
echo ""

# Run each migration
success_count=0
failed_count=0

for sql_file in $migration_files; do
    if execute_sql "$sql_file"; then
        ((success_count++))
    else
        ((failed_count++))
        echo ""
        echo -e "${RED}Migration failed. Stopping execution.${NC}"
        break
    fi
done

# Summary
echo ""
echo "========================================="
if [ $failed_count -eq 0 ]; then
    echo -e "${GREEN}✓ All migrations completed successfully!${NC}"
    echo -e "  ${GREEN}Success: $success_count${NC}"
else
    echo -e "${RED}✗ Migrations failed${NC}"
    echo -e "  ${GREEN}Success: $success_count${NC}"
    echo -e "  ${RED}Failed: $failed_count${NC}"
    exit 1
fi
echo "========================================="

# Verify tables were created
echo ""
echo -e "${BLUE}Verifying tables...${NC}"

if [ "$USE_DOCKER" = true ]; then
    docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -c "\dt mcp_performance.*" 2>/dev/null
else
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "\dt mcp_performance.*" 2>/dev/null
fi

echo ""
echo -e "${GREEN}Migrations complete!${NC}"
