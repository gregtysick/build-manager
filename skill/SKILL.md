---
name: build-manager
description: Manage OpenClaw development-scope projects, tasks, subtasks, notes, status changes, work sessions, simple read views, and a thin natural-language adapter using the live local SQLite backend for Build Manager.
---

## Trigger identification

When this skill is triggered, first output this two-line header:
```text
Build Manager
~/.openclaw/skills/build-manager
```

# Build Manager

## Purpose

This skill is the callable interface for the live OpenClaw development-scope Build Manager backend.

Use it to:
- create projects
- list projects
- create tasks
- create subtasks
- list tasks by status
- show current active tasks
- show paused tasks
- update task status
- start and stop work sessions
- attach notes
- use a thin natural-language adapter for the current deterministic command surface

## Scope

Current scope:
- OpenClaw development
- internal OpenClaw system work only
- local SQLite backend under `~/.openclaw/skills-workspaces/build-manager/`
- human-facing markdown/context material under `/mnt/d/Dropbox/Obsidian/OpenClaw/Build_Manager/`
- canonical shared HTML dashboard output under `/mnt/d/Dropbox/Obsidian/OpenClaw/Dashboards/Build_Manager/`
- deterministic CLI commands first
- thin NL adapter on top of those commands
- chat-first menu wrapper for common Build Manager actions
- agent-operated execution with human oversight

This Build Manager skill is not the general life/project system.
It is specifically for OpenClaw system development, agent development, skills, workflows, tooling, and architecture work.

## Trigger behavior

Treat requests like these as a request to open the Build Manager menu:
- `build manager`
- `open build manager`
- `show build manager`
- `build manager menu`
- `add something to build manager`
- `add this to build manager`
- `put this in build manager`
- `track this in build manager`
- `project manager` (legacy alias)
- `projectmanger` (legacy alias)
- `open project manager` (legacy alias)
- `show project manager` (legacy alias)
- `project manager menu` (legacy alias)
- `add something to project manager` (legacy alias)
- `add this to project manager` (legacy alias)
- `put this in project manager` (legacy alias)
- `track this in project manager` (legacy alias)

When triggered this way, first output:
```text
Build Manager
~/.openclaw/skills/build-manager
```

Then show this menu:

```text
**Build Manager**
**Backend root:** ~/.openclaw/skills-workspaces/build-manager
**Database:** ~/.openclaw/skills-workspaces/build-manager/data/build_manager.db

1. Capture Project
2. Capture Task
3. Capture Subtask
4. Show Projects
5. Show Current
6. Show Queued
7. Show Paused
8. Mark Task Active
9. Mark Task Done
10. Add Note
11. Start Work Session
12. Stop Work Session
13. Refresh Dashboard
14. End

Reply with 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, or 14.
```

Keep the interaction compact and menu-driven.
If the user gives a direct Build Manager request, or a legacy project-manager request, without enough structure, prefer opening the menu instead of guessing.

## Capture-title behavior

For task capture requests, prefer deriving a short practical task title from the user's sentence instead of using the full sentence as the title.

Default behavior:
- infer a short task title
- keep the user's original wording as task detail/context
- include small useful suggestions only when they genuinely help

When a capture request is clear but the title could be improved, propose a compact confirmation flow:

```text
Suggested task title: <short title>

1. Keep original
2. Use rewritten title
3. Provide task name
```

Interpretation rules:
- `1` means keep the user's original wording as the task title
- `2` means use the assistant's shorter rewritten title
- `3` means the user will provide a custom task title

Preferred behavior most of the time:
- infer a short title automatically
- create the task under that short title once the user accepts
- preserve the user's original sentence in the task description, note, or added detail
- keep titles concise and action-oriented
- avoid long sentence-like titles unless the user explicitly wants that

## Operating model

Treat this as the internal OpenClaw systems work manager.

Projects should represent meaningful OpenClaw system outcomes such as:
- agent improvements
- skill development
- workflow redesign
- dashboard/view improvements
- browser/tooling integration
- architecture cleanup
- automation work

Target operating model:
- all new project ideas should enter **Hopper** first
- Hopper is the universal pre-project intake area
- Hopper is for rough ideas, raw capture, brainstorming, evaluation, and shelved material
- not every Hopper item should become a real project
- real projects now move through the canonical lifecycle directly in the backend

