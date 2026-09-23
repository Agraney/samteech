import os
import re
import json
from typing import Dict, Any, List, Optional
from app.config import GEMINI_API_KEY, LLM_MODEL
from app.db import query_all, query_one, get_db

SCHEMA_PROMPT = """
You are an expert SQL analyst for a transformer manufacturing factory.
You have access to a local SQLite database with normalized operational data from the factory's Excel sheets.

Database Tables:
1. materials (id, rating, sheet_name, material_name, material_type, size, unit, min_reorder_level)
   - rating: '16KVA', '25KVA', '63KVA', '100KVA', '250KVA', or 'COMMON'
   - material_name: e.g. 'HV Copper Wire', 'LV Copper Strip', 'Transformer Oil IS 335', 'Transformer Tank 63KVA'

2. stock_master_snapshots (id, snapshot_id, material_id, opening_balance, received_qty, rate, value, issued_qty, closing_balance)
   - Contains latest rollup inventory counts for each material per snapshot.

3. stock_transactions (id, snapshot_id, material_id, s_no, date, opening_balance, received_qty, rate, value, supplier_name, invoice_no, issued_qty, issued_to_section, closing_balance, remarks)
   - Granular ledger entries with dates, received_qty, issued_qty, supplier, invoice, and section issued to.

4. production_entries (id, snapshot_id, date, section, rating, units_produced)
   - Daily production logs.
   - section values: 'HV WINDING', 'LV WINDING', 'CORE COIL ASSEMBLY', 'TANKING', 'TESTING PASSED', 'TESTING FAILED', 'PAINTING', 'DISPATCH'
   - rating values: '16KVA', '25KVA', '63KVA', '100KVA', '250KVA'

5. consumption_norms (id, snapshot_id, rating, material_name, qty_per_transformer, unit)
   - Standard BOM norms per transformer from the BASIC sheet.

6. snapshots (id, filename, file_hash, uploaded_at, file_path, notes)
   - Tracked uploads over time. Current/latest snapshot is MAX(id).

CRITICAL OPERATIONAL RULES:
- PRODUCTION COUNTS / OUTPUT (e.g. HV Winding count, LV Winding count, Tanking count):
  MUST be queried from 'production_entries' (sections: 'HV WINDING', 'LV WINDING', 'CORE COIL ASSEMBLY', 'TANKING', 'TESTING PASSED', 'TESTING FAILED', 'PAINTING', 'DISPATCH').
- STOCK / INVENTORY ON HAND:
  Comes from 'stock_master_snapshots' / 'materials'.
  Note that finished goods & assemblies (e.g. 'HV COIL (FINISHED)', 'LV COIL (FINISHED)', 'CCA (FINISHED)', 'FINISHED TRANSFORMER') represent units currently sitting in warehouse stock (closing balance), NOT the production output. Never sum finished stock balances into production counts.

Instructions:
- Write ONLY a valid SQLite SELECT query.
- Always use the latest snapshot unless the user asks for historical comparison across snapshots.
- Do NOT use any DROP, DELETE, INSERT, or UPDATE statements.
- Return ONLY the SQL query enclosed in ```sql ... ``` code block.
"""


def is_safe_sql(sql: str) -> bool:
    cleaned = sql.strip().upper()
    # Must start with SELECT or WITH
    if not (cleaned.startswith("SELECT") or cleaned.startswith("WITH")):
        return False
    # Check for forbidden mutation keywords
    forbidden = ["DELETE", "UPDATE", "INSERT", "DROP", "ALTER", "TRUNCATE", "REPLACE", "CREATE", "EXEC"]
    for word in forbidden:
        pattern = rf"\b{word}\b"
        if re.search(pattern, cleaned):
            return False
    return True

