@echo off
REM ===================================================================
REM LearnAI Backend - Start All Services
REM Starts: Daphne (ASGI Server - HTTP + WebSocket)
REM Background tasks run in-process via threading (no separate worker)
REM ===================================================================

echo.
echo ========================================================================
echo  STARTING LEARNAI BACKEND
echo ========================================================================
echo.
echo Services:
echo   Uvicorn (ASGI Server - HTTP + WebSocket + SSE)
echo   Background Tasks (in-process via threading)
echo.
echo Server: http://localhost:8000
echo ========================================================================
echo.

REM Check if virtual environment is activated
if "%VIRTUAL_ENV%"=="" (
    echo WARNING: Virtual environment not activated!
    echo    Please activate your venv first:
    echo    .\venv\Scripts\activate
    echo.
    pause
    exit /b 1
)

echo Virtual environment: %VIRTUAL_ENV%
echo.

REM Check if Redis is running
echo Checking Redis connection...
redis-cli ping >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: Redis is not running!
    echo    Please start Redis first:
    echo    redis-server
    echo.
) else (
    echo Redis is running
)
echo.

echo ========================================================================
echo Starting server...
echo ========================================================================
echo.
echo Press Ctrl+C to stop
echo.

uvicorn config.asgi:application --host 127.0.0.1 --port 8000 --timeout-keep-alive 300

echo.
echo ========================================================================
echo Server stopped
echo ========================================================================
echo.
pause