Current live runtime model:
- standalone tasks use the operational task statuses below
- project-owned tasks use the simpler project-task statuses below
- project records use the canonical project lifecycle stages below

Valid standalone task statuses in the live backend:
- `captured` = rough captured task or intake item
- `queued` = approved and ready for execution
- `active` = currently in progress
- `paused` = blocked on dependency, permission, confirmation, or external state
- `parked` = intentionally deferred but still worth keeping
- `done` = completed
- `archived` = historical cleanup only

Valid project-task statuses in the live backend:
- `planned`
- `active`
- `waiting`
- `done`

Valid project lifecycle stages in the live backend:
- `hopper`
- `capture`
- `evaluation`
- `design`
- `planning`
- `build`
- `support`
- `parked`
- `archived`

Default operating behavior:
- the user can drop rough project ideas into Hopper in plain language
- the user can also create direct standalone tasks immediately when the intent is clearly "this is a task"
- the agent should preserve raw wording and supporting material without forcing weak ideas to look like real projects too early
- the agent should shape items only as much as needed for triage and later recovery
- the agent may create supporting tasks and subtasks while executing approved work
- the agent should keep task state current as work progresses
- the dashboard is the primary human operational view
- chat is the control surface
- autonomy should remain bounded by explicit user direction for unbounded or risky work
- never guess or assume when source of truth is unclear, ask instead

## Project intake flow

All new ideas should begin in **Hopper**.
Even if an item is likely to become a real project immediately, it should still land in Hopper first and only then move forward by explicit instruction.

Recommended Hopper statuses:
- `Idea` = initial entry, tentative name, minimal detail
- `Capture` = raw material collection only, including notes, references, attachments, URLs, voice-note style dumping, and source material
- `Brainstorm` = interactive shaping and organizing with Greg
- `Evaluation` = decide whether the item deserves real project investment
- `Shelved` = keep indefinitely without moving forward now

Recommended Hopper item kinds:
- `idea`
- `project_candidate`
- `task`
- `reference`

Preferred intake process for project-like ideas:
1. create or update the Hopper item first
2. preserve the raw wording and any attached/supporting material
3. let Greg keep talking, typing, linking, or dropping references into the Hopper item without forcing early structure
4. when useful, help organize the material through Brainstorm
5. move to Evaluation only when the item is coherent enough to judge whether it should move forward
6. either shelve it, keep collecting, convert it into a standalone task, or explicitly move it forward into the canonical project lifecycle as a real project

Direct standalone task rule:
- if Greg clearly gives something as a **task**, create it directly as a standalone task unless he explicitly wants it treated as a project candidate
- standalone tasks may have subtasks and light complexity without becoming projects
- standalone tasks do not require project-level capture, evaluation, design, planning, or curation docs by default
- a dedicated task-intake channel may default plain incoming messages to new standalone task capture when that channel is explicitly configured for task intake

Preferred intake questions inside Hopper:
1. Is this just an idea, or a likely real project?
2. What outcome seems interesting or valuable here?
3. Is this worth deeper definition now, or should it stay in Hopper?
4. Is this a project candidate, a task, or just supporting/reference material?
5. What supporting material should be attached before deciding?

## Project move-forward gate

A Hopper item should not be pushed forward casually.
Moving it into the canonical project lifecycle should require an explicit move-forward decision.

The move-forward package should clearly state:
- what has been locked
- what remains open
- the first practical outcome being targeted
- what stage the project should move into next
- exactly what Greg is approving if he says yes

Rules:
- a Hopper item does **not** become an active project without explicit approval
- when asking for approval, the agent must state the approval object clearly, not just ask for a generic yes
- the agent should use the current canonical stages `Hopper`, `Capture`, `Evaluation`, `Design`, `Planning`, `Build`, `Support`, `Parked`, and `Archived`

## Project-intake notes style

For larger projects, capture should produce:
- short project title
- plain-language summary
- technical summary when useful
- version 1 scope
- later-phase ideas when relevant
- key operating rules
- remaining open questions
- a clear finished-product description
- a realistic near-term outcome
- a practical execution-design outline
- a capture completion indicator
- a clear approval checkpoint before Step 2
- an explicit statement of what approval authorizes

## Model and thinking guidance

The workflow must include complexity-aware model guidance.

