@echo off
REM -------------------------------------------------
REM  Start FastAPI backend
REM -------------------------------------------------
python -u backend\server.py
set HF_HOME=%~dp0model_cache

REM Remove or comment out the line below
:: pause