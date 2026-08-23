@echo off
echo Iniciando Aureum Dashboard (porta 8001)...
echo Streamlit permanece em execucao independentemente.
echo.
echo Acesse: http://localhost:8001
echo Para parar: Ctrl+C
echo.
cd /d "%~dp0.."
uvicorn web.main:app --port 8001 --reload