Required behavior:
- during capture, assess project complexity
- recommend an appropriate model tier and thinking level
- carry that recommendation into Step 2 planning unless the work clearly changes in complexity
- during Step 2, re-check whether the project still fits the original recommendation
- if the recommendation changes, say so explicitly and explain why

Simple guidance:
- simple / routine projects -> cheaper or faster model, low thinking
- medium projects -> workhorse model, medium thinking
- high-complexity architecture or synthesis projects -> stronger model, medium or high thinking

Important distinction:
- model choice controls the capability/cost tier
- thinking level controls how much effort that chosen model spends

Until this becomes a first-class runtime feature, the agent should still perform the assessment explicitly as part of capture and planning outputs.

## Canonical five-step project flow

1. Define the finished product
   - pressure-test the idea
   - simulate real use
   - rule out unrealistic or unused parts
   - produce a clear end-state description before building

2. Design the execution plan
   - work backward from the agreed end state
   - define phases, review checkpoints, and task ownership
   - make the plan visible in the project view/dashboard
   - this step is done when the project is fully laid out and ready to run

3. Execute through phases
   - carry out the work autonomously within each phase
   - stop at intentional review checkpoints
   - present a review package
   - after approval, continue automatically to the next phase

4. Ongoing support and versioned continuation
   - keep the project alive after v1
   - support fixes, questions, improvements, and major revisions
   - allow version progression such as v1.0, v1.1, v2.0

5. Curation and publishable documentation
   - maintain reusable project content for GitHub, social posts, blogs, and future handoff
   - preserve polished summaries, prompts, timelines, and supporting material
   - treat curation as a first-class project outcome, not an afterthought

## Agent-created task description rule

When creating technical tasks for the agent's own use:
- include a short layman summary at the top
- explain what it is, what it does, and why it is needed for a non-technical reader
- technical detail can follow below as needed
- every task should have an assignee
- default assignee is the agent unless the task can only be done by Greg
- Greg-assigned tasks should be easy to filter in the dashboard

## Execution permission model

The agent should not self-run project work just because a project exists.
Recommended execution modes:
- `off` = only work when directly instructed in the moment
- `guided` = work through clearly defined queued tasks and pause on ambiguity/risk
- `autonomous session` = user explicitly authorizes the agent to work through the task list for a defined session/window

Required before autonomous execution:
- capture is complete enough
- goals are clear enough
- constraints are known enough
- the user has explicitly enabled execution mode

## Step 2 planning behavior

Step 2 should be mostly agent-driven once Step 1 capture is approved, but still visibly supervised.

Rules for Step 2:
- the agent should do most of the planning work directly
- the agent should ask Greg questions when source of truth, intent, or tradeoffs are unclear
- the agent should present the initial planning package clearly, especially early while the workflow is still being developed
- the agent should recommend how many execution phases there should be
- the agent should recommend where Greg should review and approve
- the project must not move past Step 2 until Greg is satisfied with how Step 2 was done
- after Step 2 is proven, update the skill with the Stage 2 workflow that actually worked best

A good Step 2 output should include:
- recommended phase count
- phase purposes
- review checkpoints
- where Greg must step in
- what the agent can carry autonomously
- any remaining open questions before execution
- what GitHub handoff package should be prepared during Stage 2

## Human-facing lifecycle naming
Recommended lifecycle model:

### Master project stages
- **Hopper** = intake area for early raw project ideas
- **Capture** = raw material collection and light organization
- **Evaluation** = move-forward vs shelf decision
- **Design** = clearer final picture and what good looks like
- **Planning** = phases, tasks, checkpoints, and execution order
- **Build** = work through the plan to completion
- **Support** = ongoing support, cleanup, curation, and future-growth support
- **Parked** = intentionally not moving right now, but still worth keeping
- **Archived** = historical record

Notes:
- GitHub, packaging, publishing, and documentation are cross-cutting workflows, not master lifecycle stages
- Hopper remains the intake container for project-like work
- Design and Planning are distinct stages
- Build should begin after Planning is clear enough to execute

