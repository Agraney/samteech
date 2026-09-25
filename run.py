import os
import sys
from pathlib import Path
import uvicorn

# Ensure project root is in python path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8000))
    is_render = os.environ.get("RENDER") is not None or os.environ.get("ENV") == "production"
    reload = not is_render and host in ("127.0.0.1", "localhost")

    print("=" * 65)
    print(" [SAMTECH] TRANSFORMER FACTORY INSIGHTS & OPERATIONS APP")
    print(f" Server starting on: http://{host}:{port}")
    print(" Drop incoming workbooks into: data/incoming/")
    print(" Press Ctrl+C to stop.")
    print("=" * 65)
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)
