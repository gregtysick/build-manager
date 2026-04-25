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


def parse_task_breakdown(markdown: str) -> list[dict]:
    section = extract_markdown_section(markdown, 'Task breakdown')
    if not section:
        return []
    tasks = []
    current = None
    for raw_line in section.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('- task key: '):
            if current:
                tasks.append(current)
            current = {
                'task_key': stripped[len('- task key: '):].strip(),
                'task_title': '',
                'owner': 'system_engineer',
                'dependency': '',
                'depends_on_task_key': '',
                'expected_status_model': 'planned -> active -> done',
            }
            continue
        if stripped.startswith('- task title: '):
            if current and current.get('task_title'):
                tasks.append(current)
                current = {
                    'task_key': '',
                    'task_title': stripped[len('- task title: '):].strip(),
                    'owner': 'system_engineer',
                    'dependency': '',
                    'depends_on_task_key': '',
                    'expected_status_model': 'planned -> active -> done',
                }
            else:
                current = current or {
                    'task_key': '',
                    'task_title': '',
                    'owner': 'system_engineer',
                    'dependency': '',
                    'depends_on_task_key': '',
                    'expected_status_model': 'planned -> active -> done',
                }
                current['task_title'] = stripped[len('- task title: '):].strip()
            continue
        if current is None:
            continue
        if stripped.startswith('task title: '):
            current['task_title'] = stripped[len('task title: '):].strip()
        elif stripped.startswith('owner: '):
            current['owner'] = stripped[len('owner: '):].strip()
        elif stripped.startswith('dependency: '):
            current['dependency'] = stripped[len('dependency: '):].strip()
        elif stripped.startswith('depends on task key: '):
            current['depends_on_task_key'] = stripped[len('depends on task key: '):].strip()
        elif stripped.startswith('expected status model: '):
            current['expected_status_model'] = stripped[len('expected status model: '):].strip()
    if current:
        tasks.append(current)
    return [task for task in tasks if task.get('task_title')]


def render_build_kickoff_markdown(project: sqlite3.Row, created_tasks: list[dict], entity_id: int, created_at: str) -> str:
    task_lines = '\n'.join(
        f"- #{task['task_id']}: {task['title']} ({task['status']}, owner={task['owner']})"
        for task in created_tasks
    ) or '- No tasks were created.'
    return f"""---
created: {created_at}
updated: {created_at}
parent: \"[[Hopper]]\"
workflow: build
entity_type: project
entity_id: {entity_id}
status: build-started
---
# Build Kickoff

## Project title
{project['title']}

## Build kickoff summary
The planning package was converted into real project tasks and the project moved into Build.

## Created tasks
{task_lines}
"""


def write_obsidian_build(project: sqlite3.Row, created_tasks: list[dict], entity_id: int, created_at: str) -> Path:
    OBSIDIAN_HOPPER.mkdir(parents=True, exist_ok=True)
    stamp = created_at.replace(':', '').replace('-', '')[:15]
    filename = f"{stamp}-{slugify(project['title'])}-build.md"
    note_path = OBSIDIAN_HOPPER / filename
    note_path.write_text(render_build_kickoff_markdown(project, created_tasks, entity_id, created_at))
    return note_path


