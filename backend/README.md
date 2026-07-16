# 后端服务

后端基于 FastAPI，包含认证、会话、Multi-Agents、RAG、学习流程、测验和代码评测模块。

## 安装与启动

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

API 文档位于 `http://localhost:8000/api/v1/docs`。

## 测试

```powershell
python -m pytest -q
```

数据库、公共知识库和代码沙箱配置请阅读根目录 [README](../README.md)。
