@echo off
set "SCRIPT_DIR=%~dp0"
start "INT-Slim Backend" cmd /k call "%SCRIPT_DIR%start_backend.cmd"
start "INT-Slim Frontend" cmd /k call "%SCRIPT_DIR%start_frontend.cmd"
