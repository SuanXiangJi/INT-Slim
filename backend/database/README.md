# 数据库资源

本目录只保存可公开发布的数据库资源：

- `schema.sql`：MySQL 表结构，不包含任何业务数据。
- `system_kb/`：经过压缩的公共知识库文档和切片。
- `../scripts/system_kb_backup.py`：带 SHA-256 校验的导入导出工具。

## 初始化数据库

```powershell
mysql -u root -p -e "CREATE DATABASE xbots_v2 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
cmd /c "mysql -u root -p xbots_v2 < backend\\database\\schema.sql"
```

## 恢复公共知识库

先配置 `backend/.env`，然后执行：

```powershell
cd backend
python scripts/system_kb_backup.py restore --input database/system_kb
```

恢复操作只替换系统公共知识库身份下的文档和切片，不会修改用户私有知识库。

## 导出新的公共知识库

```powershell
cd backend
python scripts/system_kb_backup.py export --compress --output database/system_kb-new
```

导出后应核对 `manifest.json` 中的文档数量、切片数量和文件校验和，再替换正式发布包。

禁止向仓库添加完整数据库备份。完整备份包含账号、Token、会话和学习记录等私有数据。
