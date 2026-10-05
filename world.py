"""A synthetic registered investment advisor: households, accounts, an external custodian, and
the internal ledger that is supposed to agree with it.

Fixed seed, no real firm or client. Failures are injected with ground truth; T+1 settlement and
monthly-priced interval funds are included as things that look like breaks but are not.
"""
import random
from datetime import date, timedelta

SEED = 1940  # the year the Investment Advisers Act passed
SYMBOLS = {"VTI": 290.0, "VXUS": 64.0, "BND": 72.0, "AAPL": 230.0, "NVDA": 120.0, "MSFT": 430.0,
           "AMZN": 190.0, "GOOGL": 170.0, "META": 560.0, "INTV": 25.0}  # INTV = interval fund, priced monthly
INTERVAL = "INTV"
FEE_EXCLUDED = {"INTV"}  # sleeves excluded from eligible AUM
SPLIT = ("NVDA", 2)      # a 2-for-1 split on SPLIT_DAY


def trading_days(start, n):
    d, out = start, []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


DAYS = trading_days(date(2026, 7, 1), 63)        # one quarter
SPLIT_DAY = DAYS[30]


def build():
    rng = random.Random(SEED)
    advisors = [f"adv_{i:02d}" for i in range(1, 31)]
    households, accounts = [], []
    aid = 0
    for h in range(1, 2001):
        adv = rng.choice(advisors)
        households.append({"household_id": h, "advisor": adv})
        for t in rng.sample(["taxable", "ira", "roth", "joint"], rng.choice([1, 1, 2, 2, 3])):
            aid += 1
            accounts.append({"account_id": f"A{aid:05d}", "household_id": h, "advisor": adv, "type": t})
    # opening positions
    holdings = {}
    for a in accounts:
        size = rng.lognormvariate(11.2, 1.0)  # ~ $73k median
        picks = rng.sample([s for s in SYMBOLS if s != INTERVAL], rng.randint(3, 6))
        if rng.random() < 0.18 and INTERVAL not in picks:
            picks.append(INTERVAL)
        w = [rng.random() for _ in picks]
        holdings[a["account_id"]] = {s: round(size * wi / sum(w) / SYMBOLS[s], 3) for s, wi in zip(picks, w)}
        holdings[a["account_id"]]["CASH"] = round(size * rng.uniform(0.01, 0.06), 2)

    # daily prices: random walk; interval fund NAV only changes on month starts
    prices, p = {}, dict(SYMBOLS)
    for i, d in enumerate(DAYS):
        for s in p:
            if s == INTERVAL:
                if d.day <= 3 and (i == 0 or DAYS[i - 1].month != d.month):
                    p[s] *= 1 + rng.gauss(0.006, 0.004)
            else:
                p[s] *= 1 + rng.gauss(0.0004, 0.013)
            if s == SPLIT[0] and d == SPLIT_DAY:
                p[s] /= SPLIT[1]
        prices[d] = dict(p)

    # trades: trade date in the ledger, settles T+1 at the custodian
    trades = []
    for i, d in enumerate(DAYS[:-1]):
        for a in rng.sample(accounts, 40):
            s = rng.choice([x for x in SYMBOLS if x != INTERVAL])
            qty = round(rng.uniform(1, 30), 3) * rng.choice([1, -1])
            trades.append({"account_id": a["account_id"], "symbol": s, "qty": qty, "trade_date": d,
                           "settle_date": DAYS[i + 1], "price": prices[d][s]})

    truth = {"misposted": [], "split_lag_days": 1}
    # misposting: a trade booked to the wrong account inside the same household, at the custodian side
    by_house = {}
    for a in accounts:
        by_house.setdefault(a["household_id"], []).append(a["account_id"])
    pool = [t for t in trades if len(by_house[[a for a in accounts if a["account_id"] == t["account_id"]][0]["household_id"]]) > 1]
    for t in rng.sample(pool, 45):
        hh = [a for a in accounts if a["account_id"] == t["account_id"]][0]["household_id"]
        other = rng.choice([x for x in by_house[hh] if x != t["account_id"]])
        t["custodian_account"] = other
        truth["misposted"].append(t)
    return advisors, households, accounts, holdings, prices, trades, truth


def positions(holdings, trades, day, side, split_applied_from):
    """Positions at end of `day`. side='custodian' uses settle date and custodian_account;
    side='ledger' uses trade date and the account the advisor intended."""
    pos = {a: dict(h) for a, h in holdings.items()}
    for t in trades:
        when = t["settle_date"] if side == "custodian" else t["trade_date"]
        if when > day:
            continue
        acct = t.get("custodian_account", t["account_id"]) if side == "custodian" else t["account_id"]
        pos[acct][t["symbol"]] = pos[acct].get(t["symbol"], 0) + t["qty"]
        pos[acct]["CASH"] = pos[acct].get("CASH", 0) - t["qty"] * t["price"]
    if day >= split_applied_from:
        for a in pos:
            if SPLIT[0] in pos[a]:
                pos[a][SPLIT[0]] *= SPLIT[1]
    return pos
