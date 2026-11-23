"""Generates the fictitious data for the Financial Dashboard (made-up company: Aurora Home Decor, Brazil).

Physical store + e-commerce + B2B sales (architects and partner shops), Jan 2025 to Oct 2026.
Snapshot date: 2026-10-31. Output: CSV files in ../data (UTF-8, dot decimal). Amounts in BRL.
Usage: python scripts/generate_data.py
"""
from datetime import date, timedelta
from pathlib import Path
import calendar
import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)
OUT = Path(__file__).resolve().parent.parent / "data"
INICIO, FIM = date(2025, 1, 1), date(2026, 10, 31)
DATA_REF = FIM
SALDO_INICIAL = 180_000.0

SAZON = {1: .85, 2: .85, 3: .95, 4: .95, 5: 1.12, 6: .95, 7: .95, 8: 1.0, 9: .95, 10: 1.02, 11: 1.25, 12: 1.45}

# ---------- chart of accounts ----------
CONTAS = [
    # id, account, group, group order
    (101, "Store Sales", "Gross Revenue", 1),
    (102, "E-commerce Sales", "Gross Revenue", 1),
    (103, "B2B Sales (Architects and Partners)", "Gross Revenue", 1),
    (201, "Sales Taxes (Simples Nacional)", "Deductions", 2),
    (202, "Returns", "Deductions", 2),
    (301, "Cost of Goods Sold", "COGS", 3),
    (401, "Salaries and Payroll Taxes", "Personnel", 4),
    (402, "Owners' Compensation", "Personnel", 4),
    (403, "Benefits", "Personnel", 4),
    (501, "Rent", "Occupancy", 5),
    (502, "Building Fees and Property Tax", "Occupancy", 5),
    (503, "Electricity", "Occupancy", 5),
    (601, "Digital Marketing", "Sales and Marketing", 6),
    (602, "E-commerce Shipping", "Sales and Marketing", 6),
    (603, "Packaging", "Sales and Marketing", 6),
    (701, "Accounting Services", "General and Administrative", 7),
    (702, "Software and Internet", "General and Administrative", 7),
    (703, "Maintenance", "General and Administrative", 7),
    (801, "Card Processing Fees", "Financial Result", 8),
    (802, "Receivables Advance Cost", "Financial Result", 8),
    (803, "Bank Fees", "Financial Result", 8),
    (804, "Interest Income", "Financial Result", 8),
    (901, "Profit Distribution", "Equity Movements", 9),   # cash out, not in the P&L
]
dPlano = pd.DataFrame(CONTAS, columns=["AccountID", "Account", "Group", "GroupOrder"])

lanc, titulos, cartao = [], [], []


def L(competencia, caixa, conta, valor, descricao, origem):
    lanc.append({"AccrualDate": competencia, "CashDate": caixa, "AccountID": conta,
                 "Amount": round(valor, 2), "Description": descricao, "Source": origem})


def dias(d0, d1):
    d = d0
    while d <= d1:
        yield d
        d += timedelta(days=1)


def fim_mes(y, m):
    return date(y, m, calendar.monthrange(y, m)[1])


def add_mes(d, n=1):
    y, m = d.year + (d.month - 1 + n) // 12, (d.month - 1 + n) % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def crescimento(d):
    return 1 + 0.12 * ((d - INICIO).days / 365)


# ---------- retail sales (store + e-commerce), cards ----------
MIX = {
    "Store": [("Pix", .30), ("Cash", .05), ("Debit", .20), ("Credit (single payment)", .20), ("Credit (installments)", .25)],
    "E-commerce": [("Pix", .35), ("Credit (single payment)", .25), ("Credit (installments)", .40)],
}
MDR = {"Debit": .012, "Credit (single payment)": .029, "Credit (installments)": .039}
BANDEIRAS = [("Visa", .45), ("Mastercard", .40), ("Elo", .15)]
receita_mes = {}

