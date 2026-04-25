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


def build_planning_package(project: sqlite3.Row, design_note: sqlite3.Row | None) -> dict:
    design_content = design_note['content'] if design_note else ''
    title = project['title']
    design_goal = extract_markdown_section(design_content, 'Design goal') or (project['goal'] or '').strip()
    finished_product = extract_markdown_section(design_content, 'Finished-product description') or (project['description'] or '').strip()
    core_capabilities = extract_markdown_section(design_content, 'Core capabilities for v1')
    later_phase_ideas = extract_markdown_section(design_content, 'Later-phase ideas')
    risks = extract_markdown_section(design_content, 'Risks / likely break points')
    greg_review = extract_markdown_section(design_content, 'What still needs Greg review')

    planning_goal = f'Turn the current design for {title} into an execution-ready plan.'
    execution_strategy = f'Start with a narrow foundation slice for {title}, then add the next operational slice once the first one is verified.'
    phase_1 = {
        'purpose': 'Establish the smallest verified implementation slice that proves the design is real.',
        'main_tasks': [
            f'Confirm the minimal v1 boundary for {title}.',
            'Implement the first concrete working slice.',
            'Verify the result end to end before expanding scope.',
        ],
        'checkpoint': 'Greg can see the first working slice and agrees the project direction is correct.',
    }
    phase_2 = {
        'purpose': 'Extend the verified foundation into the next cohesive capability group.',
        'main_tasks': [
            'Add the next set of supporting workflow or runtime pieces.',
            'Refine the stored notes/packages so handoff quality stays high.',
            'Verify that the expanded slice still matches the design boundaries.',
        ],
        'checkpoint': 'The project has enough structure to continue with deliberate task-by-task execution.',
    }
    task_breakdown = [
        {
            'task_key': 'slice_definition',
            'task_title': f'Define the first implementation slice for {title}',
            'owner': 'system_engineer',
            'dependency': 'Approved Design Package',
            'depends_on_task_key': '',
            'expected_status_model': 'planned -> active -> done',
        },
        {
            'task_key': 'slice_implementation',
            'task_title': 'Implement and verify the first slice',
            'owner': 'system_engineer',
            'dependency': 'Defined first implementation slice',
            'depends_on_task_key': 'slice_definition',
            'expected_status_model': 'planned -> active -> done',
        },
        {
            'task_key': 'greg_review_next_expansion',
            'task_title': 'Review the first verified slice and confirm the next expansion point',
            'owner': 'Greg',
            'dependency': 'First slice verification',
            'depends_on_task_key': 'slice_implementation',
            'expected_status_model': 'planned -> waiting -> done',
        },
    ]
    review_checkpoints = [
        'Checkpoint 1: confirm the first slice before broader buildout.',
        'Checkpoint 2: confirm the next expansion point after the first slice is working.',
    ]
    agent_run = [
        'Package generation and note writing.',
        'Implementation of the first verified slice.',
        'Routine verification and state updates.',
    ]
    greg_review_items = [
        greg_review or 'Confirm the planned first slice and whether the project is still aimed at the right v1.',
        'Approve the next expansion point after the first slice is validated.',
    ]
    risks_during_execution = risks or 'The design may still contain ambiguity that should be caught early through checkpoint reviews.'
    immediate_next_actions = [
        f'Approve this planning package for {title}.',
        'Start the first implementation slice.',
        'Keep execution narrow until the first slice is proven.',
    ]

    return {
        'project_title': title,
        'planning_goal': planning_goal,
        'execution_strategy': execution_strategy,
        'phase_1': phase_1,
        'phase_2': phase_2,
        'task_breakdown': task_breakdown,
        'review_checkpoints': review_checkpoints,
        'agent_run': agent_run,
        'greg_review_items': greg_review_items,
        'risks_during_execution': risks_during_execution,
        'recommended_immediate_next_actions': immediate_next_actions,
        'source_design_goal': design_goal,
        'source_finished_product': finished_product,
        'source_core_capabilities': core_capabilities,
        'source_later_phase_ideas': later_phase_ideas,
        'approval_object': {
            'what_greg_is_approving': 'That this execution strategy and initial task breakdown are the right way to start the project build.',
            'next_stage_if_approved': 'Build',
        },
    }


def render_task_breakdown(items: list[dict]) -> str:
    lines = []
    for item in items:
        lines.append(f"- task key: {item['task_key']}")
        lines.append(f"  task title: {item['task_title']}")
        lines.append(f"  owner: {item['owner']}")
        lines.append(f"  dependency: {item['dependency']}")
        if item.get('depends_on_task_key'):
            lines.append(f"  depends on task key: {item['depends_on_task_key']}")
        lines.append(f"  expected status model: {item['expected_status_model']}")
    return '\n'.join(lines)


