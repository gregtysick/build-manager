# Planning Workflow

## Role
Turn the approved design into an execution-ready plan.

## Current minimal behavior
- list design-stage projects that are ready for planning
- build a Planning Package from the latest Design Package
- emit stable task keys and explicit task-key dependency references inside the planning package
- store that planning package in the database
- write a matching Obsidian planning note
- move the project from `design` into `planning`

## Current posture
Planning is still intentionally narrow:
- no automatic task creation yet
- no subtask generation yet
- no rich dependency graph beyond ordered task-key references yet
- just a real planning package, explicit dependency handoff metadata, and stage transition
