import sys
import json
sys.path.insert(0, ".")

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_factory_endpoints():
    print("--- 1. Testing GET /api/config ---")
    res = client.get("/api/config")
    assert res.status_code == 200, res.text
    print("Config:", res.json())

    print("\n--- 2. Testing GET /api/insights/dashboard (default) ---")
    res = client.get("/api/insights/dashboard")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["has_data"] is True
    print(f"Snapshot #{data['snapshot']['id']}, Month: {data['selected_month']}, Rating: {data['selected_rating']}")
    assert len(data["manufacturing_flow"]) == 7
    print(f"7 Manufacturing flow stages verified: {[s['stage_name'] for s in data['manufacturing_flow']]}")
    assert "daily_brief" in data
    assert "attention_items" in data["daily_brief"]
    print(f"Daily brief attention items: {len(data['daily_brief']['attention_items'])}")
    for item in data['daily_brief']['attention_items'][:3]:
        text = item.get("text", str(item)) if isinstance(item, dict) else str(item)
        print(f"  * {text.encode('ascii', 'replace').decode('ascii')}")

    print("\n--- 3. Testing GET /api/insights/dashboard with month=2026-09 & rating=63KVA ---")
    res = client.get("/api/insights/dashboard?month=2026-09&rating=63KVA")
    assert res.status_code == 200, res.text
    data_filtered = res.json()
    assert data_filtered["selected_month"] == "2026-09"
    assert data_filtered["selected_rating"] == "63KVA"
    print(f"Filtered Month: {data_filtered['selected_month']}, Rating: {data_filtered['selected_rating']}")

    print("\n--- 4. Testing GET /api/factory/material-readiness ---")
    res = client.get("/api/factory/material-readiness?rating=63KVA")
    assert res.status_code == 200, res.text
    readiness = res.json()
    assert "readiness_items" in readiness
    print(f"Readiness items for 63KVA: {len(readiness['readiness_items'])}")
    if readiness['readiness_items']:
        sample = readiness['readiness_items'][0]
        print(f"  Sample: {sample['material_name']} -> Required: {sample['required_qty']}, Available: {sample['available_qty']}, Status: {sample['status']}")

    print("\n--- 5. Testing GET /api/factory/wip ---")
    res = client.get("/api/factory/wip")
    assert res.status_code == 200, res.text
    wip = res.json()
    assert "physical_buffers" in wip
    print("Physical buffers:", wip["physical_buffers"])

    print("\n--- 6. Testing GET /api/factory/outsourcing ---")
    res = client.get("/api/factory/outsourcing")
    assert res.status_code == 200, res.text
    outsourcing = res.json()
    print("Outsourcing summary:", json.dumps(outsourcing, indent=2))

    print("\n--- 7. Testing POST /api/chat (Strict Read-Only AI) ---")
    chat_res = client.post("/api/chat", json={"question": "Where is the largest accumulation?"})
    assert chat_res.status_code == 200, chat_res.text
    ans = chat_res.json()
    print("Chat Answer:", ans["answer"].encode('ascii', 'replace').decode('ascii'))
    print("SQL Query Executed:", ans["sql_query"])

    print("\n=======================================================")
    print("ALL 7 FACTORY INTELLIGENCE API TESTS PASSED SUCCESSFULLY!")
    print("=======================================================")

if __name__ == "__main__":
    test_factory_endpoints()
