#!/usr/bin/env python3
import json
import re
import sqlite3
from pathlib import Path

from workflows.capture.runtime import db_path, log_activity, now_iso, slugify

OBSIDIAN_HOPPER = Path('/mnt/d/Dropbox/Obsidian/OpenClaw/Build_Manager/Hopper')


def extract_markdown_section(markdown: str, heading: str) -> str:
    pattern = rf'^## {re.escape(heading)}\n(.*?)(?=^## |\Z)'
    m = re.search(pattern, markdown, re.M | re.S)
    if not m:
        return ''
    return m.group(1).strip()


def clean_bullets(text: str) -> str:
    value = text.strip()
    if value.startswith('- '):
        return value[2:].strip()
    return value


def build_design_package(project: sqlite3.Row, review_note: sqlite3.Row | None) -> dict:
    review_content = review_note['content'] if review_note else ''
    review_summary = extract_markdown_section(review_content, 'Review summary') or (project['description'] or '').strip()
    problem = extract_markdown_section(review_content, 'Problem worth solving')
    outcome = extract_markdown_section(review_content, 'Desired outcome') or (project['goal'] or '').strip()
    scope_v1 = extract_markdown_section(review_content, 'Coherent rough-draft scope for v1')
    not_in_scope = extract_markdown_section(review_content, 'Not in scope yet')
    constraints = extract_markdown_section(review_content, 'Constraints / guardrails')
    open_questions = extract_markdown_section(review_content, 'Open questions to settle before design')

    title = project['title']
    design_goal = outcome or f'Define what good looks like for {title} before planning begins.'
    finished_product = f"A clearer defined v1 for {title}, with enough shape that planning can break it into concrete phases and tasks."
    operator_experience = 'Greg should be able to understand what the project is, what it is not, and what a successful v1 would feel like.'
    core_capabilities = scope_v1 or 'A clearly bounded v1 with explicit problem, outcome, and rough shape.'
    later_phase_ideas = not_in_scope or 'Planning detail, execution tasks, broader workflow expansion, and later enhancements.'
    architecture_layers = 'Obsidian curation, live OpenClaw runtime/database, and later repo/publish layers where relevant.'
    boundary_decisions = constraints or 'Keep Design focused on shape and boundaries, not execution breakdown.'
    workflow_decisions = 'Review should feed Design; Design should produce the clearer package that Planning can later turn into tasks.'
    risks = problem or 'The project may still contain unresolved ambiguity from the capture/review stages.'
    tradeoffs = 'Favor clarity and boundaries over premature implementation detail.'
    success_criteria = f'{title} has a coherent v1 shape, explicit boundaries, and a clear enough end state to begin Planning.'
    greg_review = open_questions or 'Confirm the shape, boundaries, and intended v1 before Planning starts.'

    return {
        'project_title': title,
        'design_goal': design_goal,
        'finished_product_description': finished_product,
        'user_operator_experience': operator_experience,
        'core_capabilities_v1': core_capabilities,
        'later_phase_ideas': later_phase_ideas,
        'architecture_layers_involved': architecture_layers,
        'boundary_decisions': boundary_decisions,
        'workflow_decisions': workflow_decisions,
        'risks': risks,
        'tradeoffs': tradeoffs,
        'success_criteria': success_criteria,
        'greg_review': greg_review,
        'source_review_summary': review_summary or title,
        'approval_object': {
            'what_greg_is_approving': 'That the project shape and boundaries are defined well enough to move into Planning.',
            'next_stage_if_approved': 'Planning',
        },
    }