def render_bullets(items: list[str]) -> str:
    return '\n'.join(f'- {item}' for item in items)


def render_planning_markdown(package: dict, entity_id: int, created_at: str) -> str:
    approval = package['approval_object']
    p1 = package['phase_1']
    p2 = package['phase_2']
    return f"""---
created: {created_at}
updated: {created_at}
parent: \"[[Hopper]]\"
workflow: planning
entity_type: project
entity_id: {entity_id}
status: planned
---
# Planning Package

## Project title
{package['project_title']}

## Planning goal
{package['planning_goal']}

## Execution strategy
{package['execution_strategy']}

## Phase list
### Phase 1
- purpose: {p1['purpose']}
- main tasks:
{render_bullets(p1['main_tasks'])}
- checkpoint: {p1['checkpoint']}

### Phase 2
- purpose: {p2['purpose']}
- main tasks:
{render_bullets(p2['main_tasks'])}
- checkpoint: {p2['checkpoint']}

## Task breakdown
{render_task_breakdown(package['task_breakdown'])}

## Review checkpoints
{render_bullets(package['review_checkpoints'])}

## What can be agent-run
{render_bullets(package['agent_run'])}

## What requires Greg review
{render_bullets(package['greg_review_items'])}

## Risks during execution
{package['risks_during_execution']}

## Recommended immediate next actions
{render_bullets(package['recommended_immediate_next_actions'])}

## Approval object
- what Greg is approving: {approval['what_greg_is_approving']}
- next stage if approved: {approval['next_stage_if_approved']}
"""


def write_obsidian_planning(package: dict, entity_id: int, created_at: str) -> Path:
    OBSIDIAN_HOPPER.mkdir(parents=True, exist_ok=True)
    stamp = created_at.replace(':', '').replace('-', '')[:15]
    filename = f"{stamp}-{slugify(package['project_title'])}-planning.md"
    note_path = OBSIDIAN_HOPPER / filename
    note_path.write_text(render_planning_markdown(package, entity_id, created_at))
    return note_path


def list_planning_queue(args):
    limit = int(getattr(args, 'limit', 20) or 20)
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            '''
            SELECT id, slug, title, status, updated_at
            FROM projects
            WHERE status = 'design'
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            ''',
            (limit,),
        ).fetchall()
        result = {
            'ok': True,
            'workflow': 'planning',
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


def run_planning(args):
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
        if project['status'] != 'design':
            raise SystemExit(f'project {project_id} is not in design status')

        existing_task = conn.execute(
            'SELECT id, title, status FROM tasks WHERE project_id = ? ORDER BY id ASC LIMIT 1',
            (project_id,),
        ).fetchone()
        if existing_task:
            raise SystemExit(
                f'project {project_id} already has project tasks ({existing_task["id"]}: {existing_task["title"]}); refusing to create a planning package that would drift from live execution state'
            )

        design_note = conn.execute(
            '''
            SELECT id, content
            FROM notes
            WHERE entity_type = 'project' AND entity_id = ? AND note_type = 'design_package'
            ORDER BY id DESC
            LIMIT 1
            ''',
            (project_id,),
        ).fetchone()

        package = build_planning_package(project, design_note)
        ts = now_iso()
        planning_markdown = render_planning_markdown(package, project_id, ts)
        note_path = write_obsidian_planning(package, project_id, ts)
        cur = conn.execute(
            '''
            INSERT INTO notes (entity_type, entity_id, note_type, title, content, created_at, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            ('project', project_id, 'planning_package', 'Planning Package', planning_markdown, ts, created_by),
        )
        planning_note_id = cur.lastrowid
        conn.execute(
            '''
            UPDATE projects
            SET description = ?,
                goal = ?,
                status = ?,
                updated_at = ?
            WHERE id = ?
            ''',
            (package['execution_strategy'], package['planning_goal'], 'planning', ts, project_id),
        )
        log_activity(conn, 'project', project_id, 'project_planned', {
            'from_status': 'design',
            'to_status': 'planning',
            'title': project['title'],
            'planning_note_id': planning_note_id,
        }, created_by)
        conn.commit()
        result = {
            'ok': True,
            'workflow': 'planning',
            'project_id': project_id,
            'from_status': 'design',
            'to_status': 'planning',
            'planning_note_id': planning_note_id,
            'obsidian_note_path': str(note_path),
            'title': package['project_title'],
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return result
    finally:
        conn.close()
