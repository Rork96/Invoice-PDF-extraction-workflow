import csv, os
from datetime import date, timedelta
from decimal import Decimal as D, ROUND_HALF_UP
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer

OUT = "/mnt/user-data/outputs/invoices"
os.makedirs(OUT, exist_ok=True)
q = lambda x: x.quantize(D("0.01"), rounding=ROUND_HALF_UP)

# ---- formatting -----------------------------------------------------------
def money(v, style):
    s = f"{v:,.2f}"
    if style == "usd":   return "$" + s
    if style == "cad":   return "CA$" + s
    if style == "cad2":  return s + " CAD"
    if style == "eur_de": return s.replace(",", "X").replace(".", ",").replace("X", ".") + " €"
    if style == "eur_en": return "€" + s
    raise ValueError(style)

DATEFMT = {
    "iso":  lambda d: d.strftime("%Y-%m-%d"),
    "dmy":  lambda d: d.strftime("%d/%m/%Y"),
    "mdy":  lambda d: d.strftime("%m/%d/%Y"),
    "long": lambda d: d.strftime("%B %d, %Y").replace(" 0", " "),
    "dmon": lambda d: d.strftime("%d %b %Y"),
    "mon":  lambda d: d.strftime("%b %d, %Y").replace(" 0", " "),
    "dot":  lambda d: d.strftime("%d.%m.%Y"),
    "ymd_slash": lambda d: d.strftime("%Y/%m/%d"),
}

