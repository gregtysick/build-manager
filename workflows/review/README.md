# Review Workflow

## Role
Turn a captured project into a coherent rough-draft review package that is ready to move into design if approved.

## Current minimal behavior
- list review-ready captured projects
- build a review package from the latest capture package
- store that review package in the database
- write a matching Obsidian review note
- move the project from `capture` into the current backend stage `evaluation`

## Why the backend still says evaluation
The human-facing workflow name is now Review.
This first runtime pass keeps the existing backend project-stage name `evaluation` to avoid broad schema churn while the workflow behavior is being proven.