## GitHub repo management rule
For projects meant to be public, professional, or publishable:
- Build Manager should prepare GitHub-ready content as a cross-cutting workflow during Design, Planning, Build, or Support when useful
- the draft content should live in the project's `curation/` area as a reusable reservoir
- `curation/github/` is draft/source material only
- the real tracked publish tree belongs in `repo/`
- before any commit, push, or publish step, stop and ask Greg to review the exact `repo/` working-tree contents because that folder is what will actually go up to GitHub
- treat internal planning, strategy, and curation notes as non-publishable by default unless Greg explicitly approves promoting them into `repo/`
- actual repo commits should come from the local repo working tree, then push to GitHub remote
- the live runtime is not the repo
- a lightweight public-facing GitHub Project board may be maintained as a transparency layer, but it should not replace the Build Manager database as the source of truth
- GitHub Projects should stay intentionally small, public-facing, and high-level, for example `Backlog`, `In Progress`, `Review`, and `Done`
- GitHub Wiki should not be the default documentation surface; prefer `README.md` and versioned in-repo `docs/` unless a repo later proves it needs a separate wiki-style manual space

Ownership split:
- Build Manager owns project truth and the factual statement of what is working
- Career Agent should later own public language consistency across GitHub and related professional surfaces
- GitHub utility behavior should remain platform mechanics/execution only

Minimum GitHub handoff/package set to prepare early:
- polished project positioning summary
- README seed material
- roadmap / phase summary
- current status wording
- proof points / screenshots list when available
- marketing-oriented repo messaging, not only technical notes
- optional public GitHub Project board structure when public transparency is part of the repo strategy

## Locations

Primary backend root:
- `~/.openclaw/skills-workspaces/build-manager/`

Human-facing root:
- `/mnt/d/Dropbox/Obsidian/OpenClaw/Build_Manager/`

Shared dashboard output folder:
- `/mnt/d/Dropbox/Obsidian/OpenClaw/Dashboards/Build_Manager/`

Important live files:
- `config/build_manager.json`
- `sql/001_init.sql`
- `data/build_manager.db`
- `scripts/build_manager.py`
- `scripts/render_dashboard.py`
- `ui/index.html`

Human-facing structure:
- `Hopper/` = universal intake, raw capture, brainstorming, evaluation, and shelved idea storage
- `Current_Projects/` = projects in active design, planning, build, support, or active revision
- `Operational_Projects/` = projects that reached usable v1 and are now mainly in Support
- `Archived_Projects/` = historical project material kept without deletion
- there is no human-facing `Tasks/` folder in the canonical model
- tasks live in the database and are viewed in the dashboard
- each individual project folder should contain `curation/`, `inputs/`, `attachments/`, and `sessions/`
- for the Build Manager project itself, the project folder may also contain `repo/` as the real local git working tree
- `sessions/` stores continuity records and summary-first session preservation for later support work
- `curation/` should normally contain `one-pager.md`, `github.md`, `workflow-map.md`, `content-generation/`, `github/`, `prompts/`, `log/`, and `changelog.md`
- the `curation/` root should stay focused on durable defining notes, not random session scraps
- `log/` is for dated day/session change records
- `github/` is for GitHub and repo-packaging draft material that is not yet in the publish tree
- `content-generation/` is a raw but organized content bank for future posts, articles, hooks, headlines, repo-adjacent messaging ideas, and marketing angles
- markdown is for curation and preserved context, database is the source of truth, dashboard is the main human operational view
- a legacy runtime-side `~/.openclaw/skills-workspaces/build-manager/projects/` tree may still exist as a temporary mirror/work area, but it is non-canonical and should not be treated as the human-facing project corpus or tracked publish source
- when moving a project between lifecycle buckets, change DB stage/status first and then move the full project folder intact rather than reconstructing it from DB alone

## Read-only dashboard

The live system includes human-facing markdown/context material plus a read-only HTML dashboard.

Current dashboard intent:
- provide a simple human-readable Build Manager snapshot
- keep all dashboards in the shared dashboards folder
- show projects separately from standalone tasks
- avoid duplicating project-linked tasks in the standalone task section
- show assignee-filterable tasks from the database
- support read-only interactive navigation with light JavaScript when useful
- act as the primary human operational interface while chat remains the control surface

Current shared dashboard location:
- `/mnt/d/Dropbox/Obsidian/OpenClaw/Dashboards/Build_Manager/index.html`

Current dashboard structure is still being finalized inside the Build Manager project scoping/design work.

Working direction:
- dashboard is the primary human operational view
- projects and tasks should be read from the database
- project-linked tasks should not be duplicated as human-facing folder mirrors
- assignee-filterable task views should be supported
- early phases should prefer a read-only visual HTML dashboard over a markdown dashboard
- multi-page generated HTML is allowed when it improves clarity, but a local server is optional rather than required

