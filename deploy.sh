#!/bin/bash

###############################################################################
# MCP Database Performance - Deployment Script
###############################################################################
# This script automates the deployment of the MCP Database Performance system
# including PostgreSQL cache database and MCP server.
#
# Usage: ./deploy.sh [--rebuild] [--skip-pg] [--help]
#
# Options:
#   --rebuild    Force rebuild of Docker images
#   --skip-pg    Skip PostgreSQL cache deployment
#   --help       Show this help message
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PG_DIR="$(dirname "$SCRIPT_DIR")/pg_mcp"
REBUILD=false
SKIP_PG=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --rebuild)
            REBUILD=true
            shift
            ;;
        --skip-pg)
            SKIP_PG=true
            shift
            ;;
        --help)
            grep "^#" "$0" | grep -v "#!/bin/bash" | sed 's/^# //'
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

###############################################################################
# Helper Functions
###############################################################################

print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
    print_success "Docker is running"
}

# Check if Docker Compose is available
check_docker_compose() {
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null 2>&1; then
        print_error "Docker Compose is not installed"
        exit 1
    fi
    print_success "Docker Compose is available"
}

# Create Docker network if it doesn't exist
create_network() {
    local NETWORK_NAME=$1
    if ! docker network inspect "$NETWORK_NAME" > /dev/null 2>&1; then
        print_info "Creating Docker network: $NETWORK_NAME"
        docker network create "$NETWORK_NAME"
        print_success "Network '$NETWORK_NAME' created"
    else
        print_success "Network '$NETWORK_NAME' already exists"
    fi
}

# Deploy PostgreSQL cache database
deploy_postgresql() {
    if [ "$SKIP_PG" = true ]; then
        print_warning "Skipping PostgreSQL deployment (--skip-pg flag)"
        return
    fi

    print_header "Deploying PostgreSQL Cache Database"

    if [ ! -d "$PG_DIR" ]; then
        print_error "PostgreSQL directory not found: $PG_DIR"
        exit 1
    fi

    cd "$PG_DIR"

    if [ "$REBUILD" = true ]; then
        print_info "Rebuilding PostgreSQL image..."
        docker-compose build --no-cache
    fi

    print_info "Starting PostgreSQL container..."
    docker-compose up -d

    # Wait for PostgreSQL to be ready
    print_info "Waiting for PostgreSQL to be ready..."
    for i in {1..30}; do
        if docker exec omni_pg_db pg_isready -U omni > /dev/null 2>&1; then
            print_success "PostgreSQL is ready"
            break
        fi
        if [ $i -eq 30 ]; then
            print_error "PostgreSQL failed to start within 30 seconds"
            docker logs omni_pg_db --tail 50
            exit 1
        fi
        sleep 1
    done

    print_success "PostgreSQL deployed successfully"
}

# Deploy MCP Server
deploy_mcp_server() {
    print_header "Deploying MCP Server"

    cd "$SCRIPT_DIR"

    # Check if .env file exists
    if [ ! -f ".env" ]; then
        print_warning ".env file not found. Creating from template..."
        if [ -f ".env.template" ]; then
            cp .env.template .env
            print_info "Please edit .env file with your database credentials"
        else
            print_error ".env.template not found"
            exit 1
        fi
    fi

    # Check if settings.yaml exists
    if [ ! -f "server/config/settings.yaml" ]; then
        print_warning "settings.yaml not found. Creating from template..."
        if [ -f "server/config/settings.template.yaml" ]; then
            cp server/config/settings.template.yaml server/config/settings.yaml
            print_info "Please edit server/config/settings.yaml with your database credentials"
        else
            print_error "settings.template.yaml not found"
            exit 1
        fi
    fi

    if [ "$REBUILD" = true ]; then
        print_info "Rebuilding MCP server image..."
        docker-compose build --no-cache
    fi

    print_info "Starting MCP server container..."
    docker-compose up -d

    # Wait for MCP server to be ready
    print_info "Waiting for MCP server to be ready..."
    for i in {1..30}; do
        if docker exec mcp_db_performance curl -sf http://localhost:8300/health > /dev/null 2>&1; then
            print_success "MCP server is ready"
            break
        fi
        if [ $i -eq 30 ]; then
            print_error "MCP server failed to start within 30 seconds"
            docker logs mcp_db_performance --tail 50
            exit 1
        fi
        sleep 1
    done

    print_success "MCP server deployed successfully"
}

