# ScoutIQ Vision

Status: **Work in progress — guiding document.**

This document clarifies what ScoutIQ is ultimately trying to become. It is a
vision for future decisions, not a promise that these features exist today.

## What ScoutIQ aims to be

ScoutIQ should eventually be a serious football recruitment intelligence and
decision-support platform.

The goal is NOT simply:

> "Predict a player's market value."

Market-value prediction is the first ML component and the foundation of the
project.

The ultimate goal is:

> "Given a club's recruitment requirements, help analysts/scouts identify,
> compare, and prioritize players who are good potential recruitment targets,
> while explaining why each player was recommended and highlighting risks."

ScoutIQ supports human decision-making. It does NOT claim to replace scouts,
recruitment analysts, sporting directors, or managers.

## Who the product is for

Primary users:

- Recruitment analysts
- Scouts
- Sporting directors
- Technical directors

Managers may eventually consume the output, but the system is primarily a
recruitment decision-support tool.

The intended workflow:

```
Club requirements
        ↓
ScoutIQ recruitment engine
        ↓
Candidate players
        ↓
Ranking + explanations + risks
        ↓
Human scouting/recruitment decision
```

## Core intelligence layers

ScoutIQ should eventually combine several signals rather than relying only on
market value.

### 1. Market value prediction

Predict a player's market value at a defined point in time using information
available at or before that point. This remains the first ML milestone. It is
a regression problem.

```
Current/known player information
        ↓
Market-value regression model
        ↓
Predicted market value
```

### 2. Undervaluation / value gap

Eventually compare current estimated market value against the ScoutIQ
predicted value:

```
value_gap = predicted_value - current_value
```

A positive gap can identify players who may deserve further investigation.

IMPORTANT: do NOT automatically call such a player a "hidden gem." A value gap
is only a signal. It does NOT mean:

- the player is definitely undervalued
- the player is cheap to buy
- the player will definitely perform well
- the player should definitely be signed

Market value is not the same thing as transfer fee, salary, or total
acquisition cost.

### 3. Player similarity

ScoutIQ should eventually support player similarity. For example, when a club
loses a winger, instead of asking "who are the best wingers?", ScoutIQ should
be able to ask: "which available players have similar playing characteristics
to this player?"

Possible similarity inputs (to be decided later):

- Position
- Age/profile
- Playing style
- Passing
- Progression
- Chance creation
- Goals/assists
- Defensive actions
- Other relevant performance metrics

The exact feature set is determined later based on data quality and
experimentation.

### 4. Future potential

Eventually ScoutIQ should estimate development/value potential:

```
Current player profile
        ↓
Historical trajectory + age + performance
        ↓
Potential future development/value
```

This is a separate intelligence layer from current market-value prediction.
Not yet implemented.

### 5. Club-specific recruitment fit

Different clubs have different recruitment requirements. A player ideal for
Club A may not be ideal for Club B.

Eventually the user specifies requirements such as:

- Position: winger
- Age: under 23
- Budget: under €30M
- High pressing ability
- Strong progressive carrying
- High chance creation

ScoutIQ then ranks players by fit:

```
Club requirements
        ↓
Candidate filtering
        ↓
Player performance
        ↓
Similarity
        ↓
Predicted value
        ↓
Potential
        ↓
Risk
        ↓
Recruitment fit score
        ↓
Ranked shortlist
```

### 6. Recruitment risk

A useful recruitment system should not only say "player X is good"; it should
also identify concerns. Possible future risk dimensions:

- Injury/availability risk
- Small sample-size risk
- Performance consistency
- League/adaptation risk
- Age/development uncertainty
- Data confidence
- Other relevant recruitment risks

A player with 500 minutes should not automatically be treated the same as a
player with 3,000 minutes. Recommendations should communicate uncertainty
where appropriate.

### 7. Explainability

Every important recommendation should eventually answer: "WHY is ScoutIQ
recommending this player?"

Example WHY block:

```
+ Strong chance creation
+ Excellent progression
+ Age fits recruitment strategy
+ Within budget
+ High similarity to target player
+ Predicted value above current estimated value
```

Example CONCERNS block:

```
- Limited top-flight experience
- Small sample
- Defensive contribution below requirement
```

The system should not simply output a score with no explanation. ML
explainability techniques such as feature importance and SHAP may be
considered later. Do not implement explainability prematurely.

### 8. Recruitment shortlist

The final product should eventually produce something like:

```
Recruitment requirement:
- Position: LW
- Age: <23
- Budget: €30M
- Strong chance creation
- Strong progression

Player A    Fit: 91/100   Predicted: €28M   Current: €21M   Potential: High    Risk: Low
Player B    Fit: 87/100   Predicted: €25M   Current: €15M   Potential: Very High Risk: Medium
Player C    Fit: 84/100   Predicted: €31M   Current: €27M   Potential: High    Risk: Low
```

The exact scoring system does NOT exist yet. We will design and validate it
later. Do not invent a final formula now.

## Product principle

ScoutIQ is a DECISION-SUPPORT SYSTEM. It helps a human answer:

> "Which players should I investigate further, and why?"

It should NOT claim:

> "ScoutIQ knows who the club should buy."

The final recommendation must remain interpretable and allow human judgment.

## How the ML components connect

```
                   PLAYER DATA
                       ↓
        ┌──────────────┼──────────────┐
        ↓              ↓              ↓
   VALUATION       PERFORMANCE     SIMILARITY
     MODEL            DATA           ENGINE
        ↓              ↓              ↓
        └──────────────┼──────────────┘
                       ↓
                  POTENTIAL
                       ↓
                    RISK
                       ↓
               CLUB REQUIREMENTS
                       ↓
               RECRUITMENT FIT
                       ↓
                PLAYER RANKING
                       ↓
                  EXPLANATION
                       ↓
                 HUMAN SCOUT
```

## Current status

Work in progress. Market-value prediction (layer 1) is the first ML milestone
and the current focus. The other layers are future work and not yet
implemented.