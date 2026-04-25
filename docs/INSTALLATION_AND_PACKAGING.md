# Installation and Packaging

## Purpose
This document explains how Build Manager should be distributed for other people to clone, fork, install, and use.

## Four-layer boundary
Build Manager currently has four layers that need to stay cleanly separated.

### 1. Obsidian curation
This is the draft and preserved-context layer.
It holds notes, prompts, strategy material, packaging notes, and reusable wording drafts.

### 2. live OpenClaw install
This is the running system on a machine.
It includes:
- installed skill package
- local runtime workspace
- local SQLite database
- generated dashboards, exports, and mutable runtime state

### 3. local git repo working tree
This is the tracked publish tree.
For the current Build Manager project, it lives under:
- `Build_Manager/Current_Projects/11-build-manager/repo/`

### 4. GitHub remote
This is the hosted copy of the local repo working tree.
It is downstream of the local repo working tree, not a replacement for it.

## Packaging rule
People should be able to:
- clone or fork the repo
- read the docs
- install the skill
- create a fresh local runtime on their own machine

They should not receive Greg's live working database or live operator runtime as the default package.

## Boundary rules
- `curation/github/` is a draft reservoir only
- repo is the tracked publish tree
- live runtime is not the repo
- publish flow should be draft -> repo -> commit/push
- internal strategy notes and packaging working notes should stay in `curation/github/`, not in the published `repo/docs/` tree

## What belongs in the repo
The repo can include:
- a mirrored copy of the publishable skill package
- a mirrored copy of the publishable runtime code
- install/setup guidance
- schema or migrations
- bootstrap scripts
- example config templates
- example screenshots and docs
- optional example or demo data

## What stays out of the repo
The repo should not ship:
- Greg's live operator database
- Greg's personal runtime state
- Greg's private Obsidian project corpus
- local machine-specific paths and secrets
- mutable production runtime state

## Install model
The clean model is:
1. user clones or installs the package
2. user reads the docs
3. setup creates a fresh local runtime workspace
4. setup initializes a fresh local SQLite database from schema/migrations
5. user starts with an empty or lightly seeded system of their own

## ClawHub model
ClawHub is a good fit for the publishable skill layer.

That means ClawHub should eventually distribute:
- the skill package
- installation instructions
- bootstrap/setup behavior
- versioned updates to the publishable package

It should not be treated as a distributor for a shared mutable operator database.

## Ownership note
- Build Manager owns the factual statement of what the project is and what is working
- Career Agent should later own cross-channel public language consistency
- GitHub utility behavior should remain execution/mechanics rather than narrative ownership

## Honest current status
The current public repo is now more than docs, but it is still earlier than a polished one-command installer.

Right now it is:
- a tracked publish tree with mirrored skill/runtime code
- a credibility-facing repo for the current skill direction
- intentionally separate from Greg's live database and mutable runtime state
- not yet a finished turnkey public installer

## Recommended next packaging steps
1. define the public install boundary clearly
2. keep the repo/package boundary explicit
3. add schema/bootstrap assets for fresh installs
4. add setup instructions for local runtime creation
5. optionally add sample/demo seed data as a separate opt-in path
6. publish to ClawHub once the skill boundary is clean enough to install without Greg-specific assumptions