# Initialize database schema
initialize_schema() {
    print_header "Initializing Database Schema"

    print_info "Running schema initialization..."
    if docker exec mcp_db_performance python test-scripts/run_complete_init.py; then
        print_success "Database schema initialized successfully"
    else
        print_error "Failed to initialize database schema"
        exit 1
    fi
}

# Display deployment summary
display_summary() {
    print_header "Deployment Summary"

    echo -e "${GREEN}✓ Deployment completed successfully!${NC}\n"

    echo -e "${BLUE}Services Status:${NC}"
    if [ "$SKIP_PG" = false ]; then
        PGSTATUS=$(docker ps --filter "name=omni_pg_db" --format "{{.Status}}" 2>/dev/null || echo "Not running")
        echo -e "  PostgreSQL Cache: ${GREEN}${PGSTATUS}${NC}"
    fi
    MCPSTATUS=$(docker ps --filter "name=mcp_db_performance" --format "{{.Status}}" 2>/dev/null || echo "Not running")
    echo -e "  MCP Server:       ${GREEN}${MCPSTATUS}${NC}"

    echo -e "\n${BLUE}Access Points:${NC}"
    echo -e "  Direct Connection:  ${GREEN}http://localhost:8300/mcp${NC}"
    echo -e "  Health Check:       ${GREEN}http://localhost:8300/health${NC}"

    if [ "$SKIP_PG" = false ]; then
        echo -e "\n${BLUE}PostgreSQL Cache:${NC}"
        echo -e "  Host:     ${GREEN}localhost${NC}"
        echo -e "  Port:     ${GREEN}5435${NC}"
        echo -e "  Database: ${GREEN}omni${NC}"
        echo -e "  User:     ${GREEN}omni${NC}"
    fi

    echo -e "\n${BLUE}Next Steps:${NC}"
    echo -e "  1. Configure database connections in ${GREEN}server/config/settings.yaml${NC}"
    echo -e "  2. Test with Claude Desktop or MCP Inspector"
    echo -e "  3. View logs: ${GREEN}docker logs -f mcp_db_performance${NC}"

    echo -e "\n${BLUE}Useful Commands:${NC}"
    echo -e "  Stop services:    ${GREEN}./deploy.sh stop${NC}"
    echo -e "  View logs:        ${GREEN}docker logs -f mcp_db_performance${NC}"
    echo -e "  Restart MCP:      ${GREEN}docker-compose restart${NC}"
    echo -e "  Rebuild:          ${GREEN}./deploy.sh --rebuild${NC}"
}

# Stop all services
stop_services() {
    print_header "Stopping Services"

    cd "$SCRIPT_DIR"
    print_info "Stopping MCP server..."
    docker-compose down

    if [ "$SKIP_PG" = false ] && [ -d "$PG_DIR" ]; then
        cd "$PG_DIR"
        print_info "Stopping PostgreSQL..."
        docker-compose down
    fi

    print_success "All services stopped"
}

###############################################################################
# Main Execution
###############################################################################

# Handle stop command
if [ "$1" = "stop" ]; then
    stop_services
    exit 0
fi

print_header "MCP Database Performance Deployment"

# Pre-flight checks
print_info "Running pre-flight checks..."
check_docker
check_docker_compose

# Create required Docker networks
create_network "db-net"

# Deploy components
deploy_postgresql
deploy_mcp_server
initialize_schema

# Display summary
display_summary

print_success "Deployment completed!"
