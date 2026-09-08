# ML Dataset — Temporal Alignment Milestone

## What we built

`src/scoutiq/build_temporal_dataset.py` turns the relational database into the
exact shape our ML problem needs: **one row per player per valuation date**,
where every feature only knows information available at that date.

Output: `data/processed/pl_valuation_features_v1.csv` (33,748 rows)

## Why this shape

Our prediction problem is:

```
player + time snapshot + information available up to that time  ->  market value
```

So the dataset must mirror that. Each row is one `(player, date)`, the target
is the market value on that date, and the features describe what we knew about
the player strictly before that date.

## How temporal alignment works

For every PL valuation we asked: "what did the world know about this player on
this date?" and wrote that into the row.

| Feature block | What it captures | How it is built |
| --- | --- | --- |
| static | age, position, height | player profile joined to the valuation; age computed at the valuation date |
| season-to-date (`st_*`) | this season so far | appearances in the same season, strictly before the valuation date |
| prior season (`ps_*`) | last full season | appearances in the season before, all of them |
| recent form (`r10_*`) | last 10 games | the 10 most recent appearances before the valuation date |
| context | days since last match, season, club | from appearances and the valuation row |

The season boundary is defined as **July**: any month >= July belongs to the
season starting that year, anything before July belongs to the previous
season. `season_year(2024-03) = 2023`, `season_year(2024-09) = 2024`.
This mirrors transfermarkt's July/June season convention.

## The leakage rule, enforced

The build does the date filter FIRST, then aggregates:

1. Join every appearance to every future valuation of that player.
2. **Keep only appearances strictly before the valuation date.**
3. Aggregate each window (current season, prior season, last 10 games).
4. Report a leak check: the most recent appearance date used by each row must
   be before its valuation date.

Result: `rows using a future match: 0  =>  PASS`.

## Coverage reality (important)

Only **39% of valuation rows** (13,167 of 33,748) have any prior PL appearance.

- 2003-2011 valuations: 0% — appearances only start in 2012.
- 2012-2016: ~25% of rows have prior performance (thin early coverage).
- 2017 onwards: 44-78% of rows have prior performance.

Implication: a model that uses performance features should train on rows with
prior performance, most realistically **2017+ PL rows**. Rows without
performance could still use static features (age, position) but that is a
weaker problem and not our first target.

## Decisions taken

- **Scope:** Premier League only (`GB1`), matching the V1 ambition.
- **Features:** static profile + three performance windows + context. This is a
  first candidate set, deliberately small and explainable; more features
  (transfers, contract, advanced stats) come later.
- **Missing performance** is recorded as 0 in the windows (truly no games
  played), while `days_since_last_match` is `NaN` when the player has no
  appearances at all (absent, not zero).
- **No transfers/contracts yet:** contract expiration lives in a snapshot
  table and would leak; transfers are a later feature.
- Build runs only on the SQLite copy; the raw DuckDB file is never touched.

## How to regenerate / inspect

```
python src/scoutiq/build_temporal_dataset.py          # rebuild the CSV
python src/scoutiq/explore_dataset_sqlite.py          # the six Q&A exploration
```

## Next milestones

1. Decide target representation (raw euros vs log euros).
2. Temporal train/validation/test split strategy.
3. Linear Regression baseline -> evaluation metrics -> tree models.