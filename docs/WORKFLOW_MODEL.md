# Workflow Model

## Current direction
Build Manager is staying as one top-level orchestrator for now.

The current goal is not to split immediately into many exposed skills.
The current goal is to make the workflow boundaries clear first, then split only where the payoff is real.

## Active internal workflow set

### 1. Capture
Purpose:
- turn rough input into a reviewable project-candidate package
- preserve source wording, scope, constraints, and open questions
- prepare a clear move-forward approval object

### 2. Design
Purpose:
- define what good looks like before planning and build
- pressure-test the desired finished product
- lock important boundary and architecture decisions

### 3. Planning
Purpose:
- turn the approved design into phases, tasks, checkpoints, and execution order
- make agent-run vs Greg-review boundaries explicit

### 4. Content generation
Purpose:
- accumulate reusable future writing and messaging material
- store headlines, hooks, article seeds, post seeds, and proof points without forcing immediate publishing

### 5. GitHub content
Purpose:
- prepare GitHub-facing repo copy and packaging material
- keep internal strategy separate from public repo documentation
- promote selected draft material into the publish tree deliberately

### 6. Publishing
Purpose:
- review the exact publish tree
- confirm what is public-safe
- commit and push only from the local tracked repo working tree

## Relationship to lifecycle stages
Build Manager still uses the project lifecycle:
`Hopper -> Capture -> Evaluation -> Design -> Planning -> Build -> Support -> Parked/Archived`

The workflow set above is not identical to the lifecycle.
Some workflows map directly to stages, while others are cross-cutting support workflows used when appropriate.

## Why this matters
This model keeps Build Manager from collapsing into either:
- one vague skill that does everything badly, or
- too many top-level skills too early

The intention is to keep one coherent surface while making the internal handoffs sharper and more reviewable.
