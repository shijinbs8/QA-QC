import os
import math
import ezdxf
from reportlab.lib.pagesizes import letter, A3, landscape
from reportlab.pdfgen import canvas
from reportlab.lib import colors

def generate_hvac_dxf(output_path):
    """Generates a professional MEP HVAC DXF drawing."""
    doc = ezdxf.new('R2010')
    doc.header['$INSUNITS'] = 4 # mm
    msp = doc.modelspace()

    # Define standard MEP layers
    layers = [
        ('A-WALL', 7, 'Architectural Walls'),
        ('A-GRID', 8, 'Column Grid Lines'),
        ('M-HVAC-DUCT-SUPP', 4, 'HVAC Supply Air Ductwork (Cyan)'),
        ('M-HVAC-DUCT-RETN', 6, 'HVAC Return Air Ductwork (Magenta)'),
        ('M-HVAC-EQUP', 2, 'HVAC Equipment (Yellow)'),
        ('M-HVAC-DIFF', 3, 'HVAC Diffusers (Green)'),
        ('M-HVAC-ANNO', 1, 'HVAC Annotations and Tags (Red)'),
        ('M-DIM', 8, 'Dimensions'),
        ('TITLE_BLOCK', 7, 'Sheet Border and Title Block')
    ]
    for l_name, l_col, _ in layers:
        doc.layers.add(l_name, color=l_col)

    # 1. Architectural Floor Outline (15m x 10m office)
    # Origin at (0, 0), dimensions in mm
    msp.add_lwpolyline([(0, 0), (15000, 0), (15000, 10000), (0, 10000)], close=True, dxfattribs={'layer': 'A-WALL'})
    # Interior Mechanical Room (0, 6000) to (5000, 10000)
    msp.add_lwpolyline([(0, 6000), (5000, 6000), (5000, 10000)], close=False, dxfattribs={'layer': 'A-WALL'})

    # Column Grid Lines
    for gx in [0, 5000, 10000, 15000]:
        msp.add_line((gx, -500), (gx, 10500), dxfattribs={'layer': 'A-GRID'})
        msp.add_text(f"GRID {gx//5000 + 1}", dxfattribs={'layer': 'A-GRID', 'height': 200, 'insert': (gx - 150, 10700)})
    for gy in [0, 5000, 10000]:
        msp.add_line((-500, gy), (15500, gy), dxfattribs={'layer': 'A-GRID'})

    # 2. Equipment: AHU-01 in Mechanical Room (2000, 7500)
    ahu_w, ahu_h = 2400, 1400
    ahu_x, ahu_y = 1500, 7500
    msp.add_lwpolyline([
        (ahu_x, ahu_y), 
        (ahu_x + ahu_w, ahu_y), 
        (ahu_x + ahu_w, ahu_y + ahu_h), 
        (ahu_x, ahu_y + ahu_h)
    ], close=True, dxfattribs={'layer': 'M-HVAC-EQUP'})
    # Fan circle inside AHU
    msp.add_circle((ahu_x + 1800, ahu_y + 700), 450, dxfattribs={'layer': 'M-HVAC-EQUP'})
    msp.add_text("AHU-01", dxfattribs={'layer': 'M-HVAC-ANNO', 'height': 250, 'insert': (ahu_x + 300, ahu_y + 600)})
    msp.add_text("2400 CFM | 15 TR", dxfattribs={'layer': 'M-HVAC-ANNO', 'height': 150, 'insert': (ahu_x + 300, ahu_y + 350)})

    # 3. Supply Air Duct System
    # Main trunk from AHU outlet (3900, 8200) eastward to (13000, 8200)
    # Duct width 800mm -> top line y=8600, bottom line y=7800
    msp.add_line((3900, 8600), (9000, 8600), dxfattribs={'layer': 'M-HVAC-DUCT-SUPP'})
    msp.add_line((3900, 7800), (9000, 7800), dxfattribs={'layer': 'M-HVAC-DUCT-SUPP'})
    msp.add_text("800x400 S.D. 2400 CFM", dxfattribs={'layer': 'M-HVAC-ANNO', 'height': 180, 'insert': (5200, 8700)})

    # Fire Damper at wall penetration (x=5000)
    msp.add_lwpolyline([(4850, 7700), (5150, 7700), (5150, 8700), (4850, 8700)], close=True, dxfattribs={'layer': 'M-HVAC-EQUP'})
    msp.add_text("FD-01 (1.5 HR)", dxfattribs={'layer': 'M-HVAC-ANNO', 'height': 140, 'insert': (4700, 8800)})

    # Duct transition / reducer from 800x400 to 600x300 at x=9000
    msp.add_line((9000, 8600), (9500, 8500), dxfattribs={'layer': 'M-HVAC-DUCT-SUPP'})
    msp.add_line((9000, 7800), (9500, 7900), dxfattribs={'layer': 'M-HVAC-DUCT-SUPP'})

    # Continued trunk 600x300 from (9500) to (13500)
    msp.add_line((9500, 8500), (13500, 8500), dxfattribs={'layer': 'M-HVAC-DUCT-SUPP'})
    msp.add_line((9500, 7900), (13500, 7900), dxfattribs={'layer': 'M-HVAC-DUCT-SUPP'})
    msp.add_text("600x300 S.D. 1200 CFM", dxfattribs={'layer': 'M-HVAC-ANNO', 'height': 180, 'insert': (10200, 8600)})

    # End cap at (13500)
    msp.add_line((13500, 8500), (13500, 7900), dxfattribs={'layer': 'M-HVAC-DUCT-SUPP'})

    # Branch ducts heading south towards occupied zone
    # Branch 1 at x=7000: VAV-101
    msp.add_lwpolyline([(6700, 4800), (7300, 4800), (7300, 5600), (6700, 5600)], close=True, dxfattribs={'layer': 'M-HVAC-EQUP'})
    msp.add_text("VAV-101", dxfattribs={'layer': 'M-HVAC-ANNO', 'height': 180, 'insert': (6800, 5200)})
    msp.add_text("600 CFM", dxfattribs={'layer': 'M-HVAC-ANNO', 'height': 140, 'insert': (6800, 4950)})

    # Run from trunk to VAV
    msp.add_line((6850, 7800), (6850, 5600), dxfattribs={'layer': 'M-HVAC-DUCT-SUPP'})
    msp.add_line((7150, 7800), (7150, 5600), dxfattribs={'layer': 'M-HVAC-DUCT-SUPP'})
    msp.add_text("400x250 S.D.", dxfattribs={'layer': 'M-HVAC-ANNO', 'height': 160, 'insert': (7250, 6500)})

    # Branch 2 at x=11500: VAV-102
    msp.add_lwpolyline([(11200, 4800), (11800, 4800), (11800, 5600), (11200, 5600)], close=True, dxfattribs={'layer': 'M-HVAC-EQUP'})
    msp.add_text("VAV-102", dxfattribs={'layer': 'M-HVAC-ANNO', 'height': 180, 'insert': (11300, 5200)})

    msp.add_line((11350, 7900), (11350, 5600), dxfattribs={'layer': 'M-HVAC-DUCT-SUPP'})
    msp.add_line((11650, 7900), (11650, 5600), dxfattribs={'layer': 'M-HVAC-DUCT-SUPP'})
    msp.add_text("400x250 S.D.", dxfattribs={'layer': 'M-HVAC-ANNO', 'height': 160, 'insert': (11750, 6500)})

    # Supply Air Diffusers (600x600 mm) at ceiling
    diffusers = [
        (6000, 2500, 'SAD-01', '250 CFM'),
        (8000, 2500, 'SAD-02', '250 CFM'),
        (10500, 2500, 'SAD-03', '250 CFM'),
        (13000, 2500, 'SAD-04', '250 CFM'),
    ]
    for dx, dy, dtag, dcfm in diffusers:
        # 600x600 box with cross lines
        msp.add_lwpolyline([(dx-300, dy-300), (dx+300, dy-300), (dx+300, dy+300), (dx-300, dy+300)], close=True, dxfattribs={'layer': 'M-HVAC-DIFF'})
        msp.add_line((dx-300, dy-300), (dx+300, dy+300), dxfattribs={'layer': 'M-HVAC-DIFF'})
        msp.add_line((dx-300, dy+300), (dx+300, dy-300), dxfattribs={'layer': 'M-HVAC-DIFF'})
        msp.add_text(f"{dtag}", dxfattribs={'layer': 'M-HVAC-ANNO', 'height': 140, 'insert': (dx - 250, dy - 500)})
        msp.add_text(f"{dcfm}", dxfattribs={'layer': 'M-HVAC-ANNO', 'height': 120, 'insert': (dx - 250, dy - 680)})
        # Flexible duct connection
        msp.add_line((dx, dy+300), (dx, dy+1200), dxfattribs={'layer': 'M-HVAC-DUCT-SUPP'})

    # 4. Return Air Ductwork (700x350)
    msp.add_line((1500, 6000), (1500, 3000), dxfattribs={'layer': 'M-HVAC-DUCT-RETN'})
    msp.add_line((2200, 6000), (2200, 3000), dxfattribs={'layer': 'M-HVAC-DUCT-RETN'})
    msp.add_line((1500, 3000), (2200, 3000), dxfattribs={'layer': 'M-HVAC-DUCT-RETN'})
    msp.add_text("700x350 R.D.", dxfattribs={'layer': 'M-HVAC-ANNO', 'height': 160, 'insert': (2350, 4500)})
    msp.add_text("RAG-01 (900x450)", dxfattribs={'layer': 'M-HVAC-ANNO', 'height': 150, 'insert': (1300, 2700)})

    # Title Block
    msp.add_lwpolyline([(-1000, -1500), (16000, -1500), (16000, 11500), (-1000, 11500)], close=True, dxfattribs={'layer': 'TITLE_BLOCK'})
    msp.add_text("PROJECT: COMMERCIAL TOWER MEP COORDINATION", dxfattribs={'layer': 'TITLE_BLOCK', 'height': 220, 'insert': (1000, -1100)})
    msp.add_text("DRAWING: LEVEL 02 - HVAC DUCTWORK & EQUIPMENT LAYOUT", dxfattribs={'layer': 'TITLE_BLOCK', 'height': 200, 'insert': (1000, -1350)})
    msp.add_text("DWG NO: M-HVAC-102 | SCALE: 1:50 | UNITS: MM", dxfattribs={'layer': 'TITLE_BLOCK', 'height': 180, 'insert': (10500, -1350)})

    doc.saveas(output_path)
    return output_path

