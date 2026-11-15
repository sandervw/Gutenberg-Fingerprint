# Simple code examples

One before/after per practice. Every "after" block passes the house rules and the ruff checks.

## 1. Push side effects to the edges

Before: reading, deciding, and writing are tangled.

```python
def apply_late_fees(invoices_path, database_path):
    connection = sqlite3.connect(database_path)
    with open(invoices_path) as invoice_file:
        for invoice in csv.DictReader(invoice_file):
            days_late = (date.today() - date.fromisoformat(invoice["due_date"])).days
            if days_late > 30:
                fee = round(float(invoice["amount"]) * 0.05, 2)
                connection.execute("INSERT INTO fees VALUES (?, ?)", (invoice["invoice_id"], fee))
    connection.commit()
```

After: the pure rule lives in `core/fees.py`; the shell does the reading and writing.

```python
from datetime import date


def late_fees(invoices, today):
    """Return (invoice id, fee) pairs for invoices over 30 days late."""
    fees = []
    for invoice in invoices:
        days_late = (today - date.fromisoformat(invoice["due_date"])).days
        if days_late > 30:
            fees.append((invoice["invoice_id"], round(float(invoice["amount"]) * 0.05, 2)))
    return fees
```

```python
import csv
import sqlite3
from datetime import date


def apply_late_fees(invoices_path, database_path):
    """Read invoices, compute fees with the pure rule, store them."""
    with open(invoices_path) as invoice_file:
        invoices = list(csv.DictReader(invoice_file))
    fees = late_fees(invoices, date.today())
    with sqlite3.connect(database_path) as connection:
        connection.executemany("INSERT INTO fees VALUES (?, ?)", fees)
```

## 2. Avoid hasty abstractions

Before: one shared function with a flag per caller.

```python
def build_message(user, kind, include_footer=True, is_admin=False, urgent=False):
    subject = "Reminder" if kind == "reminder" else "Receipt"
    if urgent and kind == "reminder":
        subject = "URGENT: " + subject
    body = f"Hi {user['name']},\n"
    if kind == "receipt" and is_admin:
        body += f"(Account id: {user['id']})\n"
    if include_footer and not is_admin:
        body += "Reply STOP to unsubscribe."
    return subject, body
```

After: one plain function per case. Keyword-only flags (`*,`) are allowed.

```python
FOOTER = "Reply STOP to unsubscribe."


def reminder_message(user, *, urgent=False):
    """Build the invoice reminder email."""
    subject = "URGENT: Reminder" if urgent else "Reminder"
    return subject, f"Hi {user['name']},\nYour invoice is due soon.\n{FOOTER}"


def receipt_message(user):
    """Build the customer payment receipt."""
    return "Receipt", f"Hi {user['name']},\nThanks for your payment.\n{FOOTER}"


def admin_receipt_message(user):
    """Build the internal receipt, which shows the account id."""
    return "Receipt", f"Hi {user['name']},\nThanks for your payment.\n(Account id: {user['id']})"
```

## 3. Build deep modules

Before: a shallow wrapper; every caller must connect, query, and close in order.

```python
database = Database("app.db")
database.connect()
try:
    rows = database.cursor().execute("SELECT id, name FROM users").fetchall()
finally:
    database.close()
```

After: one call; connection, retries, and cleanup are hidden in one place.

```python
import sqlite3
import time


def fetch_rows(database_path, query, parameters=(), retries=3):
    """Run a read query and return every row as a dictionary."""
    for attempt in range(retries):
        try:
            with sqlite3.connect(database_path) as connection:
                connection.row_factory = sqlite3.Row
                return [dict(row) for row in connection.execute(query, parameters)]
        except sqlite3.OperationalError:
            if attempt == retries - 1:
                raise
            time.sleep(0.1 * 2**attempt)
```

## 4. Keep behaviour local

Before: hooks registered in other files change the total; import order decides the sequence.

```python
PRE_SAVE_HOOKS = []


def save_order(order, orders_table):
    for hook in PRE_SAVE_HOOKS:
        hook(order)
    orders_table.append(order)
```

After: every step is visible, in order, where it happens.

```python
def member_discount(total, customer):
    """Take ten percent off for members."""
    return total * 0.9 if customer.get("member") else total


def with_tax(total, rate=0.07):
    """Add sales tax to a total."""
    return total * (1 + rate)


def save_order(order, orders_table):
    """Price the order, then store it."""
    total = member_discount(order["subtotal"], order["customer"])
    total = with_tax(total)
    orders_table.append({**order, "total": round(total, 2)})
```

## 5. Make state explicit and parse at the boundary

Before: overlapping booleans; every function re-checks the raw dictionary.

```python
def can_ship(order):
    if "paid" not in order or "shipped" not in order:
        raise ValueError("bad order")
    return order["paid"] and not order["shipped"] and not order.get("cancelled")
```

After: one enum, parsed once at the edge into an immutable object.

```python
from dataclasses import dataclass, replace
from enum import Enum


class Status(Enum):
    """Every state an order can be in."""

    PENDING = "pending"
    PAID = "paid"
    SHIPPED = "shipped"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Order:
    """An order that has already passed boundary parsing."""

    id: int
    status: Status


def parse_order(raw: dict) -> Order:
    """Turn raw input into an Order, failing loudly on bad data."""
    return Order(id=int(raw["id"]), status=Status(raw["status"]))


def ship(order: Order) -> Order:
    """Mark a paid order as shipped."""
    if order.status is not Status.PAID:
        raise ValueError(f"order {order.id} is {order.status.value}, not paid")
    return replace(order, status=Status.SHIPPED)
```

## 6. Flatten control flow

Before: nested branches and one dense condition.

```python
def route_claim(claim):
    if claim is not None:
        if claim["amount"] > 0:
            if claim["amount"] > 10000 or (claim["prior_claims"] >= 3 and claim["policy_age_days"] < 90):
                return "review"
            return "auto_approve"
        return "reject"
    return "reject"
```

After: guard clauses first, then named parts of the rule.

```python
def route_claim(claim):
    """Decide whether a claim is rejected, reviewed, or approved."""
    if claim is None or claim["amount"] <= 0:
        return "reject"
    is_large = claim["amount"] > 10000
    is_new_policy = claim["policy_age_days"] < 90
    is_frequent_claimant = claim["prior_claims"] >= 3
    if is_large or (is_frequent_claimant and is_new_policy):
        return "review"
    return "auto_approve"
```

## 7. Write boring code that fails loudly

Before: a clever one-liner with a silent fallback.

```python
def load_rate(settings, region):
    try:
        return float({**settings.get("defaults", {}), **settings.get(region, {})}.get("rate") or 0.07)
    except:
        return 0.07
```

After: plain steps, a deliberate default, and errors that name the bad value.

```python
DEFAULT_RATE = 0.07


def load_rate(settings, region):
    """Return the tax rate for a region, or the default."""
    region_settings = settings.get(region, {})
    defaults = settings.get("defaults", {})
    raw = region_settings.get("rate", defaults.get("rate", DEFAULT_RATE))
    try:
        rate = float(raw)
    except (TypeError, ValueError):
        raise ValueError(f"rate for {region!r} is not a number: {raw!r}") from None
    if not 0 <= rate < 1:
        raise ValueError(f"rate for {region!r} is out of range: {rate}")
    return rate
```
