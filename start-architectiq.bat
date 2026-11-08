@echo off
setlocal
cd /d "%~dp0"

echo ============================================================================
echo                      ARCHITECTIQ PLATFORM LAUNCHER                         
echo               Enterprise DevOps, CI/CD, and DevSecOps Suite                
echo ============================================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-architectiq.ps1"

echo.
echo ============================================================================
echo Execution complete. Console will remain open.
echo ============================================================================
pause
