# Build Workflow

## Role
Turn the approved planning package into real executable project tasks and start the build stage.

## Current minimal behavior
- list planning-stage projects that are ready for build kickoff
- parse the latest Planning Package task breakdown
- create real project tasks in the database
- resolve and store task-to-task dependencies from explicit planning-package task keys when present, with heuristic fallback for older planning packages
- write a matching Obsidian build kickoff note
- move the project from `planning` into `build`
- list project tasks for a build-stage project
- show the current task, waiting review task, or next executable task
- start an agent-executable project task
- complete an active project task, release newly-unblocked review tasks, and optionally auto-start the next agent task
- sync dependency links onto existing build-stage projects from the stored planning package
- generate deterministic subtasks for top-level build tasks
- list a task's generated subtasks
- show the next actionable subtask for a parent task
- start and complete subtasks with bounded auto-advance
- prevent parent task completion while subtasks remain unfinished
- start and complete review/manual tasks explicitly once they enter `waiting`
- start and complete review/manual subtasks explicitly within an active review task
- preserve planning-order intent as top-level task priority
- transition the project from `build` to `support` automatically once all top-level build tasks are done

## Current posture
This pass is still intentionally narrow:
- subtask generation is deterministic template-based from the parent task role, not model-generated planning yet
- subtask execution is sequential by subtask priority within a parent task
- top-level task ordering now respects planning order through task priority, with an explicit sync path for older projects
- review/manual items are first-class in the command surface, but still use the same core task-state model underneath
- dependency wiring now prefers explicit planning-package task keys, but still falls back to heuristic text matching for older planning packages
- no execution agent launch yet
- auto-advance only starts the next eligible agent-executable item at the current layer; review/manual items are surfaced or released to `waiting` instead
- build now covers real task creation, dependency gating, subtask generation, subtask execution control, explicit review-task flow, bounded execution control, and build-to-support transition
