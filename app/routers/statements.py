from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import StatementUploadResult
from ..services.analysis import analyze_statement_rows
from ..services.statement_parser import parse_statement_file

router = APIRouter(prefix="/statements", tags=["statements"])


@router.post("/upload", response_model=StatementUploadResult)
async def upload_statement(
    card_id: str = Form(...),
    statement_password: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    content = await file.read()
    try:
        rows = parse_statement_file(file.filename or "statement.csv", content, password=statement_password)
        if not rows:
            raise ValueError("No valid transactions found in uploaded file.")
        return analyze_statement_rows(db, card_id=card_id, rows=rows, source_name=file.filename or "upload", file_content=content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
