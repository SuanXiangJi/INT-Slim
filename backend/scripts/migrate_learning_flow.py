"""Create the learning-flow tables and add non-destructive columns for existing DBs."""
from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import inspect, text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.models import Base, engine  # noqa: E402


def main() -> None:
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    columns = {item["name"] for item in inspector.get_columns("chapter_progress")}
    if "assistant_conversation_id" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE chapter_progress ADD COLUMN assistant_conversation_id BINARY(16) NULL"))
    print("learning flow schema is ready")


if __name__ == "__main__":
    main()
