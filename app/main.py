import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import BASE_DIR, INCOMING_DIR
from app.db import init_db
from app.api.routes import router as api_router
from app.ingestion.parser import WorkbookIngestor

app = FastAPI(
    title="Transformer Factory Insights & Q&A",
    description="Operational analytics and AI assistant for transformer manufacturing",
    version="1.0.0"
)

# Enable CORS for local cross-origin development if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database schema
init_db()

# Auto-ingest any pending workbooks in incoming folder
def check_incoming_folder():
    if INCOMING_DIR.exists():
        for f in INCOMING_DIR.glob("*.xlsm"):
            try:
                print(f"Auto-ingesting incoming workbook: {f.name}")
                ingestor = WorkbookIngestor(f, notes="Auto-ingested from incoming folder")
                ingestor.parse_and_store()
            except Exception as e:
                print(f"Error auto-ingesting {f.name}: {e}")

check_incoming_folder()

# Auto-seed initial factory workbook if database has no snapshots (critical for ephemeral Render deployments)
def ensure_initial_data():
    from app.db import query_one
    try:
        snap_count = query_one("SELECT COUNT(*) as cnt FROM snapshots")
        if not snap_count or snap_count["cnt"] == 0:
            candidates = [
                BASE_DIR / "MATERIAL PRODUCTION DATA WORKING 20.9.26.xlsm",
                BASE_DIR / "data" / "uploads" / "MATERIAL PRODUCTION DATA WORKING 20.9.26.xlsm",
                BASE_DIR / "data" / "sample_factory_data.xlsm",
            ]
            for c in candidates:
                if c.exists():
                    print(f"No existing snapshots found. Auto-seeding initial workbook: {c.name}...")
                    ingestor = WorkbookIngestor(c, notes="Initial seed snapshot on deploy")
                    ingestor.parse_and_store()
                    print(f"Successfully seeded snapshot from {c.name}")
                    break
    except Exception as e:
        print(f"Warning during initial data check: {e}")

ensure_initial_data()

# Include API routes
app.include_router(api_router)

# Health check route for Render / uptime monitors
@app.get("/health")
def health_check():
    return {"status": "ok", "service": "samtech-factory-intelligence"}

# Mount static files
static_dir = BASE_DIR / "app" / "static"
static_dir.mkdir(parents=True, exist_ok=True)
(static_dir / "css").mkdir(parents=True, exist_ok=True)
(static_dir / "js").mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
def serve_index():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Transformer Factory Insights API is running. UI loading..."}

if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host=host, port=port)
