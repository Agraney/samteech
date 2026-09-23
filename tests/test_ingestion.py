import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db import init_db, query_all, query_one
from app.ingestion.parser import WorkbookIngestor


def test_ingestion():
    sample_file = Path(__file__).resolve().parent.parent / "data" / "sample_factory_data.xlsm"
    assert sample_file.exists(), f"Sample file not found at {sample_file}"
    
    print(f"Testing ingestion for {sample_file}...")
    ingestor = WorkbookIngestor(sample_file, notes="Initial test snapshot")
    summary = ingestor.parse_and_store()
    
    print("Ingestion Summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")
        
    assert summary["snapshot_id"] > 0
    assert summary["materials_count"] > 0
    assert summary["stock_master_rows"] > 0
    assert summary["transactions_count"] > 0
    assert summary["production_entries_count"] > 0
    assert summary["norms_count"] > 0
    
    # Query validation
    materials = query_all("SELECT * FROM materials LIMIT 5")
    print(f"\nSample materials in DB: {len(materials)}")
    for m in materials:
        print(f"  [{m['rating']}] {m['material_name']} ({m['sheet_name']}) - Unit: {m['unit']}")
        
    sm = query_all("SELECT * FROM stock_master_snapshots WHERE snapshot_id = ? LIMIT 5", (summary["snapshot_id"],))
    print(f"\nSample Stock Master rows: {len(sm)}")
    for s in sm:
        print(f"  Material ID {s['material_id']}: Close={s['closing_balance']}, Val={s['value']}")
        
    prod = query_all("SELECT section, SUM(units_produced) as total_units FROM production_entries WHERE snapshot_id = ? GROUP BY section", (summary["snapshot_id"],))
    print(f"\nProduction by Section:")
    for p in prod:
        print(f"  {p['section']}: {p['total_units']} units")
        
    print("\nINGESTION TEST PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_ingestion()
