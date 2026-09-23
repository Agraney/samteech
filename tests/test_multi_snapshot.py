import sys
import shutil
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.ingestion.parser import WorkbookIngestor
from app.services.insights import InsightsEngine

def test_multi_snapshot():
    sample1 = ROOT_DIR / "data" / "sample_factory_data.xlsm"
    snap2_file = ROOT_DIR / "data" / "sample_factory_week2.xlsm"
    
    # Copy file to simulate a second week's upload
    shutil.copyfile(sample1, snap2_file)
    
    print("Ingesting Snapshot #2 (Week 2)...")
    ingestor = WorkbookIngestor(snap2_file, notes="Simulated Week 2 Upload")
    summary2 = ingestor.parse_and_store()
    print(f"[OK] Ingested Snapshot #{summary2['snapshot_id']}")
    
    # Verify insights engine picks up prior snapshot
    eng = InsightsEngine(snapshot_id=summary2['snapshot_id'])
    dash = eng.get_dashboard_insights()
    assert dash["snapshot"]["prior_snapshot_id"] is not None
    print(f"[OK] Dashboard detected prior snapshot: #{dash['snapshot']['prior_snapshot_id']}")
    
    # Verify trend analytics
    trends = eng.get_time_series_trends()
    assert len(trends["snapshots"]) >= 2
    print(f"[OK] Trends tracked across {len(trends['snapshots'])} snapshots!")
    
    print("\nMULTI-SNAPSHOT VERIFICATION PASSED!")

if __name__ == "__main__":
    test_multi_snapshot()
