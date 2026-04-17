# Installation and Packaging

## Purpose
This document explains how Build Manager should be distributed for other people to clone, fork, install, and use.

## Short answer
People should be able to:
- clone or fork the repo
- read the docs
- install the skill
- create a fresh local runtime on their own machine

They should not receive Greg's live working database as the default package.

## Packaging boundary
Build Manager has three different layers that need to stay cleanly separated.

### 1. Publishable package layer
This is what belongs in the public repo and later on ClawHub.

It should contain:
- skill instructions
- install/setup guidance
- schema or migrations
- bootstrap scripts
- example config templates
- example screenshots and docs

It should not contain:
- Greg's live operator database
- Greg's personal runtime state
- Greg's private Obsidian project corpus
- local machine-specific paths and secrets

### 2. Local runtime layer
This is created on each user's own machine.

It should contain:
- a local SQLite database
- local config
- generated dashboards
- local exports
- mutable runtime state

This layer is installation-specific and should be created during setup or first run.

### 3. Human-facing context layer
For Greg, that currently includes the Obsidian working folder and related project material.

That layer is useful for the real operating system, but it is not the right default package for public distribution.

## What happens when someone clones the repo
The clean model is:
1. they clone the repo
2. they read the README and installation docs
3. they run setup or install the skill
4. setup creates a fresh local runtime workspace
5. setup initializes a fresh SQLite database from schema/migrations
6. they start with an empty or lightly seeded system of their own

## Does the database go in the repo
### Default answer
No, not the live working database.

### What can go in the repo instead
The repo can include:
- SQL schema
- migrations
- bootstrap logic
- optional example data
- optional demo snapshots for screenshots or testing

### What should stay out
The repo should not ship:
- Greg's actual working database
- ongoing task history
- personal or operator-specific project records
- mutable production runtime state

## Does each installation get its own database
Yes, that is the cleanest model.

Each installation should create its own local database.
That keeps the system:
- portable
- safe to share
- easier to reason about
- cleaner for forks and community use

## What about the working-folder system
The same separation applies.

A public package can define the expected folder structure, but it should not ship Greg's live working folders as the default runtime.

Public package should provide:
- documented folder layout
- folder creation scripts
- optional templates
- optional example content

Each user installation should create its own:
- local runtime workspace
- local database
- local dashboard outputs
- optional local notes/context layer

## ClawHub model
ClawHub is a good fit for the publishable skill layer.

That means ClawHub should eventually distribute:
- the skill package
- installation instructions
- bootstrap/setup behavior
- versioned updates to the publishable package

It should not be treated as a distributor for a shared mutable operator database.

## Clean future install model
Ideal install flow later:
1. install Build Manager from ClawHub
2. OpenClaw places the skill files locally
3. first-run bootstrap creates the runtime workspace
4. bootstrap initializes the SQLite database
5. optional setup asks whether to create demo/sample data
6. user begins with their own local system

## Honest current status
The current public repo is earlier than that.

Right now it is:
- a documentation-first public packaging layer
- a credibility-facing repo for the current skill direction
- not yet a finished one-command public installer

So the answer today is:
- yes, we should document how to use it
- no, we should not publish Greg's live database as the install database
- yes, each real installation should create its own local runtime state
- yes, ClawHub should package the skill boundary, not the live operator data

## Recommended next packaging steps
1. define the public install boundary clearly
2. add a real `skill/` package structure
3. add schema/bootstrap assets for fresh installs
4. add setup instructions for local runtime creation
5. optionally add sample/demo seed data as a separate opt-in path
6. publish to ClawHub once the skill boundary is clean enough to install without Greg-specific assumptions
