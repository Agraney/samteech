"""
Launcher script for Transformer Factory Insights App
Run with: python run.py
"""
import sys
from pathlib import Path
import uvicorn

# Ensure project root is in python path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if __name__ == "__main__":
    print("=" * 65)
    print(" ⚡ SAMTECH TRANSFORMER FACTORY INSIGHTS & Q&A APP")
    print(" Local server starting on: http://127.0.0.1:8000")
    print(" Drop incoming workbooks into: data/incoming/")
    print(" Press Ctrl+C to stop.")
    print("=" * 65)
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
