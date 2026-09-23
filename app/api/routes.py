import os
import shutil
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from pydantic import BaseModel

from app.config import UPLOADS_DIR, DB_PATH, BASE_DIR
from app.db import query_all, query_one
from app.ingestion.parser import WorkbookIngestor
from app.services.insights import InsightsEngine
from app.services.qa_assistant import QAAssistant

router = APIRouter(prefix="/api")

class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = "default"
    api_key: Optional[str] = None

class ApiKeyUpdate(BaseModel):
    api_key: str

@router.get("/config")
def get_config_status():
    from app.config import GEMINI_API_KEY
    has_key = bool(GEMINI_API_KEY and GEMINI_API_KEY.strip())
    latest_snap = query_one("SELECT COUNT(*) as cnt FROM snapshots")
    return {
        "has_gemini_key": has_key,
        "total_snapshots": latest_snap["cnt"] if latest_snap else 0,
        "db_path": str(DB_PATH)
    }

@router.post("/config/gemini-key")
def update_gemini_key(payload: ApiKeyUpdate):
    key = payload.api_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="API key cannot be empty")
        
    os.environ["GEMINI_API_KEY"] = key
    env_file = BASE_DIR / ".env"
    with open(env_file, "a") as f:
        f.write(f"\nGEMINI_API_KEY={key}\n")
        
    return {"status": "success", "message": "Gemini API key configured successfully"}

@router.get("/snapshots")
def get_snapshots():
    snapshots = query_all("SELECT * FROM snapshots ORDER BY id DESC")
    return {"snapshots": snapshots}

@router.post("/upload")
async def upload_workbook(
    file: UploadFile = File(...),
    notes: Optional[str] = Form("")
):
    if not file.filename.endswith((".xlsm", ".xlsx")):
        raise HTTPException(status_code=400, detail="Only .xlsm and .xlsx files are supported")
        
    dest_path = UPLOADS_DIR / file.filename
    # Handle filename collision with timestamp if exists
    if dest_path.exists():
        import datetime
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = Path(file.filename).stem
        ext = Path(file.filename).suffix
        dest_path = UPLOADS_DIR / f"{stem}_{ts}{ext}"

    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        ingestor = WorkbookIngestor(dest_path, notes=notes or "Web upload")
        summary = ingestor.parse_and_store()
        return {
            "status": "success",
            "message": f"Successfully ingested {file.filename}",
            "summary": summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process workbook: {str(e)}")

@router.get("/insights/dashboard")
def get_dashboard_insights(
    snapshot_id: Optional[int] = Query(None),
    month: Optional[str] = Query(None)
):
    engine = InsightsEngine(snapshot_id=snapshot_id)
    return engine.get_dashboard_insights(month=month)

@router.get("/inventory/finished-goods")
def get_finished_goods(snapshot_id: Optional[int] = Query(None)):
    engine = InsightsEngine(snapshot_id=snapshot_id)
    return engine._compute_finished_goods()

@router.get("/bom/specifications")
def get_bom_specifications(snapshot_id: Optional[int] = Query(None)):
    engine = InsightsEngine(snapshot_id=snapshot_id)
    return {"bom_specifications": engine._get_bom_specifications()}

@router.get("/insights/trends")

def get_trends(material_ids: Optional[str] = Query(None)):
    m_ids = None
    if material_ids:
        try:
            m_ids = [int(i.strip()) for i in material_ids.split(",") if i.strip()]
        except ValueError:
            m_ids = None
    engine = InsightsEngine()
    return engine.get_time_series_trends(material_ids=m_ids)

@router.get("/materials")
def list_materials(snapshot_id: Optional[int] = Query(None)):
    if snapshot_id is None:
        latest = query_one("SELECT id FROM snapshots ORDER BY id DESC LIMIT 1")
        snapshot_id = latest["id"] if latest else 0

    items = query_all(
        """
        SELECT 
            m.id,
            m.rating,
            m.sheet_name,
            m.material_name,
            m.material_type,
            m.size,
            m.unit,
            sms.opening_balance,
            sms.received_qty,
            sms.rate,
            sms.value,
            sms.issued_qty,
            sms.closing_balance
        FROM materials m
        LEFT JOIN stock_master_snapshots sms ON m.id = sms.material_id AND sms.snapshot_id = ?
        ORDER BY m.rating, m.material_name
        """,
        (snapshot_id,)
    )
    return {"materials": items}

@router.post("/chat")
def chat(payload: ChatRequest):
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    assistant = QAAssistant(api_key=payload.api_key)
    result = assistant.answer_question(payload.question, session_id=payload.session_id)
    return result

@router.get("/chat/history")
def get_chat_history(session_id: str = "default"):
    history = query_all(
        """
        SELECT role, content, sql_query, sql_results_json, created_at 
        FROM chat_history 
        WHERE session_id = ? 
        ORDER BY id ASC
        LIMIT 50
        """,
        (session_id,)
    )
    return {"history": history}
