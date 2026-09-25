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
    AVAILABLE_RATINGS = ['ALL', '16KVA', '25KVA', '63KVA', '100KVA', '250KVA']

    def __init__(self, snapshot_id: Optional[int] = None):
        if snapshot_id is None:
            latest = query_one("SELECT id FROM snapshots ORDER BY id DESC LIMIT 1")
            self.snapshot_id = latest["id"] if latest else None
        else:
            self.snapshot_id = snapshot_id

    def get_dashboard_insights(self, month: Optional[str] = None, rating: Optional[str] = None) -> Dict[str, Any]:
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
        active_rating = rating if (rating and rating.upper() in self.AVAILABLE_RATINGS) else "ALL"

        # Compute core domains
        stock_kpis = self._compute_stock_kpis(prior_snapshot_id, active_rating)
        production_kpis = self._compute_production_kpis(prior_snapshot_id, active_month, active_rating)
        wip_data = self._compute_wip_and_accumulation(active_month, active_rating)
        monthly_stats = self._compute_monthly_matrix(active_rating)
        manufacturing_flow = self._compute_manufacturing_flow(production_kpis, monthly_stats, wip_data, active_month, active_rating)
        material_readiness = self._compute_material_readiness(active_rating)
        outsourcing = self._compute_outsourcing_summary()
        ratings_matrix = self._compute_ratings_matrix(active_month)
        quality_kpis = self._compute_quality_kpis(active_month, active_rating)
        finished_goods = self._compute_finished_goods(active_rating)
        bom_specs = self._get_bom_specifications(active_rating)
        consumption_kpis = self._compute_consumption_vs_norms(active_rating)
        
        daily_brief = self._generate_daily_brief(stock_kpis, production_kpis, wip_data, quality_kpis, monthly_stats, material_readiness)
        executive_summary = self._generate_executive_summary(stock_kpis, production_kpis, consumption_kpis, finished_goods, wip_data, material_readiness)

        lineage = {
            "valStockTotal": "STOCK MASTER (Columns: Closing Balance × Unit Rate = Total Valuation)",
            "valStockAlerts": "STOCK MASTER (Materials where Closing Balance <= 0 or Days Remaining <= 7d)",
            "valProdTotal": "PROD_HV WINDING to PROD_DISPATCH (Daily Units Output rows 3–367)",
            "valDispatchTotal": "PROD_DISPATCH (Completed units shipped to customers)",
            "valQualityRate": "PROD_TESTING PASSED / (TESTING PASSED + TESTING FAILED) * 100",
            "valWipTotal": "STK_*_HV COIL FIN, STK_*_LV COIL FIN, STK_*_CCA FIN & Stage Accumulations",
            "valBottleneckSection": "Calculated: Minimum throughput stage along 7-stage assembly pipeline",
            "manufacturingFlow": "PROD_* Daily Logs joined with PRODUCTION MASTER Targets",
            "materialReadiness": "CONSUMPTION BOM Norms × Target Units vs STK_* Closing Balances",
            "outsourcingSummary": "STK_*_OUTSOURCED TR and STK_*_OUTSOURCED CCA Closing Balances",
            "monthlyTargets": "PRODUCTION MASTER (Monthly Target, Actual, Variance across FY)",
            "consumptionNorms": "CONSUMPTION / BASIC Norms vs STK_* Issued Quantities"
        }

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
            "selected_rating": active_rating,
            "available_ratings": self.AVAILABLE_RATINGS,
            "executive_summary": executive_summary,
            "daily_brief": daily_brief,
            "lineage": lineage,
            "stock": stock_kpis,
            "production": production_kpis,
            "manufacturing_flow": manufacturing_flow,
            "wip": wip_data,
            "material_readiness": material_readiness,
            "outsourcing": outsourcing,
            "ratings_matrix": ratings_matrix,
            "quality": quality_kpis,
            "monthly_stats": monthly_stats,
            "finished_goods": finished_goods,
            "bom_specs": bom_specs,
            "consumption": consumption_kpis
        }

    def _compute_stock_kpis(self, prior_snapshot_id: Optional[int], rating_filter: str = "ALL") -> Dict[str, Any]:
        rating_clause = "AND m.rating = ?" if rating_filter != "ALL" else ""
        params = [self.snapshot_id]
        if rating_filter != "ALL":
            params.append(rating_filter)

        # Overall inventory valuation
        val_res = query_one(
            f"""
            SELECT 
                COUNT(*) as total_items,
                SUM(sms.value) as total_value,
                SUM(sms.received_qty) as total_received_qty,
                SUM(sms.issued_qty) as total_issued_qty
            FROM stock_master_snapshots sms
            JOIN materials m ON sms.material_id = m.id
            WHERE sms.snapshot_id = ? {rating_clause}
            """,
            tuple(params)
        )
        total_value = (val_res["total_value"] or 0.0) if val_res else 0.0
        total_items = (val_res["total_items"] or 0) if val_res else 0

        # Detailed item balances joined with materials
        items = query_all(
            f"""
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
            WHERE sms.snapshot_id = ? {rating_clause}
            ORDER BY sms.closing_balance ASC
            """,
            tuple(params)
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
            "all_items": items,
            "lineage": "STOCK MASTER & STK_* Ledgers"
        }

    def _compute_production_kpis(self, prior_snapshot_id: Optional[int], month_filter: str, rating_filter: str = "ALL") -> Dict[str, Any]:
        params = [self.snapshot_id]
        clauses = []
        if month_filter != "ALL":
            clauses.append("date LIKE ?")
            params.append(f"{month_filter}%")
        if rating_filter != "ALL":
            clauses.append("rating = ?")
            params.append(rating_filter)
        month_clause = ("AND " + " AND ".join(clauses)) if clauses else ""

        # Production totals by section with optional month/rating filter
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

        # Daily production timeline for chart
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
            "daily_trends": daily_trends,
            "lineage": "PROD_HV WINDING through PROD_DISPATCH (Rows 3–367)"
        }

    def _compute_wip_and_accumulation(self, month_filter: str = "ALL", rating_filter: str = "ALL", month: Optional[str] = None, rating: Optional[str] = None) -> Dict[str, Any]:
        if month:
            month_filter = month
        if rating:
            rating_filter = rating
        """
        Calculates stage-to-stage production accumulation along the manufacturing flow:
        HV Winding -> LV Winding -> Core Coil Assembly (CCA) -> Tanking -> Testing -> Painting -> Dispatch.
        Also calculates physical sub-assembly inventory sitting in the factory (Coils, CCAs, etc.).
        """
        params = [self.snapshot_id]
        clauses = []
        if month_filter != "ALL":
            clauses.append("date LIKE ?")
            params.append(f"{month_filter}%")
        if rating_filter != "ALL":
            clauses.append("rating = ?")
            params.append(rating_filter)
        where_extra = ("AND " + " AND ".join(clauses)) if clauses else ""

        prod_rows = query_all(
            f"""
            SELECT section, SUM(units_produced) as total_units
            FROM production_entries
            WHERE snapshot_id = ? {where_extra}
            GROUP BY section
            """,
            tuple(params)
        )
        sec_map = {r["section"]: r["total_units"] for r in prod_rows}

        hv = sec_map.get("HV WINDING", 0.0)
        lv = sec_map.get("LV WINDING", 0.0)
        cca = sec_map.get("CORE COIL ASSEMBLY", 0.0)
        tank = sec_map.get("TANKING", 0.0)
        tested_passed = sec_map.get("TESTING PASSED", 0.0)
        tested_failed = sec_map.get("TESTING FAILED", 0.0)
        painted = sec_map.get("PAINTING", 0.0)
        dispatched = sec_map.get("DISPATCH", 0.0)

        accumulations = [
            {
                "from_stage": "HV Winding",
                "to_stage": "Core Coil Assembly",
                "output_prev": hv,
                "output_next": cca,
                "accumulation": round(hv - cca, 1),
                "description": f"Accumulation of completed HV coils ({int(hv)} units) before Core Coil Assembly ({int(cca)} units)."
            },
            {
                "from_stage": "LV Winding",
                "to_stage": "Core Coil Assembly",
                "output_prev": lv,
                "output_next": cca,
                "accumulation": round(lv - cca, 1),
                "description": f"Accumulation of completed LV coils ({int(lv)} units) before Core Coil Assembly ({int(cca)} units)."
            },
            {
                "from_stage": "Core Coil Assembly",
                "to_stage": "Tanking",
                "output_prev": cca,
                "output_next": tank,
                "accumulation": round(cca - tank, 1),
                "description": f"Accumulation of assembled core-coils ({int(cca)} units) waiting to be tanked and oil-filled ({int(tank)} units)."
            },
            {
                "from_stage": "Tanking",
                "to_stage": "Testing Inspection",
                "output_prev": tank,
                "output_next": tested_passed + tested_failed,
                "accumulation": round(tank - (tested_passed + tested_failed), 1),
                "description": f"Tanked transformers ({int(tank)} units) waiting for electrical testing."
            },
            {
                "from_stage": "Testing Passed",
                "to_stage": "Painting",
                "output_prev": tested_passed,
                "output_next": painted,
                "accumulation": round(tested_passed - painted, 1),
                "description": f"Passed inspection units ({int(tested_passed)} units) awaiting final painting."
            },
            {
                "from_stage": "Painting",
                "to_stage": "Dispatch",
                "output_prev": painted,
                "output_next": dispatched,
                "accumulation": round(painted - dispatched, 1),
                "description": f"Painted units ({int(painted)} units) awaiting customer dispatch."
            }
        ]

        # Physical Sub-Assembly Warehouse Stock (WIP Buffer on Floor)
        fin_rating_clause = "AND m.rating = ?" if rating_filter != "ALL" else ""
        fin_params = [self.snapshot_id]
        if rating_filter != "ALL":
            fin_params.append(rating_filter)

        sub_stock_rows = query_all(
            f"""
            SELECT m.rating, m.sheet_name, m.material_name, sms.closing_balance
            FROM stock_master_snapshots sms
            JOIN materials m ON sms.material_id = m.id
            WHERE sms.snapshot_id = ? {fin_rating_clause}
              AND (m.sheet_name LIKE '%FIN%' OR m.sheet_name LIKE '%OUT%')
            """,
            tuple(fin_params)
        )

        hv_coils_ready = sum(r["closing_balance"] for r in sub_stock_rows if "HV COIL" in r["sheet_name"])
        lv_coils_ready = sum(r["closing_balance"] for r in sub_stock_rows if "LV COIL" in r["sheet_name"])
        cca_ready = sum(r["closing_balance"] for r in sub_stock_rows if "CCA" in r["sheet_name"] and "OUTSOURCED" not in r["sheet_name"])
        tanked_ready = sum(r["closing_balance"] for r in sub_stock_rows if "FINISHED TR" in r["sheet_name"])
        outsourced_stock = sum(r["closing_balance"] for r in sub_stock_rows if "OUTSOURCED" in r["sheet_name"])

        physical_wip = [
            {"stage": "HV Coils (Buffer Stock)", "units": hv_coils_ready, "unit_type": "Coils", "lineage": "STK_*_HV COIL FIN"},
            {"stage": "LV Coils (Buffer Stock)", "units": lv_coils_ready, "unit_type": "Coils", "lineage": "STK_*_LV COIL FIN"},
            {"stage": "Core Coil Assemblies (WIP)", "units": cca_ready, "unit_type": "Assemblies", "lineage": "STK_*_CCA FIN"},
            {"stage": "Tanked / Finished Stock", "units": tanked_ready, "unit_type": "Transformers", "lineage": "STK_*_FINISHED TR"},
            {"stage": "Outsourced Buffer", "units": outsourced_stock, "unit_type": "Units", "lineage": "STK_*_OUTSOURCED TR/CCA"}
        ]

        total_wip_units = cca_ready + (tank - dispatched if tank > dispatched else 0.0)

        # Observations supported strictly by data
        observations = []
        if cca > tank and (cca - tank) > 5:
            observations.append(
                f"The data indicates an accumulation of {int(cca - tank)} units between Core Coil Assembly ({int(cca)} units) and Tanking ({int(tank)} units) for the selected period. Investigate tank availability and assembly pace."
            )
        if hv > cca and (hv - cca) > 20:
            observations.append(
                f"HV Winding output ({int(hv)} units) exceeds Core Coil Assembly throughput ({int(cca)} units). Warehouse buffer holds {int(hv_coils_ready)} completed HV coils."
            )
        if tank > 0 and (tested_passed + tested_failed) == 0:
            observations.append(
                f"{int(tank)} transformers completed Tanking but zero units have logged inspection in Testing for this period."
            )

        return {
            "total_estimated_wip": total_wip_units,
            "accumulations": accumulations,
            "throughput_accumulation": accumulations,
            "physical_wip": physical_wip,
            "physical_buffers": physical_wip,
            "observations": observations,
            "stage_outputs": {
                "HV WINDING": hv,
                "LV WINDING": lv,
                "CORE COIL ASSEMBLY": cca,
                "TANKING": tank,
                "TESTING PASSED": tested_passed,
                "TESTING FAILED": tested_failed,
                "PAINTING": painted,
                "DISPATCH": dispatched
            },
            "lineage": "PROD_* Stage Output Gaps & STK_*_FIN Warehouse Ledgers"
        }

    def _compute_manufacturing_flow(
        self, prod_kpis: Dict[str, Any], monthly_stats: Dict[str, Any], wip_data: Dict[str, Any], active_month: str, active_rating: str
    ) -> List[Dict[str, Any]]:
        """
        Creates the high-visibility, 7-stage manufacturing process pipeline:
        HV WINDING -> LV WINDING -> CORE COIL ASSEMBLY -> TANKING -> TESTING PASSED -> PAINTING -> DISPATCH
        """
        stages_order = [
            ("HV WINDING", "HV Winding", "Coils", "PROD_HV WINDING"),
            ("LV WINDING", "LV Winding", "Coils", "PROD_LV WINDING"),
            ("CORE COIL ASSEMBLY", "Core Coil Assy (CCA)", "Units", "PROD_CORE COIL ASSY"),
            ("TANKING", "Tanking & Oil Filling", "Units", "PROD_TANKING"),
            ("TESTING PASSED", "Testing (Quality Inspection)", "Units", "PROD_TESTING PASSED"),
            ("PAINTING", "Finishing & Painting", "Units", "PROD_PAINTING"),
            ("DISPATCH", "Customer Dispatch", "Units", "PROD_DISPATCH")
        ]

        targets_map = {}
        for t in monthly_stats.get("targets", []):
            if t["month"] == active_month or (active_month == "ALL" and t["month"] == "YEARLY"):
                if active_rating == "ALL" or t["rating"] == active_rating:
                    sec = t["section"]
                    targets_map[sec] = targets_map.get(sec, 0.0) + (t["target_units"] or 0.0)

        stage_outputs = wip_data.get("stage_outputs", {})
        bottleneck_sec = prod_kpis.get("bottleneck", {}).get("section", "")

        flow = []
        for i, (code, label, unit_name, lineage) in enumerate(stages_order):
            actual = stage_outputs.get(code, 0.0)
            target = targets_map.get(code, 0.0)
            variance = actual - target
            achievement = round((actual / target * 100), 1) if target > 0 else (100.0 if actual > 0 else 0.0)

            # Accumulation to next stage
            next_actual = stage_outputs.get(stages_order[i+1][0], 0.0) if i < len(stages_order) - 1 else 0.0
            accum_to_next = round(actual - next_actual, 1) if i < len(stages_order) - 1 else 0.0

            # Status determination
            status = "NORMAL"
            if code == bottleneck_sec and actual > 0:
                status = "BOTTLENECK"
            elif accum_to_next > 15:
                status = "ACCUMULATION"
            elif target > 0 and actual < target * 0.8:
                status = "BEHIND_TARGET"
            elif target > 0 and actual >= target:
                status = "TARGET_MET"

            flow.append({
                "stage_id": code,
                "section": code,
                "stage_name": label,
                "unit_name": unit_name,
                "actual_output": actual,
                "output": actual,
                "target_output": target,
                "monthly_target": target,
                "monthly_actual": actual,
                "variance": variance,
                "achievement_pct": achievement,
                "accumulation_to_next": accum_to_next,
                "status": status,
                "lineage": lineage
            })

        return flow

    def _compute_material_readiness(self, active_rating: str = "ALL", rating: Optional[str] = None) -> Dict[str, Any]:
        if rating:
            active_rating = rating
        """
        Evaluates material constraints for transformer production:
        Compares Required BOM Material (from CONSUMPTION / BASIC norms * planned units)
        against Available Stock Closing Balance.
        Calculates: Required, Available, Gap, and Status (Healthy / Attention / Insufficient).
        """
        bom_rows = query_all(
            """
            SELECT rating, material_name, material_type, size, qty_per_transformer, unit
            FROM bom_specifications
            WHERE snapshot_id = ?
            """,
            (self.snapshot_id,)
        )
        if not bom_rows:
            bom_rows = query_all(
                """
                SELECT rating, material_name, '' as material_type, '' as size, qty_per_transformer, unit
                FROM consumption_norms
                WHERE snapshot_id = ?
                """,
                (self.snapshot_id,)
            )

        stock_rows = query_all(
            """
            SELECT m.rating, m.material_name, m.material_type, m.size, m.unit, sms.closing_balance
            FROM stock_master_snapshots sms
            JOIN materials m ON sms.material_id = m.id
            WHERE sms.snapshot_id = ?
            """,
            (self.snapshot_id,)
        )
        stock_map = {}
        for s in stock_rows:
            key = (s["rating"], s["material_name"].upper().strip())
            stock_map[key] = s["closing_balance"]

        # Default planned batches from monthly targets or actuals
        target_rows = query_all(
            """
            SELECT rating, SUM(target_units) as target, SUM(actual_units) as actual
            FROM production_monthly_targets
            WHERE snapshot_id = ? AND section = 'TANKING'
            GROUP BY rating
            """,
            (self.snapshot_id,)
        )
        plan_units_map = {}
        for r in target_rows:
            t = r["target"] or 0.0
            a = r["actual"] or 0.0
            plan_units_map[r["rating"]] = t if t > 0 else (a if a > 0 else 20.0)

        readiness_items = []
        constrained_count = 0

        ratings_to_check = ['16KVA', '25KVA', '63KVA', '100KVA', '250KVA']
        if active_rating != 'ALL':
            ratings_to_check = [active_rating]

        for b in bom_rows:
            rat = b["rating"]
            if rat not in ratings_to_check:
                continue

            mat_name = b["material_name"]
            norm = b["qty_per_transformer"] or 0.0
            planned_units = plan_units_map.get(rat, 20.0)
            required_qty = round(norm * planned_units, 2)

            key = (rat, mat_name.upper().strip())
            available_qty = stock_map.get(key, stock_map.get(('COMMON', mat_name.upper().strip()), 0.0))
            gap = round(required_qty - available_qty, 2)

            if available_qty <= 0.001:
                status = "INSUFFICIENT"
                constrained_count += 1
            elif available_qty < required_qty:
                status = "ATTENTION"
                constrained_count += 1
            else:
                status = "HEALTHY"

            readiness_items.append({
                "rating": rat,
                "material_name": mat_name,
                "material_type": b.get("material_type") or "-",
                "size": b.get("size") or "-",
                "unit": b.get("unit") or "KG",
                "norm_per_transformer": norm,
                "planned_units": int(planned_units),
                "required_qty": required_qty,
                "available_qty": available_qty,
                "gap": gap,
                "status": status,
                "lineage": f"CONSUMPTION ({norm} {b.get('unit')}/TR) × {int(planned_units)} Units vs STOCK MASTER"
            })

        return {
            "readiness_items": readiness_items,
            "materials": readiness_items,
            "constrained_count": constrained_count,
            "total_assessed": len(readiness_items),
            "lineage": "CONSUMPTION BOM Norms × Target Units vs STOCK MASTER Closing Balances"
        }

    def _compute_outsourcing_summary(self) -> Dict[str, Any]:
        """
        Distinguishes in-house manufacturing from outsourced supply for:
        - Finished Transformers
        - Core Coil Assemblies (CCA)
        """
        items = query_all(
            """
            SELECT m.rating, m.sheet_name, m.material_name, sms.closing_balance
            FROM stock_master_snapshots sms
            JOIN materials m ON sms.material_id = m.id
            WHERE sms.snapshot_id = ?
              AND (m.sheet_name LIKE '%FINISHED%' OR m.sheet_name LIKE '%OUTSOURCED%' OR m.sheet_name LIKE '%CCA%')
            """,
            (self.snapshot_id,)
        )

        inhouse_tr = sum(x["closing_balance"] for x in items if "FINISHED TR" in x["sheet_name"])
        outsourced_tr = sum(x["closing_balance"] for x in items if "OUTSOURCED TR" in x["sheet_name"])
        inhouse_cca = sum(x["closing_balance"] for x in items if "CCA FIN" in x["sheet_name"])
        outsourced_cca = sum(x["closing_balance"] for x in items if "OUTSOURCED CCA" in x["sheet_name"])

        total_tr = inhouse_tr + outsourced_tr
        inhouse_tr_pct = round((inhouse_tr / total_tr * 100), 1) if total_tr > 0 else 100.0

        total_cca = inhouse_cca + outsourced_cca
        inhouse_cca_pct = round((inhouse_cca / total_cca * 100), 1) if total_cca > 0 else 100.0

        return {
            "transformers": {
                "in_house_units": inhouse_tr,
                "outsourced_units": outsourced_tr,
                "total_units": total_tr,
                "in_house_pct": inhouse_tr_pct,
                "outsourced_pct": round(100.0 - inhouse_tr_pct, 1),
                "lineage": "STK_*_FINISHED TR vs STK_*_OUTSOURCED TR"
            },
            "cca": {
                "in_house_units": inhouse_cca,
                "outsourced_units": outsourced_cca,
                "total_units": total_cca,
                "in_house_pct": inhouse_cca_pct,
                "outsourced_pct": round(100.0 - inhouse_cca_pct, 1),
                "lineage": "STK_*_CCA FIN vs STK_*_OUTSOURCED CCA"
            }
        }

    def _compute_ratings_matrix(self, active_month: str) -> List[Dict[str, Any]]:
        """
        Creates first-class rating operational breakdown across production, stock, targets, and outsourcing.
        """
        ratings = ['16KVA', '25KVA', '63KVA', '100KVA', '250KVA']

        month_clause = "AND date LIKE ?" if active_month != "ALL" else ""
        prod_params = [self.snapshot_id]
        if active_month != "ALL":
            prod_params.append(f"{active_month}%")

        prod_rows = query_all(
            f"""
            SELECT rating, section, SUM(units_produced) as units
            FROM production_entries
            WHERE snapshot_id = ? {month_clause}
            GROUP BY rating, section
            """,
            tuple(prod_params)
        )
        prod_map = {}
        for r in prod_rows:
            rat = r["rating"]
            sec = r["section"]
            if rat not in prod_map:
                prod_map[rat] = {}
            prod_map[rat][sec] = r["units"]

        target_rows = query_all(
            """
            SELECT rating, SUM(target_units) as target, SUM(actual_units) as actual, SUM(variance_units) as variance
            FROM production_monthly_targets
            WHERE snapshot_id = ? AND (month = ? OR (? = 'ALL' AND month = 'YEARLY'))
            GROUP BY rating
            """,
            (self.snapshot_id, active_month, active_month)
        )
        target_map = {r["rating"]: r for r in target_rows}

        stock_rows = query_all(
            """
            SELECT m.rating, m.sheet_name, sms.closing_balance
            FROM stock_master_snapshots sms
            JOIN materials m ON sms.material_id = m.id
            WHERE sms.snapshot_id = ?
            """,
            (self.snapshot_id,)
        )
        fin_stock_map = {}
        for s in stock_rows:
            rat = s["rating"]
            sheet = s["sheet_name"]
            bal = s["closing_balance"]
            if rat not in fin_stock_map:
                fin_stock_map[rat] = {"finished_tr": 0.0, "cca": 0.0, "hv_coils": 0.0, "lv_coils": 0.0, "outsourced": 0.0, "zero_stock_materials": 0}
            if "FINISHED TR" in sheet:
                fin_stock_map[rat]["finished_tr"] += bal
            elif "CCA FIN" in sheet:
                fin_stock_map[rat]["cca"] += bal
            elif "HV COIL" in sheet:
                fin_stock_map[rat]["hv_coils"] += bal
            elif "LV COIL" in sheet:
                fin_stock_map[rat]["lv_coils"] += bal
            elif "OUTSOURCED" in sheet:
                fin_stock_map[rat]["outsourced"] += bal
            if bal <= 0.001 and not any(k in sheet for k in ['FINISHED', 'FIN', 'OUTSOURCED']):
                fin_stock_map[rat]["zero_stock_materials"] += 1

        matrix = []
        for rat in ratings:
            p_data = prod_map.get(rat, {})
            t_data = target_map.get(rat, {})
            s_data = fin_stock_map.get(rat, {})

            matrix.append({
                "rating": rat,
                "hv_coils_produced": p_data.get("HV WINDING", 0.0),
                "lv_coils_produced": p_data.get("LV WINDING", 0.0),
                "cca_produced": p_data.get("CORE COIL ASSEMBLY", 0.0),
                "tanking_produced": p_data.get("TANKING", 0.0),
                "dispatched": p_data.get("DISPATCH", 0.0),
                "target_units": t_data.get("target", 0.0),
                "actual_units": t_data.get("actual", 0.0),
                "variance": t_data.get("variance", 0.0),
                "finished_tr_stock": s_data.get("finished_tr", 0.0),
                "cca_stock": s_data.get("cca", 0.0),
                "hv_coils_stock": s_data.get("hv_coils", 0.0),
                "lv_coils_stock": s_data.get("lv_coils", 0.0),
                "outsourced_stock": s_data.get("outsourced", 0.0),
                "out_of_stock_materials": s_data.get("zero_stock_materials", 0),
                "lineage": f"Rollup: PROD_*, PRODUCTION MASTER, and STK_{rat}_* Ledgers"
            })

        return matrix

    def _compute_quality_kpis(self, active_month: str, active_rating: str) -> Dict[str, Any]:
        """
        Extracts Quality Inspection performance from PROD_TESTING PASSED & PROD_TESTING FAILED.
        """
        clauses = ["snapshot_id = ?"]
        params = [self.snapshot_id]
        if active_month != "ALL":
            clauses.append("date LIKE ?")
            params.append(f"{active_month}%")
        if active_rating != "ALL":
            clauses.append("rating = ?")
            params.append(active_rating)

        where_str = "WHERE " + " AND ".join(clauses)

        rows = query_all(
            f"""
            SELECT section, rating, SUM(units_produced) as units
            FROM production_entries
            {where_str} AND section IN ('TESTING PASSED', 'TESTING FAILED')
            GROUP BY section, rating
            """,
            tuple(params)
        )

        passed = sum(r["units"] for r in rows if r["section"] == "TESTING PASSED")
        failed = sum(r["units"] for r in rows if r["section"] == "TESTING FAILED")
        total = passed + failed
        pass_rate = round((passed / total * 100), 1) if total > 0 else 100.0

        by_rating = {}
        for r in rows:
            rat = r["rating"]
            if rat not in by_rating:
                by_rating[rat] = {"passed": 0.0, "failed": 0.0}
            if r["section"] == "TESTING PASSED":
                by_rating[rat]["passed"] += r["units"]
            else:
                by_rating[rat]["failed"] += r["units"]

        daily_rows = query_all(
            f"""
            SELECT date, section, SUM(units_produced) as units
            FROM production_entries
            {where_str} AND section IN ('TESTING PASSED', 'TESTING FAILED')
            GROUP BY date, section
            ORDER BY date ASC
            LIMIT 30
            """,
            tuple(params)
        )

        return {
            "passed": passed,
            "failed": failed,
            "total_inspected": total,
            "pass_rate_pct": pass_rate,
            "fail_rate_pct": round(100.0 - pass_rate, 1) if total > 0 else 0.0,
            "by_rating": by_rating,
            "daily_trends": daily_rows,
            "lineage": "PROD_TESTING PASSED & PROD_TESTING FAILED"
        }

    def _compute_monthly_matrix(self, rating_filter: str = "ALL") -> Dict[str, Any]:
        """
        Computes monthly output breakdown across sections and ratings,
        joined with targets from PRODUCTION MASTER.
        """
        fy_months = ['Apr-26', 'May-26', 'Jun-26', 'Jul-26', 'Aug-26', 'Sep-26', 'Oct-26', 'Nov-26', 'Dec-26', 'Jan-27', 'Feb-27', 'Mar-27', 'YEARLY']

        rat_clause = "AND rating = ?" if rating_filter != "ALL" else ""
        params = [self.snapshot_id]
        if rating_filter != "ALL":
            params.append(rating_filter)

        targets_rows = query_all(
            f"""
            SELECT 
                month,
                section,
                rating,
                target_units,
                actual_units,
                variance_units
            FROM production_monthly_targets
            WHERE snapshot_id = ? {rat_clause}
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
            tuple(params)
        )

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
            "fy_months": fy_months,
            "monthly_summary": monthly_summary,
            "section_summary": section_summary,
            "targets": targets_rows,
            "lineage": "PRODUCTION MASTER (Target, Actual, Variance Matrix)"
        }

    def _compute_finished_goods(self, rating_filter: str = "ALL", rating: Optional[str] = None) -> Dict[str, Any]:
        if rating:
            rating_filter = rating
        """
        Extracts finished transformers, sub-assemblies (coils, CCAs),
        and outsourced inventory balances.
        """
        rat_clause = "AND m.rating = ?" if rating_filter != "ALL" else ""
        params = [self.snapshot_id]
        if rating_filter != "ALL":
            params.append(rating_filter)

        items = query_all(
            f"""
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
            WHERE sms.snapshot_id = ? {rat_clause}
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
            tuple(params)
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
            "lv_coils": lv_coils,
            "lineage": "STK_*_FINISHED TR, STK_*_CCA FIN, STK_*_HV COIL FIN, STK_*_LV COIL FIN"
        }

    def _get_bom_specifications(self, rating_filter: str = "ALL", rating: Optional[str] = None) -> List[Dict[str, Any]]:
        if rating:
            rating_filter = rating
        """Returns standard BOM specifications from CONSUMPTION sheet."""
        rat_clause = "AND rating = ?" if rating_filter != "ALL" else ""
        params = [self.snapshot_id]
        if rating_filter != "ALL":
            params.append(rating_filter)

        return query_all(
            f"""
            SELECT 
                rating, material_name, material_type, size, 
                pieces_count, qty_per_coil, qty_per_transformer, unit
            FROM bom_specifications
            WHERE snapshot_id = ? {rat_clause}
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
            tuple(params)
        )

    def _compute_consumption_vs_norms(self, rating_filter: str = "ALL") -> Dict[str, Any]:
        """
        Calculates Actual Issued vs Expected Norm (Norm Qty * Units Produced of that Rating).
        Falls back to bom_specifications if consumption_norms table is empty.
        """
        rat_clause = "AND rating = ?" if rating_filter != "ALL" else ""
        params = [self.snapshot_id]
        if rating_filter != "ALL":
            params.append(rating_filter)

        norms = query_all(
            f"""
            SELECT rating, material_name, qty_per_transformer, unit
            FROM consumption_norms
            WHERE (snapshot_id = ? OR snapshot_id IS NULL) {rat_clause}
            """,
            tuple(params)
        )
        if not norms:
            norms = query_all(
                f"""
                SELECT rating, material_name, qty_per_transformer, unit
                FROM bom_specifications
                WHERE snapshot_id = ? {rat_clause}
                """,
                tuple(params)
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
                "status": status,
                "lineage": "BASIC / CONSUMPTION Norms vs STK_* Issued Quantities"
            })

        variances.sort(key=lambda x: x["variance_pct"], reverse=True)
        return {
            "has_norms": True,
            "variances": variances,
            "over_consumed_count": sum(1 for v in variances if v["status"] == "OVER_CONSUMED"),
            "under_consumed_count": sum(1 for v in variances if v["status"] == "UNDER_CONSUMED"),
            "lineage": "CONSUMPTION BOM Norms vs STK_* Total Issued"
        }

    def _generate_daily_brief(
        self, stock: Dict[str, Any], prod: Dict[str, Any], wip: Dict[str, Any], quality: Dict[str, Any], monthly_stats: Dict[str, Any], readiness: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generates the Daily Factory Brief summarizing latest available data,
        including data-supported observations (no fabricated assumptions).
        """
        attention_items = []

        # 1. WIP accumulations
        for obs in wip.get("observations", []):
            attention_items.append({"level": "warning", "icon": "⚠️", "text": obs})

        # 2. Material shortages
        constrained = [r for r in readiness.get("readiness_items", []) if r["status"] == "INSUFFICIENT"]
        if constrained:
            top_c = constrained[:3]
            mats_str = ", ".join(f"{c['rating']} {c['material_name']}" for c in top_c)
            attention_items.append({
                "level": "danger",
                "icon": "🚨",
                "text": f"Material constraint: {len(constrained)} material item(s) have 0 stock balance against calculated requirements ({mats_str})."
            })

        # 3. Stock runouts
        if stock.get("zero_stock_count", 0) > 0:
            attention_items.append({
                "level": "warning",
                "icon": "📦",
                "text": f"{stock['zero_stock_count']} material items in STOCK MASTER currently have zero closing balance."
            })

        # 4. Bottleneck alert
        bneck = prod.get("bottleneck", {})
        if bneck.get("section") and bneck.get("section") != "None":
            attention_items.append({
                "level": "info",
                "icon": "⏱️",
                "text": f"Assembly throughput is constrained at {bneck['section']} ({int(bneck.get('throughput', 0))} units completed)."
            })

        # 5. Quality notice
        if quality.get("failed", 0) > 0:
            attention_items.append({
                "level": "danger",
                "icon": "🛡️",
                "text": f"{int(quality['failed'])} unit(s) failed electrical testing inspection."
            })

        return {
            "attention_items": attention_items,
            "headline": f"{len(attention_items)} operational condition(s) require management review" if attention_items else "All shop floor stages operating within normal tolerances.",
            "production_summary": f"Total Period Output: {int(prod.get('total_produced_units', 0))} units across all assembly stages.",
            "inventory_summary": f"{stock.get('total_items', 0)} materials tracked ({stock.get('zero_stock_count', 0)} out of stock).",
            "quality_summary": f"Testing Pass Rate: {quality.get('pass_rate_pct', 100)}% ({int(quality.get('passed', 0))} passed / {int(quality.get('failed', 0))} failed)."
        }

    def _generate_executive_summary(
        self, stock: Dict[str, Any], prod: Dict[str, Any], cons: Dict[str, Any], fin: Dict[str, Any], wip: Dict[str, Any], readiness: Dict[str, Any]
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

        # WIP observation
        wip_obs = wip.get("observations", [])
        if wip_obs:
            bullets.append(f"WIP Alert: {wip_obs[0]}")
            action_required = True

        # Material readiness constraint
        constrained = readiness.get("constrained_count", 0)
        if constrained > 0:
            bullets.append(f"Readiness Alert: {constrained} material item(s) are constrained or insufficient for planned production batch.")
            action_required = True

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
