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

## System shape
The current working system combines:
- a local SQLite-backed source of truth
- chat as the control surface
- a human-facing dashboard
- Obsidian as the preserved context and curation layer

## Current scope
Right now Build Manager is aimed at OpenClaw development work, including:
- skills
- agents
- workflows
- tooling
- architecture and system work

## Working lifecycle
`Inbox -> Capture -> Evaluation -> Design -> Plan -> Build -> Support -> Documentation / Content / GitHub`

## Why it exists
Many project systems start after someone has already decided what to build.
Build Manager starts earlier.

Its job is to improve the quality of decisions, execution, and preserved output so work becomes more realistic, more reviewable, and more reusable.

## Repository status
This repo is an early public packaging layer for a real in-progress system.
It is meant to document the direction clearly while the underlying workflow continues to tighten.

The broader future agent direction is being held separately under the later **Build Factory** project.

## In this repo
- `docs/CURRENT_STATUS.md` for current implementation posture
- `docs/POSITIONING.md` for the product framing
- `docs/REPO_STRATEGY.md` for repo-purpose and publication intent
- `docs/INSTALLATION_AND_PACKAGING.md` for cloning, runtime-data, and distribution guidance
- `skill/README.md` for the skill-facing slice of the work

## How other people should use this
The intended public model is:
- clone or fork the repo for documentation, packaging, and future install scripts
- install the skill package, not Greg's personal runtime state
- create a fresh local workspace and database per installation
- keep operator data local and mutable, not committed into the repo

## Does the database get included
Not as the default live database.

The current direction is:
- the repo can include schema, migrations, and bootstrap scripts
- each installation should create its own fresh SQLite database locally
- optional demo or seed data can be offered separately, but should not be the default operator database
- Greg's working database and Obsidian project material should stay out of the public package

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
