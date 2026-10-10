@echo off
title BodyMaxxing - Frontend Application Launcher
cd /d "%~dp0"

echo ======================================================================
echo                 BODYMAXXING DESKTOP LAUNCHER
echo ======================================================================
echo.

set CONDA_ACTIVATED=0

:: Check standard miniconda location
if exist "%UserProfile%\miniconda3\condabin\conda.bat" (
    echo [Launcher] Activating conda environment 'BMEnv' via Miniconda...
    call "%UserProfile%\miniconda3\condabin\conda.bat" activate BMEnv
    set CONDA_ACTIVATED=1
)

:: Check standard anaconda location if not already activated
if "%CONDA_ACTIVATED%"=="0" (
    if exist "%UserProfile%\anaconda3\condabin\conda.bat" (
        echo [Launcher] Activating conda environment 'BMEnv' via Anaconda...
        call "%UserProfile%\anaconda3\condabin\conda.bat" activate BMEnv
        set CONDA_ACTIVATED=1
    )
)

:: Check system conda if not already activated
if "%CONDA_ACTIVATED%"=="0" (
    where conda >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        echo [Launcher] Activating conda environment 'BMEnv' via system PATH...
        call conda activate BMEnv
        set CONDA_ACTIVATED=1
    )
)

:: Launch Flet frontend
echo [Launcher] Starting Flet user interface...
echo.

where flet >nul 2>&1
if %ERRORLEVEL% equ 0 (
    flet run frontend/main.py
) else (
    if exist "%UserProfile%\miniconda3\envs\BMEnv\Scripts\flet.exe" (
        "%UserProfile%\miniconda3\envs\BMEnv\Scripts\flet.exe" run frontend/main.py
    ) else (
        echo [Launcher] Flet executable not in PATH, falling back to python direct execution...
        python frontend/main.py
    )
)

if %ERRORLEVEL% neq 0 (
    echo.
    echo ======================================================================
    echo [Launcher Error] The application exited with an error code: %ERRORLEVEL%
    echo ======================================================================
    echo Please ensure the backend server is active:
    echo    uvicorn backend.main:app --reload --port 8000
    echo.
    pause
)