# ---- invoice definitions (all names/addresses invented) --------------------
INV = [
 dict(n=1, layout="A", cur="USD", ms="usd", df="iso", num="ZLW-2026-0147", inv=date(2026,1,12), terms=30,
  vendor="Zorvex Lumenworks Ltd", vaddr=["88 Glimmerdock Row", "Vantor Falls, Nordavia 00417"],
  cust="Bellmarrow Print House", caddr=["5 Tansy Court", "Ilmenford, Nordavia 00982"],
  taxname="Sales Tax", rate=D("7"),
  items=[("LED panel 60x60, warm white",12,D("38.50")),("Mounting bracket set",12,D("4.75")),("Installation labour (hrs)",6.5,D("55.00"))]),
 dict(n=2, layout="B", cur="CAD", ms="cad", df="dmy", num="QTC-30918", inv=date(2026,2,14), terms=14,
  vendor="Quillmere Tooling Co.", vaddr=["Unit 9, 301 Ashgrove Parkway", "Pembrook Landing, Maplevale X1X 1X1"],
  cust="Thistlewick Bakery Collective", caddr=["77 Orchard Spur", "Pembrook Landing, Maplevale X1X 2Y2"],
  taxname="GST", rate=D("5"),
  items=[("Industrial dough sheeter service call",1,D("1480.00"))]),
 dict(n=3, layout="C", cur="EUR", ms="eur_de", df="dot", num="NA-0000412", inv=date(2026,3,14), terms=30,
  vendor="Nolvane Analytics GmbH", vaddr=["Brunnenmark 12", "Kessling am Wehr, Orvania 90871"],
  cust="Havelmoor Logistik AG", caddr=["Speicherweg 3", "Havelmoor, Orvania 90113"],
  taxname="VAT", rate=D("19"),
  items=[("Data pipeline audit",1,D("4200.00")),("Dashboard design (days)",3,D("780.00")),
         ("Quarterly KPI report",2,D("650.00")),("Training workshop (half-day)",1,D("900.00")),
         ("Cloud sandbox hosting (month)",3,D("129.90")),("Travel flat fee",1,D("185.00"))]),
 dict(n=4, layout="B", cur="USD", ms="usd", df="long", num="OPS-7781", inv=date(2026,3,28), terms=15,
  vendor="Ostrel Pixel Studio", vaddr=["402 Marrowlight Ave", "Cinderfield, Westmark 20655"],
  cust="Juniper & Quarry Outfitters", caddr=["19 Wicker Mews", "Cinderfield, Westmark 20655"],
  taxname="Tax (exempt)", rate=D("0"),
  items=[("Brand identity package",1,D("2400.00")),("Social media template pack",1,D("350.00"))]),
 dict(n=5, layout="A", cur="CAD", ms="cad2", df="mdy", num="KGH/2026/055", inv=date(2026,5,21), terms=30,
  vendor="Kyrrow Greenhouses Inc.", vaddr=["RR 4, Fennel Road", "Dunmoor Flats, Maplevale Y2Y 3Z3"],
  cust="Applegarth Community Kitchen", caddr=["12 Linden Vale", "Dunmoor Flats, Maplevale Y2Y 4A4"],
  taxname="GST", rate=D("5"),
  items=[("Tomato seedlings, tray of 72",10,D("46.00")),("Organic potting mix 50L",20,D("18.25")),
         ("Raised bed kit",3,D("129.00"))],
  total_err=D("100.00")),   # PROBLEM: printed total = correct + 100.00
 dict(n=6, layout="C", cur="EUR", ms="eur_en", df="dmon", num="TC-20260602-9", inv=date(2026,6,2), terms=21,
  vendor="Tavimor Cloudware", vaddr=["Lindenhof 7", "Sarrowby, Calvera 4410"],
  cust="Mirelle Archives SARL", caddr=["Rue des Tisserands 21", "Aubrelle, Calvera 4455"],
  taxname="VAT", rate=D("7"),
  items=[("Team licence (seat/month)",14,D("22.00")),("Priority support plan",1,D("240.00")),
         ("Onboarding session",1,D("350.00")),("Extra storage 500GB",2,D("19.99"))]),
 dict(n=7, layout="A", cur="USD", ms="usd", df="mon", num="PB-100236", inv=date(2026,7,9), terms=30,
  vendor="Pellwick Brineworks", vaddr=["1 Saltmarsh Quay", "Gullrock Point, Eastmere 31208"],
  cust="Corvane Diner Group", caddr=["640 Fable Street", "Greywater, Eastmere 31490"],
  taxname="Sales Tax", rate=D("6.25"),
  items=[("Sea salt, coarse 25kg",8,D("31.40")),("Smoked salt 5kg",4,D("42.10")),("Pickling brine concentrate 10L",6,D("27.95")),
         ("Pallet wrap",5,D("9.80")),("Delivery",1,D("65.00"))]),
 dict(n=8, layout="B", cur="CAD", ms="cad", df="ymd_slash", num=None, inv=date(2026,8,15), terms=30,   # PROBLEM: no invoice number
  vendor="Draxon Mapleleaf Supply", vaddr=["230 Brindle Industrial Dr", "Oakhollow, Maplevale Z3Z 5B5"],
  cust="Sunnybrook Roofing Crew", caddr=["58 Gable Close", "Oakhollow, Maplevale Z3Z 6C6"],
  taxname="GST", rate=D("5"),
  items=[("Roofing nails 25kg box",6,D("64.20")),("Underlayment roll",11,D("88.75")),("Safety harness",2,D("139.99"))]),
 dict(n=9, layout="C", cur="EUR", ms="eur_de", df="iso", num="FA-2026-1203", inv=date(2026,9,3), terms=10,
  vendor="Fennivale Audio SARL", vaddr=["Passage du Lierre 4", "Montrelle, Calvera 4502"],
  cust="Studio Orlenne", caddr=["Allée des Pins 18", "Montrelle, Calvera 4502"],
  taxname="TVA", rate=D("21"),
  items=[("Condenser microphone, matched pair",1,D("1190.00")),("Shock mount",2,D("64.50"))]),
 dict(n=10, layout="B", cur="USD", ms="usd", df="dmon", num="2026-INV-000873", inv=date(2026,9,30), terms=45,
  vendor="Brantavo Freight Partners", vaddr=["Dock 14, Harbourline Estate", "Port Esker, Westmark 20871"],
  cust="Lowmere Hardware Co-op", caddr=["900 Tallow Row", "Port Esker, Westmark 20872"],
  taxname="Sales Tax", rate=D("8.5"),
  items=[("Ocean freight, 20ft container",1,D("3150.00")),("Port handling",1,D("420.00")),("Customs paperwork",1,D("95.00")),
         ("Inland trucking (km)",212,D("2.35")),("Cargo insurance",1,D("188.40")),("Storage (days)",4,D("52.00"))]),
]

# ---- compute -------------------------------------------------------------
for i in INV:
    i["rows"] = [(d, D(str(qty)), up, q(D(str(qty)) * up)) for d, qty, up in i["items"]]
    i["sub"] = sum(r[3] for r in i["rows"])
    i["tax"] = q(i["sub"] * i["rate"] / 100)
    i["total"] = i["sub"] + i["tax"]
    i["printed_total"] = i["total"] + i.get("total_err", D("0"))
    i["due"] = i["inv"] + timedelta(days=i["terms"])
    i["file"] = f"invoice_{i['n']:02d}.pdf"

def qty_s(x): return f"{x.normalize():f}" if x == x.to_integral() else f"{x:f}"
def rate_s(r): return f"{r.normalize():f}"

# ---- layouts -------------------------------------------------------------
def P(t, **k):
    base = dict(fontName="Helvetica", fontSize=9, leading=12)
    base.update(k); return Paragraph(t, ParagraphStyle("x", **base))

