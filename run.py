"""python3 run.py  -- stdlib only, a few seconds."""
from collections import defaultdict

import world as W

advisors, households, accounts, holdings, prices, trades, truth = W.build()
DAYS = W.DAYS
SPLIT_LEDGER_FROM = DAYS[DAYS.index(W.SPLIT_DAY) + truth["split_lag_days"]]


def value(pos, px, excl=()):
    return sum(q * (1 if s == "CASH" else px[s]) for s, q in pos.items() if s not in excl)


print("=" * 78)
print("Custodian reconciliation and fee billing for a registered investment advisor (synthetic)")
print("=" * 78)
print(f"advisors {len(advisors)} | households {len(households)} | accounts {len(accounts)} | "
      f"trading days {len(DAYS)} | trades {len(trades)}")

# ---- 1 + 2: daily reconciliation -------------------------------------------------------------
def broken(c, l):
    keys = set(c) | set(l)
    return any(abs(c.get(k, 0) - l.get(k, 0)) > (1.0 if k == "CASH" else 0.001) for k in keys)


mis_accts = {t["account_id"] for t in truth["misposted"]} | {t["custodian_account"] for t in truth["misposted"]}
settled = [dict(t, trade_date=t["settle_date"]) for t in trades]
total_ok_days, value_ok_but_broken = 0, 0
naive_total, aware_total, flagged_mis = 0, 0, set()
first_seen = {}
split_breaks = 0
for d in DAYS:
    px = prices[d]
    cust = W.positions(holdings, trades, d, "custodian", W.SPLIT_DAY)
    led_td = W.positions(holdings, trades, d, "ledger", SPLIT_LEDGER_FROM)
    led_sd = W.positions(holdings, settled, d, "ledger", SPLIT_LEDGER_FROM)
    tc = sum(value(p, px) for p in cust.values())
    tl = sum(value(p, px) for p in led_sd.values())
    naive = [a for a in cust if broken(cust[a], led_td[a])]
    aware = [a for a in cust if broken(cust[a], led_sd[a])]
    naive_total += len(naive)
    aware_total += len(aware)
    for a in aware:
        first_seen.setdefault(a, d)
    if abs(tc - tl) < 10:
        total_ok_days += 1
        if aware:
            value_ok_but_broken += 1
    if d == W.SPLIT_DAY:
        split_breaks = sum(1 for a in aware if W.SPLIT[0] in cust[a])
    flagged_mis |= set(aware) & mis_accts

n = len(DAYS)
real = {a for a in first_seen if a in mis_accts}
print("\n1. TOTAL AUM TIES OUT WHILE ACCOUNTS DON'T")
print(f"   injected: 45 trades booked to the wrong account inside the same household ({len(mis_accts)} accounts affected)")
print(f"   days total AUM matched the custodian: {total_ok_days} of {n}")
print(f"   of those, days with account-level breaks underneath: {value_ok_but_broken}")
print(f"   position-level check finds {len(real)} of {len(mis_accts)} affected accounts, each on the day the trade settles")

print("\n2. MOST 'BREAKS' ARE JUST T+1")
print(f"   account-days flagged comparing a trade-date ledger to the custodian: {naive_total:,}")
print(f"   account-days flagged after aligning to settlement date: {aware_total:,} "
      f"({(1 - aware_total / naive_total) * 100:.0f}% of the alerts were settlement timing)")
print(f"   on the split day, {split_breaks} accounts holding {W.SPLIT[0]} break until the ledger applies the 2-for-1, "
      f"and total AUM misses that day too")

# ---- 3: fee billing ----------------------------------------------------------------------------
print("\n3. WHAT THE FEE IS CHARGED ON")
RATE = 0.0040 / 4  # quarterly share of an annual 0.40% advisory fee (illustrative)
qe = DAYS[-1]
cust_qe = W.positions(holdings, trades, qe, "custodian", W.SPLIT_DAY)
elig_qe = sum(value(p, prices[qe], W.FEE_EXCLUDED) for p in cust_qe.values())
total_qe = sum(value(p, prices[qe]) for p in cust_qe.values())
adb = 0
for d in DAYS:
    c = W.positions(holdings, trades, d, "custodian", W.SPLIT_DAY)
    adb += sum(value(p, prices[d], W.FEE_EXCLUDED) for p in c.values())
adb /= n
fee = lambda base: base * RATE
print(f"   eligible AUM at quarter end ${elig_qe / 1e6:,.1f}M | total incl. excluded sleeve ${total_qe / 1e6:,.1f}M")
print(f"   quarterly fee on eligible AUM, quarter-end value:  ${fee(elig_qe):,.0f}")
print(f"   quarterly fee on eligible AUM, average daily balance: ${fee(adb):,.0f}")
print(f"   quarterly fee if the excluded sleeve slips into the base: ${fee(total_qe):,.0f} "
      f"(overbilled ${fee(total_qe) - fee(elig_qe):,.0f})")
stale = [a for a, p in cust_qe.items() if W.INTERVAL in p]
print(f"   accounts holding the monthly-priced interval fund: {len(stale)} (their AUM moves only on NAV dates)")

# ---- 4: advisor capacity -------------------------------------------------------------------------
print("\n4. HOW MUCH CAN ONE ADVISOR SERVE")
hh_per = defaultdict(int)
acct_per = defaultdict(int)
aum_per = defaultdict(float)
for h in households:
    hh_per[h["advisor"]] += 1
for a in accounts:
    acct_per[a["advisor"]] += 1
    aum_per[a["advisor"]] += value(cust_qe[a["account_id"]], prices[qe])
med = lambda d: sorted(d.values())[len(d) // 2]
print(f"   median per advisor: {med(hh_per)} households | {med(acct_per)} accounts | ${med(aum_per) / 1e6:,.1f}M AUM")
print(f"   the same book reads {med(acct_per) / med(hh_per):.1f}x bigger counted in accounts than in households")
