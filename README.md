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
- `skill/README.md` for the skill-facing slice of the work

## Repo intent
This repository is being shaped as a credibility-first record of thoughtful, real engineering work.
The priority is clarity, good judgment, and steady system design, not flashy complexity.
