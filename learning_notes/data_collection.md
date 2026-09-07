# Day 2 — Data Collection and Source Evaluation

## Purpose and scope

ScoutIQ's first prediction problem is temporal: for one player at a point in
time, use only information available by that date to predict the player's
market value at that date. Day 2 is limited to source evaluation, raw-data
collection, and data understanding. It does not build features, a model, a
split, or a live-data system.

## Data requirements from Day 1

### Target-defining data

- A stable player identifier.
- A dated market-value observation, ideally in a numeric currency field.
- The date on which that value was recorded.

Without all three, we cannot form the intended target: `player_id + date ->
market_value`.

### Candidate feature data (not an approved final feature list)

- Date of birth or age, position, nationality and club.
- Appearances, minutes, goals and assists, tied to games or seasons.
- Transfer date, fee and source/destination club where available.
- Advanced performance data, if a future source supplies it.

### Context/supporting data

- Competition, club and match identifiers; match dates; line-ups; injuries;
  national-team information; and league metadata. These make time-aware joins
  and later quality checks possible.

### Useful later, not required for V1

- Event-level tracking, xG, salary/wage data, agent data, scouting reports,
  and a live/current update feed.

## Sources investigated

| Source | Strengths | Why it is not the Day 2 selection |
| --- | --- | --- |
| [Sportmonks Football API](https://www.sportmonks.com/football-api/) | Licensed-style API experience; player/team/match statistics, transfers, and historical seasons. | It does not provide the historical market-value labels necessary for the first target dataset. It is a strong future current-data/statistics source, not a complete market-value training source. |
| [StatsBomb Open Data](https://github.com/statsbomb/open-data) | Legitimate, research-oriented event data with matches, events and line-ups. | No broad, dated player-market-value table; competition coverage is selective. Useful for later event-data research only. |
| [football-data.org](https://www.football-data.org/coverage) | Clear free Premier League coverage for fixtures, tables and results. | Does not provide the required population of dated historical market values or rich player statistics on its free tier. |
| [openfootball/football.json](https://github.com/openfootball/football.json) | Public-domain historical fixtures/results and permissive reuse. | Match-level data only; no player market values and no player-level performance table adequate for this target. |
| [dcaribou/transfermarkt-datasets](https://github.com/dcaribou/transfermarkt-datasets) | 12 relational tables: player profiles, appearances, dated valuations, transfers, games and clubs. A downloadable DuckDB snapshot supports transparent inspection. | Underlying data is derived from Transfermarkt; it is therefore not approved for a public/deployed ScoutIQ product without rights clearance. |

## Selection: provisional historical learning dataset

**Selected for local Day 2 learning and exploratory research only:**
`dcaribou/transfermarkt-datasets`, downloaded as its published DuckDB snapshot.

It is the only evaluated candidate that can directly express the target
observation and relate it to dated player appearances, games, clubs, and
transfers through stable IDs. The project documents 12 joinable tables,
including `player_valuations`, `appearances`, `games`, `players`, `clubs`, and
`transfers`.

### Critical licensing and deployment caveat

The repository labels its published artifact CC0, but the underlying source is
Transfermarkt. Transfermarkt's terms prohibit automated copying and expressly
prohibit use of its digital content for training or development of AI/ML
systems. A repository's CC0 declaration cannot itself guarantee rights in
third-party source data. Therefore this snapshot is **not cleared for a public
or commercial ScoutIQ deployment**, and it must not be treated as a permanent
production data source. This is an unresolved requirement, not a detail to
ignore.

The source also states that updates are paused; its snapshot is current only to
6 July 2026, with valuation records ending no later than 12 June 2026.

## Raw artifact provenance

- Provider/project: `dcaribou/transfermarkt-datasets`
- Original artifact: `transfermarkt-datasets.duckdb`
- Local raw path: `data/raw/transfermarkt_datasets/transfermarkt-datasets.duckdb`
- Snapshot date claimed by provider: 6 July 2026
- Retrieval date: 7 September 2026
- SHA-256: `ba1eff7337b8ca78cb533df0b6eba0d6fc58218e0767460f6770e0b37f5a2113`
- File size: 210,776,064 bytes (201.01 MiB)

The raw artifact is retained unchanged. Any later derived outputs must be
stored outside `data/raw/`.

## Dataset inspection

Inspection was performed read-only with `src/scoutiq/inspect_dataset.py`.
The artifact has 13 tables: 12 domain tables plus a one-row `version` table.

| Table | Rows | What it contains | Temporal fields observed |
| --- | ---: | --- | --- |
| `players` | 50,149 | Player profile and current-snapshot attributes | `date_of_birth`, `contract_expiration_date` |
| `player_valuations` | 656,301 | Historical market-value observations | `date`: 2000-01-20 to 2026-06-12 |
| `appearances` | 1,894,350 | One player appearance per game, including minutes, goals, assists, cards | `date`: 2012-07-03 to 2026-06-28 |
| `games` | 88,958 | Match-level results and context | `date`: 2006-06-09 to 2026-07-06 |
| `transfers` | 175,165 | Player movement, fee and value at transfer | `transfer_date`: 1993-07-01 to 2030-06-30 |
| `clubs` | 796 | Club profile and current-snapshot summary data | no event date |
| `competitions` | 65 | Competition metadata | no event date |
| `club_games` | 177,916 | Club-centric game records | no date column |
| `game_events` | 1,274,469 | Goals, cards and substitutions | `date`: 2006-06-09 to 2026-07-06 |
| `game_lineups` | 3,179,016 | Starting and bench line-ups | `date`: 2013-07-02 to 2026-07-06 |
| `countries` | 124 | Country metadata | no event date |
| `national_teams` | 124 | National-team snapshot data | no event date |

### Important columns

- **Target table:** `player_valuations(player_id, date, market_value_in_eur,
  current_club_id, player_club_domestic_competition_id)`. All three essential
  target fields—player ID, date, euro value—are present and non-null.
- **Player profile:** `players(player_id, date_of_birth, position,
  sub_position, foot, height_in_cm, ...)`. Fields prefixed `current_` and the
  current/peak value fields are a download-snapshot state, not historical
  facts. They must not be used as historical features without a time-aware
  derivation.
- **Performance:** `appearances(appearance_id, player_id, game_id, date,
  competition_id, goals, assists, minutes_played, yellow_cards, red_cards)`.
- **Match context:** `games(game_id, competition_id, season, date,
  home_club_id, away_club_id, ...)`.
- **Transfer context:** `transfers(player_id, transfer_date, from_club_id,
  to_club_id, transfer_fee, market_value_in_eur)`.

### IDs and relationships verified

`player_id`, `game_id`, and `appearance_id` have no duplicates in their
respective entity tables. The composite `(player_id, date)` has no duplicates
in `player_valuations`.

| Relationship check | Result |
| --- | ---: |
| Valuations with no matching `players.player_id` | 0 |
| Transfers with no matching `players.player_id` | 0 |
| Appearances with no matching `games.game_id` | 0 |
| Appearances with no matching `players.player_id` | 2 |

Use IDs for joins; names are descriptive and can have spelling, encoding, and
duplication issues. The two unmatched appearances are a small, concrete data
quality case to investigate later rather than silently dropping now.

### Temporal interpretation

The data has the essential dates needed to *eventually* align performance
before a value date: appearance/game dates, valuation dates, and transfer
dates. We have not performed that alignment today.

Two temporal warnings are already clear:

1. There are 520 transfers dated after the provider's 6 July 2026 snapshot
   claim, and 488 after the 7 September 2026 retrieval date. These are likely
   planned/prospective records and would be leakage if used for an earlier
   observation.
2. The `players` and `clubs` tables contain current-snapshot fields. For a
   historical row, they may reveal information not known at the value date.

These findings make the dataset suitable for an initial **historical data
understanding and temporal-ML design exercise**, but not automatically safe
for model training. Time-aware feature construction and validation remain
future work.

## Relationship map

```text
players (player_id)
  ├── player_valuations (player_id, date, market_value_in_eur)
  ├── appearances (player_id, game_id)
  └── transfers (player_id, transfer_date, from_club_id, to_club_id)

games (game_id, date, competition_id, home_club_id, away_club_id)
  └── appearances (game_id)

clubs (club_id)
  └── players / transfers / games
```

Names are descriptive fields, not join keys. The core player/game relationships
above were verified; club foreign-key quality has not yet been exhaustively
audited.

## Data gaps and decisions

| Gap | Classification | Decision |
| --- | --- | --- |
| Rights-cleared historical market-value labels for public deployment | Required for a deployed product | Postponed; obtain a licensed source before public use. |
| Advanced event metrics such as xG/progressive actions | Useful, optional | Later evaluation of a licensed provider or allowed research data. |
| Current/live player updates | Future enhancement | Keep separate from Day 2 historical training data. |
| Snapshot freshness after June/July 2026 | Future enhancement | Do not use this artifact as a current-data feed. |
| Two appearance rows without a matching profile | Useful but optional for V1 exploration | Investigate and document before any future training dataset is built. |
| Prospective/future transfer dates | Required for temporal modelling | Exclude or otherwise time-filter them in a future leakage-safe design. |

## What remains to be solved

1. Verify the raw database schema, IDs, dates, and basic quality.
2. Establish whether the actual dates permit leakage-safe temporal alignment.
3. Define a rights-cleared source strategy for a future public product.
4. Separately evaluate a current-data API only after the historical dataset is
   understood.

## What we learned

- The selected artifact is relational rather than a single spreadsheet. That
  is useful because each entity has an appropriate grain: player, valuation,
  appearance, game, or transfer.
- The target is observable at the right grain: one player and one valuation
  date. Market value is not a static player attribute.
- Stable IDs make the intended joins feasible, but foreign-key checks are
  still necessary.
- A date column is not a guarantee against leakage. Snapshot columns and
  future-dated records must be treated carefully.
- Historical training data and a future current-data API are different
  systems. A future API will need player/club IDs, dated player statistics,
  transfers, injuries, and current profiles, but it is outside Day 2 scope.
