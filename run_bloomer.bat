@echo off
cd /d "%~dp0"
py bloomer.py
if errorlevel 1 pause
