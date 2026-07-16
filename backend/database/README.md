# Database resources

This directory contains only resources that are safe to publish:

- `schema.sql`: the MySQL schema without user rows, tokens, conversations, or messages.
- `system_kb/`: the shared read-only knowledge base in compressed JSONL form.
- `../scripts/system_kb_backup.py`: checksum-verified export and restore utility.

Create the database and import the schema:

```powershell
mysql -u root -p -e "CREATE DATABASE xbots_v2 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -u root -p xbots_v2 < backend/database/schema.sql
```

After configuring `backend/.env`, restore the shared knowledge base:

```powershell
cd backend
python scripts/system_kb_backup.py restore --input database/system_kb
```

The restore operation replaces only rows owned by the system knowledge-base identity. It does not modify user-owned documents.

To create a reviewed replacement package:

```powershell
cd backend
python scripts/system_kb_backup.py export --compress --output database/system_kb-new
```

Never add a full database dump to this repository. Full dumps contain private account and learning data.