class QAAssistant:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or GEMINI_API_KEY
        self.client = None
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"Warning: Could not initialize Gemini client: {e}")

    def answer_question(self, question: str, session_id: str = "default") -> Dict[str, Any]:
        latest_snap = query_one("SELECT id FROM snapshots ORDER BY id DESC LIMIT 1")
        if not latest_snap:
            return {
                "answer": "No factory data has been uploaded yet. Please upload an Excel workbook (.xlsm) to get started.",
                "sql_query": None,
                "data": []
            }
        latest_snapshot_id = latest_snap["id"]

        sql_query = None
        if self.client:
            try:
                sql_query = self._generate_sql_with_gemini(question, latest_snapshot_id)
            except Exception as e:
                print(f"Gemini SQL generation error: {e}, falling back to local engine")
                sql_query = None

        if not sql_query:
            sql_query = self._fallback_sql_generator(question, latest_snapshot_id)

        # Execute SQL safely
        if not is_safe_sql(sql_query):
            return {
                "answer": "Security warning: generated query contained non-permitted database operations.",
                "sql_query": sql_query,
                "data": []
            }

        try:
            results = query_all(sql_query)
        except Exception as e:
            return {
                "answer": f"Encountered an error executing SQL query: {e}",
                "sql_query": sql_query,
                "data": []
            }

        # Format final answer
        if self.client and results:
            try:
                answer = self._synthesize_answer_with_gemini(question, sql_query, results)
            except Exception:
                answer = self._format_local_answer(question, results)
        else:
            answer = self._format_local_answer(question, results)

        # Store in chat history
        try:
            with get_db() as conn:
                conn.execute(
                    """
                    INSERT INTO chat_history (session_id, role, content, sql_query, sql_results_json)
                    VALUES (?, 'user', ?, NULL, NULL)
                    """,
                    (session_id, question)
                )
                conn.execute(
                    """
                    INSERT INTO chat_history (session_id, role, content, sql_query, sql_results_json)
                    VALUES (?, 'assistant', ?, ?, ?)
                    """,
                    (session_id, answer, sql_query, json.dumps(results[:50]))
                )
        except Exception as e:
            print(f"Failed to record chat history: {e}")

        return {
            "answer": answer,
            "sql_query": sql_query,
            "data": results[:50] # cap preview to 50 rows
        }

    def _generate_sql_with_gemini(self, question: str, latest_snapshot_id: int) -> str:
        prompt = f"""
{SCHEMA_PROMPT}

Current latest snapshot_id is: {latest_snapshot_id}

User Question: "{question}"

Write the exact SQLite query to answer this question.
"""
        response = self.client.models.generate_content(
            model=LLM_MODEL,
            contents=prompt,
        )
        text = response.text or ""
        match = re.search(r"```sql(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        # Fallback if no code block
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for l in lines:
            if l.upper().startswith("SELECT") or l.upper().startswith("WITH"):
                return l
        return text.strip()

    def _synthesize_answer_with_gemini(self, question: str, sql: str, results: List[Dict[str, Any]]) -> str:
        prompt = f"""
You are the factory manager's operational assistant.
The user asked: "{question}"
We ran this SQL query:
{sql}

Database results (JSON):
{json.dumps(results[:30], indent=2)}

Synthesize a clear, concise, direct answer for the factory owner.
- Include the exact numbers, ratings, units, and material names.
- If there are multiple items, format with a brief markdown table or bullet points.
- Do not make up any numbers; ground your response strictly in the query results.
"""
        response = self.client.models.generate_content(
            model=LLM_MODEL,
            contents=prompt,
        )
        return response.text.strip()

    def _fallback_sql_generator(self, question: str, snapshot_id: int) -> str:
        q = question.lower()

        # 1. HV Wire / specific material queries for rating (e.g. "how much HV wire do we have left for 63KVA?")
        rating_match = re.search(r"\b(16|25|63|100|250)\s*kva\b", q)
        found_rating = f"{rating_match.group(1)}KVA" if rating_match else None

        # Winding count / stage production queries (e.g. "what is the HV winding count", "how many HV coils produced")
        if "winding" in q or ("hv" in q and "coil" in q and "stock" not in q) or ("lv" in q and "coil" in q and "stock" not in q):
            sec = "LV WINDING" if "lv" in q else ("HV WINDING" if "hv" in q else None)
            sec_clause = f"AND section = '{sec}'" if sec else ""
            rating_clause = f"AND rating = '{found_rating}'" if found_rating else ""
            return f"""
            SELECT 
                section,
                rating,
                SUM(units_produced) as total_units_produced
            FROM production_entries
            WHERE snapshot_id = {snapshot_id}
              {sec_clause}
              {rating_clause}
            GROUP BY section, rating
            ORDER BY total_units_produced DESC;
            """.strip()

        if "wire" in q or "hv wire" in q or "copper" in q:
            rating_clause = f"AND m.rating = '{found_rating}'" if found_rating else ""

            return f"""
            SELECT 
                m.rating,
                m.material_name,
                m.size,
                m.unit,
                sms.closing_balance,
                sms.value as total_value_rs
            FROM stock_master_snapshots sms
            JOIN materials m ON sms.material_id = m.id
            WHERE sms.snapshot_id = {snapshot_id}
              AND (m.material_name LIKE '%Wire%' OR m.material_name LIKE '%Strip%')
              {rating_clause}
            ORDER BY sms.closing_balance ASC;
            """.strip()

        # 2. Oil balance / consumption
        if "oil" in q:
            if "consumption" in q or "issued" in q or "use" in q or "change" in q or "weeks" in q or "month" in q:
                return f"""
                SELECT 
                    st.date,
                    m.material_name,
                    st.issued_qty,
                    st.issued_to_section,
                    st.closing_balance
                FROM stock_transactions st
                JOIN materials m ON st.material_id = m.id
                WHERE st.snapshot_id = {snapshot_id}
                  AND m.material_name LIKE '%Oil%'
                  AND st.issued_qty > 0
                ORDER BY st.date DESC
                LIMIT 15;
                """.strip()
            else:
                return f"""
                SELECT 
                    m.rating,
                    m.material_name,
                    m.unit,
                    sms.closing_balance,
                    sms.rate as unit_rate_rs,
                    sms.value as total_value_rs
                FROM stock_master_snapshots sms
                JOIN materials m ON sms.material_id = m.id
                WHERE sms.snapshot_id = {snapshot_id}
                  AND m.material_name LIKE '%Oil%';
                """.strip()

        # 3. Bottleneck / behind / slow section
        if "bottleneck" in q or "behind" in q or "slowest" in q or "lowest" in q:
            return f"""
            SELECT 
                section,
                SUM(units_produced) as total_units_produced
            FROM production_entries
            WHERE snapshot_id = {snapshot_id}
              AND section NOT IN ('TESTING FAILED')
            GROUP BY section
            ORDER BY total_units_produced ASC;
            """.strip()

        # 4. Out of stock / zero stock / low stock
        if "zero" in q or "out of stock" in q or "low stock" in q or "reorder" in q or "shortage" in q:
            return f"""
            SELECT 
                m.rating,
                m.material_name,
                m.unit,
                sms.closing_balance,
                sms.rate as unit_rate_rs,
                sms.value as total_value_rs
            FROM stock_master_snapshots sms
            JOIN materials m ON sms.material_id = m.id
            WHERE sms.snapshot_id = {snapshot_id}
              AND sms.closing_balance <= 20.0
            ORDER BY sms.closing_balance ASC;
            """.strip()

        # 5. Production output by rating or section
        if "production" in q or "produced" in q or "output" in q or "units" in q:
            if found_rating:
                return f"""
                SELECT 
                    section,
                    rating,
                    SUM(units_produced) as total_units
                FROM production_entries
                WHERE snapshot_id = {snapshot_id}
                  AND rating = '{found_rating}'
                GROUP BY section, rating
                ORDER BY total_units DESC;
                """.strip()
            else:
                return f"""
                SELECT 
                    rating,
                    SUM(units_produced) as total_units
                FROM production_entries
                WHERE snapshot_id = {snapshot_id}
                  AND section NOT IN ('TESTING FAILED')
                GROUP BY rating
                ORDER BY total_units DESC;
                """.strip()

        # 6. Testing pass / fail rate
        if "testing" in q or "pass rate" in q or "failed" in q or "quality" in q:
            return f"""
            SELECT 
                section,
                SUM(units_produced) as total_units
            FROM production_entries
            WHERE snapshot_id = {snapshot_id}
              AND section IN ('TESTING PASSED', 'TESTING FAILED')
            GROUP BY section;
            """.strip()

        # Default query: summary of materials
        return f"""
        SELECT 
            m.rating,
            m.material_name,
            m.unit,
            sms.closing_balance,
            sms.value as total_value_rs
        FROM stock_master_snapshots sms
        JOIN materials m ON sms.material_id = m.id
        WHERE sms.snapshot_id = {snapshot_id}
        ORDER BY sms.closing_balance ASC
        LIMIT 10;
        """.strip()

    def _format_local_answer(self, question: str, results: List[Dict[str, Any]]) -> str:
        if not results:
            return "No matching records found in the current workbook snapshot."

        # Generate a clean tabular response
        keys = list(results[0].keys())
        header = " | ".join(keys)
        separator = " | ".join(["---"] * len(keys))
        rows = []
        for r in results[:10]:
            row_str = " | ".join([str(r.get(k, "")) for k in keys])
            rows.append(row_str)
        table_md = f"| {header} |\n| {separator} |\n" + "\n".join([f"| {row} |" for row in rows])

        count_msg = f"Found **{len(results)}** result(s) based on your question:"
        return f"{count_msg}\n\n{table_md}"
