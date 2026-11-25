"""SQLite dataset for Harbor & Pine Supply Co. (fictional).

Deterministic seed, data through 2026-10-31. The tricky bits are
deliberate: orders.total_cents is INTEGER CENTS (not dollars),
payments.status in ('paid','refunded','failed'), channels in
('online','phone','in-store'), plus discontinued / is_vip flags.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    signup_date TEXT NOT NULL,
    is_vip INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    order_date TEXT NOT NULL,
    channel TEXT NOT NULL,
    total_cents INTEGER NOT NULL,
    discount_code TEXT
);
CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    qty INTEGER NOT NULL,
    unit_price_cents INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    sku TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    discontinued INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    method TEXT NOT NULL
);
"""

PRODUCTS = [
    (1, "P-1001", "Cedar Garden Bench", "outdoor", 0),
    (2, "P-1002", "Pine Bookshelf", "furniture", 0),
    (3, "P-1003", "Harbor Rope Lantern", "lighting", 0),
    (4, "P-1004", "Maple Cutting Board", "kitchen", 0),
    (5, "P-1005", "Canvas Tool Tote", "storage", 0),
    (6, "P-1006", "Brass Compass", "decor", 1),
    (7, "P-1007", "Oak Side Table", "furniture", 0),
    (8, "P-1008", "Wool Throw Blanket", "textiles", 1),
    (9, "P-1009", "Steel Garden Trowel", "outdoor", 0),
    (10, "P-1010", "Ceramic Pour-Over Set", "kitchen", 0),
]

# unit price per product, for order_items
PRICE = {1: 12999, 2: 4599, 3: 3499, 4: 2100, 5: 2799,
         6: 8999, 7: 7499, 8: 5499, 9: 1999, 10: 6499}

CUSTOMERS = [
    (1, "Mara Ellison", "mara@example.com", "2025-03-14", 1),
    (2, "Tom Becker", "tom@example.com", "2025-06-02", 0),
    (3, "Priya Nair", "priya@example.com", "2024-11-20", 1),
    (4, "Sam Whitfield", "sam@example.com", "2026-01-09", 0),
    (5, "June Park", "june@example.com", "2025-09-30", 0),
    (6, "Diego Ramos", "diego@example.com", "2026-02-18", 1),
    (7, "Hannah Cole", "hannah@example.com", "2024-05-11", 0),
    (8, "Owen Marsh", "owen@example.com", "2025-12-01", 0),
    (9, "Lena Fischer", "lena@example.com", "2026-04-22", 0),
    (10, "Noah Bennett", "noah@example.com", "2026-07-30", 1),
    (11, "Ivy Chen", "ivy@example.com", "2026-09-15", 0),
    (12, "Caleb Duarte", "caleb@example.com", "2026-10-05", 0),
]

# (id, customer_id, order_date, channel, total_cents, discount_code)
ORDERS = [
    (1, 1, "2026-01-12", "online", 12999, None),
    (2, 2, "2026-01-20", "in-store", 4599, None),
    (3, 3, "2026-02-03", "online", 18999, "WELCOME10"),
    (4, 1, "2026-02-14", "phone", 7999, None),
    (5, 4, "2026-03-05", "online", 2499, None),
    (6, 5, "2026-03-11", "in-store", 8999, None),
    (7, 3, "2026-03-22", "online", 5499, None),
    (8, 6, "2026-04-02", "phone", 15999, None),
    (9, 2, "2026-04-15", "online", 3499, None),
    (10, 7, "2026-05-06", "in-store", 6499, None),
    (11, 1, "2026-05-19", "online", 59999, None),
    (12, 8, "2026-06-01", "online", 2999, None),
    (13, 3, "2026-06-14", "phone", 12999, None),
    (14, 9, "2026-06-28", "in-store", 1999, None),
    (15, 4, "2026-07-07", "online", 7499, None),
    (16, 10, "2026-07-19", "online", 9999, None),
    (17, 5, "2026-08-03", "phone", 4499, None),
    (18, 6, "2026-08-12", "online", 11999, None),
    (19, 2, "2026-08-25", "in-store", 5999, None),
    (20, 7, "2026-09-08", "online", 3999, None),
    (21, 3, "2026-09-17", "online", 21999, None),
    (22, 8, "2026-09-29", "phone", 2799, None),
    (23, 1, "2026-10-02", "online", 14999, None),
    (24, 3, "2026-10-06", "online", 17999, None),
    (25, 4, "2026-10-09", "in-store", 3299, None),
    (26, 6, "2026-10-13", "phone", 8999, None),
    (27, 10, "2026-10-16", "online", 13999, None),
    (28, 9, "2026-10-20", "online", 4999, None),
    (29, 2, "2026-10-24", "in-store", 6799, None),
    (30, 12, "2026-10-27", "online", 5999, None),
    (31, 5, "2026-10-30", "online", 10999, None),
]

