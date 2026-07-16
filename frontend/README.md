# 前端应用

前端使用 Vue 3、Vite、Element Plus 和 ECharts，包含 Agents 伴学、课程学习、测验、代码实训、错题本和学习分析页面。

## 开发

```powershell
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

## 构建

```powershell
npm run build
```

开发环境通过 Vite 将 `/api` 请求代理到 `http://localhost:8000`。
