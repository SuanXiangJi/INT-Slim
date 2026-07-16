@echo off
cd /d "D:\Desktop\XBots Agent\backend"
"D:\ProgramData\anaconda3\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
