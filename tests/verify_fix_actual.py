import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.db import init_db, query_all, query_one
from app.ingestion.parser import WorkbookIngestor
from app.services.insights import InsightsEngine
from app.services.qa_assistant import QAAssistant

def run_verification():
    actual_file = ROOT_DIR / "MATERIAL PRODUCTION DATA WORKING 20.9.26.xlsm"
    assert actual_file.exists(), f"File not found: {actual_file}"

    print(f"Re-ingesting {actual_file.name} with fixed parser...")
    ingestor = WorkbookIngestor(actual_file, notes="Re-ingestion with monthly summary fix")
    summary = ingestor.parse_and_store()
    snapshot_id = summary["snapshot_id"]
    print(f"[OK] Ingestion complete. Snapshot ID: #{snapshot_id}")
    print(f"     Production entries count: {summary['production_entries_count']}")
    print(f"     Transactions count: {summary['transactions_count']}")

    print("\n--- Production Counts by Section ---")
    sections = query_all("""
        SELECT section, SUM(units_produced) as total_units, COUNT(*) as daily_record_count
        FROM production_entries
        WHERE snapshot_id = ?
        GROUP BY section
        ORDER BY total_units DESC
    """, (snapshot_id,))
    for s in sections:
        print(f"  {s['section']}: {s['total_units']} units across {s['daily_record_count']} daily records")

    print("\n--- HV Winding Breakdown by Rating ---")
    hv_by_rating = query_all("""
        SELECT rating, SUM(units_produced) as units
        FROM production_entries
        WHERE snapshot_id = ? AND section = 'HV WINDING'
        GROUP BY rating
        ORDER BY rating
    """, (snapshot_id,))
    for r in hv_by_rating:
        print(f"  {r['rating']}: {r['units']} units")
    total_hv = sum(r['units'] for r in hv_by_rating)
    print(f"  ==> TOTAL HV WINDING: {total_hv} units")

    # Assert HV Winding is exactly 423 (NOT 846!)
    assert total_hv == 423.0, f"Expected 423.0 but got {total_hv}"

    print("\n--- LV Winding Breakdown by Rating ---")
    lv_by_rating = query_all("""
        SELECT rating, SUM(units_produced) as units
        FROM production_entries
        WHERE snapshot_id = ? AND section = 'LV WINDING'
        GROUP BY rating
        ORDER BY rating
    """, (snapshot_id,))
    for r in lv_by_rating:
        print(f"  {r['rating']}: {r['units']} units")
    total_lv = sum(r['units'] for r in lv_by_rating)
    print(f"  ==> TOTAL LV WINDING: {total_lv} units")

    # Assert LV Winding is exactly 176 (NOT 352!)
    assert total_lv == 176.0, f"Expected 176.0 but got {total_lv}"

    print("\n--- Insights Engine Test ---")
    eng = InsightsEngine(snapshot_id=snapshot_id)
    dash = eng.get_dashboard_insights()
    print("Headline:", dash["executive_summary"]["headline"])
    print("Bottleneck:", dash["production"]["bottleneck"])
    print("Total units produced in factory:", dash["production"]["total_produced_units"])

    print("\n--- QA Assistant Test ---")
    qa = QAAssistant()
    res1 = qa.answer_question("What is the HV winding production count?", session_id="test_qa")
    print("Q: What is the HV winding production count?")
    print("SQL Query:\n", res1["sql_query"])
    print("Answer:\n", res1["answer"])

    res2 = qa.answer_question("How much finished HV coil do we have in stock?", session_id="test_qa")
    print("\nQ: How much finished HV coil do we have in stock?")
    print("SQL Query:\n", res2["sql_query"])
    print("Answer:\n", res2["answer"])

    print("\nVERIFICATION SUITE COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    run_verification()