def generate_plumbing_fire_dxf(output_path):
    """Generates a professional Chilled Water & Fire Protection DXF drawing."""
    doc = ezdxf.new('R2010')
    doc.header['$INSUNITS'] = 4
    msp = doc.modelspace()

    layers = [
        ('A-WALL', 7, 'Architectural Walls'),
        ('M-PLUMB-CHWS', 5, 'Chilled Water Supply (Blue)'),
        ('M-PLUMB-CHWR', 4, 'Chilled Water Return (Cyan)'),
        ('M-FIRE-MAIN', 1, 'Fire Sprinkler Main (Red)'),
        ('M-FIRE-SPRN', 1, 'Fire Sprinkler Heads (Red)'),
        ('M-EQUP-PUMP', 3, 'Pumps & Chillers (Green)'),
        ('M-ANNO-TEXT', 2, 'Annotations and Tags (Yellow)'),
        ('TITLE_BLOCK', 7, 'Border')
    ]
    for l_name, l_col, _ in layers:
        doc.layers.add(l_name, color=l_col)

    # Floor Outline
    msp.add_lwpolyline([(0, 0), (16000, 0), (16000, 10000), (0, 10000)], close=True, dxfattribs={'layer': 'A-WALL'})

    # Chiller CH-01 at (1500, 6500)
    msp.add_lwpolyline([(1000, 6500), (4500, 6500), (4500, 8500), (1000, 8500)], close=True, dxfattribs={'layer': 'M-EQUP-PUMP'})
    msp.add_text("CH-01 (120 TR CHILLER)", dxfattribs={'layer': 'M-ANNO-TEXT', 'height': 220, 'insert': (1400, 7500)})

    # Chilled Water Pump CHWP-01 at (2000, 4000)
    msp.add_circle((2000, 4000), 400, dxfattribs={'layer': 'M-EQUP-PUMP'})
    msp.add_text("CHWP-01", dxfattribs={'layer': 'M-ANNO-TEXT', 'height': 180, 'insert': (1700, 3300)})
    msp.add_text("120 GPM | 25m Head", dxfattribs={'layer': 'M-ANNO-TEXT', 'height': 140, 'insert': (1400, 3050)})

    # Chilled Water Supply & Return Pipes (4" / DN100)
    # Supply Pipe (Blue)
    msp.add_line((4500, 7800), (14500, 7800), dxfattribs={'layer': 'M-PLUMB-CHWS'})
    msp.add_text('4" CHW-S (DN100 Sch 40)', dxfattribs={'layer': 'M-ANNO-TEXT', 'height': 180, 'insert': (6500, 8000)})

    # Return Pipe (Cyan)
    msp.add_line((4500, 7200), (14500, 7200), dxfattribs={'layer': 'M-PLUMB-CHWR'})
    msp.add_text('4" CHW-R (DN100 Sch 40)', dxfattribs={'layer': 'M-ANNO-TEXT', 'height': 180, 'insert': (6500, 6850)})

    # Fire Protection Sprinkler Main & Grid (Red)
    # Zone Control Valve ZCV-01 at riser (x=1000, y=1500)
    msp.add_circle((1000, 1500), 250, dxfattribs={'layer': 'M-FIRE-MAIN'})
    msp.add_text("ZCV-01 (DN100)", dxfattribs={'layer': 'M-ANNO-TEXT', 'height': 160, 'insert': (700, 1900)})

    # 3" Sprinkler Main running horizontally at y=1500
    msp.add_line((1000, 1500), (14500, 1500), dxfattribs={'layer': 'M-FIRE-MAIN'})
    msp.add_text('3" FP-MAIN (DN80)', dxfattribs={'layer': 'M-ANNO-TEXT', 'height': 180, 'insert': (5000, 1150)})

    # Branch lines running north at x=4000, 8000, 12000
    for bx in [4000, 8000, 12000]:
        msp.add_line((bx, 1500), (bx, 6000), dxfattribs={'layer': 'M-FIRE-MAIN'})
        msp.add_text('1-1/2" FP-BR', dxfattribs={'layer': 'M-ANNO-TEXT', 'height': 150, 'insert': (bx + 100, 3000)})
        
        # Pendant Sprinklers along branch (SP-01 to SP-09)
        for sy in [2800, 4200, 5600]:
            sp_idx = len(msp.query('CIRCLE[layer=="M-FIRE-SPRN"]')) + 1
            sp_tag = f"SP-{sp_idx:02d}"
            # Sprinkler symbol: small circle with triangle deflector
            msp.add_circle((bx, sy), 120, dxfattribs={'layer': 'M-FIRE-SPRN'})
            msp.add_line((bx-120, sy-60), (bx+120, sy-60), dxfattribs={'layer': 'M-FIRE-SPRN'})
            msp.add_text(f"{sp_tag} (K=5.6)", dxfattribs={'layer': 'M-ANNO-TEXT', 'height': 130, 'insert': (bx + 180, sy - 50)})

    # Fire Hose Reel Cabinet FHR-01 at entry (x=15000, y=5000)
    msp.add_lwpolyline([(14600, 4600), (15000, 4600), (15000, 5400), (14600, 5400)], close=True, dxfattribs={'layer': 'M-FIRE-MAIN'})
    msp.add_text("FHR-01 (30m)", dxfattribs={'layer': 'M-ANNO-TEXT', 'height': 160, 'insert': (14200, 5600)})

    # Title Block
    msp.add_lwpolyline([(-1000, -1500), (17000, -1500), (17000, 11500), (-1000, 11500)], close=True, dxfattribs={'layer': 'TITLE_BLOCK'})
    msp.add_text("PROJECT: RESEARCH FACILITY MEP PIPING", dxfattribs={'layer': 'TITLE_BLOCK', 'height': 220, 'insert': (1000, -1100)})
    msp.add_text("DRAWING: CHILLED WATER & FIRE SPRINKLER PLAN", dxfattribs={'layer': 'TITLE_BLOCK', 'height': 200, 'insert': (1000, -1350)})
    msp.add_text("DWG NO: P-FP-201 | SCALE: 1:50 | UNITS: MM", dxfattribs={'layer': 'TITLE_BLOCK', 'height': 180, 'insert': (11000, -1350)})

    doc.saveas(output_path)
    return output_path

