#!/usr/bin/env python3
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / 'config' / 'build_manager.json'
OBSIDIAN_HOPPER = Path('/mnt/d/Dropbox/Obsidian/OpenClaw/Build_Manager/Hopper')
CAPTURE_PROJECT_PROMOTION_STATUSES = {'evaluation', 'planning', 'build', 'support', 'parked', 'archived'}
CAPTURE_TASK_PROMOTION_STATUSES = {'queued', 'active', 'parked', 'done', 'archived'}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def db_path() -> Path:
    cfg = load_config()
    return (CONFIG_PATH.parent / cfg['database']['path']).resolve()


def slugify(text: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
    return slug or 'capture'


def derive_title(raw_text: str, explicit_title: str | None = None) -> str:
    if explicit_title and explicit_title.strip():
        return explicit_title.strip()
    first_line = next((line.strip() for line in raw_text.splitlines() if line.strip()), '').strip()
    if not first_line:
        return 'Untitled capture'
    candidate = re.sub(r'^[\-\*\d\.\)\s]+', '', first_line).strip()
    if len(candidate) <= 80:
        return candidate or 'Untitled capture'
    shortened = candidate[:80].rsplit(' ', 1)[0].strip(' ,:;-')
    return shortened or candidate[:80].rstrip(' ,:;-') or 'Untitled capture'


def summarize(raw_text: str) -> str:
    clean = ' '.join(raw_text.split())
    if not clean:
        return 'No summary available yet.'
    return clean[:280] + ('...' if len(clean) > 280 else '')


def infer_problem(raw_text: str) -> str:
    lowered = raw_text.lower()
    if 'because' in lowered:
        return raw_text[lowered.index('because') + len('because'):].strip() or 'Needs clarification.'
    if 'so that' in lowered:
        return raw_text[lowered.index('so that') + len('so that'):].strip() or 'Needs clarification.'
    return 'Needs clarification from the raw capture.'


def infer_outcome(raw_text: str) -> str:
    lowered = raw_text.lower()
    for marker in ['so i can', 'so we can', 'so that', 'to help']:
        if marker in lowered:
            return raw_text[lowered.index(marker) + len(marker):].strip() or 'Needs clarification.'
    return 'Initial capture stored for later clarification.'


def build_capture_package(kind: str, raw_text: str, explicit_title: str | None = None, source: str = 'chat') -> dict:
    title = derive_title(raw_text, explicit_title)
    recommendation = 'convert to task' if kind == 'task' else 'move to Capture'
    next_stage = 'task queue' if kind == 'task' else 'Capture'
    return {
        'candidate_title': title,
        'raw_request': raw_text.strip(),
        'plain_language_summary': summarize(raw_text),
        'problem_to_solve': infer_problem(raw_text),
        'desired_outcome': infer_outcome(raw_text),
        'likely_scope_v1': 'Capture the core request, preserve the source wording, and create one stored intake record.',
        'not_in_scope_yet': 'Detailed design, phased planning, dashboard work, GitHub packaging, and broader workflow routing.',
        'constraints_guardrails': 'Keep capture minimal and reversible. Do not over-structure the request before review.',
        'source_material_and_references': f'Source: {source}',
        'open_questions': 'What is the smallest useful next step after capture review?',
        'complexity_recommendation': {
            'model_tier': 'standard',
            'thinking_level': 'low',
            'why': 'This is a first-pass intake record, not a design or planning pass.',
        },
        'recommendation': recommendation,
        'approval_object': {
            'what_greg_is_approving': 'Whether this capture is accurately framed and should be kept as the stored intake record.',
            'next_stage_if_approved': next_stage,
        },
    }


def render_capture_markdown(package: dict, kind: str, entity_type: str, entity_id: int, created_at: str) -> str:
    complexity = package['complexity_recommendation']
    approval = package['approval_object']
    return f"""---
created: {created_at}
updated: {created_at}
parent: \"[[Hopper]]\"
capture_kind: {kind}
entity_type: {entity_type}
entity_id: {entity_id}
status: captured
---
# Capture Package

## Candidate title
{package['candidate_title']}

## Raw request / source wording
{package['raw_request']}

## Plain-language summary
{package['plain_language_summary']}

## What problem this seems to solve
{package['problem_to_solve']}

## Desired outcome
{package['desired_outcome']}

## Likely scope for v1
{package['likely_scope_v1']}

## Not in scope yet
{package['not_in_scope_yet']}

## Constraints / guardrails
{package['constraints_guardrails']}

## Source material and references
{package['source_material_and_references']}

## Open questions
{package['open_questions']}

## Complexity recommendation
- model tier: {complexity['model_tier']}
- thinking level: {complexity['thinking_level']}
- why: {complexity['why']}

## Recommendation
- {package['recommendation']}

## Approval object
- what Greg is approving: {approval['what_greg_is_approving']}
- next stage if approved: {approval['next_stage_if_approved']}
"""


def write_obsidian_capture(package: dict, kind: str, entity_type: str, entity_id: int, created_at: str) -> Path:
    OBSIDIAN_HOPPER.mkdir(parents=True, exist_ok=True)
    stamp = created_at.replace(':', '').replace('-', '')[:15]
    filename = f"{stamp}-{slugify(package['candidate_title'])}-capture.md"
    note_path = OBSIDIAN_HOPPER / filename
    note_path.write_text(render_capture_markdown(package, kind, entity_type, entity_id, created_at))
    return note_path


def log_activity(conn, entity_type: str, entity_id: int, event_type: str, payload: dict, created_by: str):
    conn.execute(
        '''
        INSERT INTO activity_log (entity_type, entity_id, event_type, payload_json, created_at, created_by)
        VALUES (?, ?, ?, ?, ?, ?)
        ''',
        (entity_type, entity_id, event_type, json.dumps(payload, sort_keys=True), now_iso(), created_by),
    )


def create_project_capture(conn, package: dict, created_by: str, source: str) -> int:
    ts = now_iso()
    slug_base = slugify(package['candidate_title'])
    slug = slug_base
    i = 2
    while conn.execute('SELECT 1 FROM projects WHERE slug = ?', (slug,)).fetchone():
        slug = f'{slug_base}-{i}'
        i += 1
    cur = conn.execute(
        '''
        INSERT INTO projects (slug, title, description, status, owner_agent, goal, default_context, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            slug,
            package['candidate_title'],
            package['plain_language_summary'],
            'capture',
            created_by,
            package['desired_outcome'],
            package['raw_request'],
            ts,
            ts,
        ),
    )
    project_id = cur.lastrowid
    conn.execute(
        '''
        INSERT INTO notes (entity_type, entity_id, note_type, title, content, created_at, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''',
        ('project', project_id, 'capture_package', 'Capture Package', render_capture_markdown(package, 'project', 'project', project_id, ts), ts, created_by),
    )
    log_activity(conn, 'project', project_id, 'project_captured', {'source': source, 'title': package['candidate_title']}, created_by)
    return project_id


def create_task_capture(conn, package: dict, created_by: str, source: str, kind: str) -> int:
    ts = now_iso()
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
            None,
            None,
            package['candidate_title'],
            package['plain_language_summary'],
            'captured',
            3,
            'Review capture package and decide whether to promote, convert, or shelve.',
            package['raw_request'],
            kind,
            created_by,
            source,
            0,
            0,
            0,
            0,
            1,
            package['open_questions'],
            ts,
            ts,
        ),
    )
    task_id = cur.lastrowid
    conn.execute(
        '''
        INSERT INTO notes (entity_type, entity_id, note_type, title, content, created_at, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''',
        ('task', task_id, 'capture_package', 'Capture Package', render_capture_markdown(package, kind, 'task', task_id, ts), ts, created_by),
    )
    log_activity(conn, 'task', task_id, 'task_captured', {'source': source, 'title': package['candidate_title'], 'kind': kind}, created_by)
    return task_id


def list_captures(args):
    kind = (getattr(args, 'kind', None) or '').strip().lower() or None
    limit = int(getattr(args, 'limit', 20) or 20)
    if kind not in {None, 'project', 'task', 'note'}:
        raise SystemExit('capture kind must be one of: project, task, note')

    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    try:
        result = {}
        if kind in {None, 'project'}:
            project_rows = conn.execute(
                '''
                SELECT id, slug, title, status, updated_at
                FROM projects
                WHERE status = 'capture'
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                ''',
                (limit,),
            ).fetchall()
            result['projects'] = [
                {
                    'id': row['id'],
                    'slug': row['slug'],
                    'title': row['title'],
                    'status': row['status'],
                    'updated_at': row['updated_at'],
                }
                for row in project_rows
            ]

        if kind in {None, 'task', 'note'}:
            task_filter = None if kind in {None, 'project'} else kind
            task_rows = conn.execute(
                '''
                SELECT id, title, status, task_type, capture_source, updated_at
                FROM tasks
                WHERE status = 'captured'
                  AND (? IS NULL OR task_type = ?)
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                ''',
                (task_filter, task_filter, limit),
            ).fetchall()
            result['tasks'] = [
                {
                    'id': row['id'],
                    'title': row['title'],
                    'status': row['status'],
                    'task_type': row['task_type'],
                    'capture_source': row['capture_source'],
                    'updated_at': row['updated_at'],
                }
                for row in task_rows
            ]

        result['ok'] = True
        result['workflow'] = 'capture-review'
        print(json.dumps(result, indent=2, sort_keys=True))
        return result
    finally:
        conn.close()


def review_capture(args):
    entity_type = (getattr(args, 'entity_type', None) or '').strip().lower()
    entity_id = getattr(args, 'entity_id', None)
    if entity_type not in {'project', 'task'}:
        raise SystemExit('entity_type must be project or task')
    if entity_id is None:
        raise SystemExit('entity_id is required')

    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    try:
        if entity_type == 'project':
            row = conn.execute(
                '''
                SELECT id, slug, title, description, status, goal, default_context, created_at, updated_at
                FROM projects
                WHERE id = ?
                ''',
                (entity_id,),
            ).fetchone()
        else:
            row = conn.execute(
                '''
                SELECT id, project_id, parent_task_id, title, description, status, task_type,
                       next_action, resume_prompt, capture_source, created_at, updated_at
                FROM tasks
                WHERE id = ?
                ''',
                (entity_id,),
            ).fetchone()
        if not row:
            raise SystemExit(f'{entity_type} not found: {entity_id}')

        capture_note = conn.execute(
            '''
            SELECT id, title, content, created_at, created_by
            FROM notes
            WHERE entity_type = ? AND entity_id = ? AND note_type = 'capture_package'
            ORDER BY id DESC
            LIMIT 1
            ''',
            (entity_type, entity_id),
        ).fetchone()
        latest_activity = conn.execute(
            '''
            SELECT event_type, payload_json, created_at, created_by
            FROM activity_log
            WHERE entity_type = ? AND entity_id = ?
            ORDER BY id DESC
            LIMIT 1
            ''',
            (entity_type, entity_id),
        ).fetchone()

        result = {
            'ok': True,
            'workflow': 'capture-review',
            'entity_type': entity_type,
            'entity': dict(row),
            'capture_note': dict(capture_note) if capture_note else None,
            'latest_activity': dict(latest_activity) if latest_activity else None,
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return result
    finally:
        conn.close()


def promote_capture(args):
    entity_type = (getattr(args, 'entity_type', None) or '').strip().lower()
    entity_id = getattr(args, 'entity_id', None)
    created_by = getattr(args, 'created_by', None) or 'system_engineer'
    event_type = getattr(args, 'event_type', None) or 'capture_promoted'
    action = getattr(args, 'action', None) or 'promoted'
    if entity_type not in {'project', 'task'}:
        raise SystemExit('entity_type must be project or task')
    if entity_id is None:
        raise SystemExit('entity_id is required')

    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        ts = now_iso()
        if entity_type == 'project':
            row = conn.execute('SELECT id, title, status FROM projects WHERE id = ?', (entity_id,)).fetchone()
            if not row:
                raise SystemExit(f'project not found: {entity_id}')
            if row['status'] != 'capture':
                raise SystemExit(f'project {entity_id} is not in capture status')
            to_status = (getattr(args, 'to_status', None) or 'evaluation').strip().lower()
            if to_status not in CAPTURE_PROJECT_PROMOTION_STATUSES:
                allowed = ', '.join(sorted(CAPTURE_PROJECT_PROMOTION_STATUSES))
                raise SystemExit(f'project promotion status must be one of: {allowed}')
            conn.execute(
                'UPDATE projects SET status = ?, updated_at = ? WHERE id = ?',
                (to_status, ts, entity_id),
            )
            log_activity(conn, 'project', entity_id, event_type, {
                'action': action,
                'from_status': 'capture',
                'to_status': to_status,
                'title': row['title'],
            }, created_by)
        else:
            row = conn.execute('SELECT id, title, status, task_type FROM tasks WHERE id = ?', (entity_id,)).fetchone()
            if not row:
                raise SystemExit(f'task not found: {entity_id}')
            if row['status'] != 'captured':
                raise SystemExit(f'task {entity_id} is not in captured status')
            to_status = (getattr(args, 'to_status', None) or 'queued').strip().lower()
            if to_status not in CAPTURE_TASK_PROMOTION_STATUSES:
                allowed = ', '.join(sorted(CAPTURE_TASK_PROMOTION_STATUSES))
                raise SystemExit(f'task promotion status must be one of: {allowed}')
            conn.execute(
                '''
                UPDATE tasks
                SET status = ?,
                    human_active = ?,
                    last_worked_at = CASE WHEN ? = 'active' THEN ? ELSE last_worked_at END,
                    updated_at = ?
                WHERE id = ?
                ''',
                (to_status, 1 if to_status == 'active' else 0, to_status, ts, ts, entity_id),
            )
            log_activity(conn, 'task', entity_id, event_type, {
                'action': action,
                'from_status': 'captured',
                'to_status': to_status,
                'title': row['title'],
                'task_type': row['task_type'],
            }, created_by)

        conn.commit()
        result = {
            'ok': True,
            'workflow': 'capture-review',
            'action': action,
            'entity_type': entity_type,
            'entity_id': entity_id,
            'from_status': row['status'],
            'to_status': to_status,
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return result
    finally:
        conn.close()


def shelve_capture(args):
    return promote_capture(SimpleNamespace(
        entity_type=getattr(args, 'entity_type', None),
        entity_id=getattr(args, 'entity_id', None),
        to_status='parked',
        created_by=getattr(args, 'created_by', None) or 'system_engineer',
        event_type='capture_shelved',
        action='shelved',
    ))


def archive_capture(args):
    return promote_capture(SimpleNamespace(
        entity_type=getattr(args, 'entity_type', None),
        entity_id=getattr(args, 'entity_id', None),
        to_status='archived',
        created_by=getattr(args, 'created_by', None) or 'system_engineer',
        event_type='capture_archived',
        action='archived',
    ))


def run_capture(args):
    raw_text = args.text.strip()
    if not raw_text:
        raise SystemExit('capture text is required')
    kind = (getattr(args, 'kind', None) or 'project').strip().lower()
    if kind not in {'project', 'task', 'note'}:
        raise SystemExit('capture kind must be one of: project, task, note')

    source = getattr(args, 'source', None) or 'chat'
    created_by = getattr(args, 'created_by', None) or 'system_engineer'
    explicit_title = getattr(args, 'title', None)
    package = build_capture_package(kind=kind, raw_text=raw_text, explicit_title=explicit_title, source=source)

    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        if kind == 'project':
            entity_type = 'project'
            entity_id = create_project_capture(conn, package, created_by, source)
        else:
            entity_type = 'task'
            entity_id = create_task_capture(conn, package, created_by, source, kind)
        note_path = write_obsidian_capture(package, kind, entity_type, entity_id, now_iso())
        conn.commit()
    finally:
        conn.close()

    result = {
        'ok': True,
        'workflow': 'capture',
        'kind': kind,
        'entity_type': entity_type,
        'entity_id': entity_id,
        'title': package['candidate_title'],
        'db_path': str(db_path()),
        'obsidian_note_path': str(note_path),
        'recommendation': package['recommendation'],
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return result
