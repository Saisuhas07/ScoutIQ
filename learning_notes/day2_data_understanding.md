# Day 2 — Data Understanding: Transfermarkt Historical Dataset

## Purpose and scope

Day 2 is the *data understanding* stage. We inspect the raw DuckDB artifact
that was obtained and committed to the repository on Day 2 using Git LFS. We
are NOT yet doing feature engineering, ML training, temporal validation, or
data-pipeline construction. This day answers one question: **does this dataset
support our prediction problem?**

The prediction problem (from Day 1):

```
player + time snapshot + information available up to that time  ->  market value
```

Unit of observation: one player at one season/date snapshot.

## Raw artifact

- Local path: `data/raw/transfermarkt_datasets/transfermarkt-datasets.duckdb`
- Opened read-only for every inspection in this document.
- Provider: `dcaribou/transfermarkt-datasets` (snapshot, not a live feed).
- Licensing caveat from Day 2 collection notes: the underlying data is derived
  from Transfermarkt and is **not cleared for a public/commercial deployment**
  or for training AI/ML systems in production. Local learning/exploration only.

## Tables and schemas

The database has 13 tables: 12 domain tables plus a one-row `version` table.

| Table | Rows | Role for our problem |
| --- | ---: | --- |
| `player_valuations` | 656,301 | Target: dated market value per player |
| `appearances` | 1,894,350 | Performance features (goals, assists, minutes) |
| `games` | 88,958 | Match context (date, competition, home/away clubs) |
| `players` | 50,149 | Player profile (DOB, position, height, foot) |
| `transfers` | 175,165 | Movement/fee context and cross-check |
| `clubs` | 796 | Club metadata |
| `competitions` | 65 | League/cup metadata |
| `club_games` | 177,916 | Club-centric game results |
| `game_events` | 1,274,469 | Goals, cards, subs per game |
| `game_lineups` | 3,179,016 | Starting/bench line-ups |
| `countries` | 124 | Country metadata |
| `national_teams` | 124 | National-team snapshot |
| `version` | 1 | Commit hash of the source build |

### Key columns

- **Target:** `player_valuations(player_id, date, market_value_in_eur,
  current_club_id, player_club_domestic_competition_id)`. All essential
  target fields are present and non-null.
- **Performance:** `appearances(appearance_id, player_id, game_id, date,
  competition_id, goals, assists, minutes_played, yellow_cards, red_cards)`.
- **Match context:** `games(game_id, competition_id, season, date,
  home_club_id, away_club_id, ...)`.
- **Player profile:** `players(player_id, date_of_birth, position,
  sub_position, foot, height_in_cm, ...)`. Fields prefixed `current_` and the
  `market_value_in_eur`/`highest_market_value_in_eur` **current/peak value
  fields describe the snapshot at download time, not historical fact** — they
  must NOT be used as historical features without a time-aware derivation.
- **Transfer context:** `transfers(player_id, transfer_date, from_club_id,
  to_club_id, transfer_fee, market_value_in_eur)`.

## Relationships verified (joins)

| Relationship | Check |
| --- | ---: |
| Valuations -> players | 656,301 / 656,301 match (0 unmatched) |
| Games -> competitions | 88,958 / 88,958 match (0 unmatched) |
| PL clubs with a rank index in `clubs` | 37 distinct clubs |
| Appearances -> games (via game_id) | 73,426 distinct game ids fully matched |
| Appearances -> players | 2 of 1,894,350 unmatched |

Names are descriptive fields, not join keys; IDs are the join keys. The two
unmatched appearances are a concrete data-quality case to investigate later.

## Temporal coverage

| Table | Earliest | Latest | Notes |
| --- | --- | --- | --- |
| `player_valuations` | 2000-01-20 | 2026-06-12 | Sparse 2000–2003; dense from ~2007 |
| `appearances` | 2012-07-03 | 2026-06-28 | Performance only available from 2012 |
| `games` (GB1) | 2012-08-18 | 2026-05-24 | 380 matches per season |
| `transfers` | 1993-07-01 | 2030-06-30 | Contains future-dated planned transfers |

### Critical temporal mismatch

Valuations begin in 2000, but appearances (our primary performance features)
do not begin until 2012. For a model that uses performance statistics, the
usable historical window is effectively **2012–2026**. Valuations before 2012
can only use player-profile features (age, position, club), not performance.

### Panel structure

Most players are observed repeatedly over time. In the full dataset,
12,797 players have 21+ valuations and 14,294 players have 11–20 valuations.
The data is a **panel** (repeated observations of the same entity), not
independent rows. This matters for:

