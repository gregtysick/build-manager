# How Build Manager Works

Build Manager is a skill-first OpenClaw workflow for taking rough technical ideas and turning them into staged, reviewable execution.

## Plain-language overview
Most project systems start once someone has already decided exactly what to build.
Build Manager starts earlier.

It helps:
- capture rough ideas without losing context
- evaluate whether the idea is worth real project investment
- design the intended outcome
- plan the execution path
- convert that plan into real tracked work
- keep review checkpoints explicit during execution

In other words, it tries to improve the quality of the work before and during execution, not just store tasks.

## The working model
The current workflow is:

`Hopper -> Capture -> Evaluation -> Design -> Planning -> Build -> Support -> Parked/Archived`

Within that lifecycle, Build Manager currently supports a real execution path:
- planning packages can generate top-level build tasks
- build tasks can carry dependency relationships
- top-level tasks can generate deterministic subtasks
- subtasks can be executed in priority order
- review/manual checkpoints can be surfaced as explicit waiting tasks
- once build work is complete, the project can move into support

## Core layers
Build Manager is intentionally split across a few boundaries:

1. **Obsidian curation**
   - notes, drafts, working docs, and GitHub-facing reservoir content
2. **live OpenClaw runtime**
   - installed skill, local workspace, runtime database, dashboard outputs
3. **local repo working tree**
   - publishable tracked source
4. **GitHub remote**
   - hosted downstream copy of the repo working tree

This keeps live operator state separate from publishable repo content.

## What is working now
Build Manager is already a working internal product.

Current working capabilities include:
- live local SQLite-backed runtime
- deterministic CLI command surface
- thin natural-language adapter
- capture/review/design/planning/build workflow chain
- planning-to-build dependency handoff
- deterministic subtask generation
- subtask execution control
- review/manual task flow inside build execution
- automatic build-to-support transition when top-level build work is complete
- project-level conversation binding metadata so a build/project can keep one canonical chat surface as dashboard prompt work is added

## What is still being tightened
The system is real, but not finished.

Current tightening areas include:
- support-stage behavior and continuation rules
- dashboard/read-model clarity for parent/subtask/review state
- dashboard prompt running on top of canonical project conversation binding
- packaging/install boundary
- public documentation polish
- repo-to-GitHub promotion flow

## Why this project exists
Build Manager exists because execution quality depends heavily on pre-execution judgment.

A system that only stores tasks usually misses:
- whether the idea was shaped well enough
- whether a review checkpoint should happen before continuing
- whether the outcome has been made reusable and explainable afterward

Build Manager is trying to close that gap.
