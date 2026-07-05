@echo off
REM Wrapper for Windows Task Scheduler. Anchors the working directory to this
REM file's own location so config.yaml/.env are found regardless of the
REM scheduled task's "Start in" setting.
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python -m property_monitor.cli --config config.yaml