def generate_hvac_pdf(output_path):
    """Generates an MEP HVAC multi-page PDF drawing using ReportLab."""
    c = canvas.Canvas(output_path, pagesize=landscape(A3))
    w, h = landscape(A3) # 1190 x 842 points

    # Page 1: Sheet M-101 - Level 02 HVAC Ductwork Layout
    # Border & Title Block
    c.setStrokeColor(colors.HexColor('#212529'))
    c.setLineWidth(2)
    c.rect(30, 30, w - 60, h - 60)
    c.rect(30, 30, w - 60, 60)

    # Title text
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(colors.HexColor('#0d6efd'))
    c.drawString(45, 65, "METROPOLITAN ENGINEERING CONSULTANTS")
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor('#212529'))
    c.drawString(45, 45, "PROJECT: COMMERCIAL TOWER COMPLEX | CLIENT: VERTEX DEVELOPMENTS")
    c.drawString(600, 65, "DRAWING: LEVEL 02 - HVAC DUCTWORK & EQUIPMENT DISTRIBUTION")
    c.drawString(600, 45, "DWG NO: M-101 | REV: C | SCALE: 1:50 | SHEET 1 OF 2")

    # Legend Table at right
    c.rect(w - 220, 100, 180, 220)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(w - 210, 300, "MEP DRAWING LEGEND")
    c.setFont("Helvetica", 9)
    # Legend items
    c.setFillColor(colors.HexColor('#0096c7'))
    c.rect(w - 210, 275, 15, 10, fill=1)
    c.setFillColor(colors.black)
    c.drawString(w - 185, 277, "SUPPLY AIR DUCT")

    c.setFillColor(colors.HexColor('#7209b7'))
    c.rect(w - 210, 250, 15, 10, fill=1)
    c.setFillColor(colors.black)
    c.drawString(w - 185, 252, "RETURN AIR DUCT")

    c.setFillColor(colors.HexColor('#2a9d8f'))
    c.rect(w - 210, 225, 15, 10, fill=1)
    c.setFillColor(colors.black)
    c.drawString(w - 185, 227, "4-WAY DIFFUSER (SAD)")

    c.setFillColor(colors.HexColor('#e63946'))
    c.rect(w - 210, 200, 15, 10, fill=1)
    c.setFillColor(colors.black)
    c.drawString(w - 185, 202, "FIRE DAMPER (FD)")

    # Architectural room walls
    c.setStrokeColor(colors.HexColor('#6c757d'))
    c.setLineWidth(1.5)
    c.rect(80, 150, 850, 580)
    # Mechanical Room
    c.rect(80, 500, 280, 230)
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.HexColor('#495057'))
    c.drawString(140, 700, "MECHANICAL PLANT ROOM")
    c.drawString(450, 700, "OPEN OFFICE WORKSPACE (ZONE 1)")

    # AHU-01 in Mech Room
    c.setStrokeColor(colors.HexColor('#d90429'))
    c.setFillColor(colors.HexColor('#f8f9fa'))
    c.rect(120, 540, 180, 110, fill=1)
    c.circle(260, 595, 35)
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(colors.black)
    c.drawString(140, 605, "AHU-01")
    c.setFont("Helvetica", 9)
    c.drawString(140, 585, "2400 CFM | 15 TR")
    c.drawString(140, 565, "ESP: 350 Pa | 400V 3Ph")

    # Supply Air Trunk (Cyan)
    c.setStrokeColor(colors.HexColor('#0096c7'))
    c.setLineWidth(3)
    c.line(300, 600, 750, 600)
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor('#0077b6'))
    c.drawString(380, 612, "800x400 S.D. 2400 CFM")

    # Fire Damper FD-01 at wall boundary
    c.setStrokeColor(colors.HexColor('#e63946'))
    c.setFillColor(colors.HexColor('#ffccd5'))
    c.rect(350, 585, 20, 30, fill=1)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(colors.HexColor('#9d0208'))
    c.drawString(340, 625, "FD-01 (1.5 HR)")

    # Branches to VAVs
    c.setStrokeColor(colors.HexColor('#0096c7'))
    c.setLineWidth(2)
    c.line(550, 600, 550, 440)
    c.setFont("Helvetica", 9)
    c.drawString(560, 510, "600x300 S.D. 1200 CFM")

    # VAV-101
    c.setStrokeColor(colors.HexColor('#023e8a'))
    c.setFillColor(colors.HexColor('#caf0f8'))
    c.rect(525, 400, 50, 40, fill=1)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.black)
    c.drawString(530, 418, "VAV-101")
    c.setFont("Helvetica", 8)
    c.drawString(530, 388, "650 CFM")

    # Diffusers SAD-01 to SAD-04
    for idx, dx in enumerate([420, 550, 680, 810]):
        c.setStrokeColor(colors.HexColor('#2a9d8f'))
        c.setFillColor(colors.HexColor('#e9d8a6'))
        c.rect(dx - 15, 250, 30, 30, fill=1)
        c.line(dx - 15, 250, dx + 15, 280)
        c.line(dx - 15, 280, dx + 15, 250)
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(colors.black)
        c.drawString(dx - 20, 235, f"SAD-{idx+1:02d}")
        c.setFont("Helvetica", 8)
        c.drawString(dx - 20, 222, "250 CFM")
        # Duct link
        c.setStrokeColor(colors.HexColor('#0096c7'))
        c.line(dx, 280, dx, 380)

    # Return Air Duct (Purple)
    c.setStrokeColor(colors.HexColor('#7209b7'))
    c.setLineWidth(2.5)
    c.line(160, 500, 160, 320)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.HexColor('#7209b7'))
    c.drawString(175, 410, "700x350 R.D.")
    c.rect(130, 290, 60, 30)
    c.drawString(135, 275, "RAG-01 (900x450)")

    # Page 2: Sheet M-102 - Equipment Schedule & Specifications
    c.showPage()
    c.setStrokeColor(colors.HexColor('#212529'))
    c.setLineWidth(2)
    c.rect(30, 30, w - 60, h - 60)
    c.rect(30, 30, w - 60, 60)
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(colors.HexColor('#0d6efd'))
    c.drawString(45, 65, "METROPOLITAN ENGINEERING CONSULTANTS")
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor('#212529'))
    c.drawString(45, 45, "PROJECT: COMMERCIAL TOWER COMPLEX | CLIENT: VERTEX DEVELOPMENTS")
    c.drawString(600, 65, "DRAWING: MECHANICAL EQUIPMENT SCHEDULES & AIR BALANCE TABLE")
    c.drawString(600, 45, "DWG NO: M-102 | REV: C | SCALE: N.T.S. | SHEET 2 OF 2")

    # Schedule Table
    c.setFont("Helvetica-Bold", 14)
    c.drawString(60, 720, "AIR HANDLING & TERMINAL UNIT SCHEDULE")
    
    # Table Header
    headers = ["TAG", "EQUIPMENT DESCRIPTION", "AIRFLOW (CFM)", "COOLING (TR)", "DIMENSIONS (MM)", "ELECTRICAL", "LOCATION"]
    col_x = [60, 140, 380, 500, 620, 780, 930]
    c.setFillColor(colors.HexColor('#e9ecef'))
    c.rect(50, 675, 1050, 25, fill=1)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 9)
    for i, h_text in enumerate(headers):
        c.drawString(col_x[i], 683, h_text)

    # Table Rows
    rows = [
        ("AHU-01", "Air Handling Unit (Chilled Water Coil)", "2400 CFM", "15 TR", "2200 x 1400 x 1200", "400V / 3Ph / 50Hz, 7.5 kW", "Mech Room L2"),
        ("VAV-101", "Pressure Independent VAV Terminal", "650 CFM", "N/A", "850 x 500 x 300", "24V AC Actuator, 10VA", "Ceiling Zone 1"),
        ("VAV-102", "Pressure Independent VAV Terminal", "550 CFM", "N/A", "850 x 500 x 300", "24V AC Actuator, 10VA", "Ceiling Zone 2"),
        ("FD-01", "Motorized Fire & Smoke Damper", "2400 CFM", "N/A", "850 x 450 x 250", "230V Spring Return, 15W", "Mech Room Wall"),
        ("SAD-01..04", "4-Way Modular Supply Diffusers", "250 CFM each", "N/A", "600 x 600 x 300 Neck", "Passive", "Ceiling Grid"),
        ("RAG-01", "Perforated Return Air Grille", "2200 CFM", "N/A", "900 x 450", "Passive", "Low Wall Entry")
    ]
    c.setFont("Helvetica", 9)
    y_pos = 650
    for r in rows:
        for i, val in enumerate(r):
            c.drawString(col_x[i], y_pos, val)
        c.setStrokeColor(colors.HexColor('#dee2e6'))
        c.setLineWidth(0.5)
        c.line(50, y_pos - 6, 1100, y_pos - 6)
        y_pos -= 30

    c.save()
    return output_path

