# INT-Slim 智能伴学平台

INT-Slim 是一个面向自主学习场景的多智能体平台，后端使用 FastAPI、LangGraph、MySQL 与 Chroma，前端使用 Vue 3 和 Vite。系统提供智能问答、知识检索、章节学习、自动出题、代码实训、错题整理与学习分析。

## 主要功能

- **Agents 伴学**：流式展示智能体协作步骤、工具调用、参考来源与最终回答。
- **知识库检索**：支持公共知识库和用户私有知识库，通过 Chroma 完成向量检索。
- **课程学习**：按课程和章节组织内容，记录阅读进度与通关状态。
- **章节测验**：根据当前章节生成选择题，保存题目、作答记录、评分和解析。
- **代码实训**：支持 Python、C、C++、Java，以及 ACM/核心代码两种模式。
- **错题本**：统一整理测验错题和代码提交问题。
- **学习分析**：展示学习任务、掌握度、复习安排和学习报告。

## 技术架构

```text
Vue 3 + Vite
       |
       | HTTP / SSE
       v
FastAPI + LangGraph
       |
       +-- MySQL：业务数据、课程、题目、作答记录、知识库元数据
       +-- Chroma：知识切片向量索引
       +-- LLM：DeepSeek / MiniMax 等模型服务
       +-- Conda Sandbox：Python / C / C++ / Java 代码执行
```

## 目录结构

```text
backend/
  app/                    FastAPI、Agents、RAG、工具和业务模型
  database/               数据库结构与公共知识库发布包
  scripts/                数据迁移、知识库维护、沙箱安装脚本
  tests/                  后端自动化测试
frontend/
  src/                    Vue 页面、组件、路由和 API 封装
  public/                 前端静态资源
docs/                     知识库采集和数据规范
scripts/                  Windows 快速启动与停止脚本
```

运行时产生的沙箱文件、Chroma 数据、日志、构建产物、真实环境变量和完整数据库备份不会提交到 Git。

## 环境要求

- Python 3.11 或更高版本
- Node.js 20 或更高版本
- MySQL 8.0 或更高版本
- Conda 或 Miniconda，代码实训功能推荐安装

## 快速开始

### 1. 克隆项目

```powershell
git clone git@github.com:SuanXiangJi/INT-Slim.git
cd INT-Slim
```

### 2. 配置后端

```powershell
Copy-Item backend/.env.example backend/.env
```

编辑 `backend/.env`，至少填写：

- `mysql_host`、`mysql_port`、`mysql_user`、`mysql_password`、`mysql_database`
- `secret_key`
- 至少一个模型服务密钥，例如 `deepseek_api_key`

需要联网搜索时填写 `tavily_api_key`；需要邮件验证码时填写 SMTP 配置。

### 3. 初始化数据库

```powershell
mysql -u root -p -e "CREATE DATABASE xbots_v2 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
cmd /c "mysql -u root -p xbots_v2 < backend\\database\\schema.sql"
```

恢复仓库附带的公共知识库：

```powershell
cd backend
python scripts/system_kb_backup.py restore --input database/system_kb
cd ..
```

公共知识库发布包只包含系统学习资料，不包含账号、密码哈希、Token、会话、作答记录或用户画像。维护方式参见 [数据库资源说明](backend/database/README.md)。

### 4. 安装依赖

后端：

```powershell
cd backend
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
cd ..
```

前端：

```powershell
cd frontend
npm install
cd ..
```

### 5. 配置代码沙箱（可选）

```powershell
powershell -ExecutionPolicy Bypass -File backend/scripts/setup_sandbox_env.ps1
```

该脚本会安装并验证 Python、Node.js、OpenJDK、GCC/G++ 及常用数据科学依赖。详细说明见 [沙箱环境文档](backend/SANDBOX_ENV.md)。

## 启动项目

分别打开两个终端。

后端：

```powershell
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

前端：

```powershell
cd frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

访问地址：

- 前端开发环境：`http://localhost:5173`
- API 文档：`http://localhost:8000/api/v1/docs`
- 健康检查：`http://localhost:8000/health`

Windows 也可以直接运行：

```powershell
.\\scripts\\start_project.cmd
```

## 生产方式运行

```powershell
cd frontend
npm run build
cd ../backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

构建完成后，FastAPI 会在 `http://localhost:8000/app/` 提供前端页面。

## 测试

```powershell
cd backend
python -m pytest -q
cd ../frontend
npm run build
```

## 数据安全

- 不要提交 `backend/.env`、完整数据库备份、日志、Chroma 运行目录或沙箱会话。
- 部署时必须替换默认 `secret_key`。
- 生产环境应使用低权限账户运行代码沙箱，并在系统或容器层限制 CPU、内存和执行时间。
- 更新公共知识库前，应检查来源授权、内容质量和元数据完整性。