for d in dias(INICIO, FIM):
    for canal, conta, base in (("Store", 101, 4600), ("E-commerce", 102, 2500)):
        if canal == "Store":
            wd = {5: 1.45, 6: 0.0}.get(d.weekday(), 1.0)
        else:
            wd = {0: 1.1, 6: 0.85}.get(d.weekday(), 1.0)
        if wd == 0:
            continue
        total = base * SAZON[d.month] * crescimento(d) * wd * RNG.lognormal(0, .18)
        if canal == "E-commerce" and d.month == 11 and 24 <= d.day <= 30:   # Black Friday
            total *= 2.2
        receita_mes[(d.year, d.month)] = receita_mes.get((d.year, d.month), 0) + total
        for forma, peso in MIX[canal]:
            v = total * peso * RNG.uniform(.85, 1.15)
            if forma in ("Pix", "Cash"):
                L(d, d, conta, v, f"{canal} - {forma}", "Retail")
                continue
            for band, pb in BANDEIRAS:
                vb = v * pb
                parcelas = int(RNG.choice([2, 3, 4, 5, 6], p=[.25, .3, .2, .1, .15])) if forma == "Credit (installments)" else 1
                taxa = MDR[forma] + (0.006 if canal == "E-commerce" else 0) + (0.005 * (parcelas - 1) if parcelas > 1 else 0)
                antecipado = forma == "Credit (installments)" and (RNG.random() < (.55 if d.month in (11, 12) else .25))
                custo_antec = 0.0
                for k in range(1, parcelas + 1):
                    if forma == "Debit":
                        rec = d + timedelta(days=1)
                    elif antecipado:
                        rec = d + timedelta(days=2)
                    else:
                        rec = d + timedelta(days=30 * k)
                    vp = vb / parcelas
                    L(d, rec, conta, vp, f"{canal} - {forma} {band}", "Card")
                    L(d, rec, 801, -vp * taxa, f"Card fee {band} {forma}", "Card")
                    if antecipado:
                        c = vp * (1 - taxa) * 0.018 * k
                        custo_antec += c
                        L(d, rec, 802, -c, f"Receivables advance {band}", "Card")
                cartao.append({
                    "SaleDate": d, "Channel": canal, "PaymentType": forma, "CardBrand": band, "Installments": parcelas,
                    "GrossAmount": round(vb, 2), "FeeRate": round(taxa, 4), "FeeAmount": round(vb * taxa, 2),
                    "Advanced": "Yes" if antecipado else "No", "AdvanceCost": round(custo_antec, 2),
                    "NetAmount": round(vb * (1 - taxa) - custo_antec, 2),
                    "FirstSettlement": d + timedelta(days=1 if forma == "Debit" else 2 if antecipado else 30),
                    "LastSettlement": d + timedelta(days=1 if forma == "Debit" else 2 if antecipado else 30 * parcelas),
                })

# ---------- bills (receivables and payables) ----------
tid = [0]


def titulo(tipo, contraparte, conta, emissao, venc, valor, categoria, atraso_p=(.88, .09, .03)):
    """Creates the bill and its ledger lines. atraso_p: on time / late / unpaid (as of the snapshot)."""
    tid[0] += 1
    r = RNG.random()
    if venc > DATA_REF:
        pag = None                                    # vence depois da data de referência
    elif r < atraso_p[0]:
        pag = venc - timedelta(days=int(RNG.integers(0, 3)))
    elif r < atraso_p[0] + atraso_p[1]:
        pag = venc + timedelta(days=int(RNG.integers(3, 50)))
        if pag > DATA_REF:
            pag = None
    else:
        pag = None                                    # inadimplente / em atraso
    titulos.append({"BillID": tid[0], "Type": tipo, "Counterparty": contraparte, "Category": categoria,
                    "AccountID": conta, "IssueDate": emissao, "DueDate": venc, "PaymentDate": pag,
                    "Amount": round(valor, 2)})
    sinal = 1 if tipo == "Receivable" else -1
    L(emissao, pag, conta, sinal * valor, f"{tipo}: {contraparte}", "Bill")


CLIENTES_B2B = ["Studio Linha Arquitetura", "Marina Couto Interiores", "Arq. Paulo Mendes", "Casa & Forma Projetos",
                "Loja Raiz Decor", "Atelier Nobre", "Construtora Vale Verde", "Espaço Bossa Interiores",
                "Hotel Serra Azul", "Clínica Vitta", "Rocha & Lima Arquitetos", "Bistrô Jardim"]
FORNECEDORES = ["Têxtil Paraná", "Cerâmica Vale", "Madeira Nobre Móveis", "Iluminar Distribuidora",
                "Import Decor Brasil", "Vidros Cristal"]

