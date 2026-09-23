import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.db import query_all, query_one
from app.ingestion.parser import WorkbookIngestor

# Re-ingest to test new parser logic
actual_file = ROOT_DIR / "MATERIAL PRODUCTION DATA WORKING 20.9.26.xlsm"
ingestor = WorkbookIngestor(actual_file, notes="Snapshot with PM and BOM")
summary = ingestor.parse_and_store()
snapshot_id = summary["snapshot_id"]
print(f"Ingested snapshot #{snapshot_id}:")
print(f"  Monthly targets count: {summary.get('monthly_targets_count')}")
print(f"  BOM specs count: {summary.get('bom_spec_count')}")

# Test finished goods query
fin_items = query_all("""
    SELECT 
        m.rating,
        m.material_name,
        m.sheet_name,
        sms.opening_balance,
        sms.received_qty,
        sms.issued_qty,
        sms.closing_balance
    FROM stock_master_snapshots sms
    JOIN materials m ON sms.material_id = m.id
    WHERE sms.snapshot_id = ?
      AND (
          m.material_type IN ('FINISHED', 'TRANSFORMER', 'CCA')
          OR m.sheet_name LIKE '%FINISHED%'
          OR m.sheet_name LIKE '%OUTSOURCED%'
          OR m.sheet_name LIKE '%FIN%'
      )
    ORDER BY m.rating, m.material_name
""", (snapshot_id,))
print(f"\nFinished goods items found: {len(fin_items)}")
for f in fin_items[:10]:
    print(" ", f)

# Test monthly matrix
matrix = query_all("""
    SELECT 
        SUBSTR(date, 1, 7) as month_val,
        section,
        SUM(units_produced) as units
    FROM production_entries
    WHERE snapshot_id = ?
    GROUP BY month_val, section
    ORDER BY month_val, section
""", (snapshot_id,))
print(f"\nMonthly matrix rows: {len(matrix)}")
for m in matrix:
    print(" ", m)

# Test BOM specs
boms = query_all("""
    SELECT rating, material_name, material_type, size, pieces_count, qty_per_coil, qty_per_transformer, unit
    FROM bom_specifications
    WHERE snapshot_id = ?
    LIMIT 6
""", (snapshot_id,))
print(f"\nBOM specs count: {len(boms)}")
for b in boms:
    print(" ", b)
