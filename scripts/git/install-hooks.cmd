@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-hooks.ps1"
exit /b %errorlevel%
