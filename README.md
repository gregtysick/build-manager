# Build Manager

Build Manager is a skill-first OpenClaw workflow for turning rough project ideas into realistic, structured, reviewable execution.

It is not meant to be just a task tracker and not meant to be a blind automation wrapper.
The goal is to add a practical consultant layer before and during execution.

## What it does
Build Manager helps:
- catch likely break points early
- spot design mistakes before they harden
- pressure-test scope and expectations
- use outside inspiration before execution becomes rigid
- walk through the likely end result before too much is built
- keep review checkpoints and approvals visible

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
This repo is an early tracked packaging layer for a real in-progress system.
It is meant to document the direction clearly while the underlying workflow continues to tighten.

The broader future agent direction is being held separately under the later **Build Factory** project.

## In this repo
- `docs/CURRENT_STATUS.md` for current implementation posture
- `docs/POSITIONING.md` for the product framing
- `docs/WORKFLOW_MODEL.md` for the workflow split and current orchestrator direction
- `docs/INSTALLATION_AND_PACKAGING.md` for cloning, runtime-data, and distribution guidance
- `skill/README.md` for the skill-facing slice of the work

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