def layout_A(i, path):   # classic: left vendor block, right title, full grid table
    m = lambda v: money(v, i["ms"]); f = DATEFMT[i["df"]]
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm, topMargin=18*mm, bottomMargin=18*mm)
    meta = [P(f"<b>Invoice No:</b> {i['num']}", alignment=2)] if i["num"] else []
    meta += [P(f"<b>Date:</b> {f(i['inv'])}", alignment=2), P(f"<b>Due:</b> {f(i['due'])}", alignment=2)]
    head = Table([[[P(f"<b>{i['vendor']}</b>", fontSize=14, leading=18)] + [P(l) for l in i["vaddr"]],
                   [P("INVOICE", fontName="Helvetica-Bold", fontSize=22, leading=26, alignment=2)] + meta]],
                 colWidths=[95*mm, 79*mm])
    bill = Table([[P("<b>Bill to</b>")], [P(i["cust"])], *[[P(l)] for l in i["caddr"]]], colWidths=[90*mm])
    data = [["Description", "Qty", "Unit price", "Amount"]] + \
           [[r[0], qty_s(r[1]), m(r[2]), m(r[3])] for r in i["rows"]]
    t = Table(data, colWidths=[85*mm, 18*mm, 35*mm, 36*mm])
    t.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.6,colors.black),("BACKGROUND",(0,0),(-1,0),colors.HexColor("#DDDDDD")),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),9),("ALIGN",(1,0),(-1,-1),"RIGHT")]))
    tot = Table([["Subtotal", m(i["sub"])], [f"{i['taxname']} ({rate_s(i['rate'])}%)", m(i["tax"])],
                 ["TOTAL DUE", m(i["printed_total"])]], colWidths=[35*mm, 36*mm], hAlign="RIGHT")
    tot.setStyle(TableStyle([("ALIGN",(1,0),(1,-1),"RIGHT"),("FONTNAME",(0,2),(-1,2),"Helvetica-Bold"),
        ("LINEABOVE",(0,2),(-1,2),1,colors.black),("FONTSIZE",(0,0),(-1,-1),10)]))
    doc.build([head, Spacer(1,10*mm), bill, Spacer(1,8*mm), t, Spacer(1,5*mm), tot, Spacer(1,15*mm),
               P(f"Payment terms: net {i['terms']} days. Currency: {i['cur']}.", fontSize=8)])

def layout_B(i, path):   # modern: colored top band, borderless table, zebra rows
    m = lambda v: money(v, i["ms"]); f = DATEFMT[i["df"]]
    accent = colors.HexColor("#1F6F6B")
    def band(c, d):
        c.saveState(); c.setFillColor(accent); c.rect(0, A4[1]-38*mm, A4[0], 38*mm, stroke=0, fill=1)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 20); c.drawString(18*mm, A4[1]-18*mm, i["vendor"])
        c.setFont("Helvetica", 9)
        for k, l in enumerate(i["vaddr"]): c.drawString(18*mm, A4[1]-25*mm-k*4.5*mm, l)
        c.setFont("Helvetica-Bold", 26); c.drawRightString(A4[0]-18*mm, A4[1]-20*mm, "Invoice"); c.restoreState()
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm, topMargin=48*mm, bottomMargin=18*mm)
    cells = [[P("<b>BILLED TO</b>", textColor=accent)] , [P(i["cust"])], *[[P(l)] for l in i["caddr"]]]
    left = Table(cells, colWidths=[85*mm])
    rows = []
    if i["num"]: rows.append([P("<b>Invoice #</b>"), P(i["num"])])
    rows += [[P("<b>Issued</b>"), P(f(i["inv"]))], [P("<b>Payment due</b>"), P(f(i["due"]))], [P("<b>Currency</b>"), P(i["cur"])]]
    right = Table(rows, colWidths=[30*mm, 50*mm])
    top = Table([[left, right]], colWidths=[90*mm, 84*mm])
    data = [["ITEM", "QTY", "PRICE", "LINE TOTAL"]] + [[r[0], qty_s(r[1]), m(r[2]), m(r[3])] for r in i["rows"]]
    t = Table(data, colWidths=[85*mm, 18*mm, 35*mm, 36*mm])
    st = [("TEXTCOLOR",(0,0),(-1,0),accent),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("LINEBELOW",(0,0),(-1,0),1.2,accent),
          ("ALIGN",(1,0),(-1,-1),"RIGHT"),("FONTSIZE",(0,0),(-1,-1),9),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]
    for k in range(2, len(data), 2): st.append(("BACKGROUND",(0,k),(-1,k),colors.HexColor("#EEF4F3")))
    t.setStyle(TableStyle(st))
    tot = Table([["Subtotal", m(i["sub"])], [f"{i['taxname']} {rate_s(i['rate'])}%", m(i["tax"])], ["Amount due", m(i["printed_total"])]],
                colWidths=[35*mm, 36*mm], hAlign="RIGHT")
    tot.setStyle(TableStyle([("ALIGN",(1,0),(1,-1),"RIGHT"),("FONTNAME",(0,2),(-1,2),"Helvetica-Bold"),("FONTSIZE",(0,2),(-1,2),12),
        ("TEXTCOLOR",(0,2),(-1,2),accent),("LINEABOVE",(0,2),(-1,2),1.2,accent)]))
    doc.build([top, Spacer(1,10*mm), t, Spacer(1,6*mm), tot, Spacer(1,20*mm), P("Thank you for your business.", textColor=accent)],
              onFirstPage=band, onLaterPages=band)

