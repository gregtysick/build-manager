# Build Manager Workflows

This folder is the runtime home for Build Manager workflow modules.

## Purpose
Build Manager stays one top-level orchestrator.
These workflow folders are the internal execution lanes behind that orchestrator.

## Current workflow set
- `capture/`
- `review/`
- `design/`
- `planning/`
- `build/`
- `content_generation/`
- `github_content/`
- `publishing/`

## Working rule
- `scripts/build_manager.py` remains the main command/orchestrator entry point
- workflow-specific logic should gradually move into these workflow folders instead of being buried in one large script or scattered through curation notes
- curation notes define the human-facing workflow design
- this runtime folder is where executable workflow behavior should live

## Expected evolution
Each workflow folder can later hold things like:
- prompt/instruction notes
- workflow-specific config
- schema for expected input/output packages
- helper scripts or Python modules
- tests or validation notes
