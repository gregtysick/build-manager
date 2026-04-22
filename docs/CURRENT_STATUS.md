# Current Status

## Current state
Build Manager is in active development.

What already exists:
- live local SQLite-backed runtime
- deterministic project/task command surface
- thin natural-language adapter
- human-facing Obsidian project/capture layer
- read-only HTML dashboard foundation
- Tailscale-accessible dashboard hosting path

What has recently been clarified:
- `repo/` is the exact tracked publish tree
- internal GitHub drafting now lives outside the repo in a separate curation reservoir
- the curation package is being cleaned up into canonical notes, logs, and archive buckets
- the active skill/repo name is now consistently **Build Manager**
- the workflow model is being tightened around one orchestrator with separate internal workflows

What is still being tightened:
- dashboard polish
- limited safe interactivity
- workflow handoff quality between capture, design, planning, and publish-related work
- repo packaging
- public-facing documentation

## Workflow direction
Build Manager currently remains one top-level orchestrator.

The current workflow split being formalized is:
- capture
- design
- planning
- content generation
- GitHub content
- publishing

## Boundary
This repo is for the current skill-first system.
The later broader agent direction is a separate future project named **Build Factory**.
