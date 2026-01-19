@echo off
REM ============================================================================
REM Migration Runner Script (Windows)
REM ============================================================================
REM Automatically runs all SQL migrations in order
REM Usage:
REM   run_migrations.cmd                    Run on Docker (default)
REM   run_migrations.cmd omni_pg_db         Run on specific container

setlocal enabledelayedexpansion

set CONTAINER_NAME=%1
if "%CONTAINER_NAME%"=="" set CONTAINER_NAME=omni_pg_db

set DB_USER=omni
set DB_NAME=omni
set MIGRATIONS_DIR=%~dp0

echo ========================================
echo Migration Runner
echo ========================================
echo Container: %CONTAINER_NAME%
echo Database: %DB_NAME%
echo Schema: mcp_performance
echo ========================================
echo.

REM Check if Docker is running
docker ps >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running or not accessible
    exit /b 1
)

REM Check if container exists
docker ps | findstr /C:"%CONTAINER_NAME%" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Container '%CONTAINER_NAME%' is not running
    echo.
    echo Available containers:
    docker ps --format "table {{.Names}}\t{{.Status}}"
    exit /b 1
)

REM Count migration files
set count=0
for %%f in ("%MIGRATIONS_DIR%*.sql") do set /a count+=1

if %count%==0 (
    echo [WARNING] No migration files found in %MIGRATIONS_DIR%
    exit /b 0
)

echo Found %count% migration(s) to run
echo.

REM Run each migration
set success=0
set failed=0

for %%f in ("%MIGRATIONS_DIR%*.sql") do (
    echo Running migration: %%~nxf ...
    docker exec -i %CONTAINER_NAME% psql -U %DB_USER% -d %DB_NAME% < "%%f" >nul 2>&1
    if errorlevel 1 (
        echo [FAILED] %%~nxf
        set /a failed+=1
        echo.
        echo [ERROR] Migration failed. Stopping execution.
        goto summary
    ) else (
        echo [SUCCESS] %%~nxf
        set /a success+=1
    )
)

:summary
echo.
echo ========================================
if %failed%==0 (
    echo [SUCCESS] All migrations completed!
    echo   Success: %success%
) else (
    echo [FAILED] Migrations failed
    echo   Success: %success%
    echo   Failed: %failed%
)
echo ========================================

REM Verify tables
echo.
echo Verifying tables...
docker exec %CONTAINER_NAME% psql -U %DB_USER% -d %DB_NAME% -c "\dt mcp_performance.*"

if %failed%==0 (
    echo.
    echo [SUCCESS] Migrations complete!
    exit /b 0
) else (
    exit /b 1
)