def generate_plumbing_pdf(output_path):
    """Generates an MEP Chilled Water & Fire Protection PDF drawing."""
    c = canvas.Canvas(output_path, pagesize=landscape(A3))
    w, h = landscape(A3)

    c.setStrokeColor(colors.HexColor('#212529'))
    c.setLineWidth(2)
    c.rect(30, 30, w - 60, h - 60)
    c.rect(30, 30, w - 60, 60)
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(colors.HexColor('#0d6efd'))
    c.drawString(45, 65, "METROPOLITAN ENGINEERING CONSULTANTS")
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor('#212529'))
    c.drawString(45, 45, "PROJECT: RESEARCH FACILITY | CLIENT: ADVANCED BIOMED")
    c.drawString(600, 65, "DRAWING: CHILLED WATER & FIRE SPRINKLER SYSTEM")
    c.drawString(600, 45, "DWG NO: P-FP-201 | REV: B | SCALE: 1:50 | SHEET 1 OF 1")

    # Legend
    c.rect(w - 220, 100, 180, 200)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(w - 210, 280, "PIPING & FIRE LEGEND")
    c.setFont("Helvetica", 9)
    
    c.setFillColor(colors.HexColor('#00509d'))
    c.rect(w - 210, 255, 15, 8, fill=1)
    c.setFillColor(colors.black)
    c.drawString(w - 185, 256, 'CHILLED WATER SUPPLY (4")')

    c.setFillColor(colors.HexColor('#e63946'))
    c.rect(w - 210, 230, 15, 8, fill=1)
    c.setFillColor(colors.black)
    c.drawString(w - 185, 231, 'FIRE SPRINKLER MAIN (3")')

    c.setFillColor(colors.HexColor('#2a9d8f'))
    c.circle(w - 202, 210, 6, fill=1)
    c.setFillColor(colors.black)
    c.drawString(w - 185, 207, 'PENDANT SPRINKLER (SP)')

    # Building boundary
    c.setStrokeColor(colors.HexColor('#6c757d'))
    c.setLineWidth(1.5)
    c.rect(80, 140, 850, 590)

    # Chiller CH-01
    c.setStrokeColor(colors.HexColor('#0077b6'))
    c.setFillColor(colors.HexColor('#e0f2fe'))
    c.rect(120, 520, 240, 140, fill=1)
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(colors.black)
    c.drawString(140, 615, "CH-01 (120 TR CHILLER)")
    c.setFont("Helvetica", 9)
    c.drawString(140, 595, "Flow: 288 GPM | 400V 3Ph 85kW")
    c.drawString(140, 575, "Refrigerant: R134a | Sch 40 Steel")

    # Pump CHWP-01
    c.circle(240, 380, 35, fill=1)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(205, 380, "CHWP-01")
    c.setFont("Helvetica", 9)
    c.drawString(190, 325, "120 GPM | 25m Head")

    # Piping lines
    c.setStrokeColor(colors.HexColor('#00509d'))
    c.setLineWidth(3)
    c.line(360, 600, 880, 600)
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor('#00509d'))
    c.drawString(450, 610, '4" CHW-S (DN100 Sch 40 Carbon Steel)')

    c.setStrokeColor(colors.HexColor('#00b4d8'))
    c.line(360, 550, 880, 550)
    c.drawString(450, 535, '4" CHW-R (DN100 Sch 40 Carbon Steel)')

    # Fire Sprinkler Main & Heads
    c.setStrokeColor(colors.HexColor('#e63946'))
    c.setLineWidth(2.5)
    c.line(120, 220, 880, 220)
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor('#e63946'))
    c.drawString(380, 205, '3" FP-MAIN (DN80 Sch 40 Steel)')

    # Sprinkler Zone Valve ZCV-01
    c.circle(150, 220, 15, fill=1)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(130, 245, "ZCV-01")

    # Sprinkler Heads along branches
    for b_idx, bx in enumerate([350, 520, 690, 850]):
        c.setStrokeColor(colors.HexColor('#e63946'))
        c.setLineWidth(1.5)
        c.line(bx, 220, bx, 460)
        c.setFont("Helvetica", 8)
        c.drawString(bx + 5, 330, '1-1/2" FP-BR')
        for sy in [300, 420]:
            sp_num = (b_idx * 2) + (1 if sy == 300 else 2)
            c.setFillColor(colors.HexColor('#e63946'))
            c.circle(bx, sy, 8, fill=1)
            c.setFont("Helvetica-Bold", 8)
            c.drawString(bx + 12, sy - 3, f"SP-{sp_num:02d} (K=5.6, 68°C)")

    # Fire Hose Reel
    c.rect(840, 480, 35, 45)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(830, 535, "FHR-01 (30m)")

    c.save()
    return output_path
