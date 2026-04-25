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


def build_review_package(project: sqlite3.Row, capture_note: sqlite3.Row | None) -> dict:
    capture_content = capture_note['content'] if capture_note else ''
    raw_request = extract_markdown_section(capture_content, 'Raw request / source wording') or (project['default_context'] or '').strip()
    summary = extract_markdown_section(capture_content, 'Plain-language summary') or (project['description'] or '').strip()
    problem = extract_markdown_section(capture_content, 'What problem this seems to solve')
    outcome = extract_markdown_section(capture_content, 'Desired outcome') or (project['goal'] or '').strip()
    if not outcome or outcome == 'Initial capture stored for later clarification.':
        outcome = 'Clarify the project enough to decide whether it should move into design.'
    scope = extract_markdown_section(capture_content, 'Likely scope for v1')
    not_in_scope = extract_markdown_section(capture_content, 'Not in scope yet')
    constraints = extract_markdown_section(capture_content, 'Constraints / guardrails')
    open_questions = extract_markdown_section(capture_content, 'Open questions')
    recommendation = clean_bullets(extract_markdown_section(capture_content, 'Recommendation'))
    if not recommendation or recommendation.lower() in {'move to capture', 'keep in hopper'}:
        recommendation = 'Move forward into design when the rough draft feels coherent enough.'
    next_stage = 'Design'
    return {
        'working_title': project['title'],
        'raw_request': raw_request or 'No raw request recorded.',
        'review_summary': summary or project['title'],
        'problem': problem or 'Needs explicit review clarification.',
        'outcome': outcome or 'Needs explicit review clarification.',
        'scope_v1': scope or 'Define the rough v1 clearly enough to decide whether design should begin.',
        'not_in_scope_yet': not_in_scope or 'Detailed design, formal planning, and build execution.',
        'constraints': constraints or 'Keep this as a rough but coherent draft, not a polished design.',
        'open_questions': open_questions or 'What must be clarified before design begins?',
        'recommendation': recommendation,
        'approval_object': {
            'what_greg_is_approving': 'That this rough draft is coherent enough to move forward from review into design.',
            'next_stage_if_approved': next_stage,
        },
    }


def render_review_markdown(package: dict, entity_id: int, created_at: str) -> str:
    approval = package['approval_object']
    return f"""---
created: {created_at}
updated: {created_at}
parent: \"[[Hopper]]\"
workflow: review
entity_type: project
entity_id: {entity_id}
status: reviewed
---
# Review Package

## Working title
{package['working_title']}

## Raw request / source wording
{package['raw_request']}

## Review summary
{package['review_summary']}

## Problem worth solving
{package['problem']}

## Desired outcome
{package['outcome']}

## Coherent rough-draft scope for v1
{package['scope_v1']}

## Not in scope yet
{package['not_in_scope_yet']}

## Constraints / guardrails
{package['constraints']}

## Open questions to settle before design
{package['open_questions']}

## Recommendation
{package['recommendation']}

## Approval object
- what Greg is approving: {approval['what_greg_is_approving']}
- next stage if approved: {approval['next_stage_if_approved']}
"""


def write_obsidian_review(package: dict, entity_id: int, created_at: str) -> Path:
    OBSIDIAN_HOPPER.mkdir(parents=True, exist_ok=True)
    stamp = created_at.replace(':', '').replace('-', '')[:15]
    filename = f"{stamp}-{slugify(package['working_title'])}-review.md"
    note_path = OBSIDIAN_HOPPER / filename
    note_path.write_text(render_review_markdown(package, entity_id, created_at))
    return note_path


def list_review_queue(args):
    limit = int(getattr(args, 'limit', 20) or 20)
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            '''
            SELECT id, slug, title, status, updated_at
            FROM projects
            WHERE status = 'capture'
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            ''',
            (limit,),
        ).fetchall()
        result = {
            'ok': True,
            'workflow': 'review',
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


def run_review(args):
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
        if project['status'] != 'capture':
            raise SystemExit(f'project {project_id} is not in capture status')

        capture_note = conn.execute(
            '''
            SELECT id, content
            FROM notes
            WHERE entity_type = 'project' AND entity_id = ? AND note_type = 'capture_package'
            ORDER BY id DESC
            LIMIT 1
            ''',
            (project_id,),
        ).fetchone()

        package = build_review_package(project, capture_note)
        ts = now_iso()
        review_markdown = render_review_markdown(package, project_id, ts)
        note_path = write_obsidian_review(package, project_id, ts)
        cur = conn.execute(
            '''
            INSERT INTO notes (entity_type, entity_id, note_type, title, content, created_at, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            ('project', project_id, 'review_package', 'Review Package', review_markdown, ts, created_by),
        )
        review_note_id = cur.lastrowid
        conn.execute(
            '''
            UPDATE projects
            SET description = ?,
                goal = ?,
                status = ?,
                updated_at = ?
            WHERE id = ?
            ''',
            (package['review_summary'], package['outcome'], 'evaluation', ts, project_id),
        )
        log_activity(conn, 'project', project_id, 'project_reviewed', {
            'from_status': 'capture',
            'to_status': 'evaluation',
            'title': project['title'],
            'review_note_id': review_note_id,
        }, created_by)
        conn.commit()
        result = {
            'ok': True,
            'workflow': 'review',
            'project_id': project_id,
            'from_status': 'capture',
            'to_status': 'evaluation',
            'review_note_id': review_note_id,
            'obsidian_note_path': str(note_path),
            'title': package['working_title'],
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return result
    finally:
        conn.close()