Local fallback copy:
- `~/.openclaw/skills-workspaces/build-manager/ui/index.html`

Menu support:
- `Refresh Dashboard` should refresh the current human-facing dashboard implementation
- for now this may still mean a markdown dashboard or the current HTML dashboard path, depending on the runtime stage
- later phases should allow the visual HTML dashboard to become the primary refreshed output
- early dashboard work should make standalone tasks visible as first-class non-project work
- a dedicated task-intake surface should allow simple task-first capture without forcing the project workflow

Rules:
- SQLite remains the source of truth
- markdown is the human-facing mirror
- browser edits are out of scope
- all mutations remain through chat, agent actions, or runtime commands
- for public Build Manager dashboard publishing, prefer the clean HTTPS path-based route (currently `/build-manager`) over raw-port URLs
- when generating or regenerating the HTML dashboard, preserve installable web-app basics when Android app-style save/install behavior matters: linked manifest, required icon sizes, theme/app metadata, and base-path-safe internal navigation

## Currently supported deterministic commands

Verified live command surface from `scripts/build_manager.py`:
- `create-project`
- `list-projects`
- `create-task`
- `create-subtask`
- `list-tasks --status <status>`
- `show-current`
- `show-paused`
- `show-waiting`
- `mark-task-status --task-id <id> --status <status>`
- `start-work-session`
- `stop-work-session`
- `add-note`
- `nl "<request>"`

Also available as convenience aliases:
- `list-active-tasks`
- `list-queued-tasks`
- `mark-task-active`
- `mark-task-done`

Important runtime note:
- the live deterministic backend now distinguishes standalone task statuses from project-task statuses
- standalone tasks still use the operational status model
- project-owned tasks now use the simplified execution model: `planned`, `active`, `waiting`, `done`
- project lifecycle stages remain separate from both task models

Valid task statuses in the current live backend:
- standalone task statuses: `captured`, `queued`, `active`, `paused`, `parked`, `done`, `archived`
- project-task statuses: `planned`, `active`, `waiting`, `done`

Valid project statuses for `list-projects --status` in the current live backend:
- `hopper`
- `capture`
- `evaluation`
- `design`
- `planning`
- `build`
- `support`
- `parked`
- `archived`

## Thin NL adapter: supported intents

Supported intent families in the first NL layer:
- create project
- create task
- create subtask
- list projects
- list tasks by status
- show current
- show paused
- show waiting
- mark task active
- mark task done
- add note to task
- start work session for task
- stop current work session

Examples that match the current thin parser:
- `create a project called Email Triage Skill`
- `add a task called confirm browser control`
- `add a task called confirm browser control to project 3`
- `add a subtask called test gmail flow to task 6`
- `show projects`
- `show queued tasks`
- `show current`
- `show paused`
- `show waiting`
- `mark task 6 active`
- `mark task 6 done`
- `add a note to task 6 saying browser control is blocked`
- `start a work session for task 6`
- `stop the current work session`

## Thin NL adapter: known limits

The first NL layer is intentionally narrow.

Current limits:
- no recommendation logic
- no dependency reasoning
- no tag/category management
- no GUI behavior
- no project-by-title resolution for task creation
- task references support only:
  - numeric task id
  - exact task title when unique
  - partial task title when unambiguous
  - `current` / `active` task when exactly one active task exists
- if a task reference is ambiguous, the adapter returns one short clarification message
- NL parsing is pattern-based, not a general language model planner

## Usage examples

Base deterministic command:
- `python3 ~/.openclaw/skills-workspaces/build-manager/scripts/build_manager.py <command> ...`

Natural-language adapter command:
- `python3 ~/.openclaw/skills-workspaces/build-manager/scripts/build_manager.py nl "<request>"`

Deterministic examples:
- Create a project:
  - `python3 ~/.openclaw/skills-workspaces/build-manager/scripts/build_manager.py create-project --slug build-manager-backend --title "Build Manager Backend"`
- List all projects:
  - `python3 ~/.openclaw/skills-workspaces/build-manager/scripts/build_manager.py list-projects`
- Create a task:
  - `python3 ~/.openclaw/skills-workspaces/build-manager/scripts/build_manager.py create-task --project-id 1 --title "Implement task listing"`
