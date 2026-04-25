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
- real planning-to-build task handoff
- deterministic subtask generation and execution control
- explicit review/manual task flow inside build execution
- automatic build-to-support transition when build work is finished
- project-level conversation binding metadata for keeping a build/project tied to its canonical chat surface

What has recently been clarified:
- `repo/` is the exact tracked publish tree
- internal GitHub drafting now lives outside the repo in a separate curation reservoir
- the curation package is being cleaned up into canonical notes, logs, and archive buckets
- the active skill/repo name is now consistently **Build Manager**
- the workflow model is being tightened around one orchestrator with separate internal workflows
- the repo is allowed to mirror publishable code for GitHub/portfolio inspection even though the live install continues to run separately

What is still being tightened:
- dashboard polish
- limited safe interactivity
- dashboard prompt running on top of the canonical project conversation binding
- support-stage and continuation behavior
- workflow handoff quality between capture, design, planning, and publish-related work
- repo packaging
- public-facing documentation

## Working-product answer
If the question is "does this work yet?" the honest answer is yes — as an internal product.

Build Manager is already capable of running a real staged workflow through capture, planning, build execution, review checkpoints, and support transition.

If the question is "is it fully packaged and publication-ready?" then not yet.

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