# order_id -> payment status. Everything is 'paid' except the two
# refunded orders (11, 22) and the one failed payment (30).
PAYMENT_STATUS = {11: "refunded", 22: "refunded", 30: "failed"}

# order_id -> [(product_id, qty), ...]
ITEMS = {
    1: [(2, 1), (4, 2)],
    2: [(2, 1), (9, 1)],
    3: [(1, 1), (4, 3)],
    4: [(2, 1), (5, 1)],
    5: [(4, 1), (9, 2)],
    6: [(2, 1), (7, 1)],
    7: [(3, 2), (4, 2)],
    8: [(6, 1), (2, 1)],
    9: [(2, 1), (10, 1)],
    10: [(7, 1), (4, 1)],
    11: [(1, 2), (2, 1), (7, 1)],
    12: [(9, 1), (4, 1)],
    13: [(2, 1), (8, 1)],
    14: [(9, 1)],
    15: [(4, 4), (2, 1)],
    16: [(10, 1), (2, 1)],
    17: [(5, 1), (4, 2)],
    18: [(2, 1), (1, 1)],
    19: [(2, 1), (3, 1)],
    20: [(4, 1), (9, 1)],
    21: [(4, 5), (2, 1)],
    22: [(9, 1)],
    23: [(2, 1), (4, 3)],
    24: [(4, 4), (1, 1)],
    25: [(9, 1), (5, 1)],
    26: [(6, 1), (2, 1)],
    27: [(8, 1), (2, 1)],
    28: [(4, 2), (10, 1)],
    29: [(2, 1), (7, 1)],
    30: [(3, 1), (4, 1)],
    31: [(4, 3), (2, 1)],
}


def build_db(path: str | Path) -> Path:
    """Create (or rebuild) the seeded SQLite database at *path*."""
    path = Path(path)
    if path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(SCHEMA)
        conn.executemany("INSERT INTO products VALUES (?,?,?,?,?)", PRODUCTS)
        conn.executemany("INSERT INTO customers VALUES (?,?,?,?,?)", CUSTOMERS)
        conn.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?)", ORDERS)
        rows = []
        item_id = 1
        for order_id in sorted(ITEMS):
            for product_id, qty in ITEMS[order_id]:
                rows.append((item_id, order_id, product_id, qty, PRICE[product_id]))
                item_id += 1
        conn.executemany("INSERT INTO order_items VALUES (?,?,?,?,?)", rows)
        payments = []
        for order_id, _cid, _d, _ch, total, _dc in ORDERS:
            status = PAYMENT_STATUS.get(order_id, "paid")
            payments.append((order_id, order_id, status, total, "card"))
        conn.executemany("INSERT INTO payments VALUES (?,?,?,?,?)", payments)
        conn.commit()
    finally:
        conn.close()
    return path


_READ_ONLY_FIRST_WORDS = ("select", "with")


def _check_read_only(sql: str) -> None:
    """Reject anything that is not a single read-only statement.

    A model-generated DROP/DELETE/INSERT would otherwise execute
    against the shared dataset and corrupt every later question in
    the run (verified: ``DROP TABLE orders`` succeeded through this
    function before this guard). Leading ``--``/``/* */`` comments
    are skipped so a model cannot smuggle a write past the check.
    Raises sqlite3.OperationalError, which the agent scores as a
    wrong answer instead of crashing.
    """
    text = sql.strip()
    while True:
        if text.startswith("--"):
            _, _, text = text.partition("\n")
            text = text.strip()
        elif text.startswith("/*"):
            end = text.find("*/")
            if end == -1:
                break
            text = text[end + 2:].strip()
        else:
            break
    first = text.split(None, 1)[0].lower().lstrip("(") if text.split(None, 1) else ""
    if first not in _READ_ONLY_FIRST_WORDS:
        raise sqlite3.OperationalError(
            f"only SELECT/WITH statements are allowed, got: {first or 'empty'}")


def execute_sql(db_path: str | Path, sql: str) -> list[tuple]:
    """Run a read-only *sql* (SELECT/WITH) against the SQLite DB and
    return rows as tuples.

    The database is opened read-only (``mode=ro``) so that even a
    statement that passes the keyword check cannot mutate the
    dataset — a second layer of defence behind _check_read_only.
    """
    _check_read_only(sql)
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        return [tuple(row) for row in conn.execute(sql)]
    finally:
        conn.close()


def normalize_rows(rows: list[tuple]) -> list[tuple[str, ...]]:
    """Execution-accuracy comparison, BIRD-style: order-insensitive,
    type-insensitive — every value stringified, rows sorted."""
    return sorted(tuple(str(v) for v in row) for row in rows)


def rows_match(a: list[tuple], b: list[tuple]) -> bool:
    return normalize_rows(a) == normalize_rows(b)