- Create a subtask:
  - `python3 ~/.openclaw/skills-workspaces/build-manager/scripts/build_manager.py create-subtask --project-id 1 --parent-task-id 2 --title "Add status filter"`
- Show current active tasks:
  - `python3 ~/.openclaw/skills-workspaces/build-manager/scripts/build_manager.py show-current`
- Show paused tasks:
  - `python3 ~/.openclaw/skills-workspaces/build-manager/scripts/build_manager.py show-paused`
- Mark a task active:
  - `python3 ~/.openclaw/skills-workspaces/build-manager/scripts/build_manager.py mark-task-status --task-id 2 --status active`
- Start a work session:
  - `python3 ~/.openclaw/skills-workspaces/build-manager/scripts/build_manager.py start-work-session --task-id 2`
- Stop a work session:
  - `python3 ~/.openclaw/skills-workspaces/build-manager/scripts/build_manager.py stop-work-session --task-id 2`
- Add a note to a task:
  - `python3 ~/.openclaw/skills-workspaces/build-manager/scripts/build_manager.py add-note --entity-type task --entity-id 2 --content "Needs schema review"`

Natural-language examples:
- `python3 ~/.openclaw/skills-workspaces/build-manager/scripts/build_manager.py nl "show projects"`
- `python3 ~/.openclaw/skills-workspaces/build-manager/scripts/build_manager.py nl "show queued tasks"`
- `python3 ~/.openclaw/skills-workspaces/build-manager/scripts/build_manager.py nl "mark task 6 active"`
- `python3 ~/.openclaw/skills-workspaces/build-manager/scripts/build_manager.py nl "add a note to task 6 saying browser control is blocked"`

## Verified backend behavior

- Uses SQLite directly via Python `sqlite3`
- Resolves DB path from `config/build_manager.json`
- Uses the live database at `~/.openclaw/skills-workspaces/build-manager/data/build_manager.db`
- Logs meaningful changes to `activity_log`
- Live schema is initialized from `sql/001_init.sql`
- `list-projects` is a deterministic read-only view over `projects`
- `show-current` is a deterministic read-only view of tasks with status `active`
- `show-paused` is a deterministic read-only view of tasks with status `paused`
- `show-waiting` is a deterministic read-only view of tasks with status `waiting`
- the thin NL adapter reuses the deterministic runtime functions rather than bypassing them

Observed activity log events in validation runs:
- `project_created`
- `task_created`
- `subtask_created`
- `task_marked_active`
- `task_marked_done`
- `work_session_started`
- `work_session_stopped`
- `note_added`

Also supported through deterministic status update path:
- `task_status_updated`

## Planned but not yet implemented

These may exist as design intent, but should not be treated as currently live unless separately verified in the runtime:
- what-should-I-work-on-next recommendation logic
- dependency management commands
- category management commands
- tag management commands
- next-action update commands
- resume-prompt update commands
- automatic session-summary generation and storage
- richer exports/views generation
- visual UI-backed runtime behavior
- Obsidian link/reference workflows
- broader conversational planning beyond the thin supported NL patterns

## Current maturity note

The five-step project model and folder structure are far enough along that this skill should already be usable for starting capture on unrelated projects in parallel.

What is still evolving inside the Build Manager project itself:
- the final dashboard design
- the exact dashboard-to-project navigation model
- the exact automation level for session capture and curation updates

## Future structure direction

There is a strong case for treating the five-step workflow as staged subskills or stage-specific agent behaviors rather than one large undifferentiated skill.

Likely future direction:
- keep one top-level Build Manager orchestrator
- implement distinct internal workflows for capture, design, planning, content generation, GitHub content generation, and publishing
- split into separate exposed skills only after those workflows are stable enough to deserve their own boundaries

In that model, each workflow should produce a clear structured output for the next workflow instead of relying on loosely remembered conversation state.

Do not force the split prematurely while the Build Manager project itself is still being defined.
Lock the workflow behavior first, then document and split only where the payoff is real.

## Operating rules

- Use the database as the source of truth
- Prefer minimal, direct operations
- Do not claim support for features that are not verified in the live runtime
- Keep Build Manager naming consistent with OpenClaw development scope while preserving legacy compatibility where needed
- NL interpretation should stay thin and explicit; backend execution remains deterministic
