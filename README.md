# ScoutIQ

### Football Recruitment Intelligence & Decision-Support Platform

> **Work in progress.** ScoutIQ is under active development. Some capabilities described below are planned, not yet implemented.

## Purpose

ScoutIQ is a football recruitment decision-support platform for recruitment
analysts, scouts, sporting directors, and technical directors.

The goal is not simply to predict player market value. Market-value prediction
is the **foundation** — the first ML component. The ultimate goal is:

> Given a club's recruitment requirements, help analysts and scouts identify,
> compare, and prioritize players who are good potential recruitment targets,
> while explaining why each player was recommended and highlighting risks.

ScoutIQ supports human decision-making. It does not claim to replace scouts or
recruitment analysts, and it never claims to "know who the club should buy."

## Current status

- Historical football data acquired (Transfermarkt datasets), Premier League is
  the initial focus.
- Data exploration and understanding complete, documented in
  `learning_notes/`.
- A leak-safe temporal ML dataset (`data/processed/pl_valuation_features_v1.csv`)
  has been built for market-value modelling.
- The first ML milestone — a market-value regression model — is the current
  focus. No model exists yet.

## Planned capabilities

- Estimate player market value from historical data (regression).
- Surface potential value gaps between current and predicted value — a signal
  worth investigating, not a claim of a "hidden gem."
- Find players similar to a reference player by playing characteristics.
- Rank candidates against club-specific recruitment requirements
  (position, age, budget, playing style).
- Estimate future development/value potential.
- Highlight recruitment risks (injuries, small samples, consistency,
  adaptation, uncertainty).
- Explain why each player is recommended, including concerns.
- Generate ranked, explainable recruitment shortlists for human review.

## Vision

See [`learning_notes/vision.md`](learning_notes/vision.md) for the full
intelligence architecture and product principles.

## Repository layout

- `data/raw/` — original Transfermarkt datasets (read-only).
- `data/interim/` — working SQLite copy used for analysis.
- `data/processed/` — built ML datasets.
- `src/scoutiq/` — data exploration and ML pipeline scripts.
- `learning_notes/` — milestone notes and decisions.

## Licensing

The current dataset is used for private learning and prototyping only. A
public deployment would require licensed data or APIs.

## Roadmap

1. Market-value regression model (current milestone).
2. Player similarity engine.
3. Recruitment requirements & fit scoring.
4. Risk and explainability layers.
5. Shortlist generation and an initial UI.
6. Expansion to additional major European leagues and live data.