def list_build_queue(args):
    limit = int(getattr(args, 'limit', 20) or 20)
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            '''
            SELECT id, slug, title, status, updated_at
            FROM projects
            WHERE status = 'planning'
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            ''',
            (limit,),
        ).fetchall()
        result = {
            'ok': True,
            'workflow': 'build',
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


def dependency_ids_for_task(conn, task_id: int) -> list[int]:
    rows = conn.execute(
        'SELECT depends_on_task_id FROM dependencies WHERE task_id = ? ORDER BY depends_on_task_id ASC',
        (task_id,),
    ).fetchall()
    return [row['depends_on_task_id'] for row in rows]


def unresolved_dependency_ids(conn, task_id: int) -> list[int]:
    rows = conn.execute(
        '''
        SELECT d.depends_on_task_id
        FROM dependencies d
        JOIN tasks t ON t.id = d.depends_on_task_id
        WHERE d.task_id = ? AND t.status != 'done'
        ORDER BY d.depends_on_task_id ASC
        ''',
        (task_id,),
    ).fetchall()
    return [row['depends_on_task_id'] for row in rows]


def normalize_dependency_text(text: str) -> str:
    cleaned = re.sub(r'[^a-z0-9]+', ' ', (text or '').lower()).strip()
    tokens = []
    for raw in cleaned.split():
        token = raw
        if token.endswith('ied') and len(token) > 4:
            token = token[:-3] + 'y'
        elif token.endswith('ing') and len(token) > 5:
            token = token[:-3]
        elif token.endswith('ed') and len(token) > 4:
            token = token[:-2]
        elif token.endswith('es') and len(token) > 4:
            token = token[:-2]
        elif token.endswith('s') and len(token) > 3:
            token = token[:-1]
        tokens.append(token)
    return ' '.join(tokens)


def significant_dependency_tokens(text: str) -> list[str]:
    stop = {
        'the', 'a', 'an', 'and', 'or', 'to', 'for', 'of', 'in', 'on', 'with', 'after', 'before', 'from',
        'package', 'project', 'task', 'approved', 'approval',
    }
    return [token for token in normalize_dependency_text(text).split() if len(token) > 2 and token not in stop]


def resolve_dependency_task_id(task_specs: list[dict], created_tasks: list[dict], index: int) -> int | None:
    explicit_key = (task_specs[index].get('depends_on_task_key') or '').strip()
    if explicit_key:
        for prior_index in range(index):
            if prior_index >= len(created_tasks):
                break
            if (task_specs[prior_index].get('task_key') or '').strip() == explicit_key:
                return created_tasks[prior_index]['task_id']
    dependency_text = (task_specs[index].get('dependency') or '').strip()
    if not dependency_text:
        return None
    dependency_tokens = set(significant_dependency_tokens(dependency_text))
    if not dependency_tokens:
        return None
    best_task_id = None
    best_score = 0.0
    for prior_index in range(index):
        if prior_index >= len(created_tasks):
            break
        title_tokens = set(significant_dependency_tokens(task_specs[prior_index].get('task_title') or ''))
        if not title_tokens:
            continue
        overlap = dependency_tokens & title_tokens
        if not overlap:
            continue
        score = len(overlap) / max(len(dependency_tokens), 1)
        if score > best_score:
            best_score = score
            best_task_id = created_tasks[prior_index]['task_id']
    return best_task_id if best_score >= 0.5 else None


def release_waiting_tasks(conn, project_id: int, created_by: str, triggered_by_task_id: int | None = None) -> list[dict]:
    releasable = conn.execute(
        '''
        SELECT id, project_id, title, status, priority, needs_user_input, can_agent_execute, waiting_question, updated_at
        FROM tasks
        WHERE project_id = ?
          AND parent_task_id IS NULL
          AND status = 'planned'
          AND needs_user_input = 1
          AND NOT EXISTS (
            SELECT 1
            FROM dependencies d
            JOIN tasks dep ON dep.id = d.depends_on_task_id
            WHERE d.task_id = tasks.id AND dep.status != 'done'
          )
        ORDER BY priority ASC, id ASC
        ''',
        (project_id,),
    ).fetchall()
    released = []
    if not releasable:
        return released
    ts = now_iso()
    for row in releasable:
        conn.execute(
            '''
            UPDATE tasks
            SET status = 'waiting', updated_at = ?
            WHERE id = ?
            ''',
            (ts, row['id']),
        )
        log_activity(conn, 'task', row['id'], 'project_task_waiting_released', {
            'project_id': project_id,
            'from_status': 'planned',
            'to_status': 'waiting',
            'triggered_by_task_id': triggered_by_task_id,
        }, created_by)
        released_row = dict(row)
        released_row['status'] = 'waiting'
        released_row['updated_at'] = ts
        released.append(task_row_with_dependency_meta(conn, released_row))
    return released


def next_attention_task_row(conn, project_id: int):
    return conn.execute(
        '''
        SELECT t.id, t.project_id, t.title, t.status, t.priority, t.needs_user_input, t.can_agent_execute, t.waiting_question, t.updated_at
        FROM tasks t
        WHERE t.project_id = ?
          AND t.parent_task_id IS NULL
          AND t.status = 'waiting'
          AND NOT EXISTS (
            SELECT 1
            FROM dependencies d
            JOIN tasks dep ON dep.id = d.depends_on_task_id
            WHERE d.task_id = t.id AND dep.status != 'done'
          )
        ORDER BY t.priority ASC, t.id ASC
        LIMIT 1
        ''',
        (project_id,),
    ).fetchone()


def next_startable_task_row(conn, project_id: int):
    return conn.execute(
        '''
        SELECT t.id, t.project_id, t.title, t.status, t.priority, t.needs_user_input, t.can_agent_execute, t.waiting_question, t.updated_at
        FROM tasks t
        WHERE t.project_id = ?
          AND t.parent_task_id IS NULL
          AND t.status IN ('planned', 'waiting')
          AND t.can_agent_execute = 1
          AND t.needs_user_input = 0
          AND NOT EXISTS (
            SELECT 1
            FROM dependencies d
            JOIN tasks dep ON dep.id = d.depends_on_task_id
            WHERE d.task_id = t.id AND dep.status != 'done'
          )
        ORDER BY CASE t.status WHEN 'waiting' THEN 0 ELSE 1 END, t.priority ASC, t.id ASC
        LIMIT 1
        ''',
        (project_id,),
    ).fetchone()


def next_eligible_task_row(conn, project_id: int):
    return conn.execute(
        '''
        SELECT t.id, t.project_id, t.title, t.status, t.priority, t.needs_user_input, t.can_agent_execute, t.waiting_question, t.updated_at
        FROM tasks t
        WHERE t.project_id = ?
          AND t.parent_task_id IS NULL
          AND t.status IN ('planned', 'waiting')
          AND NOT EXISTS (
            SELECT 1
            FROM dependencies d
            JOIN tasks dep ON dep.id = d.depends_on_task_id
            WHERE d.task_id = t.id AND dep.status != 'done'
          )
        ORDER BY CASE t.status WHEN 'waiting' THEN 0 ELSE 1 END, t.priority ASC, t.id ASC
        LIMIT 1
        ''',
        (project_id,),
    ).fetchone()


def all_top_level_tasks_done(conn, project_id: int) -> bool:
    row = conn.execute(
        '''
        SELECT COUNT(*) AS remaining
        FROM tasks
        WHERE project_id = ?
          AND parent_task_id IS NULL
          AND status != 'done'
        ''',
        (project_id,),
    ).fetchone()
    return bool(row) and row['remaining'] == 0


def maybe_transition_project_to_support(conn, project_id: int, created_by: str, triggered_by_task_id: int | None = None) -> dict | None:
    project = conn.execute('SELECT id, title, status FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not project:
        return None
    if project['status'] != 'build':
        return None
    if not all_top_level_tasks_done(conn, project_id):
        return None
    ts = now_iso()
    conn.execute(
        'UPDATE projects SET status = ?, updated_at = ? WHERE id = ?',
        ('support', ts, project_id),
    )
    log_activity(conn, 'project', project_id, 'project_build_completed', {
        'from_status': 'build',
        'to_status': 'support',
        'triggered_by_task_id': triggered_by_task_id,
        'title': project['title'],
    }, created_by)
    return {
        'project_id': project_id,
        'from_status': 'build',
        'to_status': 'support',
        'updated_at': ts,
    }


def task_row_with_dependency_meta(conn, row):
    if not row:
        return None
    data = dict(row)
    dependency_ids = dependency_ids_for_task(conn, row['id'])
    blocked_by = unresolved_dependency_ids(conn, row['id'])
    data['dependency_ids'] = dependency_ids
    data['blocked_by'] = blocked_by
    data['is_blocked'] = bool(blocked_by)
    return data


def subtask_progress_for_parent(conn, parent_task_id: int) -> dict:
    rows = conn.execute(
        '''
        SELECT id, status
        FROM tasks
        WHERE parent_task_id = ?
        ORDER BY priority ASC, id ASC
        ''',
        (parent_task_id,),
    ).fetchall()
    total = len(rows)
    done = sum(1 for row in rows if row['status'] == 'done')
    active = sum(1 for row in rows if row['status'] == 'active')
    waiting = sum(1 for row in rows if row['status'] == 'waiting')
    return {
        'total': total,
        'done': done,
        'active': active,
        'waiting': waiting,
        'remaining': total - done,
        'all_done': total > 0 and done == total,
        'has_subtasks': total > 0,
    }


def unfinished_subtask_rows(conn, parent_task_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        '''
        SELECT id, title, status, priority
        FROM tasks
        WHERE parent_task_id = ?
          AND status != 'done'
        ORDER BY priority ASC, id ASC
        ''',
        (parent_task_id,),
    ).fetchall()


def subtask_blocker_ids(conn, subtask_id: int, parent_task_id: int, priority: int) -> list[int]:
    rows = conn.execute(
        '''
        SELECT id
        FROM tasks
        WHERE parent_task_id = ?
          AND id != ?
          AND priority < ?
          AND status != 'done'
        ORDER BY priority ASC, id ASC
        ''',
        (parent_task_id, subtask_id, priority),
    ).fetchall()
    return [row['id'] for row in rows]


def subtask_row_with_progress_meta(conn, row):
    if not row:
        return None
    data = dict(row)
    blocked_by = subtask_blocker_ids(conn, row['id'], row['parent_task_id'], row['priority'])
    data['blocked_by'] = blocked_by
    data['is_blocked'] = bool(blocked_by)
    return data


def active_subtask_row(conn, parent_task_id: int):
    return conn.execute(
        '''
        SELECT id, project_id, parent_task_id, title, status, priority, task_type, needs_user_input, can_agent_execute, waiting_question, updated_at
        FROM tasks
        WHERE parent_task_id = ?
          AND status = 'active'
        ORDER BY priority ASC, id ASC
        LIMIT 1
        ''',
        (parent_task_id,),
    ).fetchone()


def next_attention_subtask_row(conn, parent_task_id: int):
    rows = conn.execute(
        '''
        SELECT id, project_id, parent_task_id, title, status, priority, task_type, needs_user_input, can_agent_execute, waiting_question, updated_at
        FROM tasks
        WHERE parent_task_id = ?
          AND status = 'waiting'
        ORDER BY priority ASC, id ASC
        ''',
        (parent_task_id,),
    ).fetchall()
    for row in rows:
        if not subtask_blocker_ids(conn, row['id'], parent_task_id, row['priority']):
            return row
    return None


def next_startable_subtask_row(conn, parent_task_id: int):
    rows = conn.execute(
        '''
        SELECT id, project_id, parent_task_id, title, status, priority, task_type, needs_user_input, can_agent_execute, waiting_question, updated_at
        FROM tasks
        WHERE parent_task_id = ?
          AND status IN ('planned', 'waiting')
          AND can_agent_execute = 1
          AND needs_user_input = 0
        ORDER BY CASE status WHEN 'waiting' THEN 0 ELSE 1 END, priority ASC, id ASC
        ''',
        (parent_task_id,),
    ).fetchall()
    for row in rows:
        if not subtask_blocker_ids(conn, row['id'], parent_task_id, row['priority']):
            return row
    return None


def next_eligible_subtask_row(conn, parent_task_id: int):
    rows = conn.execute(
        '''
        SELECT id, project_id, parent_task_id, title, status, priority, task_type, needs_user_input, can_agent_execute, waiting_question, updated_at
        FROM tasks
        WHERE parent_task_id = ?
          AND status IN ('planned', 'waiting')
        ORDER BY CASE status WHEN 'waiting' THEN 0 ELSE 1 END, priority ASC, id ASC
        ''',
        (parent_task_id,),
    ).fetchall()
    for row in rows:
        if not subtask_blocker_ids(conn, row['id'], parent_task_id, row['priority']):
            return row
    return None


def subtask_templates_for_task(task_row: sqlite3.Row | dict) -> list[dict]:
    title = (task_row['title'] or '').strip()
    lowered = title.lower()
    needs_user_input = bool(task_row['needs_user_input'])
    can_agent_execute = bool(task_row['can_agent_execute'])
    if lowered.startswith('define the first implementation slice'):
        titles = [
            'Review planning inputs and current project context',
            'Define the exact v1 slice boundary',
            'Record the slice handoff and success criteria',
        ]
    elif lowered.startswith('implement and verify'):
        titles = [
            'Implement the scoped slice',
            'Verify the slice end to end',
            'Record verification results and follow-up notes',
        ]
    elif lowered.startswith('review the first verified slice'):
        titles = [
            'Review the verified slice output',
            'Decide whether the checkpoint is satisfied',
            'Confirm the next expansion point',
        ]
    elif needs_user_input and not can_agent_execute:
        titles = [
            'Review the current output or evidence',
            'Decide whether the task objective is satisfied',
            'Confirm the next action or follow-up question',
        ]
    else:
        titles = [
            'Clarify the exact task boundary',
            'Execute the main task body',
            'Record results and next-step notes',
        ]
    return [
        {
            'title': item,
            'can_agent_execute': 1 if can_agent_execute else 0,
            'needs_user_input': 1 if needs_user_input else 0,
            'autonomous_safe': 1 if can_agent_execute and not needs_user_input else 0,
        }
        for item in titles
    ]


def render_subtask_package_markdown(task_row: sqlite3.Row | dict, subtasks: list[dict], created_at: str) -> str:
    lines = '\n'.join(f"- #{item['task_id']}: {item['title']} ({item['status']})" for item in subtasks) or '- No subtasks created.'
    return f"""---
created: {created_at}
updated: {created_at}
workflow: build-subtasks
entity_type: task
entity_id: {task_row['id']}
status: subtasks-generated
---
# Subtask Package

## Parent task
{task_row['title']}

## Generated subtasks
{lines}
"""


def list_task_subtasks(args):
    task_id = getattr(args, 'task_id', None)
    if task_id is None:
        raise SystemExit('task_id is required')
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    try:
        parent = conn.execute(
            'SELECT id, project_id, title, status, needs_user_input, can_agent_execute FROM tasks WHERE id = ?',
            (task_id,),
        ).fetchone()
        if not parent:
            raise SystemExit(f'task not found: {task_id}')
        rows = conn.execute(
            '''
            SELECT id, project_id, parent_task_id, title, status, priority, task_type, needs_user_input, can_agent_execute, waiting_question, updated_at
            FROM tasks
            WHERE parent_task_id = ?
            ORDER BY priority ASC, id ASC
            ''',
            (task_id,),
        ).fetchall()
        result = {
            'ok': True,
            'workflow': 'build-subtasks',
            'task_id': task_id,
            'parent_task': dict(parent),
            'subtask_progress': subtask_progress_for_parent(conn, task_id),
            'subtasks': [subtask_row_with_progress_meta(conn, row) for row in rows],
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return result
    finally:
        conn.close()


def generate_task_subtasks(args):
    task_id = getattr(args, 'task_id', None)
    created_by = getattr(args, 'created_by', None) or 'system_engineer'
    quiet = bool(getattr(args, 'quiet', False))
    if task_id is None:
        raise SystemExit('task_id is required')
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        parent = conn.execute(
            '''
            SELECT id, project_id, parent_task_id, title, status, priority, task_type, needs_user_input, can_agent_execute, waiting_question
            FROM tasks
            WHERE id = ?
            ''',
            (task_id,),
        ).fetchone()
        if not parent:
            raise SystemExit(f'task not found: {task_id}')
        if parent['project_id'] is None:
            raise SystemExit(f'task {task_id} is not attached to a project')
        if parent['parent_task_id'] is not None or parent['task_type'] == 'subtask':
            raise SystemExit(f'task {task_id} is already a subtask')
        existing = conn.execute('SELECT id, title FROM tasks WHERE parent_task_id = ? ORDER BY id ASC', (task_id,)).fetchall()
        if existing:
            result = {
                'ok': True,
                'workflow': 'build-subtasks',
                'action': 'already_exists',
                'task_id': task_id,
                'project_id': parent['project_id'],
                'existing_subtasks': [dict(row) for row in existing],
            }
            if not quiet:
                print(json.dumps(result, indent=2, sort_keys=True))
            return result
        specs = subtask_templates_for_task(parent)
        ts = now_iso()
        created = []
        for index, spec in enumerate(specs, start=1):
            waiting_question = parent['waiting_question'] if spec['needs_user_input'] and index == 1 else None
            cur = conn.execute(
                '''
                INSERT INTO tasks (
                  project_id, parent_task_id, title, description, status, priority,
                  next_action, resume_prompt, task_type, origin_agent, capture_source,
                  human_active, agent_active, can_agent_execute, needs_user_input,
                  autonomous_safe, waiting_question, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    parent['project_id'],
                    task_id,
                    spec['title'],
                    f"Generated from parent task #{task_id}: {parent['title']}",
                    'planned',
                    index,
                    'Complete this subtask as part of the parent task.',
                    parent['title'],
                    'subtask',
                    created_by,
                    'build_subtask_generation',
                    0,
                    0,
                    spec['can_agent_execute'],
                    spec['needs_user_input'],
                    spec['autonomous_safe'],
                    waiting_question,
                    ts,
                    ts,
                ),
            )
            subtask_id = cur.lastrowid
            log_activity(conn, 'task', subtask_id, 'subtask_created_from_build', {
                'project_id': parent['project_id'],
                'parent_task_id': task_id,
            }, created_by)
            created.append({'task_id': subtask_id, 'title': spec['title'], 'status': 'planned'})
        note_content = render_subtask_package_markdown(parent, created, ts)
        cur = conn.execute(
            '''
            INSERT INTO notes (entity_type, entity_id, note_type, title, content, created_at, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            ('task', task_id, 'subtask_package', 'Subtask Package', note_content, ts, created_by),
        )
        note_id = cur.lastrowid
        log_activity(conn, 'task', task_id, 'task_subtasks_generated', {
            'project_id': parent['project_id'],
            'subtask_count': len(created),
            'note_id': note_id,
        }, created_by)
        conn.commit()
        result = {
            'ok': True,
            'workflow': 'build-subtasks',
            'action': 'generated',
            'task_id': task_id,
            'project_id': parent['project_id'],
            'subtask_package_note_id': note_id,
            'subtasks_created': created,
        }
        if not quiet:
            print(json.dumps(result, indent=2, sort_keys=True))
        return result
    finally:
        conn.close()


def generate_project_subtasks(args):
    project_id = getattr(args, 'project_id', None)
    created_by = getattr(args, 'created_by', None) or 'system_engineer'
    if project_id is None:
        raise SystemExit('project_id is required')
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            '''
            SELECT id
            FROM tasks
            WHERE project_id = ?
              AND parent_task_id IS NULL
            ORDER BY id ASC
            ''',
            (project_id,),
        ).fetchall()
    finally:
        conn.close()
    generated = []
    already = []
    for row in rows:
        result = generate_task_subtasks(type('Args', (), {'task_id': row['id'], 'created_by': created_by, 'quiet': True})())
        if result.get('action') == 'generated':
            generated.append(result)
        else:
            already.append(result)
    final = {
        'ok': True,
        'workflow': 'build-subtasks',
        'action': 'project_generation',
        'project_id': project_id,
        'generated_count': len(generated),
        'already_existing_count': len(already),
        'generated': generated,
        'already_existing': already,
    }
    print(json.dumps(final, indent=2, sort_keys=True))
    return final


def list_project_tasks(args):
    project_id = getattr(args, 'project_id', None)
    if project_id is None:
        raise SystemExit('project_id is required')
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            '''
            SELECT id, project_id, title, status, priority, needs_user_input, can_agent_execute, waiting_question, updated_at
            FROM tasks
            WHERE project_id = ?
              AND parent_task_id IS NULL
            ORDER BY CASE status
                WHEN 'active' THEN 0
                WHEN 'planned' THEN 1
                WHEN 'waiting' THEN 2
                WHEN 'done' THEN 3
                ELSE 4
            END, priority ASC, id ASC
            ''',
            (project_id,),
        ).fetchall()
        result = {
            'ok': True,
            'workflow': 'build-execution',
            'project_id': project_id,
            'tasks': [task_row_with_dependency_meta(conn, row) for row in rows],
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return result
    finally:
        conn.close()


def show_next_project_task(args):
    project_id = getattr(args, 'project_id', None)
    if project_id is None:
        raise SystemExit('project_id is required')
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    try:
        active = conn.execute(
            'SELECT id, project_id, title, status, priority, needs_user_input, can_agent_execute, waiting_question, updated_at FROM tasks WHERE project_id = ? AND parent_task_id IS NULL AND status = ? ORDER BY id ASC LIMIT 1',
            (project_id, 'active'),
        ).fetchone()
        if active:
            result = {'ok': True, 'workflow': 'build-execution', 'project_id': project_id, 'mode': 'active', 'task': task_row_with_dependency_meta(conn, active)}
            print(json.dumps(result, indent=2, sort_keys=True))
            return result
        waiting = next_attention_task_row(conn, project_id)
        if waiting:
            result = {'ok': True, 'workflow': 'build-execution', 'project_id': project_id, 'mode': 'waiting', 'task': task_row_with_dependency_meta(conn, waiting)}
            print(json.dumps(result, indent=2, sort_keys=True))
            return result
        planned = next_eligible_task_row(conn, project_id)
        result = {'ok': True, 'workflow': 'build-execution', 'project_id': project_id, 'mode': 'next', 'task': task_row_with_dependency_meta(conn, planned)}
        print(json.dumps(result, indent=2, sort_keys=True))
        return result
    finally:
        conn.close()


def start_project_task(args):
    project_id = getattr(args, 'project_id', None)
    task_id = getattr(args, 'task_id', None)
    created_by = getattr(args, 'created_by', None) or 'system_engineer'
    if project_id is None and task_id is None:
        raise SystemExit('project_id or task_id is required')
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        if task_id is not None:
            task = conn.execute('SELECT id, project_id, title, status, needs_user_input, can_agent_execute FROM tasks WHERE id = ?', (task_id,)).fetchone()
        else:
            task = next_startable_task_row(conn, project_id)
        if not task:
            raise SystemExit('no eligible task found to start')
        project_id = task['project_id']
        if project_id is None:
            raise SystemExit(f'task {task["id"]} is not attached to a project')
        if task['status'] not in {'planned', 'waiting'}:
            raise SystemExit(f'task {task["id"]} is not startable from status {task["status"]}')
        if task['needs_user_input'] and not task['can_agent_execute']:
            raise SystemExit(f'task {task["id"]} requires user input and cannot be agent-started')
        blocked_by = unresolved_dependency_ids(conn, task['id'])
        if blocked_by:
            raise SystemExit(f'task {task["id"]} is blocked by unfinished dependencies: {blocked_by}')
        active = conn.execute('SELECT id, title FROM tasks WHERE project_id = ? AND parent_task_id IS NULL AND status = ? AND id != ? ORDER BY id ASC LIMIT 1', (project_id, 'active', task['id'])).fetchone()
        if active:
            raise SystemExit(f'project {project_id} already has an active task: {active["id"]} {active["title"]}')
        ts = now_iso()
        conn.execute(
            '''
            UPDATE tasks
            SET status = 'active', human_active = 1, last_worked_at = ?, updated_at = ?
            WHERE id = ?
            ''',
            (ts, ts, task['id']),
        )
        log_activity(conn, 'task', task['id'], 'project_task_started', {
            'project_id': project_id,
            'from_status': task['status'],
            'to_status': 'active',
        }, created_by)
        conn.commit()
        result = {'ok': True, 'workflow': 'build-execution', 'action': 'started', 'project_id': project_id, 'task_id': task['id'], 'from_status': task['status'], 'to_status': 'active'}
        print(json.dumps(result, indent=2, sort_keys=True))
        return result
    finally:
        conn.close()


def start_review_task(args):
    project_id = getattr(args, 'project_id', None)
    task_id = getattr(args, 'task_id', None)
    created_by = getattr(args, 'created_by', None) or 'system_engineer'
    if project_id is None and task_id is None:
        raise SystemExit('project_id or task_id is required')
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        if task_id is not None:
            task = conn.execute('SELECT id, project_id, title, status, needs_user_input, can_agent_execute FROM tasks WHERE id = ?', (task_id,)).fetchone()
        else:
            task = next_attention_task_row(conn, project_id)
        if not task:
            raise SystemExit('no waiting review task found to start')
        project_id = task['project_id']
        if project_id is None:
            raise SystemExit(f'task {task["id"]} is not attached to a project')
        if task['status'] not in {'planned', 'waiting'}:
            raise SystemExit(f'task {task["id"]} is not review-startable from status {task["status"]}')
        if not task['needs_user_input']:
            raise SystemExit(f'task {task["id"]} is not a review/manual task')
        blocked_by = unresolved_dependency_ids(conn, task['id'])
        if blocked_by:
            raise SystemExit(f'task {task["id"]} is blocked by unfinished dependencies: {blocked_by}')
        active = conn.execute('SELECT id, title FROM tasks WHERE project_id = ? AND parent_task_id IS NULL AND status = ? AND id != ? ORDER BY id ASC LIMIT 1', (project_id, 'active', task['id'])).fetchone()
        if active:
            raise SystemExit(f'project {project_id} already has an active task: {active["id"]} {active["title"]}')
        ts = now_iso()
        conn.execute(
            '''
            UPDATE tasks
            SET status = 'active', human_active = 1, last_worked_at = ?, updated_at = ?
            WHERE id = ?
            ''',
            (ts, ts, task['id']),
        )
        log_activity(conn, 'task', task['id'], 'review_task_started', {
            'project_id': project_id,
            'from_status': task['status'],
            'to_status': 'active',
        }, created_by)
        conn.commit()
        result = {'ok': True, 'workflow': 'build-review', 'action': 'started', 'project_id': project_id, 'task_id': task['id'], 'from_status': task['status'], 'to_status': 'active'}
        print(json.dumps(result, indent=2, sort_keys=True))
        return result
    finally:
        conn.close()


def complete_review_task(args):
    return complete_project_task(args)


def show_next_task_subtask(args):
    task_id = getattr(args, 'task_id', None)
    if task_id is None:
        raise SystemExit('task_id is required')
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    try:
        parent = conn.execute(
            'SELECT id, project_id, title, status, needs_user_input, can_agent_execute FROM tasks WHERE id = ?',
            (task_id,),
        ).fetchone()
        if not parent:
            raise SystemExit(f'task not found: {task_id}')
        active = active_subtask_row(conn, task_id)
        if active:
            result = {
                'ok': True,
                'workflow': 'build-subtask-execution',
                'task_id': task_id,
                'parent_task': dict(parent),
                'mode': 'active',
                'subtask': subtask_row_with_progress_meta(conn, active),
            }
            print(json.dumps(result, indent=2, sort_keys=True))
            return result
        waiting = next_attention_subtask_row(conn, task_id)
        if waiting:
            result = {
                'ok': True,
                'workflow': 'build-subtask-execution',
                'task_id': task_id,
                'parent_task': dict(parent),
                'mode': 'waiting',
                'subtask': subtask_row_with_progress_meta(conn, waiting),
            }
            print(json.dumps(result, indent=2, sort_keys=True))
            return result
        planned = next_eligible_subtask_row(conn, task_id)
        result = {
            'ok': True,
            'workflow': 'build-subtask-execution',
            'task_id': task_id,
            'parent_task': dict(parent),
            'mode': 'next',
            'subtask': subtask_row_with_progress_meta(conn, planned) if planned else None,
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return result
    finally:
        conn.close()


def start_task_subtask(args):
    parent_task_id = getattr(args, 'task_id', None)
    subtask_id = getattr(args, 'subtask_id', None)
    created_by = getattr(args, 'created_by', None) or 'system_engineer'
    if parent_task_id is None and subtask_id is None:
        raise SystemExit('task_id or subtask_id is required')
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        if subtask_id is not None:
            subtask = conn.execute(
                'SELECT id, project_id, parent_task_id, title, status, priority, needs_user_input, can_agent_execute FROM tasks WHERE id = ?',
                (subtask_id,),
            ).fetchone()
        else:
            subtask = next_startable_subtask_row(conn, parent_task_id)
        if not subtask:
            raise SystemExit('no eligible subtask found to start')
        if subtask['parent_task_id'] is None:
            raise SystemExit(f'task {subtask["id"]} is not a subtask')
        parent = conn.execute('SELECT id, project_id, title, status FROM tasks WHERE id = ?', (subtask['parent_task_id'],)).fetchone()
        if not parent:
            raise SystemExit(f'parent task not found for subtask {subtask["id"]}')
        if parent['status'] != 'active':
            raise SystemExit(f'parent task {parent["id"]} must be active before starting subtasks')
        if subtask['status'] not in {'planned', 'waiting'}:
            raise SystemExit(f'subtask {subtask["id"]} is not startable from status {subtask["status"]}')
        if subtask['needs_user_input'] and not subtask['can_agent_execute']:
            raise SystemExit(f'subtask {subtask["id"]} requires user input and cannot be agent-started')
        blocked_by = subtask_blocker_ids(conn, subtask['id'], subtask['parent_task_id'], subtask['priority'])
        if blocked_by:
            raise SystemExit(f'subtask {subtask["id"]} is blocked by unfinished earlier subtasks: {blocked_by}')
        active = active_subtask_row(conn, subtask['parent_task_id'])
        if active and active['id'] != subtask['id']:
            raise SystemExit(f'parent task {subtask["parent_task_id"]} already has an active subtask: {active["id"]} {active["title"]}')
        ts = now_iso()
        conn.execute(
            '''
            UPDATE tasks
            SET status = 'active', human_active = 1, last_worked_at = ?, updated_at = ?
            WHERE id = ?
            ''',
            (ts, ts, subtask['id']),
        )
        log_activity(conn, 'task', subtask['id'], 'subtask_started', {
            'project_id': subtask['project_id'],
            'parent_task_id': subtask['parent_task_id'],
            'from_status': subtask['status'],
            'to_status': 'active',
        }, created_by)
        conn.commit()
        result = {
            'ok': True,
            'workflow': 'build-subtask-execution',
            'action': 'started',
            'project_id': subtask['project_id'],
            'parent_task_id': subtask['parent_task_id'],
            'subtask_id': subtask['id'],
            'from_status': subtask['status'],
            'to_status': 'active',
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return result
    finally:
        conn.close()


def start_review_subtask(args):
    parent_task_id = getattr(args, 'task_id', None)
    subtask_id = getattr(args, 'subtask_id', None)
    created_by = getattr(args, 'created_by', None) or 'system_engineer'
    if parent_task_id is None and subtask_id is None:
        raise SystemExit('task_id or subtask_id is required')
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        if subtask_id is not None:
            subtask = conn.execute(
                'SELECT id, project_id, parent_task_id, title, status, priority, needs_user_input, can_agent_execute FROM tasks WHERE id = ?',
                (subtask_id,),
            ).fetchone()
        else:
            subtask = next_attention_subtask_row(conn, parent_task_id) or next_eligible_subtask_row(conn, parent_task_id)
        if not subtask:
            raise SystemExit('no review subtask found to start')
        if subtask['parent_task_id'] is None:
            raise SystemExit(f'task {subtask["id"]} is not a subtask')
        if not subtask['needs_user_input']:
            raise SystemExit(f'subtask {subtask["id"]} is not a review/manual subtask')
        parent = conn.execute('SELECT id, project_id, title, status FROM tasks WHERE id = ?', (subtask['parent_task_id'],)).fetchone()
        if not parent:
            raise SystemExit(f'parent task not found for subtask {subtask["id"]}')
        if parent['status'] != 'active':
            raise SystemExit(f'parent task {parent["id"]} must be active before starting review subtasks')
        if subtask['status'] not in {'planned', 'waiting'}:
            raise SystemExit(f'subtask {subtask["id"]} is not review-startable from status {subtask["status"]}')
        blocked_by = subtask_blocker_ids(conn, subtask['id'], subtask['parent_task_id'], subtask['priority'])
        if blocked_by:
            raise SystemExit(f'subtask {subtask["id"]} is blocked by unfinished earlier subtasks: {blocked_by}')
        active = active_subtask_row(conn, subtask['parent_task_id'])
        if active and active['id'] != subtask['id']:
            raise SystemExit(f'parent task {subtask["parent_task_id"]} already has an active subtask: {active["id"]} {active["title"]}')
        ts = now_iso()
        conn.execute(
            '''
            UPDATE tasks
            SET status = 'active', human_active = 1, last_worked_at = ?, updated_at = ?
            WHERE id = ?
            ''',
            (ts, ts, subtask['id']),
        )
        log_activity(conn, 'task', subtask['id'], 'review_subtask_started', {
            'project_id': subtask['project_id'],
            'parent_task_id': subtask['parent_task_id'],
            'from_status': subtask['status'],
            'to_status': 'active',
        }, created_by)
        conn.commit()
        result = {
            'ok': True,
            'workflow': 'build-review',
            'action': 'started',
            'project_id': subtask['project_id'],
            'parent_task_id': subtask['parent_task_id'],
            'subtask_id': subtask['id'],
            'from_status': subtask['status'],
            'to_status': 'active',
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return result
    finally:
        conn.close()


def complete_review_subtask(args):
    return complete_task_subtask(args)


def complete_task_subtask(args):
    subtask_id = getattr(args, 'subtask_id', None)
    created_by = getattr(args, 'created_by', None) or 'system_engineer'
    auto_advance = bool(getattr(args, 'auto_advance', False))
    if subtask_id is None:
        raise SystemExit('subtask_id is required')
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        subtask = conn.execute(
            'SELECT id, project_id, parent_task_id, title, status, priority, needs_user_input, can_agent_execute FROM tasks WHERE id = ?',
            (subtask_id,),
        ).fetchone()
        if not subtask:
            raise SystemExit(f'subtask not found: {subtask_id}')
        if subtask['parent_task_id'] is None:
            raise SystemExit(f'task {subtask_id} is not a subtask')
        if subtask['status'] != 'active':
            raise SystemExit(f'subtask {subtask_id} is not active')
        ts = now_iso()
        conn.execute(
            '''
            UPDATE tasks
            SET status = 'done', human_active = 0, completed_at = COALESCE(completed_at, ?), updated_at = ?
            WHERE id = ?
            ''',
            (ts, ts, subtask_id),
        )
        log_activity(conn, 'task', subtask_id, 'subtask_completed', {
            'project_id': subtask['project_id'],
            'parent_task_id': subtask['parent_task_id'],
            'from_status': 'active',
            'to_status': 'done',
        }, created_by)
        released_waiting_subtask = None
        next_subtask = next_eligible_subtask_row(conn, subtask['parent_task_id'])
        if next_subtask is not None and next_subtask['needs_user_input'] and next_subtask['status'] == 'planned':
            conn.execute(
                '''
                UPDATE tasks
                SET status = 'waiting', updated_at = ?
                WHERE id = ?
                ''',
                (ts, next_subtask['id']),
            )
            log_activity(conn, 'task', next_subtask['id'], 'subtask_waiting_released', {
                'project_id': subtask['project_id'],
                'parent_task_id': subtask['parent_task_id'],
                'from_status': 'planned',
                'to_status': 'waiting',
                'triggered_by_subtask_id': subtask_id,
            }, created_by)
            next_subtask = dict(next_subtask)
            next_subtask['status'] = 'waiting'
            next_subtask['updated_at'] = ts
            released_waiting_subtask = subtask_row_with_progress_meta(conn, next_subtask)
        auto_started = None
        if auto_advance and next_subtask is not None and next_subtask['can_agent_execute'] and not next_subtask['needs_user_input']:
            conn.execute(
                '''
                UPDATE tasks
                SET status = 'active', human_active = 1, last_worked_at = ?, updated_at = ?
                WHERE id = ?
                ''',
                (ts, ts, next_subtask['id']),
            )
            log_activity(conn, 'task', next_subtask['id'], 'subtask_auto_started', {
                'project_id': subtask['project_id'],
                'parent_task_id': subtask['parent_task_id'],
                'from_status': next_subtask['status'],
                'to_status': 'active',
                'triggered_by_subtask_id': subtask_id,
            }, created_by)
            auto_started = dict(next_subtask)
            auto_started['status'] = 'active'
            auto_started['updated_at'] = ts
        conn.commit()
        result = {
            'ok': True,
            'workflow': 'build-subtask-execution',
            'action': 'completed',
            'project_id': subtask['project_id'],
            'parent_task_id': subtask['parent_task_id'],
            'subtask_id': subtask_id,
            'from_status': 'active',
            'to_status': 'done',
            'released_waiting_subtask': released_waiting_subtask,
            'next_subtask': subtask_row_with_progress_meta(conn, next_eligible_subtask_row(conn, subtask['parent_task_id'])),
            'auto_started_subtask': subtask_row_with_progress_meta(conn, auto_started) if auto_started else None,
            'subtask_progress': subtask_progress_for_parent(conn, subtask['parent_task_id']),
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return result
    finally:
        conn.close()


def complete_project_task(args):
    task_id = getattr(args, 'task_id', None)
    created_by = getattr(args, 'created_by', None) or 'system_engineer'
    auto_advance = bool(getattr(args, 'auto_advance', False))
    if task_id is None:
        raise SystemExit('task_id is required')
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        task = conn.execute('SELECT id, project_id, parent_task_id, title, status FROM tasks WHERE id = ?', (task_id,)).fetchone()
        if not task:
            raise SystemExit(f'task not found: {task_id}')
        if task['project_id'] is None:
            raise SystemExit(f'task {task_id} is not attached to a project')
        if task['parent_task_id'] is not None:
            raise SystemExit(f'task {task_id} is a subtask; use complete-task-subtask instead')
        if task['status'] != 'active':
            raise SystemExit(f'task {task_id} is not active')
        unfinished_subtasks = unfinished_subtask_rows(conn, task_id)
        if unfinished_subtasks:
            raise SystemExit(f'task {task_id} still has unfinished subtasks: {[row["id"] for row in unfinished_subtasks]}')
        ts = now_iso()
        conn.execute(
            '''
            UPDATE tasks
            SET status = 'done', human_active = 0, completed_at = COALESCE(completed_at, ?), updated_at = ?
            WHERE id = ?
            ''',
            (ts, ts, task_id),
        )
        log_activity(conn, 'task', task_id, 'project_task_completed', {
            'project_id': task['project_id'],
            'from_status': 'active',
            'to_status': 'done',
        }, created_by)
        released_waiting_tasks = release_waiting_tasks(conn, task['project_id'], created_by, triggered_by_task_id=task_id)
        next_task = next_eligible_task_row(conn, task['project_id'])
        auto_started = None
        if auto_advance and next_task is not None and next_task['can_agent_execute'] and not next_task['needs_user_input']:
            conn.execute(
                '''
                UPDATE tasks
                SET status = 'active', human_active = 1, last_worked_at = ?, updated_at = ?
                WHERE id = ?
                ''',
                (ts, ts, next_task['id']),
            )
            log_activity(conn, 'task', next_task['id'], 'project_task_auto_started', {
                'project_id': task['project_id'],
                'from_status': next_task['status'],
                'to_status': 'active',
                'triggered_by_task_id': task_id,
            }, created_by)
            auto_started = dict(next_task)
            auto_started['status'] = 'active'
        project_transition = maybe_transition_project_to_support(conn, task['project_id'], created_by, triggered_by_task_id=task_id)
        conn.commit()
        result = {
            'ok': True,
            'workflow': 'build-execution',
            'action': 'completed',
            'project_id': task['project_id'],
            'task_id': task_id,
            'from_status': 'active',
            'to_status': 'done',
            'released_waiting_tasks': released_waiting_tasks,
            'next_task': task_row_with_dependency_meta(conn, next_task) if next_task else None,
            'auto_started_task': auto_started,
            'project_transition': project_transition,
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return result
    finally:
        conn.close()


def sync_project_task_order(args):
    project_id = getattr(args, 'project_id', None)
    created_by = getattr(args, 'created_by', None) or 'system_engineer'
    if project_id is None:
        raise SystemExit('project_id is required')
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        planning_note = conn.execute(
            '''
            SELECT id, content
            FROM notes
            WHERE entity_type = 'project' AND entity_id = ? AND note_type = 'planning_package'
            ORDER BY id DESC
            LIMIT 1
            ''',
            (project_id,),
        ).fetchone()
        if not planning_note:
            raise SystemExit(f'planning package not found for project {project_id}')
        task_specs = parse_task_breakdown(planning_note['content'])
        if not task_specs:
            raise SystemExit(f'no task breakdown found in planning package for project {project_id}')
        task_rows = conn.execute(
            '''
            SELECT id, title, priority
            FROM tasks
            WHERE project_id = ?
              AND parent_task_id IS NULL
            ORDER BY id ASC
            ''',
            (project_id,),
        ).fetchall()
        tasks_by_title = {row['title']: row for row in task_rows}
        updates = []
        missing_titles = []
        ts = now_iso()
        for index, item in enumerate(task_specs, start=1):
            row = tasks_by_title.get(item['task_title'])
            if row is None:
                missing_titles.append(item['task_title'])
                continue
            if row['priority'] != index:
                conn.execute('UPDATE tasks SET priority = ?, updated_at = ? WHERE id = ?', (index, ts, row['id']))
                updates.append({'task_id': row['id'], 'title': row['title'], 'from_priority': row['priority'], 'to_priority': index})
        if updates:
            log_activity(conn, 'project', project_id, 'project_task_order_synced', {
                'updated_count': len(updates),
                'missing_task_titles': missing_titles,
            }, created_by)
        conn.commit()
        result = {
            'ok': True,
            'workflow': 'build-execution',
            'action': 'sync_task_order',
            'project_id': project_id,
            'updated_priorities': updates,
            'missing_task_titles': missing_titles,
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return result
    finally:
        conn.close()


def sync_project_dependencies(args):
    project_id = getattr(args, 'project_id', None)
    created_by = getattr(args, 'created_by', None) or 'system_engineer'
    if project_id is None:
        raise SystemExit('project_id is required')

    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        planning_note = conn.execute(
            '''
            SELECT id, content
            FROM notes
            WHERE entity_type = 'project' AND entity_id = ? AND note_type = 'planning_package'
            ORDER BY id DESC
            LIMIT 1
            ''',
            (project_id,),
        ).fetchone()
        if not planning_note:
            raise SystemExit(f'planning package not found for project {project_id}')
        task_specs = parse_task_breakdown(planning_note['content'])
        if not task_specs:
            raise SystemExit(f'no task breakdown found in planning package for project {project_id}')

        task_rows = conn.execute(
            '''
            SELECT id, project_id, title, status, priority, needs_user_input, can_agent_execute, waiting_question, updated_at
            FROM tasks
            WHERE project_id = ?
              AND parent_task_id IS NULL
            ORDER BY id ASC
            ''',
            (project_id,),
        ).fetchall()
        tasks_by_title = {row['title']: row for row in task_rows}
        created_tasks = []
        missing_titles = []
        for item in task_specs:
            row = tasks_by_title.get(item['task_title'])
            if row is None:
                missing_titles.append(item['task_title'])
                created_tasks.append({'task_id': None, 'title': item['task_title']})
            else:
                created_tasks.append({'task_id': row['id'], 'title': row['title']})

        existing_pairs = {
            (row['task_id'], row['depends_on_task_id'])
            for row in conn.execute('SELECT task_id, depends_on_task_id FROM dependencies WHERE task_id IN (SELECT id FROM tasks WHERE project_id = ? AND parent_task_id IS NULL)', (project_id,)).fetchall()
        }
        ts = now_iso()
        created_links = []
        for index, item in enumerate(task_specs):
            task_id = created_tasks[index]['task_id']
            if task_id is None:
                continue
            depends_on_task_id = resolve_dependency_task_id(task_specs, created_tasks, index)
            if depends_on_task_id is None:
                continue
            pair = (task_id, depends_on_task_id)
            if pair in existing_pairs:
                continue
            conn.execute(
                '''
                INSERT INTO dependencies (task_id, depends_on_task_id, dependency_type, created_at, created_by)
                VALUES (?, ?, 'requires', ?, ?)
                ''',
                (task_id, depends_on_task_id, ts, created_by),
            )
            existing_pairs.add(pair)
            created_links.append({
                'task_id': task_id,
                'depends_on_task_id': depends_on_task_id,
                'dependency': item.get('dependency') or '',
            })

        released_waiting_tasks = release_waiting_tasks(conn, project_id, created_by)
        if created_links or released_waiting_tasks:
            log_activity(conn, 'project', project_id, 'project_dependencies_synced', {
                'dependency_count': len(created_links),
                'released_waiting_count': len(released_waiting_tasks),
            }, created_by)
        conn.commit()
        result = {
            'ok': True,
            'workflow': 'build-execution',
            'action': 'sync_dependencies',
            'project_id': project_id,
            'dependencies_created': created_links,
            'released_waiting_tasks': released_waiting_tasks,
            'missing_task_titles': missing_titles,
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return result
    finally:
        conn.close()


def run_build(args):
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
        if project['status'] != 'planning':
            raise SystemExit(f'project {project_id} is not in planning status')

        existing = conn.execute('SELECT id FROM tasks WHERE project_id = ? LIMIT 1', (project_id,)).fetchone()
        if existing:
            raise SystemExit(f'project {project_id} already has project tasks; refusing to generate duplicates')

        planning_note = conn.execute(
            '''
            SELECT id, content
            FROM notes
            WHERE entity_type = 'project' AND entity_id = ? AND note_type = 'planning_package'
            ORDER BY id DESC
            LIMIT 1
            ''',
            (project_id,),
        ).fetchone()
        if not planning_note:
            raise SystemExit(f'planning package not found for project {project_id}')

        task_specs = parse_task_breakdown(planning_note['content'])
        if not task_specs:
            raise SystemExit(f'no task breakdown found in planning package for project {project_id}')

        ts = now_iso()
        created_tasks = []
        for index, item in enumerate(task_specs, start=1):
            owner = item['owner']
            status_model = item['expected_status_model'].lower()
            waiting = 'waiting' in status_model and owner.lower() == 'greg'
            cur = conn.execute(
                '''
                INSERT INTO tasks (
                  project_id, parent_task_id, title, description, status, priority,
                  next_action, resume_prompt, task_type, origin_agent, capture_source,
                  human_active, agent_active, can_agent_execute, needs_user_input,
                  autonomous_safe, waiting_question, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    project_id,
                    None,
                    item['task_title'],
                    item['dependency'] or f"Generated from planning package for {project['title']}.",
                    'planned',
                    index,
                    'Start this task when its dependency is satisfied.',
                    item['expected_status_model'],
                    'task',
                    created_by,
                    'build_from_planning',
                    0,
                    0,
                    1 if owner.lower() != 'greg' else 0,
                    1 if owner.lower() == 'greg' else 0,
                    1 if owner.lower() != 'greg' else 0,
                    item['dependency'] if waiting else None,
                    ts,
                    ts,
                ),
            )
            task_id = cur.lastrowid
            log_activity(conn, 'task', task_id, 'task_created_from_planning', {
                'project_id': project_id,
                'owner': owner,
                'dependency': item['dependency'],
                'expected_status_model': item['expected_status_model'],
            }, created_by)
            created_tasks.append({
                'task_id': task_id,
                'title': item['task_title'],
                'status': 'planned',
                'owner': owner,
            })

        dependency_links = []
        for index, item in enumerate(task_specs):
            depends_on_task_id = resolve_dependency_task_id(task_specs, created_tasks, index)
            if depends_on_task_id is None:
                continue
            conn.execute(
                '''
                INSERT INTO dependencies (task_id, depends_on_task_id, dependency_type, created_at, created_by)
                VALUES (?, ?, 'requires', ?, ?)
                ''',
                (created_tasks[index]['task_id'], depends_on_task_id, ts, created_by),
            )
            dependency_links.append({
                'task_id': created_tasks[index]['task_id'],
                'depends_on_task_id': depends_on_task_id,
                'dependency': item.get('dependency') or '',
            })

        note_path = write_obsidian_build(project, created_tasks, project_id, ts)
        cur = conn.execute(
            '''
            INSERT INTO notes (entity_type, entity_id, note_type, title, content, created_at, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            ('project', project_id, 'build_kickoff', 'Build Kickoff', render_build_kickoff_markdown(project, created_tasks, project_id, ts), ts, created_by),
        )
        build_note_id = cur.lastrowid
        conn.execute(
            'UPDATE projects SET status = ?, updated_at = ? WHERE id = ?',
            ('build', ts, project_id),
        )
        log_activity(conn, 'project', project_id, 'project_build_started', {
            'from_status': 'planning',
            'to_status': 'build',
            'build_note_id': build_note_id,
            'task_count': len(created_tasks),
            'dependency_count': len(dependency_links),
            'title': project['title'],
        }, created_by)
        conn.commit()
        result = {
            'ok': True,
            'workflow': 'build',
            'project_id': project_id,
            'from_status': 'planning',
            'to_status': 'build',
            'build_note_id': build_note_id,
            'task_count': len(created_tasks),
            'dependencies_created': dependency_links,
            'task_ids': [task['task_id'] for task in created_tasks],
            'obsidian_note_path': str(note_path),
            'title': project['title'],
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return result
    finally:
        conn.close()