m = INICIO
while m <= FIM:
    y, mo = m.year, m.month
    fm = fim_mes(y, mo)
    # B2B: notas de projetos, boleto 28/42 dias
    b2b = 0.0
    for _ in range(int(RNG.integers(6, 11))):
        em = date(y, mo, int(RNG.integers(1, fm.day + 1)))
        v = RNG.uniform(3000, 22000) * SAZON[mo] ** .5 * crescimento(em)
        b2b += v
        titulo("Receivable", str(RNG.choice(CLIENTES_B2B)), 103, em, em + timedelta(days=int(RNG.choice([28, 42]))),
               v, "B2B Sale", (.80, .14, .06))
    receita = receita_mes[(y, mo)] + b2b
    # Simples Nacional: dia 20 do mês seguinte
    titulo("Payable", "Federal Revenue - Simples Nacional", 201, fm, add_mes(date(y, mo, 20)), receita * .095, "Taxes", (.99, .01, 0))
    # Devoluções (estorno no mesmo mês)
    dv = receita * RNG.uniform(.008, .015)
    L(fm, fm, 202, -dv, "Customer returns", "Retail")
    # CMV: compras de fornecedores, 30/60/90 dias
    cmv = receita * RNG.uniform(.42, .45)
    partes = RNG.dirichlet(np.ones(4))
    for p in partes:
        em = date(y, mo, int(RNG.integers(1, fm.day + 1)))
        forn = str(RNG.choice(FORNECEDORES))
        for k, frac in ((30, .4), (60, .3), (90, .3)):
            titulo("Payable", forn, 301, em, em + timedelta(days=k), cmv * p * frac, "Suppliers", (.96, .04, 0))
    g = crescimento(m)
    folha = 42000 * (1.06 if y == 2026 else 1) * (1.5 if mo == 12 else 1)   # 13º em dezembro
    fixos = [
        (401, "Payroll", folha, add_mes(date(y, mo, 5)), "Personnel"),
        (402, "Owners' compensation", 12000, add_mes(date(y, mo, 5)), "Personnel"),
        (403, "Meal, transport and health plan", 5200 * (1.05 if y == 2026 else 1), date(y, mo, 10), "Personnel"),
        (501, "Centro Real Estate", 18000 * (1.045 if y == 2026 else 1), date(y, mo, 10), "Occupancy"),
        (502, "Building fees and property tax", 2500, date(y, mo, 10), "Occupancy"),
        (503, "Power utility", RNG.uniform(2200, 3600), date(y, mo, 18), "Occupancy"),
        (601, "Google and Meta Ads", RNG.uniform(5000, 9000) * SAZON[mo], date(y, mo, 25), "Marketing"),
        (602, "Carriers", receita_mes[(y, mo)] * .35 * .08, add_mes(date(y, mo, 10)), "Logistics"),
        (603, "Embalagens Sul", receita * .015, add_mes(date(y, mo, 15)), "Supplies"),
        (701, "Exato Accounting", 2200, date(y, mo, 15), "Services"),
        (702, "ERP, website and internet", 1300 * g, date(y, mo, 12), "Services"),
        (703, "Building maintenance", RNG.uniform(0, 2500), date(y, mo, 22), "Services"),
        (803, "Bank fees", RNG.uniform(300, 520), date(y, mo, 28), "Banks"),
    ]
    for conta, quem, v, venc, cat in fixos:
        if v < 1:
            continue
        titulo("Payable", quem, conta, fm if venc > fm else date(y, mo, 1), venc, v, cat, (.95, .05, 0))
    L(fm, fm, 804, RNG.uniform(900, 1800), "CDB interest", "Bank")
    if mo in (3, 6, 9, 12):   # quarterly distribution to owners
        titulo("Payable", "Owners - distribution", 901, fm, add_mes(date(y, mo, 15)), 95000 if y == 2025 else 105000,
               "Owners", (1, 0, 0))
    m = add_mes(date(y, mo, 1))

# ---------- budget (monthly target per account) ----------
f = pd.DataFrame(lanc)
f["Month"] = pd.to_datetime(f["AccrualDate"]).dt.to_period("M").dt.to_timestamp()
real = f.groupby(["Month", "AccountID"])["Amount"].sum().reset_index()
orc = real.copy()
fator = np.where(orc["AccountID"] < 200, RNG.uniform(.98, 1.07, len(orc)), RNG.uniform(.95, 1.06, len(orc)))
orc["Amount"] = (orc["Amount"] * fator).round(-2)
orc = orc[["Month", "AccountID", "Amount"]]

