from typing import Dict, Any, List, Optional
import json
import datetime
from app.db import query_all, query_one

MONTH_NAME_TO_NUM = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06",
    "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"
}

def normalize_month_to_ym(val: Optional[str]) -> str:
    if not val or val.upper() in ("ALL", "YEARLY"):
        return "ALL"
    val = val.strip()
    if "-" in val:
        parts = val.split("-")
        if parts[0].capitalize() in MONTH_NAME_TO_NUM:
            m = MONTH_NAME_TO_NUM[parts[0].capitalize()]
            y = f"20{parts[1]}" if len(parts[1]) == 2 else parts[1]
            return f"{y}-{m}"
    return val

def format_month_label(ym_str: str) -> str:
    """Converts '2026-09' to 'Sep 2026'."""
    try:
        dt = datetime.datetime.strptime(ym_str, "%Y-%m")
        return dt.strftime("%b %Y")
    except Exception:
        return ym_str

class InsightsEngine:
    def __init__(self, snapshot_id: Optional[int] = None):
        if snapshot_id is None:
            latest = query_one("SELECT id FROM snapshots ORDER BY id DESC LIMIT 1")
            self.snapshot_id = latest["id"] if latest else None
        else:
            self.snapshot_id = snapshot_id

    def get_dashboard_insights(self, month: Optional[str] = None) -> Dict[str, Any]:
        if not self.snapshot_id:
            return {
                "error": "No data available. Please upload a workbook first.",
                "has_data": False
            }

        snapshot_info = query_one(
            "SELECT * FROM snapshots WHERE id = ?", (self.snapshot_id,)
        )
        
        # Check prior snapshot for delta calculations
        prior_snapshot = query_one(
            "SELECT id, uploaded_at FROM snapshots WHERE id < ? ORDER BY id DESC LIMIT 1",
            (self.snapshot_id,)
        )
        prior_snapshot_id = prior_snapshot["id"] if prior_snapshot else None

        # Detect all available months from production entries
        month_rows = query_all(
            """
            SELECT DISTINCT SUBSTR(date, 1, 7) as m_val 
            FROM production_entries 
            WHERE snapshot_id = ? 
            ORDER BY m_val ASC
            """,
            (self.snapshot_id,)
        )
        available_months = [
            {"id": "ALL", "label": "All Months (Full FY)"}
        ] + [
            {"id": r["m_val"], "label": format_month_label(r["m_val"])}
            for r in month_rows if r["m_val"]
        ]

        norm_m = normalize_month_to_ym(month)
        active_month = norm_m if (norm_m and any(m["id"] == norm_m for m in available_months)) else "ALL"

        stock_kpis = self._compute_stock_kpis(prior_snapshot_id)
        production_kpis = self._compute_production_kpis(prior_snapshot_id, active_month)
        monthly_stats = self._compute_monthly_matrix()
        finished_goods = self._compute_finished_goods()
        bom_specs = self._get_bom_specifications()
        consumption_kpis = self._compute_consumption_vs_norms()
        executive_summary = self._generate_executive_summary(stock_kpis, production_kpis, consumption_kpis, finished_goods)

        return {
            "has_data": True,
            "snapshot": {
                "id": self.snapshot_id,
                "filename": snapshot_info["filename"],
                "uploaded_at": snapshot_info["uploaded_at"],
                "prior_snapshot_id": prior_snapshot_id
            },
            "selected_month": active_month,
            "available_months": available_months,
            "executive_summary": executive_summary,
            "stock": stock_kpis,
            "production": production_kpis,
            "monthly_stats": monthly_stats,
            "finished_goods": finished_goods,
            "bom_specs": bom_specs,
            "consumption": consumption_kpis
        }

    def _compute_stock_kpis(self, prior_snapshot_id: Optional[int]) -> Dict[str, Any]:
        # Overall inventory valuation
        val_res = query_one(
            """
            SELECT 
                COUNT(*) as total_items,
                SUM(value) as total_value,
                SUM(received_qty) as total_received_qty,
                SUM(issued_qty) as total_issued_qty
            FROM stock_master_snapshots
            WHERE snapshot_id = ?
            """,
            (self.snapshot_id,)
        )
        total_value = val_res["total_value"] or 0.0
        total_items = val_res["total_items"] or 0

        # Detailed item balances joined with materials
        items = query_all(
            """
            SELECT 
                m.id as material_id,
                m.rating,
                m.material_name,
                m.material_type,
                m.size,
                m.unit,
                m.sheet_name,
                sms.opening_balance,
                sms.received_qty,
                sms.rate,
                sms.value,
                sms.issued_qty,
                sms.closing_balance
            FROM stock_master_snapshots sms
            JOIN materials m ON sms.material_id = m.id
            WHERE sms.snapshot_id = ?
            ORDER BY sms.closing_balance ASC
            """,
            (self.snapshot_id,)
        )

        zero_stock = []
        low_stock = []
        healthy_stock = []

        # Calculate run-rate from stock_transactions (last 30 days)
        run_rates = query_all(
            """
            SELECT 
                material_id,
                SUM(issued_qty) as total_issued_recent,
                COUNT(DISTINCT date) as days_with_activity
            FROM stock_transactions
            WHERE snapshot_id = ?
            GROUP BY material_id
            """,
            (self.snapshot_id,)
        )
        run_rate_map = {r["material_id"]: r["total_issued_recent"] for r in run_rates}

        for item in items:
            mat_id = item["material_id"]
            cl_bal = item["closing_balance"]
            recent_iss = run_rate_map.get(mat_id, 0.0)
            
            daily_burn = recent_iss / 30.0 if recent_iss > 0 else 0.0
            if daily_burn > 0:
                days_remaining = round(cl_bal / daily_burn, 1)
            else:
                days_remaining = 999.0 if cl_bal > 0 else 0.0

            item_data = {
                **item,
                "daily_burn_rate": round(daily_burn, 2),
                "days_remaining": days_remaining
            }

            if cl_bal <= 0.001:
                zero_stock.append(item_data)
            elif days_remaining <= 7.0 or cl_bal < 20.0:
                low_stock.append(item_data)
            else:
                healthy_stock.append(item_data)

        # Movers (highest issued and highest received)
        top_issued = sorted(items, key=lambda x: x["issued_qty"], reverse=True)[:5]
        top_received = sorted(items, key=lambda x: x["received_qty"], reverse=True)[:5]

        prior_value_delta = 0.0
        if prior_snapshot_id:
            prior_val = query_one(
                "SELECT SUM(value) as val FROM stock_master_snapshots WHERE snapshot_id = ?",
                (prior_snapshot_id,)
            )
            if prior_val and prior_val["val"]:
                prior_value_delta = total_value - prior_val["val"]

        return {
            "total_items": total_items,
            "total_value": round(total_value, 2),
            "prior_value_delta": round(prior_value_delta, 2),
            "zero_stock_count": len(zero_stock),
            "low_stock_count": len(low_stock),
            "zero_stock_items": zero_stock,
            "low_stock_items": low_stock,
            "top_issued": top_issued,
            "top_received": top_received,
            "all_items": items
        }

    def _compute_production_kpis(self, prior_snapshot_id: Optional[int], month_filter: str) -> Dict[str, Any]:
        params = [self.snapshot_id]
        month_clause = ""
        if month_filter != "ALL":
            month_clause = "AND date LIKE ?"
            params.append(f"{month_filter}%")

        # Production totals by section with optional month filter
        section_totals = query_all(
            f"""
            SELECT 
                section,
                SUM(units_produced) as total_units
            FROM production_entries
            WHERE snapshot_id = ? {month_clause}
            GROUP BY section
            ORDER BY total_units DESC
            """,
            tuple(params)
        )
        sec_map = {s["section"]: s["total_units"] for s in section_totals}

        # Production totals by rating
        rating_totals = query_all(
            f"""
            SELECT 
                rating,
                SUM(units_produced) as total_units
            FROM production_entries
            WHERE snapshot_id = ? {month_clause} AND section NOT IN ('TESTING FAILED')
            GROUP BY rating
            ORDER BY 
                CASE rating
                    WHEN '16KVA' THEN 1
                    WHEN '25KVA' THEN 2
                    WHEN '63KVA' THEN 3
                    WHEN '100KVA' THEN 4
                    WHEN '250KVA' THEN 5
                    ELSE 6
                END
            """,
            tuple(params)
        )

        # Quality metrics (Passed vs Failed)
        testing_passed = sec_map.get("TESTING PASSED", 0.0)
        testing_failed = sec_map.get("TESTING FAILED", 0.0)
        total_tested = testing_passed + testing_failed
        pass_rate = round((testing_passed / total_tested * 100), 1) if total_tested > 0 else 100.0

        # Assembly workflow stages
        flow_stages = [
            ("HV WINDING", sec_map.get("HV WINDING", 0.0)),
            ("LV WINDING", sec_map.get("LV WINDING", 0.0)),
            ("CORE COIL ASSEMBLY", sec_map.get("CORE COIL ASSEMBLY", 0.0)),
            ("TANKING", sec_map.get("TANKING", 0.0)),
            ("TESTING PASSED", sec_map.get("TESTING PASSED", 0.0)),
            ("PAINTING", sec_map.get("PAINTING", 0.0)),
            ("DISPATCH", sec_map.get("DISPATCH", 0.0)),
        ]

        bottleneck_candidates = [
            (name, qty) for name, qty in flow_stages 
            if name not in ("PAINTING", "DISPATCH") and qty > 0
        ]
        bottleneck_section = min(bottleneck_candidates, key=lambda x: x[1]) if bottleneck_candidates else ("None", 0)

        # Daily production timeline for chart (last 30 dates in current filter)
        daily_trends = query_all(
            f"""
            SELECT 
                date,
                SUM(units_produced) as total_daily_units
            FROM production_entries
            WHERE snapshot_id = ? {month_clause} AND section NOT IN ('TESTING FAILED')
            GROUP BY date
            ORDER BY date ASC
            LIMIT 30
            """,
            tuple(params)
        )

        total_dispatched = sec_map.get("DISPATCH", 0.0)
        total_produced_all = sum(s["total_units"] for s in section_totals if s["section"] != "TESTING FAILED")

        return {
            "total_produced_units": total_produced_all,
            "total_dispatched": total_dispatched,
            "sections": section_totals,
            "ratings": rating_totals,
            "quality": {
                "passed": testing_passed,
                "failed": testing_failed,
                "total_tested": total_tested,
                "pass_rate_pct": pass_rate
            },
            "bottleneck": {
                "section": bottleneck_section[0],
                "throughput": bottleneck_section[1],
                "reason": f"{bottleneck_section[0]} has the lowest throughput ({int(bottleneck_section[1])} units) along the primary assembly pipeline."
            },
            "flow_stages": flow_stages,
            "daily_trends": daily_trends
        }

    def _compute_monthly_matrix(self) -> Dict[str, Any]:
        """
        Computes monthly output breakdown across sections and ratings,
        joined with targets from PRODUCTION MASTER.
        """
        # Monthly actuals from production_entries
        monthly_actuals = query_all(
            """
            SELECT 
                SUBSTR(date, 1, 7) as month_key,
                section,
                rating,
                SUM(units_produced) as units
            FROM production_entries
            WHERE snapshot_id = ?
            GROUP BY month_key, section, rating
            ORDER BY month_key ASC, section ASC
            """,
            (self.snapshot_id,)
        )

        # Aggregate by month_key and section
        months_dict = {}
        for row in monthly_actuals:
            m_key = row["month_key"]
            sec = row["section"]
            rat = row["rating"]
            u = row["units"]

            if m_key not in months_dict:
                months_dict[m_key] = {
                    "month_key": m_key,
                    "month_label": format_month_label(m_key),
                    "sections": {},
                    "ratings": {},
                    "total_units": 0.0
                }

            months_dict[m_key]["sections"][sec] = months_dict[m_key]["sections"].get(sec, 0.0) + u
            months_dict[m_key]["ratings"][rat] = months_dict[m_key]["ratings"].get(rat, 0.0) + u
            if sec != "TESTING FAILED":
                months_dict[m_key]["total_units"] += u

        # Order for Financial Year months
        fy_months = ['Apr-26', 'May-26', 'Jun-26', 'Jul-26', 'Aug-26', 'Sep-26', 'Oct-26', 'Nov-26', 'Dec-26', 'Jan-27', 'Feb-27', 'Mar-27', 'YEARLY']

        # Targets from production_monthly_targets ordered by Financial Year
        targets_rows = query_all(
            """
            SELECT 
                month,
                section,
                rating,
                target_units,
                actual_units,
                variance_units
            FROM production_monthly_targets
            WHERE snapshot_id = ?
            ORDER BY 
                CASE month
                    WHEN 'Apr-26' THEN 1
                    WHEN 'May-26' THEN 2
                    WHEN 'Jun-26' THEN 3
                    WHEN 'Jul-26' THEN 4
                    WHEN 'Aug-26' THEN 5
                    WHEN 'Sep-26' THEN 6
                    WHEN 'Oct-26' THEN 7
                    WHEN 'Nov-26' THEN 8
                    WHEN 'Dec-26' THEN 9
                    WHEN 'Jan-27' THEN 10
                    WHEN 'Feb-27' THEN 11
                    WHEN 'Mar-27' THEN 12
                    WHEN 'YEARLY' THEN 13
                    ELSE 14
                END, section, rating
            """,
            (self.snapshot_id,)
        )

        # Monthly summary rollup (Target vs Actual vs Variance by month and section)
        monthly_summary = {}
        section_summary = {}
        for r in targets_rows:
            m = r["month"]
            sec = r["section"]
            t = r["target_units"] or 0.0
            a = r["actual_units"] or 0.0
            v = r["variance_units"] or 0.0

            if m not in monthly_summary:
                monthly_summary[m] = {
                    "month": m,
                    "target": 0.0,
                    "actual": 0.0,
                    "variance": 0.0,
                    "sections": {}
                }
            monthly_summary[m]["target"] += t
            monthly_summary[m]["actual"] += a
            monthly_summary[m]["variance"] += v

            if sec not in monthly_summary[m]["sections"]:
                monthly_summary[m]["sections"][sec] = {"target": 0.0, "actual": 0.0, "variance": 0.0}
            monthly_summary[m]["sections"][sec]["target"] += t
            monthly_summary[m]["sections"][sec]["actual"] += a
            monthly_summary[m]["sections"][sec]["variance"] += v

            if sec not in section_summary:
                section_summary[sec] = {}
            if m not in section_summary[sec]:
                section_summary[sec][m] = {"target": 0.0, "actual": 0.0, "variance": 0.0}
            section_summary[sec][m]["target"] += t
            section_summary[sec][m]["actual"] += a
            section_summary[sec][m]["variance"] += v

        return {
            "matrix": list(months_dict.values()),
            "fy_months": fy_months,
            "monthly_summary": monthly_summary,
            "section_summary": section_summary,
            "targets": targets_rows
        }

    def _compute_finished_goods(self) -> Dict[str, Any]:
        """
        Extracts finished transformers, sub-assemblies (coils, CCAs),
        and outsourced inventory balances.
        """
        items = query_all(
            """
            SELECT 
                m.id as material_id,
                m.rating,
                m.material_name,
                m.material_type,
                m.sheet_name,
                sms.opening_balance,
                sms.received_qty,
                sms.issued_qty,
                sms.closing_balance,
                sms.rate,
                sms.value
            FROM stock_master_snapshots sms
            JOIN materials m ON sms.material_id = m.id
            WHERE sms.snapshot_id = ?
              AND (
                  m.material_type IN ('FINISHED', 'TRANSFORMER', 'CCA')
                  OR m.sheet_name LIKE '%FINISHED%'
                  OR m.sheet_name LIKE '%OUTSOURCED%'
                  OR m.sheet_name LIKE '%FIN%'
              )
            ORDER BY 
                CASE m.rating
                    WHEN '16KVA' THEN 1
                    WHEN '25KVA' THEN 2
                    WHEN '63KVA' THEN 3
                    WHEN '100KVA' THEN 4
                    WHEN '250KVA' THEN 5
                    ELSE 6
                END, m.material_name
            """,
            (self.snapshot_id,)
        )

        finished_tr = [x for x in items if "FINISHED TR" in x["sheet_name"] or "FINISHED TRANSFORMER" in x["material_name"]]
        outsourced = [x for x in items if "OUTSOURCED" in x["sheet_name"] or "OUTSOURCED" in x["material_name"]]
        cca_fin = [x for x in items if "CCA FIN" in x["sheet_name"] or ("CCA" in x["material_name"] and "OUTSOURCED" not in x["sheet_name"])]
        hv_coils = [x for x in items if "HV COIL FIN" in x["sheet_name"]]
        lv_coils = [x for x in items if "LV COIL FIN" in x["sheet_name"]]

        return {
            "total_finished_transformers": sum(x["closing_balance"] for x in finished_tr),
            "total_cca_ready": sum(x["closing_balance"] for x in cca_fin),
            "total_hv_coils_ready": sum(x["closing_balance"] for x in hv_coils),
            "total_lv_coils_ready": sum(x["closing_balance"] for x in lv_coils),
            "total_outsourced_ready": sum(x["closing_balance"] for x in outsourced),
            "finished_transformers": finished_tr,
            "outsourced_units": outsourced,
            "cca_fin": cca_fin,
            "hv_coils": hv_coils,
            "lv_coils": lv_coils
        }

    def _get_bom_specifications(self) -> List[Dict[str, Any]]:
        """Returns standard BOM specifications from CONSUMPTION sheet."""
        return query_all(
            """
            SELECT 
                rating, material_name, material_type, size, 
                pieces_count, qty_per_coil, qty_per_transformer, unit
            FROM bom_specifications
            WHERE snapshot_id = ?
            ORDER BY 
                CASE rating
                    WHEN '16KVA' THEN 1
                    WHEN '25KVA' THEN 2
                    WHEN '63KVA' THEN 3
                    WHEN '100KVA' THEN 4
                    WHEN '250KVA' THEN 5
                    ELSE 6
                END, id
            """,
            (self.snapshot_id,)
        )

    def _compute_consumption_vs_norms(self) -> Dict[str, Any]:
        """
        Calculates Actual Issued vs Expected Norm (Norm Qty * Units Produced of that Rating).
        """
        norms = query_all(
            """
            SELECT rating, material_name, qty_per_transformer, unit
            FROM consumption_norms
            WHERE snapshot_id = ? OR snapshot_id IS NULL
            """,
            (self.snapshot_id,)
        )
        if not norms:
            return {"variances": [], "has_norms": False}

        prod_by_rating = query_all(
            """
            SELECT rating, SUM(units_produced) as units
            FROM production_entries
            WHERE snapshot_id = ? AND section IN ('CORE COIL ASSEMBLY', 'TANKING', 'TESTING PASSED')
            GROUP BY rating
            """,
            (self.snapshot_id,)
        )
        prod_map = {p["rating"]: (p["units"] / 3.0) for p in prod_by_rating}

        actual_issued_rows = query_all(
            """
            SELECT 
                m.rating,
                m.material_name,
                m.unit,
                SUM(sms.issued_qty) as total_actual_issued
            FROM stock_master_snapshots sms
            JOIN materials m ON sms.material_id = m.id
            WHERE sms.snapshot_id = ?
            GROUP BY m.rating, m.material_name, m.unit
            """,
            (self.snapshot_id,)
        )
        actual_map = {(r["rating"], r["material_name"]): r["total_actual_issued"] for r in actual_issued_rows}

        variances = []
        for norm in norms:
            rating = norm["rating"]
            mat_name = norm["material_name"]
            norm_per_unit = norm["qty_per_transformer"]
            unit = norm["unit"]

            units_prod = prod_map.get(rating, 0.0)
            expected_consumption = units_prod * norm_per_unit
            actual_consumption = actual_map.get((rating, mat_name), 0.0)

            if expected_consumption > 0:
                variance_pct = round(((actual_consumption - expected_consumption) / expected_consumption) * 100.0, 1)
            else:
                variance_pct = 0.0

            status = "NORMAL"
            if variance_pct > 10.0:
                status = "OVER_CONSUMED"
            elif variance_pct < -15.0 and actual_consumption > 0:
                status = "UNDER_CONSUMED"

            variances.append({
                "rating": rating,
                "material_name": mat_name,
                "unit": unit,
                "norm_per_transformer": norm_per_unit,
                "units_produced": round(units_prod, 1),
                "expected_qty": round(expected_consumption, 1),
                "actual_qty": round(actual_consumption, 1),
                "variance_pct": variance_pct,
                "status": status
            })

        variances.sort(key=lambda x: x["variance_pct"], reverse=True)
        return {
            "has_norms": True,
            "variances": variances,
            "over_consumed_count": sum(1 for v in variances if v["status"] == "OVER_CONSUMED"),
            "under_consumed_count": sum(1 for v in variances if v["status"] == "UNDER_CONSUMED")
        }

    def _generate_executive_summary(
        self, stock: Dict[str, Any], prod: Dict[str, Any], cons: Dict[str, Any], fin: Dict[str, Any]
    ) -> Dict[str, Any]:
        bullets = []
        action_required = False

        # Stock summary
        zero_count = stock.get("zero_stock_count", 0)
        low_count = stock.get("low_stock_count", 0)
        tot_val = stock.get("total_value", 0.0)

        # Finished Goods highlight
        fin_tr = fin.get("total_finished_transformers", 0)
        cca_ready = fin.get("total_cca_ready", 0)
        bullets.append(f"Finished Goods Stock: {int(fin_tr)} finished transformers and {int(cca_ready)} core-coil assemblies ready in stock.")

        if zero_count > 0:
            zero_names = ", ".join([f"{item['rating']} {item['material_name']}" for item in stock["zero_stock_items"][:3]])
            bullets.append(f"CRITICAL: {zero_count} material(s) are completely out of stock ({zero_names}). Immediate procurement needed.")
            action_required = True
        elif low_count > 0:
            bullets.append(f"WARNING: {low_count} material(s) have under 7 days of supply remaining.")
            action_required = True

        # Bottleneck summary
        bottleneck = prod.get("bottleneck", {})
        if bottleneck.get("section") and bottleneck["section"] != "None":
            bullets.append(
                f"Bottleneck Alert: {bottleneck['section']} has the lowest throughput ({int(bottleneck['throughput'])} units) restricting downstream assembly."
            )

        # Quality status
        quality = prod.get("quality", {})
        pass_rate = quality.get("pass_rate_pct", 100.0)
        if quality.get("total_tested", 0) > 0 and pass_rate < 95.0:
            bullets.append(f"Testing Quality Alert: Quality pass rate is currently {pass_rate}%.")
            action_required = True

        # Consumption summary
        over_cons = cons.get("over_consumed_count", 0)
        if over_cons > 0:
            bullets.append(
                f"Consumption Variance: {over_cons} material(s) exceed standard BOM norms by over 10%."
            )

        headline = "Immediate Shop Floor Attention Required" if action_required else "Factory Operations Running Smoothly"

        return {
            "headline": headline,
            "action_required": action_required,
            "bullets": bullets,
            "total_inventory_value": f"₹{tot_val:,.2f}" if tot_val > 0 else "Unpriced",
            "quality_pass_rate": f"{pass_rate}%",
            "key_bottleneck": bottleneck.get("section", "None")
        }

    def get_time_series_trends(self, material_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        snapshots = query_all("SELECT id, filename, uploaded_at FROM snapshots ORDER BY id ASC")
        if not snapshots:
            return {"snapshots": [], "stock_trends": {}, "prod_trends": {}}

        snapshot_ids = [s["id"] for s in snapshots]
        prod_trends = {}
        for s_id in snapshot_ids:
            rows = query_all(
                """
                SELECT section, SUM(units_produced) as total
                FROM production_entries
                WHERE snapshot_id = ?
                GROUP BY section
                """,
                (s_id,)
            )
            for r in rows:
                sec = r["section"]
                if sec not in prod_trends:
                    prod_trends[sec] = []
                prod_trends[sec].append({"snapshot_id": s_id, "units": r["total"]})

        stock_trends = {}
        mat_filter = ""
        params = []
        if material_ids:
            placeholders = ",".join("?" * len(material_ids))
            mat_filter = f"WHERE m.id IN ({placeholders})"
            params = material_ids

        stock_rows = query_all(
            f"""
            SELECT 
                sms.snapshot_id,
                m.id as material_id,
                m.rating,
                m.material_name,
                sms.closing_balance,
                sms.value
            FROM stock_master_snapshots sms
            JOIN materials m ON sms.material_id = m.id
            {mat_filter}
            ORDER BY sms.snapshot_id ASC
            """,
            tuple(params)
        )
        for r in stock_rows:
            key = f"{r['rating']} - {r['material_name']}"
            if key not in stock_trends:
                stock_trends[key] = []
            stock_trends[key].append({
                "snapshot_id": r["snapshot_id"],
                "closing_balance": r["closing_balance"],
                "value": r["value"]
            })

        return {
            "snapshots": snapshots,
            "stock_trends": stock_trends,
            "prod_trends": prod_trends
        }
