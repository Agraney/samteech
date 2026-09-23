"""
Sample Workbook Generator for Transformer Factory
Creates an .xlsm (or .xlsx) matching the exact ~87 sheet structure
described in the specification for local development and testing.
"""

import datetime
from pathlib import Path
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

def generate_sample_workbook(output_path: Path):
    wb = openpyxl.Workbook()
    # Remove default sheet
    default_sheet = wb.active
    
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    bold_font = Font(name="Calibri", size=11, bold=True)
    regular_font = Font(name="Calibri", size=10)
    center_align = Alignment(horizontal="center", vertical="center")
    right_align = Alignment(horizontal="right", vertical="center")
    
    ratings = ["16KVA", "25KVA", "63KVA", "100KVA", "250KVA"]
    
    # Material catalog definition
    # (rating, sheet_suffix, material_name, mat_type, size, unit, base_rate, qty_per_transformer)
    materials_catalog = [
        # 16KVA materials
        ("16KVA", "HV WIRE", "HV Copper Wire", "Enamelled Wire", "1.2 mm", "KG", 850.0, 42.5),
        ("16KVA", "LV STRIP", "LV Copper Strip", "Paper Covered", "8x2 mm", "KG", 820.0, 38.0),
        ("16KVA", "CRGO CORE", "CRGO Silicon Steel Core", "M4 Grade", "0.27 mm", "KG", 280.0, 95.0),
        ("16KVA", "TANK", "Transformer Tank 16KVA", "Mild Steel", "Standard", "NOS", 4500.0, 1.0),
        ("16KVA", "BUSHING HV", "HV Bushing 11KV", "Porcelain", "11KV", "NOS", 350.0, 3.0),
        ("16KVA", "BUSHING LV", "LV Bushing 1.1KV", "Brass/Porcelain", "1.1KV", "NOS", 180.0, 4.0),
        
        # 25KVA materials
        ("25KVA", "HV WIRE", "HV Copper Wire", "Enamelled Wire", "1.4 mm", "KG", 850.0, 58.0),
        ("25KVA", "LV STRIP", "LV Copper Strip", "Paper Covered", "10x2 mm", "KG", 820.0, 52.0),
        ("25KVA", "CRGO CORE", "CRGO Silicon Steel Core", "M4 Grade", "0.27 mm", "KG", 280.0, 135.0),
        ("25KVA", "TANK", "Transformer Tank 25KVA", "Mild Steel", "Standard", "NOS", 5800.0, 1.0),
        ("25KVA", "BUSHING HV", "HV Bushing 11KV", "Porcelain", "11KV", "NOS", 350.0, 3.0),
        ("25KVA", "BUSHING LV", "LV Bushing 1.1KV", "Brass/Porcelain", "1.1KV", "NOS", 195.0, 4.0),
        
        # 63KVA materials
        ("63KVA", "HV WIRE", "HV Copper Wire", "Enamelled Wire", "1.8 mm", "KG", 850.0, 110.0),
        ("63KVA", "LV STRIP", "LV Copper Strip", "Paper Covered", "12x2.5 mm", "KG", 820.0, 105.0),
        ("63KVA", "CRGO CORE", "CRGO Silicon Steel Core", "M4 Grade", "0.27 mm", "KG", 280.0, 260.0),
        ("63KVA", "TANK", "Transformer Tank 63KVA", "Mild Steel", "Standard", "NOS", 9200.0, 1.0),
        ("63KVA", "BUSHING HV", "HV Bushing 11KV", "Porcelain", "11KV", "NOS", 380.0, 3.0),
        ("63KVA", "BUSHING LV", "LV Bushing 1.1KV", "Brass/Porcelain", "1.1KV", "NOS", 240.0, 4.0),
        
        # 100KVA materials
        ("100KVA", "HV WIRE", "HV Copper Wire", "Enamelled Wire", "2.1 mm", "KG", 850.0, 165.0),
        ("100KVA", "LV STRIP", "LV Copper Strip", "Paper Covered", "15x3 mm", "KG", 820.0, 160.0),
        ("100KVA", "CRGO CORE", "CRGO Silicon Steel Core", "M4 Grade", "0.27 mm", "KG", 280.0, 380.0),
        ("100KVA", "TANK", "Transformer Tank 100KVA", "Mild Steel", "Standard", "NOS", 14500.0, 1.0),
        ("100KVA", "BUSHING HV", "HV Bushing 11KV", "Porcelain", "11KV", "NOS", 380.0, 3.0),
        ("100KVA", "BUSHING LV", "LV Bushing 1.1KV", "Brass/Porcelain", "1.1KV", "NOS", 320.0, 4.0),

        # 250KVA materials
        ("250KVA", "HV WIRE", "HV Copper Wire", "Enamelled Wire", "2.6 mm", "KG", 850.0, 340.0),
        ("250KVA", "LV STRIP", "LV Copper Strip", "Paper Covered", "20x3 mm", "KG", 820.0, 330.0),
        ("250KVA", "CRGO CORE", "CRGO Silicon Steel Core", "M4 Grade", "0.27 mm", "KG", 280.0, 720.0),
        ("250KVA", "TANK", "Transformer Tank 250KVA", "Mild Steel", "Standard", "NOS", 2600.0, 1.0),
        ("250KVA", "BUSHING HV", "HV Bushing 11KV", "Porcelain", "11KV", "NOS", 420.0, 3.0),
        ("250KVA", "BUSHING LV", "LV Bushing 1.1KV", "Brass/Porcelain", "1.1KV", "NOS", 480.0, 4.0),

        # Common materials
        ("COMMON", "OIL", "Transformer Oil IS 335", "Mineral Oil", "Grade A", "LTR", 95.0, 160.0),
        ("COMMON", "INSULATION", "Kraft Paper / Pressboard", "Class A", "Various", "KG", 420.0, 18.0),
        ("COMMON", "GASKET", "Cork Neoprene Gaskets", "Nitrile Rubber", "6 mm", "SETS", 650.0, 1.0),
        ("COMMON", "SILICA GEL", "Breather Silica Gel", "Blue to Pink", "Commercial", "KG", 180.0, 1.5),
        ("COMMON", "PAINT", "Epoxy Polyurethane Paint", "PU Gray", "RAL 7032", "LTR", 320.0, 8.0)
    ]
    
    # -------------------------------------------------------------------------
    # 1. STOCK MASTER SHEET
    # -------------------------------------------------------------------------
    ws_stock_master = wb.create_sheet(title="STOCK MASTER")
    
    # Title row
    ws_stock_master.cell(row=2, column=2, value="TRANSFORMER FACTORY — STOCK MASTER ROLLUP").font = Font(name="Calibri", size=14, bold=True)
    
    # Headers on row 4
    # Columns: Rating (B), Sheet name (C), Material (D), Type (E), Size (F), Unit (G), 
    # Opening Balance (H), Received Qty (I), Rate (J), Value (K), Issued Qty (O), Closing Balance (Q)
    headers_sm = {
        2: "RATING",
        3: "SHEET NAME",
        4: "MATERIAL NAME",
        5: "TYPE",
        6: "SIZE",
        7: "UNIT",
        8: "OPENING BALANCE",
        9: "RECEIVED QTY",
        10: "RATE (₹)",
        11: "VALUE (₹)",
        15: "ISSUED QTY",
        17: "CLOSING BALANCE"
    }
    
    for col_idx, col_name in headers_sm.items():
        cell = ws_stock_master.cell(row=4, column=col_idx, value=col_name)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
    
    # -------------------------------------------------------------------------
    # 2. STK_* SHEETS
    # -------------------------------------------------------------------------
    today = datetime.date(2026, 9, 20)
    start_date = datetime.date(2026, 8, 1)
    
    sections = [
        "HV WINDING", "LV WINDING", "CORE COIL ASSEMBLY", "TANKING", 
        "TESTING PASSED", "TESTING FAILED", "PAINTING", "DISPATCH"
    ]
    
    suppliers = ["National Copper Corp", "Steel Industries Ltd", "Apex Bushings", "Petrochem Oils", "Insul-Tech Solutions"]
    
    row_sm_idx = 5
    for item in materials_catalog:
        rating, suffix, mat_name, mat_type, mat_size, unit, base_rate, norm_qty = item
        sheet_name = f"STK_{suffix}" if rating == "COMMON" else f"STK_{rating}_{suffix}"
        
        ws_stk = wb.create_sheet(title=sheet_name[:31]) # Excel sheet name limit
        
        # STK sheet title
        ws_stk.cell(row=2, column=2, value=f"STOCK REGISTER: {rating} - {mat_name}").font = Font(name="Calibri", size=12, bold=True)
        ws_stk.cell(row=3, column=2, value=f"Size: {mat_size} | Unit: {unit}").font = regular_font
        
        # Header row 5: S.NO | DATE | OPENING BALANCE | RECEIVED QTY | RATE (₹) | VALUE (₹) | SUPPLIER NAME | INVOICE NO | ISSUED QTY | ISSUED TO SECTION | CLOSING BALANCE | REMARKS
        stk_headers = [
            "S.NO", "DATE", "OPENING BALANCE", "RECEIVED QTY", "RATE (₹)", "VALUE (₹)",
            "SUPPLIER NAME", "INVOICE NO", "ISSUED QTY", "ISSUED TO SECTION", "CLOSING BALANCE", "REMARKS"
        ]
        for c_idx, h_text in enumerate(stk_headers, start=1):
            c = ws_stk.cell(row=5, column=c_idx, value=h_text)
            c.fill = header_fill
            c.font = header_font
            c.alignment = center_align
            
        # Add 15 sample transactions
        curr_balance = 250.0 if "WIRE" in suffix or "CORE" in suffix else (1200.0 if "OIL" in suffix else 40.0)
        # Low stock simulated for a couple of items
        is_zero_stock_item = (rating == "250KVA" and suffix == "TANK")
        is_low_stock_item = (rating == "63KVA" and suffix == "HV WIRE")
        if is_low_stock_item:
            curr_balance = 12.0
        elif is_zero_stock_item:
            curr_balance = 0.0
            
        initial_opening = curr_balance
        total_received = 0.0
        total_issued = 0.0
        
        for t_idx in range(1, 16):
            r_row = 5 + t_idx
            t_date = start_date + datetime.timedelta(days=t_idx * 3)
            is_receipt = (t_idx % 4 == 0) and not is_zero_stock_item and not is_low_stock_item
            
            rec_qty = 100.0 if is_receipt else 0.0
            iss_qty = 25.0 if not is_receipt and curr_balance >= 25.0 else (curr_balance if not is_receipt and curr_balance > 0 and not is_low_stock_item else 0.0)
            
            op_bal = curr_balance
            cl_bal = op_bal + rec_qty - iss_qty
            val = rec_qty * base_rate if rec_qty > 0 else 0.0
            
            total_received += rec_qty
            total_issued += iss_qty
            curr_balance = cl_bal

            
            ws_stk.cell(row=r_row, column=1, value=t_idx)
            ws_stk.cell(row=r_row, column=2, value=t_date.strftime("%Y-%m-%d"))
            ws_stk.cell(row=r_row, column=3, value=round(op_bal, 2))
            ws_stk.cell(row=r_row, column=4, value=round(rec_qty, 2))
            ws_stk.cell(row=r_row, column=5, value=base_rate)
            ws_stk.cell(row=r_row, column=6, value=round(val, 2))
            ws_stk.cell(row=r_row, column=7, value=suppliers[t_idx % len(suppliers)] if is_receipt else "")
            ws_stk.cell(row=r_row, column=8, value=f"INV-2026-{1000 + t_idx}" if is_receipt else "")
            ws_stk.cell(row=r_row, column=9, value=round(iss_qty, 2))
            ws_stk.cell(row=r_row, column=10, value="HV WINDING" if "HV" in suffix else ("TANKING" if "TANK" in suffix or "OIL" in suffix else "ASSEMBLY") if iss_qty > 0 else "")
            ws_stk.cell(row=r_row, column=11, value=round(cl_bal, 2))
            ws_stk.cell(row=r_row, column=12, value="Routine batch issuance" if iss_qty > 0 else "Supplier replenishment")
            
        # Populate row in STOCK MASTER
        # Rating (B), Sheet name (C), Material (D), Type (E), Size (F), Unit (G), 
        # Opening Balance (H), Received Qty (I), Rate (J), Value (K), Issued Qty (O), Closing Balance (Q)
        ws_stock_master.cell(row=row_sm_idx, column=2, value=rating)
        ws_stock_master.cell(row=row_sm_idx, column=3, value=sheet_name[:31])
        ws_stock_master.cell(row=row_sm_idx, column=4, value=mat_name)
        ws_stock_master.cell(row=row_sm_idx, column=5, value=mat_type)
        ws_stock_master.cell(row=row_sm_idx, column=6, value=mat_size)
        ws_stock_master.cell(row=row_sm_idx, column=7, value=unit)
        ws_stock_master.cell(row=row_sm_idx, column=8, value=round(initial_opening, 2))
        ws_stock_master.cell(row=row_sm_idx, column=9, value=round(total_received, 2))
        ws_stock_master.cell(row=row_sm_idx, column=10, value=base_rate)
        ws_stock_master.cell(row=row_sm_idx, column=11, value=round(curr_balance * base_rate, 2))
        ws_stock_master.cell(row=row_sm_idx, column=15, value=round(total_issued, 2))
        ws_stock_master.cell(row=row_sm_idx, column=17, value=round(curr_balance, 2))
        
        row_sm_idx += 1
        
    # -------------------------------------------------------------------------
    # 3. PRODUCTION MASTER SHEET
    # -------------------------------------------------------------------------
    ws_prod_master = wb.create_sheet(title="PRODUCTION MASTER")
    ws_prod_master.cell(row=2, column=2, value="TRANSFORMER FACTORY — PRODUCTION MASTER ROLLUP").font = Font(name="Calibri", size=14, bold=True)
    
    pm_headers = ["SECTION", "RATING", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC", "JAN", "FEB", "MAR", "YTD ACTUAL"]
    for c_idx, h_text in enumerate(pm_headers, start=2):
        c = ws_prod_master.cell(row=4, column=c_idx, value=h_text)
        c.fill = header_fill
        c.font = header_font
        c.alignment = center_align
        
    pm_row = 5
    for sec in sections:
        for rat in ratings:
            ws_prod_master.cell(row=pm_row, column=2, value=sec)
            ws_prod_master.cell(row=pm_row, column=3, value=rat)
            # Sample monthly figures
            ytd = 0
            for m_idx in range(4, 16):
                val = 15 if sec != "TANKING" else 9 # simulate tanking as a slight bottleneck
                ws_prod_master.cell(row=pm_row, column=m_idx, value=val)
                ytd += val
            ws_prod_master.cell(row=pm_row, column=16, value=ytd)
            pm_row += 1

    # -------------------------------------------------------------------------
    # 4. 8 PROD_<SECTION> SHEETS
    # -------------------------------------------------------------------------
    prod_sheet_names = [
        "PROD_HV WINDING", "PROD_LV WINDING", "PROD_CORE COIL ASSEMBLY",
        "PROD_TANKING", "PROD_TESTING PASSED", "PROD_TESTING FAILED",
        "PROD_PAINTING", "PROD_DISPATCH"
    ]
    
    # 60 days of daily entries
    for p_sheet_name in prod_sheet_names:
        ws_p = wb.create_sheet(title=p_sheet_name)
        sec_name = p_sheet_name.replace("PROD_", "")
        ws_p.cell(row=2, column=1, value=f"DAILY PRODUCTION LOG — {sec_name}").font = Font(name="Calibri", size=12, bold=True)
        
        # Header row 4: DATE | 16KVA | 25KVA | 63KVA | 100KVA | 250KVA | TOTAL
        headers_p = ["DATE"] + ratings + ["TOTAL"]
        for c_idx, h_text in enumerate(headers_p, start=1):
            c = ws_p.cell(row=4, column=c_idx, value=h_text)
            c.fill = header_fill
            c.font = header_font
            c.alignment = center_align
            
        # Daily production rows
        for d_idx in range(60):
            p_date = datetime.date(2026, 7, 25) + datetime.timedelta(days=d_idx)
            row_idx = 5 + d_idx
            
            # Base numbers depending on section
            if sec_name == "TESTING FAILED":
                row_vals = [1 if (d_idx + r_i) % 7 == 0 else 0 for r_i in range(5)]
            elif sec_name == "TANKING":
                # Bottleneck: lower output than HV WINDING
                row_vals = [2, 2, 1, 1, 1]
            elif sec_name in ["HV WINDING", "LV WINDING"]:
                row_vals = [4, 3, 2, 2, 1]
            elif sec_name == "TESTING PASSED":
                row_vals = [3, 3, 2, 1, 1]
            else:
                row_vals = [3, 2, 2, 1, 1]
                
            total_u = sum(row_vals)
            
            ws_p.cell(row=row_idx, column=1, value=p_date.strftime("%Y-%m-%d"))
            for r_i, v in enumerate(row_vals, start=2):
                ws_p.cell(row=row_idx, column=r_i, value=v)
            ws_p.cell(row=row_idx, column=7, value=total_u)
            
    # -------------------------------------------------------------------------
    # 5. BASIC SHEET (Consumption Norms)
    # -------------------------------------------------------------------------
    ws_basic = wb.create_sheet(title="BASIC")
    ws_basic.cell(row=2, column=1, value="BILL OF MATERIALS / CONSUMPTION NORMS PER TRANSFORMER").font = Font(name="Calibri", size=12, bold=True)
    
    basic_headers = ["RATING", "MATERIAL NAME", "QTY PER TRANSFORMER", "UNIT"]
    for c_idx, h_text in enumerate(basic_headers, start=1):
        c = ws_basic.cell(row=4, column=c_idx, value=h_text)
        c.fill = header_fill
        c.font = header_font
        c.alignment = center_align
        
    b_row = 5
    for item in materials_catalog:
        rating, suffix, mat_name, mat_type, mat_size, unit, base_rate, norm_qty = item
        ws_basic.cell(row=b_row, column=1, value=rating)
        ws_basic.cell(row=b_row, column=2, value=mat_name)
        ws_basic.cell(row=b_row, column=3, value=norm_qty)
        ws_basic.cell(row=b_row, column=4, value=unit)
        b_row += 1

    # -------------------------------------------------------------------------
    # 6. CONSUMPTION and WIP Data Sheets
    # -------------------------------------------------------------------------
    ws_cons = wb.create_sheet(title="CONSUMPTION")
    ws_cons.cell(row=2, column=1, value="DERIVED CONSUMPTION SUMMARY").font = bold_font
    ws_cons.cell(row=4, column=1, value="Auto-calculated from shop transactions and production norms").font = regular_font
    
    ws_wip = wb.create_sheet(title="WIP Data")
    ws_wip.cell(row=2, column=1, value="WORK IN PROGRESS TRACKING").font = bold_font
    ws_wip.cell(row=4, column=1, value="Derived stage-wise counts").font = regular_font

    # Remove the default initial empty sheet
    if default_sheet.title in wb.sheetnames:
        wb.remove(default_sheet)
        
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    print(f"Sample workbook created successfully at: {output_path}")

if __name__ == "__main__":
    out_file = Path(__file__).resolve().parent.parent / "data" / "sample_factory_data.xlsm"
    generate_sample_workbook(out_file)
