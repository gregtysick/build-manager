# Build Manager Runtime

This folder is the backend and runtime home of Build Manager.

## Purpose

`~/.openclaw/skills-workspaces/build-manager/` is the correct place for the live Build Manager runtime state.
It is intended to hold:
- SQLite database files
- runtime configuration
- SQL initialization and migrations
- generated exports and views
- local fallback UI assets
- helper scripts and implementation notes

## Four-layer architecture
The active Build Manager architecture should be understood as four separate layers:

1. **Obsidian curation**
   - drafts, project notes, prompts, packaging notes, and preserved human-readable context
2. **live OpenClaw install**
   - installed skill package plus this live runtime workspace, database, and generated local assets
3. **local git repo working tree**
   - the actual tracked publish tree for the Build Manager project, intended to live at `/mnt/d/Dropbox/Obsidian/OpenClaw/Build_Manager/Current_Projects/11-build-manager/repo/`
4. **GitHub remote**
   - hosted copy of the local repo working tree

## Canonical runtime path

The canonical runtime folder is `~/.openclaw/skills-workspaces/build-manager/`.
Use that path in docs, commands, and active runtime references going forward.

## Why this is separate from the skill folder and repo
The skill folder, runtime folder, and repo working tree serve different roles:

- `~/.openclaw/skills/build-manager/` = the installed skill package and instructions
- `~/.openclaw/skills-workspaces/build-manager/` = the live backend, database, scripts, config, and runtime assets
- `/mnt/d/Dropbox/Obsidian/OpenClaw/Build_Manager/Current_Projects/11-build-manager/repo/` = the tracked publish tree for the Build Manager project

This separation is intentional and cleaner than storing live databases and mutable runtime state inside the skill folder or inside the tracked repo.

Rules:
- curation is a draft and preserved-context layer
- repo is the tracked publish tree
- live runtime is not the repo
- GitHub remote is downstream of the local repo working tree

## Relationship to the human-facing Obsidian folder
The human-facing project material lives separately in Obsidian:
- `/mnt/d/Dropbox/Obsidian/OpenClaw/Build_Manager/`

That area is for:
- Hopper and project notes
- curation
- inputs
- attachments
- session rollups
- human-readable preserved context
- the Build Manager project's local repo working tree under `Current_Projects/11-build-manager/repo/`

The database remains the source of truth.
The dashboard is the main human operational view.
The canonical shared HTML dashboard location is `/mnt/d/Dropbox/Obsidian/OpenClaw/Dashboards/Build_Manager/`.
The Obsidian folder is the human-facing markdown/context layer.

## Structure

- `config/` = runtime and behavior configuration
- `sql/` = initialization and migration SQL
- `data/` = live database files
- `exports/` = generated exports and summary views
- `ui/` = local fallback UI assets
- `scripts/` = helper scripts and runtime commands

## Runtime-side `projects/` mirror note
This runtime workspace currently still contains a `projects/` subtree.
Treat that subtree as a temporary runtime mirror and compatibility holdover, not as a canonical project home.

It is explicitly:
- non-canonical
- not the source of truth
- not the human-facing project corpus
- not the tracked publish tree

Canonical truth currently lives in three different places depending on need:
- database = operational state, task/project status, and live runtime truth
- Obsidian project folders = human-facing project context and preserved working material
- `repo/` working tree = tracked publish source for Build Manager packaging and GitHub

Until a deliberate retirement pass is completed, do not treat `projects/` here as the authoritative place to edit or interpret project state.
