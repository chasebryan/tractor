@echo off
for %%V in (3.12 3.13 3.11) do (
    py -%%V -c "import sys" >nul 2>&1
    if not errorlevel 1 (
        py -%%V "%~dp0scripts\launch.py" %*
        exit /b
    )
)
echo Python 3.11-3.13 is required. Install Python 3.12 with the Python launcher enabled.
pause
exit /b 1
