@echo off
chcp 65001 >nul
cd /d "D:\A_ZJJ_Project\Multi-Modal AI Insights Agent"

REM 开机执行：按当前业务命令运行
".\multimodal_agent.venv\Scripts\python.exe" -m agent.multiModal_agent.run --paper-limit 30 --news-limit 30 --top-k 20 >> "output\multiModal_agent\startup_task.log" 2>&1
