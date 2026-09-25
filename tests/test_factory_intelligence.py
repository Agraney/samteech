import sys
sys.path.insert(0, ".")
from app.db import query_all, query_one
from typing import Dict, Any, List

snapshot_id = 5

print("Testing WIP calculation...")
# Test WIP
prod_rows = query_all("SELECT section, SUM(units_produced) as total_units FROM production_entries WHERE snapshot_id = ? GROUP BY section", (snapshot_id,))
sec_map = {r["section"]: r["total_units"] for r in prod_rows}
print("Production section map:", sec_map)

# Test readiness
bom_rows = query_all("SELECT rating, material_name, material_type, size, qty_per_transformer, unit FROM bom_specifications WHERE snapshot_id = ?", (snapshot_id,))
print(f"BOM rows: {len(bom_rows)}")

stock_rows = query_all("SELECT m.rating, m.material_name, sms.closing_balance FROM stock_master_snapshots sms JOIN materials m ON sms.material_id = m.id WHERE sms.snapshot_id = ?", (snapshot_id,))
print(f"Stock rows: {len(stock_rows)}")

# Test targets
targets = query_all("SELECT section, rating, month, target_units, actual_units, variance_units FROM production_monthly_targets WHERE snapshot_id = ? AND month = 'Sep-26'", (snapshot_id,))
print(f"Sep-26 targets: {len(targets)}")

print("ALL TEST QUERIES EXECUTED SUCCESSFULLY!")
