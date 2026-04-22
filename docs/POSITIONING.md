# Positioning

## Core idea
Build Manager is not just a task tracker and not just an automation wrapper.

It is meant to improve the quality of project execution before and during build.

## What makes it different
Many automated project systems do two things:
- take input from the user
- execute to produce the requested result

What is often missing is the consultant layer.

Build Manager is intended to add that missing layer by:
- checking for likely break points before they happen
- spotting design mistakes before they harden
- taking in inspiration before execution becomes rigid
- mentally walking through the final app or workflow to improve the outcome
- keeping approvals and review checkpoints explicit

## Product shape
Build Manager currently behaves more like a consultant-guided workflow system than a fully autonomous agent.
That is intentional for the current stage.

It is also intentionally staying as one top-level orchestrator while the internal workflow split is clarified.
Current internal workflows being shaped are capture, design, planning, content generation, GitHub content, and publishing.

## Future relationship to Build Factory
Build Manager is the skill-first system.
Build Factory is the later fuller agent direction.
