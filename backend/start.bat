@echo off
REM ===================================================================
REM LearnAI Backend - Start All Services
REM Starts: Daphne (ASGI) + Celery Worker + WebSocket Support
REM ===================================================================

echo.
echo ========================================================================
echo 🚀 STARTING LEARNAI BACKEND
echo ========================================================================
echo.
echo Services:
echo   🌐 Daphne (ASGI Server - HTTP + WebSocket)
echo   📦 Celery Worker (Async Task Queue)
echo.
echo Server: http://localhost:8000
echo ========================================================================
echo.

REM Check if virtual environment is activated
if "%VIRTUAL_ENV%"=="" (
    echo ⚠️  WARNING: Virtual environment not activated!
    echo    Please activate your venv first:
    echo    .\venv\Scripts\activate
    echo.
    pause
    exit /b 1
)

echo ✅ Virtual environment: %VIRTUAL_ENV%
echo.

REM Check if Redis is running
echo 🔍 Checking Redis connection...
redis-cli ping >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠️  WARNING: Redis is not running!
    echo    Please start Redis first:
    echo    redis-server
    echo.
    echo    Celery tasks will not work until Redis is started.
    echo.
) else (
    echo ✅ Redis is running
)
echo.

REM Check if database is accessible
echo 🔍 Checking database connection...
python manage.py check --database default >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠️  WARNING: Database connection failed!
    echo    Please ensure PostgreSQL is running and configured.
    echo.
) else (
    echo ✅ Database is accessible
)
echo.

echo ========================================================================
echo 🎯 Starting server with: python manage.py rundev
echo ========================================================================
echo.
echo Press Ctrl+C to stop all services
echo.

REM Run the custom rundev command (starts Daphne + Celery)
python manage.py rundev 8000

echo.
echo ========================================================================
echo ✅ Server stopped
echo ========================================================================
echo.
pause
