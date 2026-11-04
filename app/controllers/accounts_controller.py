"""Accounts & Finance controller: Financial KPIs, Balance Sheet, P&L, and General Ledger."""
from app.models.db import rows, one, scalar, today


def ensure_finance_tables(conn):
    """Create expense / asset tables if missing so finance features work on existing DBs."""
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY,
        date TEXT NOT NULL,
        category TEXT NOT NULL,
        vendor TEXT,
        description TEXT,
        amount REAL NOT NULL,
        paid REAL DEFAULT 0,
        status TEXT DEFAULT 'Unpaid',
        method TEXT,
        notes TEXT
    );
    CREATE TABLE IF NOT EXISTS assets (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT,
        purchase_date TEXT,
        cost REAL DEFAULT 0,
        residual_value REAL DEFAULT 0,
        status TEXT DEFAULT 'Active'
    );
    """)


def financial_kpis(conn):
    ensure_finance_tables(conn)
    accrued = scalar(conn, "SELECT COALESCE(SUM(total),0) FROM invoices") or 0
    cash_in = scalar(conn, "SELECT COALESCE(SUM(amount),0) FROM payments") or 0
    expenses_total = scalar(conn, "SELECT COALESCE(SUM(amount),0) FROM expenses") or 0
    expenses_paid = scalar(conn, "SELECT COALESCE(SUM(paid),0) FROM expenses") or 0
    ar = scalar(conn, "SELECT COALESCE(SUM(total - paid),0) FROM invoices") or 0
    ap = scalar(conn, "SELECT COALESCE(SUM(amount - paid),0) FROM expenses") or 0
    stock_val = scalar(conn, "SELECT COALESCE(SUM(stock * unit_price),0) FROM medicines") or 0
    fixed = scalar(conn, "SELECT COALESCE(SUM(cost),0) FROM assets WHERE status='Active'") or 0
    gl_credits = cash_in
    gl_debits = expenses_paid
    gl_balance = gl_credits - gl_debits
    net = accrued - expenses_total
    exp_ratio = round((expenses_total / accrued * 100), 1) if accrued else 0
    margin = round((net / accrued * 100), 1) if accrued else 0
    total_assets = gl_balance + ar + stock_val + fixed
    return {
        "accrued_revenue": round(accrued, 2),
        "cash_inflow": round(cash_in, 2),
        "operating_expenses": round(expenses_total, 2),
        "expenses_paid": round(expenses_paid, 2),
        "expense_ratio": exp_ratio,
        "net_profit": round(net, 2),
        "net_margin": margin,
        "accounts_receivable": round(ar, 2),
        "accounts_payable": round(ap, 2),
        "stock_valuation": round(stock_val, 2),
        "fixed_assets": round(fixed, 2),
        "gl_credits": round(gl_credits, 2),
        "gl_debits": round(gl_debits, 2),
        "gl_balance": round(gl_balance, 2),
        "total_assets": round(total_assets, 2),
    }


def pnl_summary(conn):
    """Revenue by clinical stream vs expenses by head."""
    ensure_finance_tables(conn)
    revenue_streams = rows(
        conn,
        """
        SELECT COALESCE(ii.description, 'Other') label, SUM(ii.amount) value
        FROM invoice_items ii
        GROUP BY COALESCE(ii.description, 'Other')
        ORDER BY value DESC
        LIMIT 8
        """,
    )
    expense_heads = rows(
        conn,
        """
        SELECT category label, SUM(amount) value
        FROM expenses
        GROUP BY category
        ORDER BY value DESC
        """,
    )
    return {"revenue_streams": revenue_streams, "expense_heads": expense_heads}


def balance_sheet(conn):
    k = financial_kpis(conn)
    equity = k["net_profit"]
    liabilities = k["accounts_payable"]
    return {
        "assets": {
            "cash_and_bank": k["gl_balance"],
            "accounts_receivable": k["accounts_receivable"],
            "pharmacy_stock": k["stock_valuation"],
            "fixed_assets": k["fixed_assets"],
            "total": k["total_assets"],
        },
        "liabilities_equity": {
            "accounts_payable": liabilities,
            "retained_surplus": equity,
            "total": liabilities + equity,
        },
        "gl": {
            "credits": k["gl_credits"],
            "debits": k["gl_debits"],
            "balance": k["gl_balance"],
        },
    }


def gl_summary(conn):
    ensure_finance_tables(conn)
    k = financial_kpis(conn)
    heads = []
    receipts = rows(
        conn,
        "SELECT COALESCE(method,'Cash') channel, COUNT(*) cnt, SUM(amount) total FROM payments GROUP BY COALESCE(method,'Cash')",
    )
    for r in receipts:
        heads.append({
            "account": f"Cash / {r['channel']}",
            "entries": r["cnt"],
            "credits": r["total"] or 0,
            "debits": 0,
            "net": r["total"] or 0,
        })
    exps = rows(
        conn,
        "SELECT category, COUNT(*) cnt, SUM(paid) paid, SUM(amount) total FROM expenses GROUP BY category",
    )
    for r in exps:
        heads.append({
            "account": r["category"],
            "entries": r["cnt"],
            "credits": 0,
            "debits": r["paid"] or 0,
            "net": -(r["paid"] or 0),
        })
    channels = []
    for r in receipts:
        channels.append({"channel": r["channel"], "inflows": r["total"] or 0, "outflows": 0, "net": r["total"] or 0})
    exp_methods = rows(
        conn,
        "SELECT COALESCE(method,'Cash') channel, SUM(paid) total FROM expenses WHERE paid>0 GROUP BY COALESCE(method,'Cash')",
    )
    for r in exp_methods:
        channels.append({"channel": r["channel"] + " (exp)", "inflows": 0, "outflows": r["total"] or 0, "net": -(r["total"] or 0)})
    return {
        "kpis": {
            "gl_credits": k["gl_credits"],
            "gl_debits": k["gl_debits"],
            "gl_balance": k["gl_balance"],
            "account_heads": len(heads),
        },
        "trial_balance": heads,
        "channels": channels,
        "entries": rows(
            conn,
            """
            SELECT date, 'Receipt' type, method account, amount credit, 0 debit, amount net
            FROM payments
            UNION ALL
            SELECT date, 'Expense' type, category account, 0 credit, paid debit, -paid net
            FROM expenses WHERE paid > 0
            ORDER BY date DESC, type
            LIMIT 100
            """,
        ),
    }
