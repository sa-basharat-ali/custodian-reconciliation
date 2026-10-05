# Custodian reconciliation for a registered investment advisor

```
python3 run.py      # stdlib only, about two seconds
```

A synthetic RIA for one quarter: 30 advisors, 2,000 households, 3,562 accounts (taxable, IRA, Roth,
joint), 63 trading days, 2,480 trades that settle T+1 at an outside custodian, a 2-for-1 stock split,
and a monthly-priced interval fund excluded from the advisory fee base. Fixed seed, no real firm or
client. Failures are injected with ground truth.

## Four findings

### 1. Total AUM ties out while accounts don't

45 trades were booked by the custodian to the wrong account inside the same household. Total AUM
matched the custodian on **62 of 63 days**, and on **61** of those days there were account-level
breaks underneath, because a trade in the wrong household account doesn't change the household's
total. A position-level check (shares and cash per account) found all 90 affected accounts on the
day each trade settled.

### 2. A third of the alerts are just T+1

Comparing a trade-date ledger to the custodian flags 7,062 account-days of breaks over the quarter.
Aligning the ledger to settlement date drops that to 4,629: **34% of the alerts were settlement
timing**, not errors. On the split day, 1,842 accounts holding the split stock break until the ledger
applies the 2-for-1, and that is the one day total AUM misses too.

### 3. What the fee is charged on is a definition, not a fact

| fee base | quarterly fee |
|---|---|
| eligible AUM, quarter-end value | $448,095 |
| eligible AUM, average daily balance | $436,218 |
| total AUM, if the excluded sleeve slips into the base | $462,620 |

The quarter-end vs average-daily-balance choice is worth $11,877 a quarter on this book. Letting the
excluded interval fund into the base overbills $14,525. 641 accounts hold that fund, and their AUM
only moves on monthly NAV dates, so daily AUM charts look flatter than the portfolio really is.

### 4. How much can one advisor serve

The median advisor has **68 households, 121 accounts and $15.1M AUM**. The same book reads 1.8x
bigger counted in accounts than in households, so the "one advisor does a team's work" metric needs
its unit decided before anyone tracks it.

## The part I got wrong

My first reconciliation compared account values. Settlement timing disappeared, because a trade
swaps cash for stock at the same price and the value barely moves on trade date. Reconciliation has
to compare positions, shares and cash, not dollars, or T+1 timing and real misbookings both hide.

## Files

| | |
|---|---|
| `world.py` | households, accounts, prices, trades, the split, the interval fund, injected misbookings |
| `run.py` | value vs position reconciliation, settlement alignment, fee bases, advisor capacity |
| `index.html` | the write-up as a page |

## Where this comes from

I spent two years on settlement and reconciliation data at Geidea, Saudi Arabia's largest payments
processor, including an automated reporting platform for FinOps reconciliation across 5+ teams.
Through my own consulting practice I later found an 80% upstream data loss that every dashboard
reported as healthy.

Syed Ahmed Basharat Ali · sabasharat.ali@gmail.com · basharat.net
