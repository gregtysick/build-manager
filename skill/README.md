# Skill Package Notes

This folder is the intended publishable skill boundary for Build Manager.

## What belongs here
This package should eventually contain the skill-facing material that another OpenClaw user can install safely, including:
- skill instructions
- packaging metadata
- bootstrap/setup guidance
- schema or migration assets
- installation helpers

## What does not belong here
This package should not contain Greg's live runtime state, including:
- the working SQLite database
- local dashboards generated from live data
- private Obsidian project material
- machine-specific paths, secrets, or mutable operator state

## Intended install model
The clean install model is:
1. install the skill package
2. create a fresh local runtime workspace
3. initialize a fresh local database
4. optionally add sample/demo seed data

## Current status
This folder now contains the mirrored skill package material for the repo/GitHub side.

It is still not Greg's live runtime.
The intent is:
- repo/GitHub shows a clean inspectable package
- the live install continues to run separately
- changes can later be promoted deliberately between the two when appropriate