- Validation: random row splits would leak the same player across training
  and test; we need temporal + player-aware splits.
- Standard errors/uncertainty: repeated observations of one player are
  correlated.

## Premier League focus (initial V1 scope)

| Measure | Value |
| --- | ---: |
| PL players with valuations | 2,934 |
| PL players with appearances | 2,466 |
| PL players with *both* | 1,993 (join without date filter) |
| PL players with a prior performance row before a valuation | 1,976 |

PL valuations span 33,748 rows; PL appearances 149,751 rows. This is more
than enough for an initial PL-only model.

### PL valuation density by year

Data is thinnest in the 2000s and densest 2019–2023 (~2,000–3,000 valuations
per year), with 2024–2026 thinner because the snapshot coverage declines.

## Market value target distribution

| Scope | n | Min | Max | Mean | Median |
| --- | ---: | ---: | ---: | ---: | ---: |
| Global | 656,300 | 10,000 | 200,000,000 | 2.29M | 500,000 |
| Premier League | 33,748 | 10,000 | 200,000,000 | 9.51M | 3,000,000 |

Implications:

1. **Heavy right skew.** Mean is far above median. A linear model on raw
   euros will struggle; a log transform of the target is a likely early
   decision (to be justified and tested later).
2. **No zeros and no NULLs** in PL valuations. Good news: target is clean.
3. PL values are considerably higher than global (top league), so league
   context must be part of the model, not silently pooled.

## Missing data and quality issues

| Location | Issue | Count |
| --- | --- | --- |
| `players.position` | literal string `'Missing'` used as a value (not NULL) | 586 |
| `players.height_in_cm` | NULL | 4,365 |
| `players.foot` | NULL | 5,893 |
| `players.date_of_birth` | NULL | 49 |
| `transfers.transfer_fee` | NULL | 61,526 |
| `transfers.transfer_fee` | 0 (free/loan) | 96,085 |
| `appearances.*` performance cols | NULL | 0 |
| `player_valuations.*` essential cols | NULL | 0 |

### Key quality lessons

1. **Missingness encoded as a value:** `position = 'Missing'` is not NULL.
   Depending on how we treat categorical features later, this either becomes
   its own category (surprisingly legitimate for tree models) or needs a real
   "unknown" sentinel we choose ourselves.
2. **Transfer fees are messy:** 35% NULL fee, 55% zero fee (loans/frees), and
   only 10% with a recorded positive fee. Transfer fee must be used carefully,
   and its missingness itself may carry signal.
3. **Future-dated transfers exist** (up to 2030). These are planned/prospective
   records and are leakage if used for an earlier observation.

## Data limitations for our problem

1. **No performance data before 2012.** Limits feature-rich modelling to
   2012+.
2. **Snapshot fields in `players`/`clubs` are not historical.** `current_*`
   fields and current/peak market value reveal information not necessarily
   known at the valuation date.
3. **No advanced statistics** (xG, progressive carries, pressures). Only basic
   appearance stats are present. Advanced features are a later-data-source
   item.
4. **Future-dated transfer records** must be excluded under a time-aware
   design.
5. **Licensing restricts deployment.** The historical labels cannot be used
   for a public product without a licensed source.

## What we learned

- The relational design is a strength: each entity has its own table and a
  clean grain (player, valuation, appearance, game, transfer).
- The target is observable at the right grain: (player, date) -> euro value.
- IDs are reliable join keys; names are not.
- A date column is not a guarantee against leakage; snapshot fields and
  future-dated rows are the traps to watch.
- The usable PL modelling window is 2012–2026 with ~1,976 players who have
  both valuations and prior performance.
- The target is heavily skewed; the same player recurs across rows; both of
  these will drive early modelling decisions.

## Tools built this day

- `src/scoutiq/explore_dataset.py` — read-only, modular, reusable deep-dive
  answering the six Day 2 questions (temporal coverage, PL coverage, joins,
  temporal-join feasibility, target distribution, missingness).
- `src/scoutiq/inspect_dataset.py` — schema listing (existing from Day 2
  collection).

## Files changed this session

- Added `src/scoutiq/explore_dataset.py`
- Added `learning_notes/day2_data_understanding.md` (this file)

## Next logical milestone

Build an explicit, documented **temporal alignment** between appearances and
valuations (features available at each valuation date) — still as a data-
understanding exercise, before any modelling. Then decide the target
representation (raw vs log) and the train/validation/test split strategy.