# ---------- bill status at the snapshot date ----------
t = pd.DataFrame(titulos)
ref = pd.Timestamp(DATA_REF)
t["IssueDate"] = pd.to_datetime(t["IssueDate"])
t["DueDate"] = pd.to_datetime(t["DueDate"])
t["PaymentDate"] = pd.to_datetime(t["PaymentDate"])
atraso = (ref - t["DueDate"]).dt.days
t["Status"] = np.where(t["PaymentDate"].notna(), "Paid", np.where(atraso > 0, "Overdue", "Not yet due"))
t["AgingBucket"] = np.select(
    [t["Status"] == "Paid", t["Status"] == "Not yet due", atraso <= 30, atraso <= 60, atraso <= 90],
    ["Paid", "Not yet due", "1-30 days", "31-60 days", "61-90 days"], "90+ days")
t["AgingOrder"] = t["AgingBucket"].map({"Not yet due": 1, "1-30 days": 2, "31-60 days": 3, "61-90 days": 4,
                                        "90+ days": 5, "Paid": 6})
t["DaysOverdue"] = np.where(t["Status"] == "Overdue", atraso, 0)
t["DaysToPay"] = (t["PaymentDate"] - t["IssueDate"]).dt.days
t["SignedAmount"] = np.where(t["Type"] == "Receivable", 1, -1) * t["Amount"]

# ---------- calendar ----------
cal = pd.DataFrame({"Date": pd.date_range("2025-01-01", "2027-06-30")})
MESES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
cal["Year"] = cal["Date"].dt.year
cal["MonthNum"] = cal["Date"].dt.month
cal["Month"] = cal["MonthNum"].map(lambda i: MESES[i - 1])
cal["MonthYear"] = cal["Month"] + " " + (cal["Year"] % 100).astype(str)
cal["YearMonth"] = cal["Year"] * 100 + cal["MonthNum"]
cal["Quarter"] = "Q" + cal["Date"].dt.quarter.astype(str)
cal["MonthStart"] = cal["Date"].dt.to_period("M").dt.to_timestamp()

# ---------- P&L lines (disconnected table) ----------
dre = pd.DataFrame([
    (1, "Gross Revenue", "Line"), (2, "(-) Deductions", "Line"), (3, "= Net Revenue", "Subtotal"),
    (4, "(-) COGS", "Line"), (5, "= Gross Profit", "Subtotal"), (6, "(-) Personnel", "Line"),
    (7, "(-) Occupancy", "Line"), (8, "(-) Sales and Marketing", "Line"), (9, "(-) General and Administrative", "Line"),
    (10, "= EBITDA", "Subtotal"), (11, "(+/-) Financial Result", "Line"), (12, "= Net Income", "Subtotal"),
], columns=["LineOrder", "Line", "LineType"])

# ---------- write ----------
OUT.mkdir(parents=True, exist_ok=True)
f.drop(columns=["Month"]).to_csv(OUT / "FactLedger.csv", index=False, date_format="%Y-%m-%d")
t.to_csv(OUT / "FactBills.csv", index=False, date_format="%Y-%m-%d")
pd.DataFrame(cartao).to_csv(OUT / "FactCardSales.csv", index=False, date_format="%Y-%m-%d")
orc.to_csv(OUT / "FactBudget.csv", index=False, date_format="%Y-%m-%d")
dPlano.to_csv(OUT / "DimAccount.csv", index=False)
cal.to_csv(OUT / "DimDate.csv", index=False, date_format="%Y-%m-%d")
dre.to_csv(OUT / "DimPnLLine.csv", index=False)
pd.DataFrame([{"SnapshotDate": DATA_REF, "OpeningCash": SALDO_INICIAL}]).to_csv(
    OUT / "Parameters.csv", index=False, date_format="%Y-%m-%d")

# summary for checking
f["Year"] = pd.to_datetime(f["AccrualDate"]).dt.year
res = f.merge(dPlano, on="AccountID").groupby(["Year", "Group"])["Amount"].sum().unstack(0).round(0)
print(res)
print("Net result by year (after distributions):", f.groupby("Year")["Amount"].sum().round(0).to_dict())
caixa = f[pd.to_datetime(f["CashDate"]) <= ref]["Amount"].sum() + SALDO_INICIAL
print("Cash balance on", DATA_REF, round(caixa, 0))
print("Rows:", {"ledger": len(f), "bills": len(t), "card_sales": len(cartao)})
