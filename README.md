# Build Manager

Build Manager is a prompt-driven dashboard for staged, reviewable software delivery.

Instead of pushing everything through button-heavy project screens, it lets work move through guided prompts, clear stages, and explicit review points.

It is meant for shaping rough ideas into realistic execution before too much time gets spent building the wrong thing.

## Why it is different
Most project tools start too late.
They assume the work is already clear.

Build Manager starts earlier.
It helps capture rough ideas, pressure-test them, define the outcome, and only then push them into real build execution.

## What it does
Build Manager helps:
- capture rough ideas before they get over-structured
- collect inspiration, references, and useful context in one place
- clarify what should actually be built before execution hardens
- turn planning into real tracked build work
- keep review checkpoints visible during execution
- move finished build work into support instead of leaving it as a dead task list

## Four-layer architecture
The current working system is intentionally split into four layers:

1. **Obsidian curation**
   - drafts, project notes, prompts, packaging notes, and preserved human context
2. **live OpenClaw install**
   - installed skill package, live runtime workspace, local DB, and generated local dashboard assets
3. **local git repo working tree**
   - this tracked publish tree, now located under `Build_Manager/Current_Projects/11-build-manager/repo/`
4. **GitHub remote**
   - hosted copy of this local repo working tree

## Boundary rules
- `curation/github/` is a draft reservoir only
- this repo is the tracked publish tree
- live runtime data is not the repo
- GitHub remote is downstream of the local repo working tree
- intended publish flow is draft -> repo -> commit/push

## Working-product status
Yes — Build Manager is now a working internal product.

What that means:
- the staged lifecycle is real in the runtime, not just documented
- planning can hand off into real build tasks
- build tasks can carry dependencies, subtasks, and explicit review checkpoints
- completed build work can now transition into support

What that does **not** mean yet:
- public packaging is finished
- install flow is fully polished
- documentation is complete
- the dashboard/read model is done evolving

## Current scope
Right now Build Manager is aimed at OpenClaw development work, including:
- skills
- agents
- workflows
- tooling
- architecture and system work

## Working lifecycle
`Hopper -> Capture -> Evaluation -> Design -> Planning -> Build -> Support -> Parked/Archived`

GitHub, packaging, publishing, and documentation are cross-cutting workflows, not master lifecycle stages.

## Workflow model direction
Build Manager is staying as one top-level orchestrator for now.

Current internal workflows being clarified behind that surface:
- capture workflow
- design workflow
- planning workflow
- content generation workflow
- GitHub content workflow
- publishing workflow

## Why it exists
Many project systems start after someone has already decided what to build.
Build Manager starts earlier.

Its job is to improve the quality of decisions, execution, and preserved output so work becomes more realistic, more reviewable, and more reusable.

## Repository status
This repo is the human-inspectable GitHub mirror for Build Manager.
It is intentionally a publishable copy of the skill and runtime code, not Greg's live working install.

What it reflects right now:
- the four-layer boundary between curation, live install, local repo, and GitHub remote
- the current Build Manager naming and scope
- the current one-orchestrator workflow direction
- a mirrored copy of the publishable skill/runtime code
- explicit separation between repo code and Greg's live mutable runtime state

The broader future agent direction is being held separately under the later **Build Factory** project.

## In this repo
- `docs/CURRENT_STATUS.md` for current implementation posture
- `docs/POSITIONING.md` for the product framing
- `docs/WORKFLOW_MODEL.md` for the workflow split and current orchestrator direction
- `docs/INSTALLATION_AND_PACKAGING.md` for cloning, runtime-data, and distribution guidance
- `docs/HOW_IT_WORKS.md` for a plain-language under-the-hood explanation
- `skill/` for the mirrored skill package content
- `scripts/` for the mirrored runtime command and dashboard scripts
- `workflows/` for workflow runtime logic
- `sql/` for initialization and migration SQL
- `config/build_manager.example.json` for a publishable config example
- `runtime/README.md` for the live-runtime boundary explanation

## How other people should use this
The intended public model is:
- clone or fork the repo for documentation, packaging, and future install scripts
- install the skill package, not Greg's personal runtime state
- create a fresh local workspace and database per installation
- keep operator data local and mutable, not committed into the repo

## Ownership split
- Build Manager owns project truth and the factual statement of what is working
- Career Agent should later own public language consistency and broader professional positioning
- GitHub utility behavior should remain platform mechanics and execution only

## ClawHub direction
ClawHub should package the skill definition and installation boundary.
It should not package a shared mutable live database.

The clean model is:
- skill files ship through the repo and later ClawHub
- install flow creates the local runtime workspace
- first run initializes a new local database for that user
- local dashboards, notes, and runtime state belong to that installation

## Repo intent
This repository is being shaped as a credibility-first record of thoughtful, real engineering work.
The priority is clarity, good judgment, and steady system design, not flashy complexity.
