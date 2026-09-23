import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.db import query_one, query_all

client = TestClient(app)

def test_api_health_and_config():
    res = client.get("/api/config")
    assert res.status_code == 200
    data = res.json()
    assert "has_gemini_key" in data
    assert "total_snapshots" in data
    print("[OK] /api/config passed")

def test_snapshots_api():
    res = client.get("/api/snapshots")
    assert res.status_code == 200
    data = res.json()
    assert "snapshots" in data
    assert len(data["snapshots"]) > 0
    print(f"[OK] /api/snapshots passed ({len(data['snapshots'])} snapshots found)")

def test_dashboard_insights_api():
    res = client.get("/api/insights/dashboard")
    assert res.status_code == 200
    data = res.json()
    assert data["has_data"] is True
    assert "stock" in data
    assert "production" in data
    assert "consumption" in data
    assert "executive_summary" in data
    assert data["stock"]["total_items"] > 0
    assert data["production"]["bottleneck"]["section"] != ""
    print(f"[OK] /api/insights/dashboard passed (Total Items: {data['stock']['total_items']}, Bottleneck: {data['production']['bottleneck']['section']})")


def test_materials_api():
    res = client.get("/api/materials")
    assert res.status_code == 200
    data = res.json()
    assert len(data["materials"]) > 0
    print(f"[OK] /api/materials passed ({len(data['materials'])} materials returned)")

def test_chat_api():
    test_questions = [
        "How much HV wire do we have left for 63KVA?",
        "Which section is behind this month?",
        "What is our current oil balance?",
        "What materials are out of stock or low stock?"
    ]
    for q in test_questions:
        res = client.post("/api/chat", json={"question": q, "session_id": "test_session"})
        assert res.status_code == 200
        data = res.json()
        assert "answer" in data
        assert "sql_query" in data
        assert len(data["data"]) > 0
        print(f"[OK] /api/chat query '{q}' -> Answer returned with {len(data['data'])} records.")

def test_trends_api():
    res = client.get("/api/insights/trends")
    assert res.status_code == 200
    data = res.json()
    assert "snapshots" in data
    assert "prod_trends" in data
    print("[OK] /api/insights/trends passed")

def test_finished_goods_api():
    res = client.get("/api/inventory/finished-goods")
    assert res.status_code == 200
    data = res.json()
    assert "total_finished_transformers" in data
    assert "finished_transformers" in data
    print(f"[OK] /api/inventory/finished-goods passed (Finished Transformers: {data['total_finished_transformers']}, CCA: {data['total_cca_ready']}, HV Coils: {data['total_hv_coils_ready']})")

def test_bom_specifications_api():
    res = client.get("/api/bom/specifications")
    assert res.status_code == 200
    data = res.json()
    assert "bom_specifications" in data
    assert len(data["bom_specifications"]) > 0
    print(f"[OK] /api/bom/specifications passed ({len(data['bom_specifications'])} BOM specs returned)")

def test_monthly_dashboard_filter():
    res = client.get("/api/insights/dashboard?month=Sep-26")
    assert res.status_code == 200
    data = res.json()
    assert data["has_data"] is True
    assert data["selected_month"] == "2026-09"
    assert "monthly_stats" in data
    assert len(data["monthly_stats"]["targets"]) > 0
    print(f"[OK] Monthly dashboard filter (Sep-26) passed (Units: {data['production']['total_produced_units']}, Bottleneck: {data['production']['bottleneck']['section']})")

if __name__ == "__main__":
    print("\nRUNNING FULL FACTORY SUITE VERIFICATION...")
    test_api_health_and_config()
    test_snapshots_api()
    test_dashboard_insights_api()
    test_monthly_dashboard_filter()
    test_finished_goods_api()
    test_bom_specifications_api()
    test_materials_api()
    test_chat_api()
    test_trends_api()
    print("\nALL TESTS PASSED SUCCESSFULLY!")