def render_design_markdown(package: dict, entity_id: int, created_at: str) -> str:
    approval = package['approval_object']
    return f"""---
created: {created_at}
updated: {created_at}
parent: \"[[Hopper]]\"
workflow: design
entity_type: project
entity_id: {entity_id}
status: designed
---
# Design Package

## Project title
{package['project_title']}

## Design goal
{package['design_goal']}

## Finished-product description
{package['finished_product_description']}

## User/operator experience
{package['user_operator_experience']}

## Core capabilities for v1
{package['core_capabilities_v1']}

## Later-phase ideas
{package['later_phase_ideas']}

## Architecture layers involved
{package['architecture_layers_involved']}

## Boundary decisions
{package['boundary_decisions']}

## Workflow decisions
{package['workflow_decisions']}

## Risks / likely break points
{package['risks']}

## Tradeoffs accepted
{package['tradeoffs']}

## Success criteria
{package['success_criteria']}

## What still needs Greg review
{package['greg_review']}

## Approval object
- what Greg is approving: {approval['what_greg_is_approving']}
- next stage if approved: {approval['next_stage_if_approved']}
"""


def write_obsidian_design(package: dict, entity_id: int, created_at: str) -> Path:
    OBSIDIAN_HOPPER.mkdir(parents=True, exist_ok=True)
    stamp = created_at.replace(':', '').replace('-', '')[:15]
    filename = f"{stamp}-{slugify(package['project_title'])}-design.md"
    note_path = OBSIDIAN_HOPPER / filename
    note_path.write_text(render_design_markdown(package, entity_id, created_at))
    return note_path


def list_design_queue(args):
    limit = int(getattr(args, 'limit', 20) or 20)
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            '''
            SELECT id, slug, title, status, updated_at
            FROM projects
            WHERE status = 'evaluation'
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            ''',
            (limit,),
        ).fetchall()
        result = {
            'ok': True,
            'workflow': 'design',
            'queue': [
                {
                    'id': row['id'],
                    'slug': row['slug'],
                    'title': row['title'],
                    'status': row['status'],
                    'updated_at': row['updated_at'],
                }
                for row in rows
            ],
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return result
    finally:
        conn.close()


def run_design(args):
    project_id = getattr(args, 'project_id', None)
    if project_id is None:
        raise SystemExit('project_id is required')
    created_by = getattr(args, 'created_by', None) or 'system_engineer'

    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        project = conn.execute(
            '''
            SELECT id, slug, title, description, status, goal, default_context, created_at, updated_at
            FROM projects
            WHERE id = ?
            ''',
            (project_id,),
        ).fetchone()
        if not project:
            raise SystemExit(f'project not found: {project_id}')
        if project['status'] != 'evaluation':
            raise SystemExit(f'project {project_id} is not in evaluation status')

        review_note = conn.execute(
            '''
            SELECT id, content
            FROM notes
            WHERE entity_type = 'project' AND entity_id = ? AND note_type = 'review_package'
            ORDER BY id DESC
            LIMIT 1
            ''',
            (project_id,),
        ).fetchone()

        package = build_design_package(project, review_note)
        ts = now_iso()
        design_markdown = render_design_markdown(package, project_id, ts)
        note_path = write_obsidian_design(package, project_id, ts)
        cur = conn.execute(
            '''
            INSERT INTO notes (entity_type, entity_id, note_type, title, content, created_at, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            ('project', project_id, 'design_package', 'Design Package', design_markdown, ts, created_by),
        )
        design_note_id = cur.lastrowid
        conn.execute(
            '''
            UPDATE projects
            SET description = ?,
                goal = ?,
                status = ?,
                updated_at = ?
            WHERE id = ?
            ''',
            (package['finished_product_description'], package['design_goal'], 'design', ts, project_id),
        )
        log_activity(conn, 'project', project_id, 'project_designed', {
            'from_status': 'evaluation',
            'to_status': 'design',
            'title': project['title'],
            'design_note_id': design_note_id,
        }, created_by)
        conn.commit()
        result = {
            'ok': True,
            'workflow': 'design',
            'project_id': project_id,
            'from_status': 'evaluation',
            'to_status': 'design',
            'design_note_id': design_note_id,
            'obsidian_note_path': str(note_path),
            'title': package['project_title'],
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return result
    finally:
        conn.close()
