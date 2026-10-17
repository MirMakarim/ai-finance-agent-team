"""Sample finance database (SQLite) and a read-only query tool.

The data is fictional and seeded, with a handful of planted exceptions so the
agents have something real to find: price and quantity mismatches, a duplicate
invoice, an invoice without a PO, unmatched bank lines and budget overruns.
"""
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "finance.db"

SCHEMA = """
CREATE TABLE vendors        (vendor_id TEXT PRIMARY KEY, vendor_name TEXT, payment_terms_days INT);
CREATE TABLE purchase_orders(po_number TEXT, po_line INT, vendor_id TEXT, description TEXT,
                             quantity INT, unit_price REAL, cost_center TEXT, po_date TEXT,
                             PRIMARY KEY (po_number, po_line));
CREATE TABLE invoices       (invoice_id TEXT PRIMARY KEY, vendor_id TEXT, vendor_invoice_no TEXT,
                             po_number TEXT, po_line INT, quantity INT, unit_price REAL,
                             amount REAL, invoice_date TEXT);
CREATE TABLE ledger_payments(payment_id TEXT PRIMARY KEY, vendor_id TEXT, invoice_id TEXT,
                             amount REAL, payment_date TEXT, reference TEXT);
CREATE TABLE bank_statement (line_id TEXT PRIMARY KEY, booking_date TEXT, amount REAL,
                             counterparty TEXT, reference TEXT);
CREATE TABLE budget         (cost_center TEXT, period TEXT, budget_amount REAL,
                             PRIMARY KEY (cost_center, period));
"""

VENDORS = [("V100", "Nordtech Components GmbH", 30), ("V101", "Rheinpack AG", 45),
           ("V102", "Baltic Logistik KG", 30), ("V103", "Apex Tooling s.r.o.", 60),
           ("V104", "Lumen Electronics B.V.", 30), ("V105", "Granite IT Services Ltd", 45)]
COST_CENTERS = ["CC-PROD", "CC-LOG", "CC-IT", "CC-MAINT"]
ITEMS = {"V100": ("Sensor modules", "CC-PROD"), "V101": ("Packaging material", "CC-LOG"),
         "V102": ("Road freight", "CC-LOG"), "V103": ("Tool maintenance", "CC-MAINT"),
         "V104": ("LED drivers", "CC-PROD"), "V105": ("IT support hours", "CC-IT")}


def build(period: str = "2025-11", seed: int = 7, path: Path = DB_PATH) -> Path:
    """Create a fresh database for one month. Returns the file path."""
    rnd = random.Random(seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    con.executemany("INSERT INTO vendors VALUES (?,?,?)", VENDORS)

    year, month = map(int, period.split("-"))
    start = date(year, month, 1)
    pos, invs, pays, bank = [], [], [], []
    for i in range(40):
        vendor = VENDORS[i % len(VENDORS)][0]
        desc, cc = ITEMS[vendor]
        po = f"45{1000 + i:06d}"
        qty, price = rnd.randint(10, 400), round(rnd.uniform(5, 180), 2)
        po_date = start + timedelta(days=rnd.randint(0, 10))
        pos.append((po, 10, vendor, desc, qty, price, cc, po_date.isoformat()))

        inv_id = f"INV-{i + 1:04d}"
        inv_date = po_date + timedelta(days=rnd.randint(3, 12))
        inv_qty, inv_price = qty, price
        if i in (4, 17):                       # planted: price higher than PO
            inv_price = round(price * 1.08, 2)
        if i == 23:                            # planted: quantity higher than PO
            inv_qty = qty + 25
        amount = round(inv_qty * inv_price, 2)
        invs.append((inv_id, vendor, f"{vendor}-{9000 + i}", po, 10, inv_qty, inv_price, amount, inv_date.isoformat()))

        pay_date = inv_date + timedelta(days=rnd.randint(2, 8))
        pays.append((f"PAY-{i + 1:04d}", vendor, inv_id, amount, pay_date.isoformat(), inv_id))
        if i != 31:                            # planted: one payment missing on the bank statement
            bank_amount = amount if i != 12 else round(amount - 15.00, 2)   # planted: bank fee deducted
            book = pay_date + timedelta(days=rnd.choice([0, 1, 1, 2]))
            vname = dict((v[0], v[1]) for v in VENDORS)[vendor]
            bank.append((f"BS-{i + 1:04d}", book.isoformat(), -bank_amount, vname, inv_id))

    # planted: duplicate invoice (same vendor invoice number, new internal id)
    dup = list(invs[8]); dup[0] = "INV-0041"; dup[8] = (date.fromisoformat(dup[8]) + timedelta(days=5)).isoformat()
    invs.append(tuple(dup))
    # planted: invoice that references no PO
    invs.append(("INV-0042", "V105", "V105-9999", None, None, 12, 95.0, 1140.0, (start + timedelta(days=20)).isoformat()))
    # planted: bank line with no ledger payment
    bank.append(("BS-0099", (start + timedelta(days=22)).isoformat(), -2380.00, "Unknown Services GmbH", "SEPA DD 77812"))

    con.executemany("INSERT INTO purchase_orders VALUES (?,?,?,?,?,?,?,?)", pos)
    con.executemany("INSERT INTO invoices VALUES (?,?,?,?,?,?,?,?,?)", invs)
    con.executemany("INSERT INTO ledger_payments VALUES (?,?,?,?,?,?)", pays)
    con.executemany("INSERT INTO bank_statement VALUES (?,?,?,?,?)", bank)

    # Budget: actual spend per cost center, with CC-LOG and CC-IT planted over budget
    actual = dict(con.execute(
        "SELECT p.cost_center, SUM(i.amount) FROM invoices i JOIN purchase_orders p "
        "ON p.po_number = i.po_number AND p.po_line = i.po_line GROUP BY p.cost_center"))
    factors = {"CC-PROD": 1.05, "CC-LOG": 0.80, "CC-IT": 0.70, "CC-MAINT": 1.10}
    con.executemany("INSERT INTO budget VALUES (?,?,?)",
                    [(cc, period, round(actual.get(cc, 0) * factors[cc], -2)) for cc in COST_CENTERS])
    con.commit()
    con.close()
    return path


class SqlTool:
    """Read-only SQL access for agents. Only single SELECT statements are allowed."""

    name = "query_finance_db"
    description = "Run a read-only SELECT query on the finance database and return rows as dicts."

    def __init__(self, path: Path = DB_PATH):
        # mode=ro opens the file read-only at the driver level
        self.con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        self.con.row_factory = sqlite3.Row
        self.calls = 0

    def __call__(self, sql: str, params: tuple = ()) -> list:
        statement = sql.strip().rstrip(";")
        if not statement.lower().startswith(("select", "with")) or ";" in statement:
            raise PermissionError("Only single read-only SELECT statements are allowed")
        self.calls += 1
        return [dict(r) for r in self.con.execute(statement, params).fetchall()]