def layout_C(i, path):   # compact centered, US Letter, boxed totals, labels in table form
    m = lambda v: money(v, i["ms"]); f = DATEFMT[i["df"]]
    doc = SimpleDocTemplate(path, pagesize=letter, leftMargin=25*mm, rightMargin=25*mm, topMargin=20*mm, bottomMargin=20*mm)
    el = [P(f"<b>{i['vendor'].upper()}</b>", fontSize=15, leading=19, alignment=1)]
    el += [P(l, alignment=1) for l in i["vaddr"]] + [Spacer(1,6*mm), P("— INVOICE —", fontName="Courier-Bold", fontSize=13, alignment=1), Spacer(1,4*mm)]
    info = []
    if i["num"]: info.append(["Invoice number", i["num"]])
    info += [["Invoice date", f(i["inv"])], ["Due date", f(i["due"])], ["Customer", i["cust"]], ["", i["caddr"][0]], ["", i["caddr"][1]]]
    ti = Table(info, colWidths=[40*mm, 90*mm]); ti.setStyle(TableStyle([("FONTSIZE",(0,0),(-1,-1),9),("FONTNAME",(0,0),(0,-1),"Helvetica-Bold")]))
    el += [ti, Spacer(1,6*mm)]
    data = [["#", "Description", "Qty", "Rate", "Total"]] + [[str(k+1), r[0], qty_s(r[1]), m(r[2]), m(r[3])] for k, r in enumerate(i["rows"])]
    t = Table(data, colWidths=[8*mm, 66*mm, 15*mm, 30*mm, 30*mm])
    t.setStyle(TableStyle([("LINEABOVE",(0,0),(-1,0),1,colors.black),("LINEBELOW",(0,0),(-1,0),0.5,colors.black),
        ("LINEBELOW",(0,-1),(-1,-1),1,colors.black),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),8.5),
        ("ALIGN",(2,0),(-1,-1),"RIGHT")]))
    tot = Table([["Net amount", m(i["sub"])], [f"{i['taxname']} @ {rate_s(i['rate'])}%", m(i["tax"])], [f"Gross total ({i['cur']})", m(i["printed_total"])]],
                colWidths=[45*mm, 35*mm], hAlign="RIGHT")
    tot.setStyle(TableStyle([("BOX",(0,0),(-1,-1),1,colors.black),("ALIGN",(1,0),(1,-1),"RIGHT"),("FONTNAME",(0,2),(-1,2),"Helvetica-Bold"),
        ("BACKGROUND",(0,2),(-1,2),colors.HexColor("#EFEFEF")),("FONTSIZE",(0,0),(-1,-1),9.5)]))
    el += [t, Spacer(1,6*mm), tot, Spacer(1,12*mm), P(f"Please pay within {i['terms']} days of the invoice date.", fontSize=8, alignment=1)]
    doc.build(el)

L = dict(A=layout_A, B=layout_B, C=layout_C)
for i in INV: L[i["layout"]](i, os.path.join(OUT, i["file"]))

# ---- expected.csv -------------------------------------------------------
iso = DATEFMT["iso"]
with open(os.path.join(OUT, "expected.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["file","layout","invoice_number","vendor_name","customer_name","invoice_date","due_date","currency",
                "line_item_count","subtotal","tax_rate_pct","tax_amount","total","printed_total","problem"])
    for i in INV:
        prob = ""
        if "total_err" in i: prob = "total_mismatch"
        if i["num"] is None: prob = "missing_invoice_number"
        w.writerow([i["file"], i["layout"], i["num"] or "", i["vendor"], i["cust"], iso(i["inv"]), iso(i["due"]), i["cur"],
                    len(i["rows"]), i["sub"], rate_s(i["rate"]), i["tax"], i["total"], i["printed_total"], prob])
print("ok")
