from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import SessionLocal, init_db
from app.services.analysis import analyze_statement_rows
from app.services.statement_parser import parse_statement_file

if __name__ == "__main__":
    init_db()
    sample_path = ROOT / "data" / "sample_statement.csv"
    content = sample_path.read_bytes()
    rows = parse_statement_file(sample_path.name, content)
    with SessionLocal() as db:
        result = analyze_statement_rows(db, card_id="CC001", rows=rows, source_name=sample_path.name, file_content=content)
    print(result)
