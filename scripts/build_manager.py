#!/usr/bin/env python3
import argparse
import json
import re
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workflows.capture.runtime import archive_capture, list_captures, promote_capture, review_capture, run_capture, shelve_capture
from workflows.review.runtime import list_review_queue, run_review
from workflows.design.runtime import list_design_queue, run_design
from workflows.planning.runtime import list_planning_queue, run_planning
from workflows.build.runtime import complete_project_task, complete_review_subtask, complete_review_task, complete_task_subtask, generate_project_subtasks, generate_task_subtasks, list_build_queue, list_project_tasks, list_task_subtasks, run_build, show_next_project_task, show_next_task_subtask, start_project_task, start_review_subtask, start_review_task, start_task_subtask, sync_project_dependencies, sync_project_task_order

CONFIG_PATH = ROOT / 'config' / 'build_manager.json'
STANDALONE_TASK_STATUSES = {'captured', 'queued', 'active', 'paused', 'parked', 'done', 'archived'}
PROJECT_TASK_STATUSES = {'planned', 'active', 'waiting', 'done'}
VALID_TASK_STATUSES = STANDALONE_TASK_STATUSES | PROJECT_TASK_STATUSES
VALID_PROJECT_STATUSES = {'hopper', 'capture', 'evaluation', 'design', 'planning', 'build', 'support', 'parked', 'archived'}
PROJECT_BINDING_COLUMNS = {
    'conversation_provider': 'TEXT',
    'conversation_surface': 'TEXT',
    'conversation_channel_id': 'TEXT',
    'conversation_thread_id': 'TEXT',
    'conversation_session_key': 'TEXT',
    'conversation_label': 'TEXT',
    'conversation_is_canonical': 'INTEGER NOT NULL DEFAULT 0',
    'conversation_bound_at': 'TEXT',
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def db_path() -> Path:
    cfg = load_config()
    return (CONFIG_PATH.parent / cfg['database']['path']).resolve()


def ensure_project_binding_schema(conn):
    existing = {row['name'] for row in conn.execute('PRAGMA table_info(projects)').fetchall()}
    changed = False
    for column, column_type in PROJECT_BINDING_COLUMNS.items():
        if column in existing:
            continue
        conn.execute(f'ALTER TABLE projects ADD COLUMN {column} {column_type}')
        changed = True
    return changed


@contextmanager
def connect():
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    ensure_project_binding_schema(conn)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def print_json(data):
    print(json.dumps(data, indent=2, sort_keys=True))


def fetch_task(conn, task_id: int):
    row = conn.execute(
        'SELECT id, project_id, parent_task_id, title, status FROM tasks WHERE id = ?',
        (task_id,),
    ).fetchone()
    if not row:
        raise SystemExit(f'task not found: {task_id}')
    return row


def fetch_project(conn, project_id: int):
    row = conn.execute(
        '''
        SELECT id, slug, title, status,
               conversation_provider, conversation_surface,
               conversation_channel_id, conversation_thread_id,
               conversation_session_key, conversation_label,
               conversation_is_canonical, conversation_bound_at
        FROM projects
        WHERE id = ?
        ''',
        (project_id,),
    ).fetchone()
    if not row:
        raise SystemExit(f'project not found: {project_id}')
    return row


def project_binding_payload_from_args(args, require_any=False):
    payload = {
        'conversation_provider': getattr(args, 'conversation_provider', None),
        'conversation_surface': getattr(args, 'conversation_surface', None),
        'conversation_channel_id': getattr(args, 'conversation_channel_id', None),
        'conversation_thread_id': getattr(args, 'conversation_thread_id', None),
        'conversation_session_key': getattr(args, 'conversation_session_key', None),
        'conversation_label': getattr(args, 'conversation_label', None),
    }
    payload = {
        key: (value.strip() if isinstance(value, str) else value)
        for key, value in payload.items()
        if value is not None and (not isinstance(value, str) or value.strip())
    }
    if getattr(args, 'canonical', False):
        payload['conversation_is_canonical'] = 1
    elif getattr(args, 'canonical_false', False):
        payload['conversation_is_canonical'] = 0
    if require_any and not payload:
        raise SystemExit('at least one binding field is required')
    return payload


def project_binding_view(row):
    return {
        'provider': row['conversation_provider'],
        'surface': row['conversation_surface'],
        'channel_id': row['conversation_channel_id'],
        'thread_id': row['conversation_thread_id'],
        'session_key': row['conversation_session_key'],
        'label': row['conversation_label'],
        'is_canonical': bool(row['conversation_is_canonical']),
        'bound_at': row['conversation_bound_at'],
    }


def task_scope(project_id):
    return 'project' if project_id is not None else 'standalone'


def valid_statuses_for_project_id(project_id):
    return PROJECT_TASK_STATUSES if project_id is not None else STANDALONE_TASK_STATUSES


def default_status_for_project_id(project_id):
    return 'planned' if project_id is not None else 'captured'


def validate_task_status_for_scope(status, project_id):
    allowed = valid_statuses_for_project_id(project_id)
    if status not in allowed:
        scope = task_scope(project_id)
        allowed_list = ', '.join(sorted(allowed))
        raise SystemExit(f'invalid {scope} task status: {status} (allowed: {allowed_list})')


def resolve_task_create_context(conn, args, parent_task_id=None):
    parent_task = None
    project_id = args.project_id
    if parent_task_id is not None:
        parent_task = fetch_task(conn, parent_task_id)
        parent_project_id = parent_task['project_id']
        if project_id is None:
            project_id = parent_project_id
        elif project_id != parent_project_id:
            raise SystemExit('subtask project_id must match parent task project_id')
    if project_id is not None:
        project = conn.execute('SELECT id FROM projects WHERE id = ?', (project_id,)).fetchone()
        if not project:
            raise SystemExit(f'project not found: {project_id}')
    status = args.status or default_status_for_project_id(project_id)
    validate_task_status_for_scope(status, project_id)
    return project_id, status, parent_task


def log_activity(conn, entity_type: str, entity_id: int, event_type: str, payload: dict, created_by: str):
    conn.execute(
        '''
        INSERT INTO activity_log (entity_type, entity_id, event_type, payload_json, created_at, created_by)
        VALUES (?, ?, ?, ?, ?, ?)
        ''',
        (entity_type, entity_id, event_type, json.dumps(payload, sort_keys=True), now_iso(), created_by),
    )


def slugify(text: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
    return slug or 'project'


def create_project(args):
    ts = now_iso()
    binding = project_binding_payload_from_args(args, require_any=False)
    if binding and 'conversation_is_canonical' not in binding:
        binding['conversation_is_canonical'] = 1
    binding_bound_at = ts if any(key != 'conversation_is_canonical' for key in binding) else None
    with connect() as conn:
        cur = conn.execute(
            '''
            INSERT INTO projects (
              slug, title, description, status, category_id, owner_agent, goal, default_context,
              conversation_provider, conversation_surface, conversation_channel_id, conversation_thread_id,
              conversation_session_key, conversation_label, conversation_is_canonical, conversation_bound_at,
              created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                args.slug,
                args.title,
                args.description,
                args.status,
                args.category_id,
                args.owner_agent,
                args.goal,
                args.default_context,
                binding.get('conversation_provider'),
                binding.get('conversation_surface'),
                binding.get('conversation_channel_id'),
                binding.get('conversation_thread_id'),
                binding.get('conversation_session_key'),
                binding.get('conversation_label'),
                binding.get('conversation_is_canonical', 0),
                binding_bound_at,
                ts,
                ts,
            ),
        )
        project_id = cur.lastrowid
        log_activity(conn, 'project', project_id, 'project_created', {
            'slug': args.slug,
            'title': args.title,
            'status': args.status,
            'binding': binding | ({'conversation_bound_at': binding_bound_at} if binding_bound_at else {}),
        }, args.created_by)
        print_json({'project_id': project_id, 'slug': args.slug, 'title': args.title, 'status': args.status, 'binding': {
            'provider': binding.get('conversation_provider'),
            'surface': binding.get('conversation_surface'),
            'channel_id': binding.get('conversation_channel_id'),
            'thread_id': binding.get('conversation_thread_id'),
            'session_key': binding.get('conversation_session_key'),
            'label': binding.get('conversation_label'),
            'is_canonical': bool(binding.get('conversation_is_canonical', 0)),
            'bound_at': binding_bound_at,
        }})


def set_project_binding(args):
    ts = now_iso()
    payload = project_binding_payload_from_args(args, require_any=True)
    with connect() as conn:
        fetch_project(conn, args.project_id)
        updates = []
        params = []
        for key in [
            'conversation_provider', 'conversation_surface', 'conversation_channel_id',
            'conversation_thread_id', 'conversation_session_key', 'conversation_label',
            'conversation_is_canonical',
        ]:
            if key not in payload:
                continue
            updates.append(f'{key} = ?')
            params.append(payload[key])
        if any(key != 'conversation_is_canonical' for key in payload):
            updates.append('conversation_bound_at = ?')
            params.append(ts)
        updates.append('updated_at = ?')
        params.append(ts)
        params.append(args.project_id)
        conn.execute(f'UPDATE projects SET {", ".join(updates)} WHERE id = ?', tuple(params))
        refreshed = fetch_project(conn, args.project_id)
        log_activity(conn, 'project', args.project_id, 'project_conversation_bound', {
            'binding': project_binding_view(refreshed),
        }, args.created_by)
        print_json({'project_id': args.project_id, 'title': refreshed['title'], 'binding': project_binding_view(refreshed)})


def clear_project_binding(args):
    ts = now_iso()
    with connect() as conn:
        project = fetch_project(conn, args.project_id)
        conn.execute(
            '''
            UPDATE projects
            SET conversation_provider = NULL,
                conversation_surface = NULL,
                conversation_channel_id = NULL,
                conversation_thread_id = NULL,
                conversation_session_key = NULL,
                conversation_label = NULL,
                conversation_is_canonical = 0,
                conversation_bound_at = NULL,
                updated_at = ?
            WHERE id = ?
            ''',
            (ts, args.project_id),
        )
        log_activity(conn, 'project', args.project_id, 'project_conversation_binding_cleared', {}, args.created_by)
        print_json({'project_id': args.project_id, 'title': project['title'], 'binding': None})


def show_project_binding(args):
    with connect() as conn:
        project = fetch_project(conn, args.project_id)
        print_json({'project_id': args.project_id, 'title': project['title'], 'binding': project_binding_view(project)})


def create_task(args, parent_task_id=None):
    ts = now_iso()
    with connect() as conn:
        project_id, status, _parent_task = resolve_task_create_context(conn, args, parent_task_id)

        cur = conn.execute(
            '''
            INSERT INTO tasks (
              project_id, parent_task_id, title, description, status, priority, category_id,
              next_action, resume_prompt, estimated_minutes, energy_level, focus_mode,
              task_type, origin_agent, capture_source, human_active, agent_active,
              can_agent_execute, needs_user_input, autonomous_safe,
              waiting_question, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                project_id,
                parent_task_id,
                args.title,
                args.description,
                status,
                args.priority,
                args.category_id,
                args.next_action,
                args.resume_prompt,
                args.estimated_minutes,
                args.energy_level,
                args.focus_mode,
                'subtask' if parent_task_id is not None else args.task_type,
                args.origin_agent,
                args.capture_source,
                1 if status == 'active' else 0,
                0,
                1 if args.can_agent_execute else 0,
                1 if args.needs_user_input else 0,
                1 if args.autonomous_safe else 0,
                args.waiting_question,
                ts,
                ts,
            ),
        )
        task_id = cur.lastrowid
        event = 'subtask_created' if parent_task_id is not None else 'task_created'
        log_activity(conn, 'task', task_id, event, {
            'project_id': project_id,
            'parent_task_id': parent_task_id,
            'title': args.title,
            'status': status,
        }, args.created_by)
        print_json({
            'task_id': task_id,
            'project_id': project_id,
            'parent_task_id': parent_task_id,
            'title': args.title,
            'status': status,
        })


def list_projects(status=None):
    if status is not None and status not in VALID_PROJECT_STATUSES:
        raise SystemExit(f'invalid project status: {status}')
    with connect() as conn:
        if status is None:
            rows = conn.execute(
                '''
                SELECT id, slug, title, status, owner_agent,
                       conversation_provider, conversation_surface,
                       conversation_channel_id, conversation_thread_id,
                       conversation_session_key, conversation_label,
                       conversation_is_canonical, conversation_bound_at,
                       updated_at, completed_at
                FROM projects
                ORDER BY updated_at DESC, id DESC
                '''
            ).fetchall()
        else:
            rows = conn.execute(
                '''
                SELECT id, slug, title, status, owner_agent,
                       conversation_provider, conversation_surface,
                       conversation_channel_id, conversation_thread_id,
                       conversation_session_key, conversation_label,
                       conversation_is_canonical, conversation_bound_at,
                       updated_at, completed_at
                FROM projects
                WHERE status = ?
                ORDER BY updated_at DESC, id DESC
                ''',
                (status,),
            ).fetchall()
        print_json([
            {
                'id': row['id'],
                'slug': row['slug'],
                'title': row['title'],
                'status': row['status'],
                'owner_agent': row['owner_agent'],
                'binding': project_binding_view(row),
                'updated_at': row['updated_at'],
                'completed_at': row['completed_at'],
            }
            for row in rows
        ])


def list_tasks(status: str):
    if status not in VALID_TASK_STATUSES:
        raise SystemExit(f'invalid task status: {status}')
    with connect() as conn:
        rows = conn.execute(
            '''
            SELECT id, project_id, parent_task_id, title, status, priority, next_action, updated_at
            FROM tasks
            WHERE status = ?
            ORDER BY priority ASC, updated_at DESC, id DESC
            ''',
            (status,),
        ).fetchall()
        print_json([
            {
                'id': row['id'],
                'project_id': row['project_id'],
                'parent_task_id': row['parent_task_id'],
                'title': row['title'],
                'status': row['status'],
                'priority': row['priority'],
                'next_action': row['next_action'],
                'updated_at': row['updated_at'],
            }
            for row in rows
        ])


def show_current():
    list_tasks('active')


def show_paused():
    list_tasks('paused')


def show_waiting():
    list_tasks('waiting')


def update_task_status(args, new_status: str, event_type: str = 'task_status_updated'):
    if new_status not in VALID_TASK_STATUSES:
        raise SystemExit(f'invalid task status: {new_status}')
    ts = now_iso()
    with connect() as conn:
        task = fetch_task(conn, args.task_id)
        validate_task_status_for_scope(new_status, task['project_id'])
        if task['status'] == new_status:
            print_json({'task_id': args.task_id, 'from_status': task['status'], 'to_status': new_status})
            return
        completed_at = ts if new_status == 'done' else None
        conn.execute(
            '''
            UPDATE tasks
            SET status = ?,
                human_active = ?,
                completed_at = CASE WHEN ? IS NOT NULL THEN COALESCE(completed_at, ?) ELSE NULL END,
                last_worked_at = CASE WHEN ? = 'active' THEN ? ELSE last_worked_at END,
                updated_at = ?
            WHERE id = ?
            ''',
            (
                new_status,
                1 if new_status == 'active' else 0,
                completed_at,
                completed_at,
                new_status,
                ts,
                ts,
                args.task_id,
            ),
        )
        log_activity(conn, 'task', args.task_id, event_type, {
            'from_status': task['status'],
            'to_status': new_status,
        }, args.created_by)
        print_json({'task_id': args.task_id, 'from_status': task['status'], 'to_status': new_status})


def update_project_status(args, new_status: str, event_type: str = 'project_status_updated'):
    if new_status not in VALID_PROJECT_STATUSES:
        raise SystemExit(f'invalid project status: {new_status}')
    ts = now_iso()
    with connect() as conn:
        project = fetch_project(conn, args.project_id)
        if project['status'] == new_status:
            print_json({'project_id': args.project_id, 'from_status': project['status'], 'to_status': new_status})
            return
        archived_at = ts if new_status == 'archived' else None
        conn.execute(
            '''
            UPDATE projects
            SET status = ?,
                completed_at = CASE WHEN ? IS NOT NULL THEN COALESCE(completed_at, ?) ELSE completed_at END,
                archived_at = CASE WHEN ? IS NOT NULL THEN COALESCE(archived_at, ?) ELSE NULL END,
                updated_at = ?
            WHERE id = ?
            ''',
            (
                new_status,
                archived_at,
                archived_at,
                archived_at,
                archived_at,
                ts,
                args.project_id,
            ),
        )
        log_activity(conn, 'project', args.project_id, event_type, {
            'from_status': project['status'],
            'to_status': new_status,
        }, args.created_by)
        print_json({'project_id': args.project_id, 'from_status': project['status'], 'to_status': new_status})


def rename_project(args):
    ts = now_iso()
    with connect() as conn:
        project = fetch_project(conn, args.project_id)
        new_title = args.title.strip()
        if project['title'] == new_title:
            print_json({'project_id': args.project_id, 'old_title': project['title'], 'new_title': new_title})
            return
        conn.execute(
            'UPDATE projects SET title = ?, updated_at = ? WHERE id = ?',
            (new_title, ts, args.project_id),
        )
        log_activity(conn, 'project', args.project_id, 'project_renamed', {
            'old_title': project['title'],
            'new_title': new_title,
        }, args.created_by)
        print_json({'project_id': args.project_id, 'old_title': project['title'], 'new_title': new_title})


def add_note(args):
    ts = now_iso()
    with connect() as conn:
        if args.entity_type == 'task':
            fetch_task(conn, args.entity_id)
        elif args.entity_type == 'project':
            row = conn.execute('SELECT id FROM projects WHERE id = ?', (args.entity_id,)).fetchone()
            if not row:
                raise SystemExit(f'project not found: {args.entity_id}')

        cur = conn.execute(
            '''
            INSERT INTO notes (entity_type, entity_id, note_type, title, content, created_at, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            (args.entity_type, args.entity_id, args.note_type, args.title, args.content, ts, args.created_by),
        )
        note_id = cur.lastrowid
        log_activity(conn, args.entity_type, args.entity_id, 'note_added', {
            'note_id': note_id,
            'note_type': args.note_type,
            'title': args.title,
        }, args.created_by)
        print_json({'note_id': note_id, 'entity_type': args.entity_type, 'entity_id': args.entity_id})


def start_work_session(args):
    ts = now_iso()
    with connect() as conn:
        fetch_task(conn, args.task_id)
        open_session = conn.execute(
            'SELECT id FROM work_sessions WHERE task_id = ? AND ended_at IS NULL ORDER BY id DESC LIMIT 1',
            (args.task_id,),
        ).fetchone()
        if open_session:
            raise SystemExit(f'open work session already exists for task {args.task_id}: {open_session[0]}')

        cur = conn.execute(
            '''
            INSERT INTO work_sessions (
              task_id, session_type, started_at, planned_minutes,
              estimated_human_minutes, estimated_agent_minutes,
              estimation_confidence, needs_confirmation, created_by, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                args.task_id,
                args.session_type,
                ts,
                args.planned_minutes,
                args.estimated_human_minutes,
                args.estimated_agent_minutes,
                args.estimation_confidence,
                1 if args.needs_confirmation else 0,
                args.created_by,
                args.notes,
            ),
        )
        session_id = cur.lastrowid
        conn.execute(
            'UPDATE tasks SET last_worked_at = ?, updated_at = ? WHERE id = ?',
            (ts, ts, args.task_id),
        )
        log_activity(conn, 'task', args.task_id, 'work_session_started', {
            'session_id': session_id,
            'session_type': args.session_type,
            'planned_minutes': args.planned_minutes,
        }, args.created_by)
        print_json({'session_id': session_id, 'task_id': args.task_id, 'started_at': ts})


def stop_work_session(args):
    ts = now_iso()
    with connect() as conn:
        fetch_task(conn, args.task_id)
        if args.session_id is not None:
            row = conn.execute(
                'SELECT id, task_id FROM work_sessions WHERE id = ? AND ended_at IS NULL',
                (args.session_id,),
            ).fetchone()
            if not row:
                raise SystemExit(f'open work session not found: {args.session_id}')
            if row['task_id'] != args.task_id:
                raise SystemExit(f'session {args.session_id} does not belong to task {args.task_id}')
            session_id = args.session_id
        else:
            row = conn.execute(
                'SELECT id FROM work_sessions WHERE task_id = ? AND ended_at IS NULL ORDER BY id DESC LIMIT 1',
                (args.task_id,),
            ).fetchone()
            if not row:
                raise SystemExit(f'no open work session for task {args.task_id}')
            session_id = row['id']

        conn.execute(
            '''
            UPDATE work_sessions
            SET ended_at = ?,
                final_human_minutes = COALESCE(?, final_human_minutes),
                final_agent_minutes = COALESCE(?, final_agent_minutes),
                confirmed_at = CASE WHEN ? THEN ? ELSE confirmed_at END,
                notes = COALESCE(?, notes)
            WHERE id = ?
            ''',
            (
                ts,
                args.final_human_minutes,
                args.final_agent_minutes,
                1 if args.confirm else 0,
                ts,
                args.notes,
                session_id,
            ),
        )
        conn.execute('UPDATE tasks SET last_worked_at = ?, updated_at = ? WHERE id = ?', (ts, ts, args.task_id))
        log_activity(conn, 'task', args.task_id, 'work_session_stopped', {
            'session_id': session_id,
            'final_human_minutes': args.final_human_minutes,
            'final_agent_minutes': args.final_agent_minutes,
            'confirmed': bool(args.confirm),
        }, args.created_by)
        print_json({'session_id': session_id, 'task_id': args.task_id, 'ended_at': ts})


def resolve_task_reference(ref: str):
    ref = ref.strip()
    with connect() as conn:
        if ref.isdigit():
            row = fetch_task(conn, int(ref))
            return row['id']
        lowered = ref.lower()
        rows = conn.execute(
            '''
            SELECT id, title FROM tasks
            WHERE lower(title) = ?
            ORDER BY id DESC
            ''',
            (lowered,),
        ).fetchall()
        if len(rows) == 1:
            return rows[0]['id']
        if len(rows) > 1:
            print_json({'clarification': f'multiple tasks match "{ref}"; use task id'})
            raise SystemExit(0)
        rows = conn.execute(
            '''
            SELECT id, title FROM tasks
            WHERE lower(title) LIKE ?
            ORDER BY id DESC
            ''',
            (f'%{lowered}%',),
        ).fetchall()
        if len(rows) == 1:
            return rows[0]['id']
        if len(rows) > 1:
            print_json({'clarification': f'multiple tasks match "{ref}"; use task id'})
            raise SystemExit(0)
        if lowered in {'current', 'active', 'current task', 'active task'}:
            rows = conn.execute(
                '''
                SELECT id, title FROM tasks
                WHERE status = 'active'
                ORDER BY updated_at DESC, id DESC
                '''
            ).fetchall()
            if len(rows) == 1:
                return rows[0]['id']
            if len(rows) > 1:
                print_json({'clarification': 'multiple active tasks exist; use task id'})
                raise SystemExit(0)
            print_json({'clarification': 'no active task found'})
            raise SystemExit(0)
    print_json({'clarification': f'task not found for "{ref}"'})
    raise SystemExit(0)


def resolve_project_reference(ref: str):
    ref = ref.strip()
    with connect() as conn:
        if ref.isdigit():
            row = fetch_project(conn, int(ref))
            return row['id']
        lowered = ref.lower()
        rows = conn.execute(
            '''
            SELECT id, slug, title FROM projects
            WHERE lower(title) = ? OR lower(slug) = ?
            ORDER BY id DESC
            ''',
            (lowered, lowered),
        ).fetchall()
        if len(rows) == 1:
            return rows[0]['id']
        if len(rows) > 1:
            print_json({'clarification': f'multiple projects match "{ref}"; use project id'})
            raise SystemExit(0)
        rows = conn.execute(
            '''
            SELECT id, slug, title FROM projects
            WHERE lower(title) LIKE ? OR lower(slug) LIKE ?
            ORDER BY id DESC
            ''',
            (f'%{lowered}%', f'%{lowered}%'),
        ).fetchall()
        if len(rows) == 1:
            return rows[0]['id']
        if len(rows) > 1:
            print_json({'clarification': f'multiple projects match "{ref}"; use project id'})
            raise SystemExit(0)
    print_json({'clarification': f'project not found for "{ref}"'})
    raise SystemExit(0)


def make_task_args(**kwargs):
    defaults = dict(
        project_id=None,
        title=None,
        description=None,
        status=None,
        priority=3,
        category_id=None,
        next_action=None,
        resume_prompt=None,
        estimated_minutes=None,
        energy_level=None,
        focus_mode=None,
        task_type='task',
        origin_agent=None,
        capture_source='nl',
        can_agent_execute=False,
        needs_user_input=False,
        autonomous_safe=False,
        waiting_question=None,
        created_by='system_engineer',
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_project_args(**kwargs):
    defaults = dict(
        slug=None,
        title=None,
        description=None,
        status='hopper',
        category_id=None,
        owner_agent='system_engineer',
        goal=None,
        default_context=None,
        created_by='system_engineer',
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_status_args(task_id, created_by='system_engineer'):
    return SimpleNamespace(task_id=task_id, created_by=created_by)


def make_project_status_args(project_id, created_by='system_engineer'):
    return SimpleNamespace(project_id=project_id, created_by=created_by)


def make_project_rename_args(project_id, title, created_by='system_engineer'):
    return SimpleNamespace(project_id=project_id, title=title, created_by=created_by)


def make_project_binding_args(project_id, created_by='system_engineer', **kwargs):
    defaults = dict(
        project_id=project_id,
        conversation_provider=None,
        conversation_surface=None,
        conversation_channel_id=None,
        conversation_thread_id=None,
        conversation_session_key=None,
        conversation_label=None,
        canonical=False,
        canonical_false=False,
        created_by=created_by,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_note_args(entity_type, entity_id, content, created_by='system_engineer'):
    return SimpleNamespace(entity_type=entity_type, entity_id=entity_id, note_type='note', title=None, content=content, created_by=created_by)


def make_session_args(task_id, created_by='system_engineer', session_id=None, notes=None):
    return SimpleNamespace(
        task_id=task_id,
        session_type='work',
        planned_minutes=None,
        estimated_human_minutes=None,
        estimated_agent_minutes=None,
        estimation_confidence=None,
        needs_confirmation=False,
        notes=notes,
        created_by=created_by,
        session_id=session_id,
        final_human_minutes=None,
        final_agent_minutes=None,
        confirm=False,
    )


def run_nl(args):
    text = args.text.strip()
    lowered = re.sub(r'\s+', ' ', text.lower()).strip()

    if lowered in {'show projects', 'list projects'}:
        return list_projects()

    if lowered in {'show current', 'show current task', 'show active', 'show active tasks'}:
        return show_current()

    if lowered in {'show paused', 'show paused tasks'}:
        return show_paused()

    if lowered in {'show waiting', 'show waiting tasks'}:
        return show_waiting()

    if lowered in {'refresh dashboard', 'refresh build manager dashboard'}:
        return print_json({'ok': True, 'message': 'dashboard refresh requested'})

    m = re.match(r'^capture (?:(project|task|note)\s*:\s*)?(.+)$', text, re.I | re.S)
    if m:
        kind = (m.group(1) or 'project').lower()
        capture_text = m.group(2).strip()
        return run_capture(SimpleNamespace(text=capture_text, kind=kind, source='nl', created_by=args.created_by, title=None))

    if lowered in {'show captures', 'list captures', 'show captured items', 'list captured items'}:
        return list_captures(SimpleNamespace(kind=None, limit=20))

    if lowered in {'show review queue', 'list review queue', 'show review-ready projects', 'list review-ready projects'}:
        return list_review_queue(SimpleNamespace(limit=20))

    if lowered in {'show design queue', 'list design queue', 'show design-ready projects', 'list design-ready projects'}:
        return list_design_queue(SimpleNamespace(limit=20))

    if lowered in {'show planning queue', 'list planning queue', 'show planning-ready projects', 'list planning-ready projects'}:
        return list_planning_queue(SimpleNamespace(limit=20))

    if lowered in {'show build queue', 'list build queue', 'show build-ready projects', 'list build-ready projects'}:
        return list_build_queue(SimpleNamespace(limit=20))

    m = re.match(r'^(show|list) project (\d+) tasks$', lowered)
    if m:
        return list_project_tasks(SimpleNamespace(project_id=int(m.group(2))))

    m = re.match(r'^(show|what is) next task for project (\d+)$', lowered)
    if m:
        return show_next_project_task(SimpleNamespace(project_id=int(m.group(2))))

    m = re.match(r'^start next task for project (\d+)$', lowered)
    if m:
        return start_project_task(SimpleNamespace(project_id=int(m.group(1)), task_id=None, created_by=args.created_by))

    m = re.match(r'^start project task (\d+)$', lowered)
    if m:
        return start_project_task(SimpleNamespace(task_id=int(m.group(1)), project_id=None, created_by=args.created_by))

    m = re.match(r'^start review task (\d+)$', lowered)
    if m:
        return start_review_task(SimpleNamespace(task_id=int(m.group(1)), project_id=None, created_by=args.created_by))

    m = re.match(r'^start next review task for project (\d+)$', lowered)
    if m:
        return start_review_task(SimpleNamespace(project_id=int(m.group(1)), task_id=None, created_by=args.created_by))

    m = re.match(r'^complete review task (\d+)(?: (?:and )?auto advance)?$', lowered)
    if m:
        auto_advance = 'auto advance' in lowered
        return complete_review_task(SimpleNamespace(task_id=int(m.group(1)), created_by=args.created_by, auto_advance=auto_advance))

    m = re.match(r'^(show|list) subtasks for task (\d+)$', lowered)
    if m:
        return list_task_subtasks(SimpleNamespace(task_id=int(m.group(2))))

    m = re.match(r'^(show|what is) next subtask for task (\d+)$', lowered)
    if m:
        return show_next_task_subtask(SimpleNamespace(task_id=int(m.group(2))))

    m = re.match(r'^start next subtask for task (\d+)$', lowered)
    if m:
        return start_task_subtask(SimpleNamespace(task_id=int(m.group(1)), subtask_id=None, created_by=args.created_by))

    m = re.match(r'^start subtask (\d+)$', lowered)
    if m:
        return start_task_subtask(SimpleNamespace(task_id=None, subtask_id=int(m.group(1)), created_by=args.created_by))

    m = re.match(r'^start next review subtask for task (\d+)$', lowered)
    if m:
        return start_review_subtask(SimpleNamespace(task_id=int(m.group(1)), subtask_id=None, created_by=args.created_by))

    m = re.match(r'^start review subtask (\d+)$', lowered)
    if m:
        return start_review_subtask(SimpleNamespace(task_id=None, subtask_id=int(m.group(1)), created_by=args.created_by))

    m = re.match(r'^complete review subtask (\d+)(?: (?:and )?auto advance)?$', lowered)
    if m:
        auto_advance = 'auto advance' in lowered
        return complete_review_subtask(SimpleNamespace(subtask_id=int(m.group(1)), created_by=args.created_by, auto_advance=auto_advance))

    m = re.match(r'^complete subtask (\d+)(?: (?:and )?auto advance)?$', lowered)
    if m:
        auto_advance = 'auto advance' in lowered
        return complete_task_subtask(SimpleNamespace(subtask_id=int(m.group(1)), created_by=args.created_by, auto_advance=auto_advance))

    m = re.match(r'^generate subtasks for task (\d+)$', lowered)
    if m:
        return generate_task_subtasks(SimpleNamespace(task_id=int(m.group(1)), created_by=args.created_by))

    m = re.match(r'^generate subtasks for project (\d+)$', lowered)
    if m:
        return generate_project_subtasks(SimpleNamespace(project_id=int(m.group(1)), created_by=args.created_by))

    m = re.match(r'^sync project (\d+) dependencies$', lowered)
    if m:
        return sync_project_dependencies(SimpleNamespace(project_id=int(m.group(1)), created_by=args.created_by))

    m = re.match(r'^sync project (\d+) task order$', lowered)
    if m:
        return sync_project_task_order(SimpleNamespace(project_id=int(m.group(1)), created_by=args.created_by))

    m = re.match(r'^complete project task (\d+)(?: (?:and )?auto advance)?$', lowered)
    if m:
        auto_advance = 'auto advance' in lowered
        return complete_project_task(SimpleNamespace(task_id=int(m.group(1)), created_by=args.created_by, auto_advance=auto_advance))

    m = re.match(r'^(show|list) (project|task|note) captures$', lowered)
    if m:
        return list_captures(SimpleNamespace(kind=m.group(2), limit=20))

    m = re.match(r'^review project (\d+)$', lowered)
    if m:
        return run_review(SimpleNamespace(project_id=int(m.group(1)), created_by=args.created_by))

    m = re.match(r'^design project (\d+)$', lowered)
    if m:
        return run_design(SimpleNamespace(project_id=int(m.group(1)), created_by=args.created_by))

    m = re.match(r'^plan project (\d+)$', lowered)
    if m:
        return run_planning(SimpleNamespace(project_id=int(m.group(1)), created_by=args.created_by))

    m = re.match(r'^build project (\d+)$', lowered)
    if m:
        return run_build(SimpleNamespace(project_id=int(m.group(1)), created_by=args.created_by))

    m = re.match(r'^review capture (project|task|note) (\d+)$', lowered)
    if m:
        requested_kind = m.group(1)
        entity_type = 'project' if requested_kind == 'project' else 'task'
        return review_capture(SimpleNamespace(entity_type=entity_type, entity_id=int(m.group(2))))

    m = re.match(r'^promote capture (project|task|note) (\d+)(?: to ([a-z]+))?$', lowered)
    if m:
        requested_kind = m.group(1)
        entity_type = 'project' if requested_kind == 'project' else 'task'
        return promote_capture(SimpleNamespace(entity_type=entity_type, entity_id=int(m.group(2)), to_status=m.group(3), created_by=args.created_by))

    m = re.match(r'^(shelve|park) capture (project|task|note) (\d+)$', lowered)
    if m:
        requested_kind = m.group(2)
        entity_type = 'project' if requested_kind == 'project' else 'task'
        return shelve_capture(SimpleNamespace(entity_type=entity_type, entity_id=int(m.group(3)), created_by=args.created_by))

    m = re.match(r'^(archive|reject) capture (project|task|note) (\d+)$', lowered)
    if m:
        requested_kind = m.group(2)
        entity_type = 'project' if requested_kind == 'project' else 'task'
        return archive_capture(SimpleNamespace(entity_type=entity_type, entity_id=int(m.group(3)), created_by=args.created_by))

    m = re.match(r'^(show|list) (captured|queued|active|paused|parked|planned|waiting|done|archived) tasks$', lowered)
    if m:
        return list_tasks(m.group(2))

    m = re.match(r'^create a project called (.+)$', text, re.I)
    if m:
        title = m.group(1).strip().strip('"').strip("'")
        return create_project(make_project_args(title=title, slug=slugify(title), created_by=args.created_by))

    m = re.match(r'^(create|add) (a )?project called (.+)$', text, re.I)
    if m:
        title = m.group(3).strip().strip('"').strip("'")
        return create_project(make_project_args(title=title, slug=slugify(title), created_by=args.created_by))

    m = re.match(r'^add a task called (.+)$', text, re.I)
    if m:
        title = m.group(1).strip().strip('"').strip("'")
        return create_task(make_task_args(title=title, created_by=args.created_by))

    m = re.match(r'^add a task called (.+) to project (\d+)$', text, re.I)
    if m:
        title = m.group(1).strip().strip('"').strip("'")
        project_id = int(m.group(2))
        return create_task(make_task_args(title=title, project_id=project_id, created_by=args.created_by))

    m = re.match(r'^add a subtask called (.+) to task (.+)$', text, re.I)
    if m:
        title = m.group(1).strip().strip('"').strip("'")
        parent_ref = m.group(2).strip()
        parent_task_id = resolve_task_reference(parent_ref)
        return create_task(make_task_args(title=title, created_by=args.created_by), parent_task_id=parent_task_id)

    m = re.match(r'^mark task (.+) active$', text, re.I)
    if m:
        task_id = resolve_task_reference(m.group(1))
        return update_task_status(make_status_args(task_id, args.created_by), 'active', 'task_marked_active')

    m = re.match(r'^mark task (.+) done$', text, re.I)
    if m:
        task_id = resolve_task_reference(m.group(1))
        return update_task_status(make_status_args(task_id, args.created_by), 'done', 'task_marked_done')

    m = re.match(r'^(set|move|update) task (.+?) to (captured|queued|active|paused|parked|planned|waiting|done|archived)$', text, re.I)
    if m:
        task_id = resolve_task_reference(m.group(2))
        return update_task_status(make_status_args(task_id, args.created_by), m.group(3).lower())

    m = re.match(r'^(set|move|update) project (.+?) to (hopper|capture|evaluation|design|planning|build|support|parked|archived)$', text, re.I)
    if m:
        project_id = resolve_project_reference(m.group(2))
        return update_project_status(make_project_status_args(project_id, args.created_by), m.group(3).lower())

    m = re.match(r'^rename project (.+?) to (.+)$', text, re.I)
    if m:
        project_id = resolve_project_reference(m.group(1))
        title = m.group(2).strip().strip('"').strip("'")
        return rename_project(make_project_rename_args(project_id, title, args.created_by))

    m = re.match(r'^(show|what is) project (.+?) binding$', text, re.I)
    if m:
        project_id = resolve_project_reference(m.group(2))
        return show_project_binding(make_project_binding_args(project_id, args.created_by))

    m = re.match(r'^clear project (.+?) binding$', text, re.I)
    if m:
        project_id = resolve_project_reference(m.group(1))
        return clear_project_binding(make_project_binding_args(project_id, args.created_by))

    m = re.match(r'^bind project (.+?) to ([a-z0-9_-]+) channel ([^\s]+)(?: thread ([^\s]+))?(?: label (.+))?$', text, re.I)
    if m:
        project_id = resolve_project_reference(m.group(1))
        provider = m.group(2).strip().lower()
        channel_id = m.group(3).strip()
        thread_id = m.group(4).strip() if m.group(4) else None
        label = m.group(5).strip().strip('"').strip("'") if m.group(5) else None
        return set_project_binding(make_project_binding_args(
            project_id,
            args.created_by,
            conversation_provider=provider,
            conversation_surface=provider,
            conversation_channel_id=channel_id,
            conversation_thread_id=thread_id,
            conversation_label=label,
            canonical=True,
        ))

    m = re.match(r'^add a note to task (.+) saying (.+)$', text, re.I)
    if m:
        task_id = resolve_task_reference(m.group(1))
        content = m.group(2).strip().strip('"').strip("'")
        return add_note(make_note_args('task', task_id, content, args.created_by))

    m = re.match(r'^add a note to project (.+) saying (.+)$', text, re.I)
    if m:
        project_id = resolve_project_reference(m.group(1))
        content = m.group(2).strip().strip('"').strip("'")
        return add_note(make_note_args('project', project_id, content, args.created_by))

    m = re.match(r'^start a work session for task (.+)$', text, re.I)
    if m:
        task_id = resolve_task_reference(m.group(1))
        return start_work_session(make_session_args(task_id, args.created_by))

    if re.match(r'^stop the current work session$', lowered):
        task_id = resolve_task_reference('current')
        return stop_work_session(make_session_args(task_id, args.created_by))

    print_json({'clarification': 'I can handle create project, create task, create subtask, list/show tasks, update task or project status, rename a project, show/set/clear project binding, add notes, and start/stop work session'})



def build_parser():
    parser = argparse.ArgumentParser(description='Minimal OpenClaw Build Manager runtime')
    sub = parser.add_subparsers(dest='command', required=True)

    p = sub.add_parser('create-project')
    p.add_argument('--slug', required=True)
    p.add_argument('--title', required=True)
    p.add_argument('--description')
    p.add_argument('--status', default='hopper')
    p.add_argument('--category-id', type=int)
    p.add_argument('--owner-agent', default='system_engineer')
    p.add_argument('--goal')
    p.add_argument('--default-context')
    p.add_argument('--conversation-provider')
    p.add_argument('--conversation-surface')
    p.add_argument('--conversation-channel-id')
    p.add_argument('--conversation-thread-id')
    p.add_argument('--conversation-session-key')
    p.add_argument('--conversation-label')
    p.add_argument('--canonical', action='store_true')
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=create_project)

    p = sub.add_parser('list-projects')
    p.add_argument('--status', choices=sorted(VALID_PROJECT_STATUSES))
    p.set_defaults(func=lambda args: list_projects(args.status))

    p = sub.add_parser('create-task')
    p.add_argument('--project-id', type=int)
    p.add_argument('--title', required=True)
    p.add_argument('--description')
    p.add_argument('--status')
    p.add_argument('--priority', type=int, default=3)
    p.add_argument('--category-id', type=int)
    p.add_argument('--next-action')
    p.add_argument('--resume-prompt')
    p.add_argument('--estimated-minutes', type=int)
    p.add_argument('--energy-level')
    p.add_argument('--focus-mode')
    p.add_argument('--task-type', default='task')
    p.add_argument('--origin-agent')
    p.add_argument('--capture-source')
    p.add_argument('--can-agent-execute', action='store_true')
    p.add_argument('--needs-user-input', action='store_true')
    p.add_argument('--autonomous-safe', action='store_true')
    p.add_argument('--waiting-question')
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=lambda args: create_task(args))

    p = sub.add_parser('create-subtask')
    p.add_argument('--parent-task-id', required=True, type=int)
    p.add_argument('--project-id', type=int)
    p.add_argument('--title', required=True)
    p.add_argument('--description')
    p.add_argument('--status')
    p.add_argument('--priority', type=int, default=3)
    p.add_argument('--category-id', type=int)
    p.add_argument('--next-action')
    p.add_argument('--resume-prompt')
    p.add_argument('--estimated-minutes', type=int)
    p.add_argument('--energy-level')
    p.add_argument('--focus-mode')
    p.add_argument('--task-type', default='subtask')
    p.add_argument('--origin-agent')
    p.add_argument('--capture-source')
    p.add_argument('--can-agent-execute', action='store_true')
    p.add_argument('--needs-user-input', action='store_true')
    p.add_argument('--autonomous-safe', action='store_true')
    p.add_argument('--waiting-question')
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=lambda args: create_task(args, parent_task_id=args.parent_task_id))

    p = sub.add_parser('list-tasks')
    p.add_argument('--status', required=True, choices=sorted(VALID_TASK_STATUSES))
    p.set_defaults(func=lambda args: list_tasks(args.status))

    p = sub.add_parser('show-current')
    p.set_defaults(func=lambda args: show_current())

    p = sub.add_parser('show-paused')
    p.set_defaults(func=lambda args: show_paused())

    p = sub.add_parser('show-waiting')
    p.set_defaults(func=lambda args: show_waiting())

    p = sub.add_parser('list-active-tasks')
    p.set_defaults(func=lambda args: list_tasks('active'))

    p = sub.add_parser('list-queued-tasks')
    p.set_defaults(func=lambda args: list_tasks('queued'))

    p = sub.add_parser('mark-task-status')
    p.add_argument('--task-id', required=True, type=int)
    p.add_argument('--status', required=True, choices=sorted(VALID_TASK_STATUSES))
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=lambda args: update_task_status(args, args.status))

    p = sub.add_parser('mark-task-active')
    p.add_argument('--task-id', required=True, type=int)
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=lambda args: update_task_status(args, 'active', 'task_marked_active'))

    p = sub.add_parser('mark-task-done')
    p.add_argument('--task-id', required=True, type=int)
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=lambda args: update_task_status(args, 'done', 'task_marked_done'))

    p = sub.add_parser('mark-project-status')
    p.add_argument('--project-id', required=True, type=int)
    p.add_argument('--status', required=True, choices=sorted(VALID_PROJECT_STATUSES))
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=lambda args: update_project_status(args, args.status))

    p = sub.add_parser('rename-project')
    p.add_argument('--project-id', required=True, type=int)
    p.add_argument('--title', required=True)
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=rename_project)

    p = sub.add_parser('show-project-binding')
    p.add_argument('--project-id', required=True, type=int)
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=show_project_binding)

    p = sub.add_parser('set-project-binding')
    p.add_argument('--project-id', required=True, type=int)
    p.add_argument('--conversation-provider')
    p.add_argument('--conversation-surface')
    p.add_argument('--conversation-channel-id')
    p.add_argument('--conversation-thread-id')
    p.add_argument('--conversation-session-key')
    p.add_argument('--conversation-label')
    p.add_argument('--canonical', action='store_true')
    p.add_argument('--not-canonical', action='store_true', dest='canonical_false')
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=set_project_binding)

    p = sub.add_parser('clear-project-binding')
    p.add_argument('--project-id', required=True, type=int)
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=clear_project_binding)

    p = sub.add_parser('add-note')
    p.add_argument('--entity-type', choices=['task', 'project'], required=True)
    p.add_argument('--entity-id', required=True, type=int)
    p.add_argument('--note-type', default='note')
    p.add_argument('--title')
    p.add_argument('--content', required=True)
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=add_note)

    p = sub.add_parser('start-work-session')
    p.add_argument('--task-id', required=True, type=int)
    p.add_argument('--session-type', default='work')
    p.add_argument('--planned-minutes', type=int)
    p.add_argument('--estimated-human-minutes', type=int)
    p.add_argument('--estimated-agent-minutes', type=int)
    p.add_argument('--estimation-confidence', type=float)
    p.add_argument('--needs-confirmation', action='store_true')
    p.add_argument('--notes')
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=start_work_session)

    p = sub.add_parser('stop-work-session')
    p.add_argument('--task-id', required=True, type=int)
    p.add_argument('--session-id', type=int)
    p.add_argument('--final-human-minutes', type=int)
    p.add_argument('--final-agent-minutes', type=int)
    p.add_argument('--notes')
    p.add_argument('--confirm', action='store_true')
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=stop_work_session)

    p = sub.add_parser('capture')
    p.add_argument('text')
    p.add_argument('--kind', choices=['project', 'task', 'note'], default='project')
    p.add_argument('--title')
    p.add_argument('--source', default='cli')
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=run_capture)

    p = sub.add_parser('list-captures')
    p.add_argument('--kind', choices=['project', 'task', 'note'])
    p.add_argument('--limit', type=int, default=20)
    p.set_defaults(func=list_captures)

    p = sub.add_parser('review-capture')
    p.add_argument('--entity-type', choices=['project', 'task'], required=True)
    p.add_argument('--entity-id', required=True, type=int)
    p.set_defaults(func=review_capture)

    p = sub.add_parser('list-review-queue')
    p.add_argument('--limit', type=int, default=20)
    p.set_defaults(func=list_review_queue)

    p = sub.add_parser('run-review')
    p.add_argument('--project-id', required=True, type=int)
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=run_review)

    p = sub.add_parser('list-design-queue')
    p.add_argument('--limit', type=int, default=20)
    p.set_defaults(func=list_design_queue)

    p = sub.add_parser('run-design')
    p.add_argument('--project-id', required=True, type=int)
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=run_design)

    p = sub.add_parser('list-planning-queue')
    p.add_argument('--limit', type=int, default=20)
    p.set_defaults(func=list_planning_queue)

    p = sub.add_parser('run-planning')
    p.add_argument('--project-id', required=True, type=int)
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=run_planning)

    p = sub.add_parser('list-build-queue')
    p.add_argument('--limit', type=int, default=20)
    p.set_defaults(func=list_build_queue)

    p = sub.add_parser('run-build')
    p.add_argument('--project-id', required=True, type=int)
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=run_build)

    p = sub.add_parser('list-project-tasks')
    p.add_argument('--project-id', required=True, type=int)
    p.set_defaults(func=list_project_tasks)

    p = sub.add_parser('show-next-project-task')
    p.add_argument('--project-id', required=True, type=int)
    p.set_defaults(func=show_next_project_task)

    p = sub.add_parser('start-project-task')
    p.add_argument('--project-id', type=int)
    p.add_argument('--task-id', type=int)
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=start_project_task)

    p = sub.add_parser('start-review-task')
    p.add_argument('--project-id', type=int)
    p.add_argument('--task-id', type=int)
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=start_review_task)

    p = sub.add_parser('complete-review-task')
    p.add_argument('--task-id', required=True, type=int)
    p.add_argument('--auto-advance', action='store_true')
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=complete_review_task)

    p = sub.add_parser('list-task-subtasks')
    p.add_argument('--task-id', required=True, type=int)
    p.set_defaults(func=list_task_subtasks)

    p = sub.add_parser('show-next-task-subtask')
    p.add_argument('--task-id', required=True, type=int)
    p.set_defaults(func=show_next_task_subtask)

    p = sub.add_parser('start-task-subtask')
    p.add_argument('--task-id', type=int)
    p.add_argument('--subtask-id', type=int)
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=start_task_subtask)

    p = sub.add_parser('start-review-subtask')
    p.add_argument('--task-id', type=int)
    p.add_argument('--subtask-id', type=int)
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=start_review_subtask)

    p = sub.add_parser('complete-review-subtask')
    p.add_argument('--subtask-id', required=True, type=int)
    p.add_argument('--auto-advance', action='store_true')
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=complete_review_subtask)

    p = sub.add_parser('complete-task-subtask')
    p.add_argument('--subtask-id', required=True, type=int)
    p.add_argument('--auto-advance', action='store_true')
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=complete_task_subtask)

    p = sub.add_parser('generate-task-subtasks')
    p.add_argument('--task-id', required=True, type=int)
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=generate_task_subtasks)

    p = sub.add_parser('generate-project-subtasks')
    p.add_argument('--project-id', required=True, type=int)
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=generate_project_subtasks)

    p = sub.add_parser('sync-project-dependencies')
    p.add_argument('--project-id', required=True, type=int)
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=sync_project_dependencies)

    p = sub.add_parser('sync-project-task-order')
    p.add_argument('--project-id', required=True, type=int)
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=sync_project_task_order)

    p = sub.add_parser('complete-project-task')
    p.add_argument('--task-id', required=True, type=int)
    p.add_argument('--auto-advance', action='store_true')
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=complete_project_task)

    p = sub.add_parser('promote-capture')
    p.add_argument('--entity-type', choices=['project', 'task'], required=True)
    p.add_argument('--entity-id', required=True, type=int)
    p.add_argument('--to-status')
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=promote_capture)

    p = sub.add_parser('shelve-capture')
    p.add_argument('--entity-type', choices=['project', 'task'], required=True)
    p.add_argument('--entity-id', required=True, type=int)
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=shelve_capture)

    p = sub.add_parser('archive-capture')
    p.add_argument('--entity-type', choices=['project', 'task'], required=True)
    p.add_argument('--entity-id', required=True, type=int)
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=archive_capture)

    p = sub.add_parser('nl')
    p.add_argument('text')
    p.add_argument('--created-by', default='system_engineer')
    p.set_defaults(func=run_nl)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
