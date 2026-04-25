#!/usr/bin/env python3
import argparse
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
import struct
import zlib

REGISTRY_PATH = Path.home() / '.openclaw' / 'registries' / 'path_registry.json'
BUILD_MANAGER_BASE_PATH = '/build-manager/'
PROMPT_API_BASE_PATH = '/build-manager-api'
TASK_SELECT = '''
SELECT
  t.id,
  t.project_id,
  t.parent_task_id,
  t.title,
  t.description,
  t.status,
  t.priority,
  t.next_action,
  t.waiting_question,
  t.updated_at,
  t.needs_user_input,
  p.title AS project_title
FROM tasks t
LEFT JOIN projects p ON p.id = t.project_id
'''

STATUS_LABELS = {
    'captured': 'Captured',
    'queued': 'Queued',
    'active': 'Active',
    'paused': 'Paused',
    'parked': 'Parked',
    'done': 'Done',
    'archived': 'Archived',
    'planned': 'Planned',
    'waiting': 'Waiting',
    'hopper': 'Hopper',
    'capture': 'Capture',
    'evaluation': 'Evaluation',
    'design': 'Design',
    'planning': 'Planning',
    'build': 'Build',
    'support': 'Support',
}

PROJECT_TASK_STATUS_ORDER = ['planned', 'active', 'waiting', 'done']

PROJECT_LIFECYCLE = [
    ('hopper', 'Hopper', 'Primary intake stage for raw project ideas before they are shaped enough to become a real project workspace.'),
    ('capture', 'Capture', 'Keep adding inputs, desired outcomes, notes, links, references, and lightly curated source material.'),
    ('evaluation', 'Evaluation', 'Clarify the idea, reduce noise, and decide whether it should move forward now.'),
    ('design', 'Design', 'Shape the clearer final picture and define what good looks like.'),
    ('planning', 'Planning', 'Break the design into phases, tasks, subtasks, checkpoints, and execution order.'),
    ('build', 'Build', 'Execute the plan.'),
    ('support', 'Support', 'Handle curation, summaries, cleanup, expert review, and future-growth support after the main build work.'),
    ('parked', 'Parked', 'Intentionally not moving right now, but still worth keeping.'),
    ('archived', 'Archived', 'Closed historical record.'),
]
PROJECT_STATUS_ORDER = [key for key, _, _ in PROJECT_LIFECYCLE]
CURRENT_PROJECT_STATUSES = ['capture', 'evaluation', 'design', 'planning', 'build', 'support']
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

BASE_CSS = """
:root {
  --bg: #0b1020;
  --bg-2: #121935;
  --bg-3: #172142;
  --line: #293760;
  --text: #eef2ff;
  --muted: #9fb0d8;
  --blue: #7cc4ff;
  --yellow: #ffd166;
  --green: #9dd38c;
  --pink: #ff9ca8;
  --anchor-offset: 164px;
}
* { box-sizing: border-box; }
html {
  scroll-behavior: smooth;
  scroll-padding-top: var(--anchor-offset);
}
body {
  margin: 0;
  background: linear-gradient(180deg, #0b1020 0%, #0f1730 100%);
  color: var(--text);
  font: 14px/1.5 Inter, Segoe UI, Arial, sans-serif;
  -webkit-text-size-adjust: 100%;
  overflow-x: hidden;
}
a { color: inherit; text-decoration: none; }
button { font: inherit; }
.page-shell { max-width: 1520px; margin: 0 auto; padding: 0 20px 28px; }
.topbar {
  position: sticky;
  top: 0;
  z-index: 40;
  margin: 0 -20px;
  padding: 10px 20px 12px;
  background: rgba(11, 16, 32, .96);
  border-bottom: 1px solid rgba(41, 55, 96, .9);
  backdrop-filter: blur(14px);
}
.brand-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}
.brand-title { margin: 0; font-size: 18px; overflow-wrap: anywhere; }
.brand-note { margin: 4px 0 0; color: var(--muted); font-size: 12px; }
.brand-status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, .08);
  background: rgba(255, 255, 255, .03);
  color: var(--muted);
  font-size: 12px;
}
.brand-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--yellow);
  box-shadow: 0 0 0 3px rgba(255, 209, 102, .12);
}
.brand-status.is-online .brand-status-dot {
  background: var(--green);
  box-shadow: 0 0 0 3px rgba(157, 211, 140, .12);
}
.brand-status.is-offline .brand-status-dot {
  background: var(--pink);
  box-shadow: 0 0 0 3px rgba(255, 156, 168, .12);
}
.top-meta { color: var(--muted); font-size: 12px; text-align: right; }
.prompt-shell {
  margin-top: 12px;
  padding: 12px;
  border: 1px solid rgba(41, 55, 96, .8);
  border-radius: 16px;
  background: rgba(18, 25, 53, .82);
}
.prompt-form {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
}
.prompt-input {
  width: 100%;
  min-width: 0;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, .04);
  color: var(--text);
}
.prompt-input::placeholder { color: var(--muted); }
.prompt-input:focus {
  outline: 2px solid rgba(124, 196, 255, .3);
  outline-offset: 1px;
  border-color: rgba(124, 196, 255, .55);
}
.prompt-submit {
  padding: 12px 16px;
  border-radius: 12px;
  border: 1px solid rgba(124, 196, 255, .35);
  background: rgba(124, 196, 255, .14);
  color: var(--text);
  cursor: pointer;
}
.prompt-submit:hover:not(:disabled) {
  background: rgba(124, 196, 255, .2);
}
.prompt-submit:disabled {
  opacity: .7;
  cursor: wait;
}
.prompt-status {
  margin-top: 8px;
  color: var(--muted);
  font-size: 12px;
  min-height: 18px;
}
.prompt-status.is-error { color: #ffb4be; }
.prompt-status.is-success { color: var(--green); }
.prompt-response {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(41, 55, 96, .9);
  background: rgba(7, 11, 24, .45);
}
.prompt-response.is-success {
  border-color: rgba(157, 211, 140, .35);
}
.prompt-response.is-error {
  border-color: rgba(255, 156, 168, .35);
}
.prompt-response pre {
  margin: 0;
  white-space: pre-wrap;
  font: 12px/1.45 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  color: var(--text);
}
.primary-nav,
.sub-nav {
  display: flex;
  gap: 8px;
  flex-wrap: nowrap;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: thin;
  -webkit-overflow-scrolling: touch;
}
.primary-nav { margin-top: 10px; }
.sub-nav { margin-top: 10px; padding-top: 10px; border-top: 1px solid rgba(41, 55, 96, .8); }
.nav-link,
.sub-link {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: max-content;
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid transparent;
  background: rgba(255, 255, 255, .03);
  color: var(--muted);
  white-space: nowrap;
}
.nav-link:hover,
.sub-link:hover,
.nav-link.is-active,
.sub-link.is-active {
  border-color: var(--line);
  color: var(--text);
  background: rgba(124, 196, 255, .12);
}
.page-content { padding-top: 18px; }
.hero { margin-bottom: 18px; }
.hero h2 { margin: 0; font-size: 30px; line-height: 1.12; overflow-wrap: anywhere; }
.hero p { margin: 10px 0 0; color: var(--muted); max-width: 980px; }
.panel {
  background: rgba(18, 25, 53, .9);
  border: 1px solid var(--line);
  border-radius: 20px;
  padding: 18px;
  min-width: 0;
}
.panel[id],
.section[id] { scroll-margin-top: var(--anchor-offset); }
.section { margin-top: 18px; }
.section h3 { margin: 0 0 14px; font-size: 18px; }
.label,
.muted,
.sub { color: var(--muted); }
.summary-cards { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }
.mini-card,
.summary-card-link {
  display: block;
  padding: 14px;
  border-radius: 16px;
  border: 1px solid var(--line);
  background: var(--bg-3);
  min-width: 0;
}
.summary-card-link:hover { border-color: rgba(124, 196, 255, .45); }
.mini-card .value,
.summary-card-link .value { font-size: 24px; font-weight: 700; margin-top: 6px; }
.grid-two { display: grid; gap: 18px; grid-template-columns: repeat(2, minmax(0, 1fr)); }
.task-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 12px; }
.task-card,
.project-card,
.project-preview-card,
.task-detail-card {
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 14px;
  background: var(--bg-3);
  min-width: 0;
}
.task-card strong,
.project-card strong,
.project-preview-card strong,
.task-detail-card strong { overflow-wrap: anywhere; }
.task-link {
  display: block;
  width: 100%;
  color: inherit;
  background: none;
  border: none;
  padding: 0;
  text-align: left;
  cursor: pointer;
}
.task-link:hover .task-card-hint,
.task-link.is-active .task-card-hint { color: var(--blue); }
.task-link.is-active { outline: 2px solid rgba(124, 196, 255, .55); outline-offset: 8px; border-radius: 8px; }
.task-card-hint { margin-top: 8px; font-size: 12px; color: var(--muted); }
.task-card-standalone { box-shadow: inset 0 0 0 1px rgba(124, 196, 255, .18); }
.task-card-project { box-shadow: inset 0 0 0 1px rgba(255, 255, 255, .04); }
.task-card-needs-user { box-shadow: inset 0 0 0 1px rgba(255, 209, 102, .24); }
.task-panel-shell { min-height: 220px; }
.task-detail-header { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.detail-grid { display: grid; gap: 14px; grid-template-columns: repeat(2, minmax(0, 1fr)); margin-top: 12px; }
.detail-backlink { font-size: 12px; color: var(--blue); white-space: nowrap; }
.task-template-store { display: none; }
.project-preview-grid { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); }
.project-card { margin-bottom: 12px; }
.project-card:last-child { margin-bottom: 0; }
.project-task-group { margin-top: 14px; }
.project-task-group h4 { margin: 0 0 10px; font-size: 14px; color: var(--muted); }
.project-page-link { display: block; }
.project-page-link:hover { border-color: rgba(124, 196, 255, .45); }
.mini-stats { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; color: var(--muted); font-size: 12px; }
.mini-stats span { padding: 4px 8px; border-radius: 999px; background: rgba(255,255,255,.05); border: 1px solid rgba(255,255,255,.06); }
.status {
  display: inline-block;
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .04em;
  font-weight: 700;
  border: 1px solid transparent;
  margin-right: 8px;
  margin-bottom: 6px;
}
.status-active, .status-design { background: rgba(124,196,255,.14); color: var(--blue); border-color: rgba(124,196,255,.28); }
.status-paused, .status-planning, .status-waiting { background: rgba(255,209,102,.12); color: var(--yellow); border-color: rgba(255,209,102,.28); }
.status-queued, .status-captured, .status-hopper, .status-capture, .status-planned { background: rgba(238,242,255,.08); color: var(--text); border-color: rgba(238,242,255,.18); }
.status-done, .status-build, .status-support { background: rgba(157,211,140,.14); color: var(--green); border-color: rgba(157,211,140,.3); }
.status-evaluation { background: rgba(167,139,250,.15); color: #c4b5fd; border-color: rgba(167,139,250,.32); }
.status-parked, .status-archived { background: rgba(255,123,138,.1); color: var(--pink); border-color: rgba(255,123,138,.25); }
.empty { color: var(--muted); padding: 14px; border: 1px dashed var(--line); border-radius: 16px; }
.callout {
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid var(--line);
  background: linear-gradient(180deg, rgba(124,196,255,.09), rgba(255,255,255,.02));
  margin-top: 14px;
}
.data-table { width: 100%; border-collapse: collapse; border: 1px solid var(--line); border-radius: 16px; overflow: hidden; table-layout: fixed; }
.data-table th,
.data-table td { text-align: left; vertical-align: top; padding: 10px 12px; border-bottom: 1px solid var(--line); overflow-wrap: anywhere; }
.data-table thead th { background: var(--bg-3); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); }
.payload { white-space: pre-wrap; word-break: break-word; max-width: 420px; color: var(--muted); }
code.inline { background: rgba(255,255,255,.06); padding: 2px 6px; border-radius: 6px; border: 1px solid rgba(255,255,255,.06); overflow-wrap: anywhere; }
.page-split { display: grid; gap: 18px; grid-template-columns: minmax(0, 1.15fr) minmax(320px, .85fr); align-items: start; }
.detail-panel-sticky { position: sticky; top: 126px; }
@media (max-width: 1100px) {
  :root { --anchor-offset: 196px; }
  .page-shell { padding: 0 16px 24px; }
  .topbar { margin: 0 -16px; padding: 10px 16px 12px; }
  .brand-note, .top-meta { display: none; }
  .page-split, .grid-two, .detail-grid { grid-template-columns: 1fr; }
  .detail-panel-sticky { position: static; }
}
@media (max-width: 880px) {
  .hero h2 { font-size: 24px; }
  .hero p { font-size: 13px; }
  .summary-cards { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .project-preview-grid { grid-template-columns: 1fr; }
  .panel { padding: 14px; border-radius: 16px; }
  .data-table, .data-table thead, .data-table tbody, .data-table tr, .data-table th, .data-table td { display: block; width: 100%; }
  .data-table thead { display: none; }
  .data-table { border: none; background: transparent; table-layout: auto; }
  .data-table tbody { display: grid; gap: 12px; }
  .data-table tr { border: 1px solid var(--line); border-radius: 16px; background: var(--bg-3); padding: 10px 12px; }
  .data-table td { border: none; padding: 6px 0; min-width: 0; }
  .data-table td::before { content: attr(data-label); display: block; font-size: 11px; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); margin-bottom: 2px; }
  .data-table .empty-cell { padding: 14px; border: 1px dashed var(--line); border-radius: 16px; color: var(--muted); background: transparent; }
  .data-table .empty-cell::before { display: none; }
  .payload { max-width: none; min-width: 0; }
}
@media (max-width: 560px) {
  body { font-size: 13px; }
  .page-shell { padding: 0 10px 18px; }
  .topbar { margin: 0 -10px; padding: 8px 10px 10px; }
  .brand-title { font-size: 14px; }
  .primary-nav, .sub-nav { gap: 5px; }
  .nav-link, .sub-link { padding: 7px 9px; font-size: 11px; }
  .prompt-form { grid-template-columns: 1fr; }
  .prompt-submit { width: 100%; }
  .hero h2 { font-size: 21px; }
  .summary-cards { grid-template-columns: 1fr; }
  .mini-card, .summary-card-link { padding: 12px; }
  .mini-card .value, .summary-card-link .value { font-size: 21px; }
  .task-card, .project-card, .project-preview-card, .task-detail-card, .empty, .callout, .data-table tr { padding: 12px; border-radius: 14px; }
  .task-link.is-active { outline-offset: 6px; }
  .section h3 { font-size: 16px; }
  .status { font-size: 10px; }
}
"""

PROMPT_FORM_SCRIPT = f"""
<script>
  (() => {{
    const form = document.getElementById('build-manager-prompt-form');
    const input = document.getElementById('build-manager-prompt-input');
    const button = document.getElementById('build-manager-prompt-submit');
    const status = document.getElementById('build-manager-prompt-status');
    const responsePanel = document.getElementById('build-manager-prompt-response');
    const responseBody = document.getElementById('build-manager-prompt-response-body');
    const runtimeBadge = document.getElementById('build-manager-runtime-status');
    const runtimeLabel = document.getElementById('build-manager-runtime-label');
    if (!form || !input || !button || !status) return;

    const FLASH_KEY = 'build-manager-prompt-flash';
    const context = {{
      page: form.dataset.page || '',
      project_id: form.dataset.projectId || '',
      task_id: form.dataset.taskId || '',
      current_path: form.dataset.currentPath || window.location.pathname.split('/').pop() || 'index.html',
      current_hash: window.location.hash || '',
    }};

    const setStatus = (message, tone = '') => {{
      status.textContent = message || '';
      status.className = `prompt-status${{tone ? ` is-${{tone}}` : ''}}`;
    }};

    const renderResponse = (payload, tone = 'success') => {{
      if (!responsePanel || !responseBody) return;
      if (!payload) {{
        responsePanel.hidden = true;
        responsePanel.className = 'prompt-response';
        responseBody.textContent = '';
        return;
      }}
      responsePanel.hidden = false;
      responsePanel.className = `prompt-response is-${{tone}}`;
      const parts = [];
      if (payload.message) parts.push(payload.message);
      if (payload.clarification) parts.push(payload.clarification);
      const targetPath = payload.refresh && payload.refresh.target_path;
      if (targetPath) parts.push(`Refresh target: ${{targetPath}}`);
      const bindingScope = payload.binding && payload.binding.scope;
      if (bindingScope) parts.push(`Binding: ${{bindingScope}}`);
      responseBody.textContent = parts.join('\n');
    }};

    try {{
      const saved = window.sessionStorage.getItem(FLASH_KEY);
      if (saved) {{
        window.sessionStorage.removeItem(FLASH_KEY);
        renderResponse(JSON.parse(saved), 'success');
      }}
    }} catch (_error) {{}}

    const setRuntimeStatus = (online, detail = '') => {{
      if (!runtimeBadge || !runtimeLabel) return;
      runtimeBadge.classList.remove('is-online', 'is-offline');
      runtimeBadge.classList.add(online ? 'is-online' : 'is-offline');
      runtimeLabel.textContent = online
        ? (detail ? `OpenClaw online, ${{detail}}` : 'OpenClaw online')
        : (detail ? `OpenClaw offline, ${{detail}}` : 'OpenClaw offline');
    }};

    const probeRuntime = async () => {{
      try {{
        const response = await fetch(`${{window.location.origin}}/`, {{
          cache: 'no-store',
        }});
        if (!response.ok) {{
          setRuntimeStatus(false, `status ${{response.status}}`);
          return;
        }}
        setRuntimeStatus(true);
      }} catch (_error) {{
        setRuntimeStatus(false);
      }}
    }};

    probeRuntime();
    window.addEventListener('online', () => probeRuntime());
    window.addEventListener('offline', () => setRuntimeStatus(false, 'network unavailable'));
    window.setInterval(probeRuntime, 30000);

    form.addEventListener('submit', async (event) => {{
      event.preventDefault();
      const prompt = input.value.trim();
      context.current_hash = window.location.hash || '';
      if (!prompt) {{
        setStatus('Enter a Build Manager command first.', 'error');
        input.focus();
        return;
      }}

      button.disabled = true;
      input.disabled = true;
      setStatus('Running prompt and refreshing the dashboard…');

      try {{
        const response = await fetch(`${{window.location.origin}}{PROMPT_API_BASE_PATH}/prompt`, {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ prompt, ...context }}),
        }});
        const raw = await response.text();
        let data = {{}};
        if (raw.trim()) {{
          try {{
            data = JSON.parse(raw);
          }} catch (_error) {{
            data = {{ message: raw.trim() }};
          }}
        }}
        if (!response.ok || data.ok === false) {{
          const message = data.message
            || data.clarification
            || (response.status === 404 ? 'Prompt API route is not published on this host yet.' : `Prompt failed (${{response.status}}).`);
          setStatus(message, 'error');
          renderResponse(data, 'error');
          probeRuntime();
        }} else {{
          probeRuntime();
          setStatus(data.message || 'Prompt applied. Refreshing…', 'success');
          renderResponse(data, 'success');
          const targetPath = data.refresh && data.refresh.target_path;
          try {{
            window.sessionStorage.setItem(FLASH_KEY, JSON.stringify(data));
          }} catch (_error) {{}}
          setTimeout(() => {{
            if (targetPath) {{
              window.location.href = new URL(targetPath, window.location.href).href;
              return;
            }}
            window.location.reload();
          }}, 900);
          return;
        }}
      }} catch (error) {{
        probeRuntime();
        setStatus(error.message || 'Prompt request failed.', 'error');
        renderResponse({{ message: error.message || 'Prompt request failed.' }}, 'error');
      }} finally {{
        button.disabled = false;
        input.disabled = false;
      }}
    }});
  }})();
</script>
"""

TASK_PANEL_SCRIPT = """
<script>
  (() => {
    const panelBody = document.getElementById('task-panel-body');
    const panel = document.getElementById('task-panel');
    const buttons = Array.from(document.querySelectorAll('.task-link[data-task-id]'));
    if (!panelBody || !panel || !buttons.length) return;

    function setActive(taskId, shouldScroll) {
      const template = document.getElementById(`task-template-${taskId}`);
      if (!template) return;
      panelBody.innerHTML = template.innerHTML;
      buttons.forEach((button) => {
        button.classList.toggle('is-active', button.dataset.taskId === String(taskId));
      });
      if (shouldScroll) {
        panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }

    function selectFromHash(shouldScroll) {
      const hash = window.location.hash || '';
      if (!hash.startsWith('#task-')) return false;
      const taskId = hash.replace('#task-', '');
      if (!document.getElementById(`task-template-${taskId}`)) return false;
      setActive(taskId, shouldScroll);
      return true;
    }

    buttons.forEach((button) => {
      button.addEventListener('click', () => {
        const taskId = button.dataset.taskId;
        history.replaceState(null, '', `#task-${taskId}`);
        const shouldScroll = window.innerWidth < 1100;
        setActive(taskId, shouldScroll);
      });
    });

    window.addEventListener('hashchange', () => {
      selectFromHash(false);
    });

    if (!selectFromHash(false)) {
      setActive(buttons[0].dataset.taskId, false);
    }
  })();
</script>
"""


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None


def fmt_ts(value):
    dt = parse_iso(value)
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC') if dt else '—'


def fmt_minutes(value):
    total = int(value or 0)
    hours, minutes = divmod(total, 60)
    if hours and minutes:
        return f'{hours}h {minutes}m'
    if hours:
        return f'{hours}h'
    return f'{minutes}m'


def root_dir():
    return Path(__file__).resolve().parent.parent


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def load_config(root):
    return load_json(root / 'config' / 'build_manager.json')


def load_registry():
    if not REGISTRY_PATH.exists():
        return {}
    try:
        return load_json(REGISTRY_PATH)
    except Exception:
        return {}


def resolve_db_path(root, config):
    return (root / 'config' / config['database']['path']).resolve()


def resolve_dropbox_mirror_path():
    registry = load_registry()
    dashboards_root = registry.get('DASHBOARDS', {}).get('wsl')
    if not dashboards_root:
        return None
    return Path(dashboards_root) / 'Build_Manager' / 'index.html'


def connect_ro(db_path):
    conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_project_binding_schema(db_path):
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        existing = {row['name'] for row in conn.execute('PRAGMA table_info(projects)').fetchall()}
        for column, column_type in PROJECT_BINDING_COLUMNS.items():
            if column in existing:
                continue
            conn.execute(f'ALTER TABLE projects ADD COLUMN {column} {column_type}')
        conn.commit()
    finally:
        conn.close()


def rows(conn, sql, params=()):
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def task_rows(conn, where_clause='', params=(), order_clause='ORDER BY t.priority ASC, t.updated_at DESC, t.id DESC', limit=None):
    sql = TASK_SELECT
    if where_clause:
        sql += f' WHERE {where_clause}'
    sql += f' {order_clause}'
    if limit is not None:
        sql += ' LIMIT ?'
        params = tuple(params) + (limit,)
    return rows(conn, sql, params)


def get_summary_counts(conn):
    task_counts = rows(conn, 'SELECT status, COUNT(*) AS count FROM tasks GROUP BY status')
    project_counts = rows(conn, 'SELECT status, COUNT(*) AS count FROM projects GROUP BY status')
    return {
        'tasks': {row['status']: row['count'] for row in task_counts},
        'projects': {row['status']: row['count'] for row in project_counts},
    }


def normalize_branding_text(value):
    text = '' if value is None else str(value)
    text = text.replace('OpenClaw Project Manager', 'Build Manager')
    text = text.replace('Project Manager', 'Build Manager')
    text = text.replace('Project Manger', 'Build Manager')
    text = text.replace('project manager', 'build manager')
    text = text.replace('project manger', 'build manager')
    text = text.replace('Project_Manager', 'Build_Manager')
    text = text.replace('project-manager', 'build-manager')
    text = text.replace('project_manager', 'build_manager')
    return text


def anonymize_text(value):
    text = normalize_branding_text(value)
    text = text.replace("Greg's", "operator's")
    text = text.replace("greg's", "operator's")
    text = text.replace('Greg', 'Operator')
    text = text.replace('greg', 'operator')
    return text


def safe_text(value):
    return escape(anonymize_text(value))


def display_project_slug(project):
    return project.get('slug') or ''


def project_binding_bits(project):
    bits = []
    if project.get('conversation_provider'):
        bits.append(project['conversation_provider'])
    if project.get('conversation_surface') and project.get('conversation_surface') != project.get('conversation_provider'):
        bits.append(project['conversation_surface'])
    if project.get('conversation_channel_id'):
        bits.append(f"channel {project['conversation_channel_id']}")
    if project.get('conversation_thread_id'):
        bits.append(f"thread {project['conversation_thread_id']}")
    if project.get('conversation_session_key'):
        bits.append(f"session {project['conversation_session_key']}")
    return bits


def project_binding_summary(project):
    bits = project_binding_bits(project)
    if not bits:
        return 'chat: unbound'
    label = project.get('conversation_label')
    prefix = 'canonical chat' if project.get('conversation_is_canonical') else 'chat'
    text = ' · '.join(bits)
    if label:
        text += f' · {label}'
    return f'{prefix}: {text}'


def render_project_binding(project):
    parts = [f"<span>{safe_text(project_binding_summary(project))}</span>"]
    if project.get('conversation_bound_at'):
        parts.append(f"<span>bound {safe_text(fmt_ts(project.get('conversation_bound_at')))}</span>")
    return '<div class="mini-stats">' + ''.join(parts) + '</div>'


def status_label(status):
    key = str(status or 'unknown')
    return STATUS_LABELS.get(key, key.replace('_', ' ').title())


def status_label_with_count(status, count):
    return f'{status_label(status)} ({count})'


def badge(status):
    key = str(status or 'unknown')
    return f'<span class="status status-{escape(key)}">{escape(status_label(key))}</span>'


def task_scope_label(task):
    if task.get('project_id') is None:
        return 'task'
    if task.get('project_title'):
        return f'project: {task["project_title"]}'
    return f'project {task["project_id"]}'


def task_card_class(task):
    classes = ['task-card']
    classes.append('task-card-standalone' if task.get('project_id') is None else 'task-card-project')
    if task.get('needs_user_input'):
        classes.append('task-card-needs-user')
    return ' '.join(classes)


def task_meta(task):
    meta = [task_scope_label(task)]
    if task.get('priority') is not None:
        meta.append(f'P{task["priority"]}')
    if task.get('parent_task_id') is not None:
        meta.append(f'child of {task["parent_task_id"]}')
    if task.get('needs_user_input'):
        meta.append('needs input')
    if task.get('next_action'):
        meta.append(f'next: {task["next_action"]}')
    if task.get('waiting_question'):
        meta.append(f'waiting: {task["waiting_question"]}')
    return ' · '.join(safe_text(x) for x in meta) if meta else '—'


def render_task_cards(items, empty_label, mode='link', href_builder=None, hint='Open in Tasks'):
    if not items:
        return f'<div class="empty">{escape(empty_label)}</div>'
    parts = ['<ul class="task-list">']
    for task in items:
        inner = f'''<div>{badge(task.get('status', 'unknown'))} <strong>#{task.get('id')} {safe_text(task.get('title') or 'Untitled')}</strong></div>
<div class="muted">{task_meta(task)}</div>
<div class="muted">updated {fmt_ts(task.get('updated_at'))}</div>
<div class="task-card-hint">{safe_text(hint)}</div>'''
        if mode == 'panel':
            control = f'<button class="task-link" type="button" data-task-id="{task.get("id")}">{inner}</button>'
        else:
            href = href_builder(task) if href_builder else '#'
            control = f'<a class="task-link" href="{escape(href)}">{inner}</a>'
        parts.append(f'<li class="{task_card_class(task)}">{control}</li>')
    parts.append('</ul>')
    return ''.join(parts)


def render_task_detail_content(task):
    scope = task_scope_label(task)
    summary = task.get('description') or 'No summary yet.'
    next_action = task.get('next_action') or '—'
    waiting_question = task.get('waiting_question') or '—'
    parent = f'#{task.get("parent_task_id")}' if task.get('parent_task_id') is not None else '—'
    return f'''<article class="task-detail-card">
<div class="task-detail-header">
  <div>{badge(task.get('status', 'unknown'))} <strong>#{task.get('id')} {safe_text(task.get('title') or 'Untitled')}</strong></div>
  <a class="detail-backlink" href="#page-top">Back to top</a>
</div>
<div class="mini-stats">
  <span>{safe_text(scope)}</span>
  <span>P{task.get('priority') if task.get('priority') is not None else '—'}</span>
  <span>updated {fmt_ts(task.get('updated_at'))}</span>
  <span>parent {safe_text(parent)}</span>
</div>
<div class="detail-grid">
  <div>
    <div class="label">Summary</div>
    <p>{safe_text(summary)}</p>
  </div>
  <div>
    <div class="label">Next action</div>
    <p>{safe_text(next_action)}</p>
    <div class="label">Waiting question</div>
    <p>{safe_text(waiting_question)}</p>
  </div>
</div>
</article>'''


def render_task_panel(tasks):
    if not tasks:
        return '<div class="empty">No task details are available in this snapshot.</div>'
    return f'''<div class="task-panel-shell">
<div class="sub" style="margin-bottom:12px;">Click any task card to update this panel.</div>
<div id="task-panel-body">{render_task_detail_content(tasks[0])}</div>
</div>
<div class="task-template-store" aria-hidden="true">{''.join(f'<template id="task-template-{task["id"]}">{render_task_detail_content(task)}</template>' for task in tasks)}</div>'''


def unique_tasks(*task_groups):
    unique = {}
    for group in task_groups:
        if isinstance(group, dict):
            iterable = group.values()
        else:
            iterable = [group]
        for items in iterable:
            for task in items:
                if task.get('id') is not None:
                    unique[task['id']] = task
    return sorted(
        unique.values(),
        key=lambda task: (parse_iso(task.get('updated_at')) or datetime.min.replace(tzinfo=timezone.utc), task.get('id') or 0),
        reverse=True,
    )


def render_summary_cards(cards):
    parts = ['<div class="summary-cards">']
    for card in cards:
        label = safe_text(card['label'])
        value = safe_text(card['value'])
        href = card.get('href')
        if href:
            parts.append(f'<a class="summary-card-link" href="{escape(href)}"><div class="label">{label}</div><div class="value">{value}</div></a>')
        else:
            parts.append(f'<div class="mini-card"><div class="label">{label}</div><div class="value">{value}</div></div>')
    parts.append('</div>')
    return ''.join(parts)


def render_lifecycle_cards(items):
    parts = ['<div class="project-preview-grid">']
    for key, title, description in items:
        parts.append(f'''<section class="project-preview-card" id="stage-{escape(key)}">
<div><strong>{safe_text(title)}</strong></div>
<p>{safe_text(description)}</p>
</section>''')
    parts.append('</div>')
    return ''.join(parts)


def render_primary_nav(active_page):
    items = [
        ('overview', 'index.html', 'Overview'),
        ('tasks', 'tasks.html', 'Tasks'),
        ('projects', 'projects.html', 'Projects'),
        ('sessions', 'sessions.html', 'Sessions'),
        ('activity', 'activity.html', 'Activity'),
    ]
    parts = ['<nav class="primary-nav">']
    for key, href, label in items:
        cls = 'nav-link is-active' if key == active_page else 'nav-link'
        parts.append(f'<a class="{cls}" href="{href}">{safe_text(label)}</a>')
    parts.append('</nav>')
    return ''.join(parts)


def render_subnav(items, current_href=''):
    if not items:
        return ''
    parts = ['<nav class="sub-nav">']
    for item in items:
        cls = 'sub-link is-active' if item.get('active') else 'sub-link'
        href = item['href']
        if current_href and href.startswith('#'):
            href = f'{current_href}{href}'
        parts.append(f'<a class="{cls}" href="{escape(href)}">{safe_text(item["label"])}</a>')
    parts.append('</nav>')
    return ''.join(parts)


def render_prompt_bar(page='overview', project_id=None, task_id=None, current_path='index.html'):
    project_attr = '' if project_id is None else f' data-project-id="{int(project_id)}"'
    task_attr = '' if task_id is None else f' data-task-id="{int(task_id)}"'
    return f'''<div class="prompt-shell">
<form class="prompt-form" id="build-manager-prompt-form" data-page="{safe_text(page)}"{project_attr}{task_attr} data-current-path="{safe_text(current_path or 'index.html')}">
  <input class="prompt-input" id="build-manager-prompt-input" name="prompt" type="text" autocomplete="off" placeholder="Try: mark task 71 done, create a project called Dashboard polish, add a note to task 71 saying refresh after submit" aria-label="Build Manager prompt">
  <button class="prompt-submit" id="build-manager-prompt-submit" type="submit">Run</button>
</form>
<div class="prompt-status" id="build-manager-prompt-status">Prompt-first control, one command at a time. Supported actions include creating projects/tasks, adding notes, and updating status.</div>
<div class="prompt-response" id="build-manager-prompt-response" hidden><pre id="build-manager-prompt-response-body"></pre></div>
</div>'''


def page_shell(page_title, generated_at, active_page, hero_title, hero_text, body_html, subnav_items=None, extra_script='', current_href='', prompt_page='overview', prompt_project_id=None, prompt_task_id=None):
    meta = f'Generated {generated_at}'
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{safe_text(page_title)}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <base href="{BUILD_MANAGER_BASE_PATH}">
  <link rel="manifest" href="{BUILD_MANAGER_BASE_PATH}manifest.webmanifest">
  <meta name="theme-color" content="#0b1020">
  <link rel="icon" href="{BUILD_MANAGER_BASE_PATH}icons/icon-192.png" sizes="192x192" type="image/png">
  <link rel="apple-touch-icon" href="{BUILD_MANAGER_BASE_PATH}icons/icon-192.png">
  <style>{BASE_CSS}</style>
</head>
<body>
  <div class="page-shell" id="page-top">
    <header class="topbar">
      <div class="brand-row">
        <div>
          <h1 class="brand-title">OpenClaw Build Manager Dashboard</h1>
          <div class="brand-note">Static HTML snapshot with prompt-first control wired into the live SQLite runtime.</div>
          <div class="brand-status" id="build-manager-runtime-status"><span class="brand-status-dot" aria-hidden="true"></span><span id="build-manager-runtime-label">Checking OpenClaw status…</span></div>
        </div>
        <div class="top-meta">{safe_text(meta)}</div>
      </div>
      {render_prompt_bar(page=prompt_page, project_id=prompt_project_id, task_id=prompt_task_id, current_path=current_href or 'index.html')}
      {render_primary_nav(active_page)}
      {render_subnav(subnav_items, current_href=current_href)}
    </header>
    <main class="page-content">
      <section class="hero">
        <h2>{safe_text(hero_title)}</h2>
        <p>{safe_text(hero_text)}</p>
      </section>
      {body_html}
    </main>
  </div>
  {PROMPT_FORM_SCRIPT}
  {extra_script}
</body>
</html>'''


def task_link_href(task):
    return f'tasks.html#task-{task["id"]}'


def hopper_link_href(task):
    return f'hopper.html#task-{task["id"]}'


def project_file_name(project_id):
    return f'project-{project_id}.html'


def render_project_preview_cards(projects, tasks_by_project):
    if not projects:
        return '<div class="empty">No current projects to preview.</div>'
    parts = ['<div class="project-preview-grid">']
    for project in projects:
        tasks = tasks_by_project.get(project['id'], [])
        active_count = sum(1 for task in tasks if task.get('status') == 'active')
        waiting_count = sum(1 for task in tasks if task.get('status') == 'waiting')
        planned_count = sum(1 for task in tasks if task.get('status') == 'planned')
        parts.append(f'''<a class="project-page-link project-preview-card" href="{project_file_name(project['id'])}">
<div>{badge(project.get('status', 'unknown'))}<strong>#{project.get('id')} {safe_text(project.get('title') or 'Untitled')}</strong></div>
<div class="muted">owner: {safe_text(project.get('owner_agent') or '—')}</div>
{render_project_binding(project)}
<p>{safe_text(project.get('description') or project.get('goal') or 'No summary yet.')}</p>
<div class="mini-stats">
  <span>{len(tasks)} tasks</span>
  <span>{active_count} active</span>
  <span>{waiting_count} waiting</span>
  <span>{planned_count} planned</span>
</div>
</a>''')
    parts.append('</div>')
    return ''.join(parts)


def group_tasks_by_status(tasks):
    grouped = {}
    for task in tasks:
        grouped.setdefault(task.get('status') or 'unknown', []).append(task)
    return grouped


def render_project_index_cards(projects, tasks_by_project):
    if not projects:
        return '<div class="empty">No projects yet.</div>'
    parts = []
    for project in projects:
        tasks = tasks_by_project.get(project['id'], [])
        parts.append(f'''<a class="project-page-link project-card" href="{project_file_name(project['id'])}">
<div>{badge(project.get('status', 'unknown'))}<strong>#{project.get('id')} {safe_text(project.get('title') or 'Untitled')}</strong></div>
<div class="muted">slug: {safe_text(display_project_slug(project))} · owner: {safe_text(project.get('owner_agent') or '—')}</div>
{render_project_binding(project)}
<p>{safe_text(project.get('description') or project.get('goal') or 'No description.')}</p>
<div class="mini-stats">
  <span>{len(tasks)} tasks</span>
  <span>{sum(1 for t in tasks if t.get('status') == 'active')} active</span>
  <span>{sum(1 for t in tasks if t.get('status') == 'waiting')} waiting</span>
  <span>{sum(1 for t in tasks if t.get('status') == 'planned')} planned</span>
</div>
</a>''')
    return ''.join(parts)


def render_activity(items):
    if not items:
        return '<div class="empty">No activity recorded yet.</div>'
    parts = ['<table class="data-table"><thead><tr><th>When</th><th>Event</th><th>Entity</th><th>By</th><th>Payload</th></tr></thead><tbody>']
    for item in items:
        payload = item.get('payload')
        payload_text = safe_text(json.dumps(payload, sort_keys=True)) if payload is not None else '—'
        parts.append(f'''<tr>
<td data-label="When">{fmt_ts(item.get('created_at'))}</td>
<td data-label="Event">{safe_text(item.get('event_type') or '—')}</td>
<td data-label="Entity">{safe_text(item.get('entity_type') or '—')} #{item.get('entity_id')}</td>
<td data-label="By">{safe_text(item.get('created_by') or '—')}</td>
<td data-label="Payload" class="payload">{payload_text}</td>
</tr>''')
    parts.append('</tbody></table>')
    return ''.join(parts)


def render_sessions(items, summary):
    cards = render_summary_cards([
        {'label': 'All sessions', 'value': summary['all_time']['sessions_total']},
        {'label': 'Open sessions', 'value': summary['all_time']['open_sessions']},
        {'label': 'All human time', 'value': fmt_minutes(summary['all_time']['human_minutes_total'])},
        {'label': 'All agent time', 'value': fmt_minutes(summary['all_time']['agent_minutes_total'])},
        {'label': '7d human', 'value': fmt_minutes(summary['last_7d']['human_minutes_total'])},
        {'label': '7d agent', 'value': fmt_minutes(summary['last_7d']['agent_minutes_total'])},
    ])
    table_parts = ['<table class="data-table"><thead><tr><th>Started</th><th>Task</th><th>Project</th><th>Type</th><th>Planned</th><th>Human</th><th>Agent</th></tr></thead><tbody>']
    if not items:
        table_parts.append('<tr><td colspan="7" class="empty-cell">No work sessions yet.</td></tr>')
    else:
        for item in items:
            table_parts.append(f'''<tr>
<td data-label="Started">{fmt_ts(item.get('started_at'))}</td>
<td data-label="Task">#{item.get('task_id')} {safe_text(item.get('task_title') or '—')}</td>
<td data-label="Project">{safe_text(item.get('project_title') or '—')}</td>
<td data-label="Type">{safe_text(item.get('session_type') or '—')}</td>
<td data-label="Planned">{fmt_minutes(item.get('planned_minutes'))}</td>
<td data-label="Human">{fmt_minutes(item.get('final_human_minutes'))}</td>
<td data-label="Agent">{fmt_minutes(item.get('final_agent_minutes'))}</td>
</tr>''')
    table_parts.append('</tbody></table>')
    return cards + ''.join(table_parts)


def build_overview_page(data):
    cards = render_summary_cards([
        {'label': 'Current projects', 'value': len(data['current_projects']), 'href': 'projects.html'},
        {'label': 'Open tasks', 'value': data['task_scope_counts']['independent_open'], 'href': 'tasks.html'},
        {'label': 'Hopper Count', 'value': len(data['project_views']['hopper']), 'href': 'hopper.html'},
        {'label': 'Needs input', 'value': len(data['waiting_on_input']), 'href': 'tasks.html'},
    ])
    body = f'''
<section class="panel section">
  <h3>Overview</h3>
  {cards}
  <div class="callout">The dashboard is now split into section pages. Use the top navigation to move between Overview, Tasks, Projects, Sessions, and Activity. Hopper now lives under Projects.</div>
</section>
<div class="grid-two section">
  <section class="panel">
    <h3>Tasks preview</h3>
    {render_task_cards(data['standalone_views']['open'], 'No tasks are open right now.', href_builder=task_link_href, hint='Open in Tasks')}
  </section>
  <section class="panel">
    <h3>Approvals / input</h3>
    {render_task_cards(data['waiting_on_input'], 'No explicit input items detected right now.', href_builder=task_link_href, hint='Open in Tasks')}
  </section>
</div>
<section class="panel section">
  <h3>Hopper</h3>
  {render_project_index_cards(data['project_views']['hopper'], data['tasks_by_project']) if data['project_views']['hopper'] else '<div class="empty">No Hopper projects right now.</div>'}
</section>
<section class="panel section">
  <h3>Projects preview</h3>
  {render_project_preview_cards(data['current_projects'], data['tasks_by_project'])}
</section>
'''
    return page_shell(
        'Build Manager Overview',
        fmt_ts(data['generated_at']),
        'overview',
        'Overview',
        'This is the top-level overview page. Tasks and Projects now live on their own pages, with Hopper treated as part of Projects so the dashboard can stay cleaner and more focused.',
        body,
        current_href='index.html',
        prompt_page='overview',
    )


def build_tasks_page(data):
    independent_tasks = unique_tasks(
        data['standalone_views']['captured'],
        data['standalone_views']['queued'],
        data['standalone_views']['active'],
        data['standalone_views']['paused'],
        data['standalone_views']['parked'],
        data['standalone_views']['done'],
        data['standalone_views']['archived'],
    )
    subnav = [
        {'href': '#captured', 'label': status_label_with_count('captured', len(data['standalone_views']['captured']))},
        {'href': '#queued', 'label': status_label_with_count('queued', len(data['standalone_views']['queued']))},
        {'href': '#active', 'label': status_label_with_count('active', len(data['standalone_views']['active']))},
        {'href': '#paused', 'label': status_label_with_count('paused', len(data['standalone_views']['paused']))},
        {'href': '#parked', 'label': status_label_with_count('parked', len(data['standalone_views']['parked']))},
        {'href': '#done', 'label': status_label_with_count('done', len(data['standalone_views']['done']))},
        {'href': '#archived', 'label': status_label_with_count('archived', len(data['standalone_views']['archived']))},
    ]
    body = f'''
<div class="page-split section">
  <div>
    <section class="panel" id="captured">
      <h3>{safe_text(status_label_with_count('captured', len(data['standalone_views']['captured'])))}</h3>
      {render_task_cards(data['standalone_views']['captured'], 'No captured tasks right now.', mode='panel', hint='Open task panel')}
    </section>
    <section class="panel section" id="queued">
      <h3>{safe_text(status_label_with_count('queued', len(data['standalone_views']['queued'])))}</h3>
      {render_task_cards(data['standalone_views']['queued'], 'No queued tasks right now.', mode='panel', hint='Open task panel')}
    </section>
    <section class="panel section" id="active">
      <h3>{safe_text(status_label_with_count('active', len(data['standalone_views']['active'])))}</h3>
      {render_task_cards(data['standalone_views']['active'], 'No active tasks right now.', mode='panel', hint='Open task panel')}
    </section>
    <section class="panel section" id="paused">
      <h3>{safe_text(status_label_with_count('paused', len(data['standalone_views']['paused'])))}</h3>
      {render_task_cards(data['standalone_views']['paused'], 'No paused tasks right now.', mode='panel', hint='Open task panel')}
    </section>
    <section class="panel section" id="parked">
      <h3>{safe_text(status_label_with_count('parked', len(data['standalone_views']['parked'])))}</h3>
      {render_task_cards(data['standalone_views']['parked'], 'No parked tasks right now.', mode='panel', hint='Open task panel')}
    </section>
    <section class="panel section" id="done">
      <h3>{safe_text(status_label_with_count('done', len(data['standalone_views']['done'])))}</h3>
      {render_task_cards(data['standalone_views']['done'], 'No done tasks right now.', mode='panel', hint='Open task panel')}
    </section>
    <section class="panel section" id="archived">
      <h3>{safe_text(status_label_with_count('archived', len(data['standalone_views']['archived'])))}</h3>
      {render_task_cards(data['standalone_views']['archived'], 'No archived tasks right now.', mode='panel', hint='Open task panel')}
    </section>
  </div>
  <aside class="panel detail-panel-sticky section" id="task-panel">
    <h3>Task panel</h3>
    {render_task_panel(independent_tasks)}
  </aside>
</div>
'''
    return page_shell(
        'Build Manager Tasks',
        fmt_ts(data['generated_at']),
        'tasks',
        'Tasks',
        'This page now uses the exact live backend status set for standalone tasks. Click any task card to update the task panel without leaving the page.',
        body,
        subnav_items=subnav,
        extra_script=TASK_PANEL_SCRIPT,
        current_href='tasks.html',
        prompt_page='tasks',
    )


def build_hopper_page(data):
    subnav = [
        {'href': 'projects.html', 'label': 'Projects'},
        {'href': '#hopper-list', 'label': f'Hopper ({len(data["project_views"]["hopper"])})'},
    ]
    body = f'''
<section class="panel section" id="hopper-list">
  <h3>Hopper</h3>
  {render_project_index_cards(data['project_views']['hopper'], data['tasks_by_project']) if data['project_views']['hopper'] else '<div class="empty">No Hopper projects right now.</div>'}
</section>
'''
    return page_shell(
        'Build Manager Hopper',
        fmt_ts(data['generated_at']),
        'projects',
        'Hopper',
        'Hopper is the raw intake stage for project ideas before they move into Capture.',
        body,
        subnav_items=subnav,
        current_href='hopper.html',
        prompt_page='hopper',
    )


def build_projects_page(data):
    sections = []
    subnav_items = []
    for status in PROJECT_STATUS_ORDER:
        items = data['project_views'][status]
        subnav_items.append({'href': f'#stage-{status}', 'label': status_label_with_count(status, len(items))})
        content = render_project_index_cards(items, data['tasks_by_project']) if items else f'<div class="empty">No {status_label(status).lower()} projects right now.</div>'
        sections.append(f'''<section class="panel section" id="stage-{status}">
  <h3>{safe_text(status_label_with_count(status, len(items)))}</h3>
  {content}
</section>''')
    body = ''.join(sections)
    return page_shell(
        'Build Manager Projects',
        fmt_ts(data['generated_at']),
        'projects',
        'Projects',
        'Projects now use the live canonical project-stage buckets directly from the backend.',
        body,
        subnav_items=subnav_items,
        current_href='projects.html',
        prompt_page='projects',
    )


def build_project_page(project, tasks):
    grouped = group_tasks_by_status(tasks)
    sections = []
    for status in PROJECT_TASK_STATUS_ORDER:
        label = status_label(status)
        count = len(grouped.get(status, []))
        sections.append(f'''<section class="panel section" id="status-{status}">
<h3>{safe_text(status_label_with_count(status, count))}</h3>
{render_task_cards(grouped.get(status, []), f'No {label.lower()} tasks in this project.', mode='panel', hint='Open task details')}
</section>''')
    subnav_items = [{'href': '#project-summary', 'label': 'Summary'}]
    for status in PROJECT_TASK_STATUS_ORDER:
        subnav_items.append({
            'href': f'#status-{status}',
            'label': status_label_with_count(status, len(grouped.get(status, []))),
        })

    body = f'''
<section class="panel section" id="project-summary">
  <h3>Summary</h3>
  <div>{badge(project.get('status', 'unknown'))} <strong>#{project.get('id')} {safe_text(project.get('title') or 'Untitled')}</strong></div>
  <div class="mini-stats">
    <span>owner {safe_text(project.get('owner_agent') or '—')}</span>
    <span>slug {safe_text(display_project_slug(project) or '—')}</span>
    <span>{len(tasks)} tasks</span>
    <span>{len(grouped.get('active', []))} active</span>
    <span>{len(grouped.get('waiting', []))} waiting</span>
    <span>{len(grouped.get('planned', []))} planned</span>
  </div>
  {render_project_binding(project)}
  <p>{safe_text(project.get('description') or project.get('goal') or 'No description.')}</p>
</section>
<div class="page-split section">
  <div>
    {''.join(sections)}
  </div>
  <aside class="panel detail-panel-sticky section" id="task-panel">
    <h3>Task details</h3>
    {render_task_panel(tasks)}
  </aside>
</div>
'''
    return page_shell(
        f'Project #{project.get("id")} {project.get("title") or "Untitled"}',
        fmt_ts(now_iso()),
        'projects',
        safe_text(project.get('title') or 'Project'),
        'This project page now uses the simplified project-task status model and shows the canonical conversation binding for the build when one has been assigned.',
        body,
        subnav_items=subnav_items,
        extra_script=TASK_PANEL_SCRIPT,
        current_href=project_file_name(project.get('id')),
        prompt_page='project',
        prompt_project_id=project.get('id'),
    )


def build_sessions_page(data):
    body = f'''
<section class="panel section">
  <h3>Sessions</h3>
  {render_sessions(data['recent_sessions'], data['time_summary'])}
</section>
'''
    return page_shell(
        'Build Manager Sessions',
        fmt_ts(data['generated_at']),
        'sessions',
        'Sessions',
        'Work session history and time summaries live on their own page now, separate from the main overview.',
        body,
        current_href='sessions.html',
        prompt_page='sessions',
    )


def build_activity_page(data):
    body = f'''
<section class="panel section">
  <h3>Activity</h3>
  {render_activity(data['recent_activity'])}
  <div class="sub" style="margin-top:14px;">Static output. Re-run the renderer to refresh the snapshot after more work lands.</div>
</section>
'''
    return page_shell(
        'Build Manager Activity',
        fmt_ts(data['generated_at']),
        'activity',
        'Activity',
        'Recent activity has its own page so the overview can stay focused on navigation and status rather than long logs.',
        body,
        current_href='activity.html',
        prompt_page='activity',
    )


def build_pages(data):
    pages = {
        'index.html': build_overview_page(data),
        'tasks.html': build_tasks_page(data),
        'hopper.html': build_hopper_page(data),
        'projects.html': build_projects_page(data),
        'sessions.html': build_sessions_page(data),
        'activity.html': build_activity_page(data),
    }
    for project in data['projects']:
        if project.get('status') == 'archived':
            continue
        pages[project_file_name(project['id'])] = build_project_page(project, data['tasks_by_project'].get(project['id'], []))
    return pages


def write_pages(target_dir, pages):
    target_dir.mkdir(parents=True, exist_ok=True)
    for name, content in pages.items():
        (target_dir / name).write_text(content, encoding='utf-8')


def _png_chunk(tag, data):
    return struct.pack('!I', len(data)) + tag + data + struct.pack('!I', zlib.crc32(tag + data) & 0xffffffff)


def _write_png(path, width, height, pixels):
    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0)
        start = y * stride
        raw.extend(pixels[start:start + stride])
    ihdr = struct.pack('!IIBBBBB', width, height, 8, 6, 0, 0, 0)
    data = zlib.compress(bytes(raw), 9)
    png = b'\x89PNG\r\n\x1a\n' + _png_chunk(b'IHDR', ihdr) + _png_chunk(b'IDAT', data) + _png_chunk(b'IEND', b'')
    path.write_bytes(png)


def _build_manager_icon_pixels(size, maskable=False):
    bg = (11, 16, 32, 255)
    panel = (23, 33, 66, 255)
    blue = (124, 196, 255, 255)
    green = (157, 211, 140, 255)
    white = (238, 242, 255, 255)
    pixels = bytearray(size * size * 4)

    def set_px(x, y, color):
        if 0 <= x < size and 0 <= y < size:
            i = (y * size + x) * 4
            pixels[i:i + 4] = bytes(color)

    for y in range(size):
        for x in range(size):
            set_px(x, y, bg)

    pad = int(size * (0.08 if maskable else 0.14))
    for y in range(pad, size - pad):
        for x in range(pad, size - pad):
            set_px(x, y, panel)

    topbar = int(size * 0.16)
    for y in range(pad, pad + topbar):
        for x in range(pad, size - pad):
            set_px(x, y, blue)

    left_x = pad + int(size * 0.08)
    upper_y = pad + topbar + int(size * 0.08)
    block_w = int(size * 0.28)
    block_h1 = int(size * 0.18)
    for y in range(upper_y, upper_y + block_h1):
        for x in range(left_x, left_x + block_w):
            set_px(x, y, white)

    lower_y = upper_y + block_h1 + int(size * 0.05)
    block_h2 = int(size * 0.26)
    for y in range(lower_y, lower_y + block_h2):
        for x in range(left_x, left_x + block_w):
            set_px(x, y, green)

    right_x = pad + int(size * 0.44)
    base_y = size - pad - int(size * 0.12)
    bar_w = int(size * 0.08)
    gap = int(size * 0.04)
    heights = [0.16, 0.28, 0.38]
    colors = [white, blue, green]
    for idx, frac in enumerate(heights):
        bx = right_x + idx * (bar_w + gap)
        bh = int(size * frac)
        for y in range(base_y - bh, base_y):
            for x in range(bx, bx + bar_w):
                set_px(x, y, colors[idx])

    return pixels


def write_pwa_assets(target_dir):
    icons_dir = target_dir / 'icons'
    icons_dir.mkdir(parents=True, exist_ok=True)
    _write_png(icons_dir / 'icon-192.png', 192, 192, _build_manager_icon_pixels(192, False))
    _write_png(icons_dir / 'icon-512.png', 512, 512, _build_manager_icon_pixels(512, False))
    _write_png(icons_dir / 'icon-512-maskable.png', 512, 512, _build_manager_icon_pixels(512, True))
    manifest = {
        'id': '/build-manager',
        'name': 'Build Manager',
        'short_name': 'BuildMgr',
        'description': 'Build Manager dashboard for OpenClaw projects, tasks, and sessions.',
        'start_url': '/build-manager',
        'scope': '/build-manager',
        'display': 'standalone',
        'background_color': '#0b1020',
        'theme_color': '#0b1020',
        'prefer_related_applications': False,
        'icons': [
            {
                'src': '/build-manager/icons/icon-192.png',
                'sizes': '192x192',
                'type': 'image/png',
                'purpose': 'any',
            },
            {
                'src': '/build-manager/icons/icon-512.png',
                'sizes': '512x512',
                'type': 'image/png',
                'purpose': 'any',
            },
            {
                'src': '/build-manager/icons/icon-512-maskable.png',
                'sizes': '512x512',
                'type': 'image/png',
                'purpose': 'maskable',
            },
        ],
    }
    (target_dir / 'manifest.webmanifest').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')


def main():
    root = root_dir()
    config = load_config(root)
    parser = argparse.ArgumentParser(description='Render a read-only Build Manager dashboard from SQLite.')
    parser.add_argument('--db', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--title', default='OpenClaw Build Manager Dashboard')
    parser.add_argument('--activity-limit', type=int, default=40)
    parser.add_argument('--task-limit', type=int, default=15)
    parser.add_argument('--session-limit', type=int, default=20)
    args = parser.parse_args()

    db_path = args.db.resolve() if args.db else resolve_db_path(root, config)
    local_output_path = (root / 'ui' / 'index.html').resolve()
    dropbox_mirror_path = resolve_dropbox_mirror_path()
    out_path = args.out.resolve() if args.out else (dropbox_mirror_path.resolve() if dropbox_mirror_path else local_output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    ensure_project_binding_schema(db_path)

    with connect_ro(db_path) as conn:
        summary_counts = get_summary_counts(conn)
        project_select = 'SELECT id, slug, title, description, status, owner_agent, goal, conversation_provider, conversation_surface, conversation_channel_id, conversation_thread_id, conversation_session_key, conversation_label, conversation_is_canonical, conversation_bound_at FROM projects'
        projects = rows(conn, project_select + ' ORDER BY updated_at DESC, id DESC')
        project_views = {
            status: rows(conn, project_select + ' WHERE status = ? ORDER BY updated_at DESC, id DESC', (status,))
            for status in PROJECT_STATUS_ORDER
        }
        current_projects = rows(conn, f"{project_select} WHERE status IN ({', '.join('?' for _ in CURRENT_PROJECT_STATUSES)}) ORDER BY updated_at DESC, id DESC", tuple(CURRENT_PROJECT_STATUSES))
        tasks_by_project = {
            project['id']: task_rows(
                conn,
                't.project_id = ?',
                (project['id'],),
                order_clause='ORDER BY t.priority ASC, t.updated_at DESC, t.id DESC'
            )
            for project in projects
        }
        task_views = {
            'active': task_rows(conn, 't.status = ?', ('active',), limit=args.task_limit),
            'paused': task_rows(conn, 't.status = ?', ('paused',), order_clause='ORDER BY t.updated_at DESC, t.id DESC', limit=args.task_limit),
            'queued': task_rows(conn, 't.status = ?', ('queued',), limit=args.task_limit),
            'hopper': task_rows(conn, 't.status = ?', ('captured',), order_clause='ORDER BY t.updated_at DESC, t.id DESC', limit=args.task_limit),
            'done': task_rows(conn, 't.status = ?', ('done',), order_clause='ORDER BY t.updated_at DESC, t.id DESC', limit=args.task_limit),
        }
        standalone_views = {
            'open': task_rows(conn, "t.project_id IS NULL AND t.status NOT IN ('done', 'archived')", order_clause='ORDER BY t.updated_at DESC, t.id DESC', limit=args.task_limit),
            'captured': task_rows(conn, 't.project_id IS NULL AND t.status = ?', ('captured',), order_clause='ORDER BY t.updated_at DESC, t.id DESC', limit=args.task_limit),
            'queued': task_rows(conn, 't.project_id IS NULL AND t.status = ?', ('queued',), order_clause='ORDER BY t.updated_at DESC, t.id DESC', limit=args.task_limit),
            'active': task_rows(conn, 't.project_id IS NULL AND t.status = ?', ('active',), limit=args.task_limit),
            'paused': task_rows(conn, 't.project_id IS NULL AND t.status = ?', ('paused',), order_clause='ORDER BY t.updated_at DESC, t.id DESC', limit=args.task_limit),
            'parked': task_rows(conn, 't.project_id IS NULL AND t.status = ?', ('parked',), order_clause='ORDER BY t.updated_at DESC, t.id DESC', limit=args.task_limit),
            'done': task_rows(conn, 't.project_id IS NULL AND t.status = ?', ('done',), order_clause='ORDER BY t.updated_at DESC, t.id DESC', limit=args.task_limit),
            'archived': task_rows(conn, 't.project_id IS NULL AND t.status = ?', ('archived',), order_clause='ORDER BY t.updated_at DESC, t.id DESC', limit=args.task_limit),
        }
        waiting_on_input = task_rows(conn, "t.needs_user_input = 1 AND t.status NOT IN ('done', 'archived')", order_clause='ORDER BY t.updated_at DESC, t.id DESC', limit=args.task_limit)
        recent_activity = []
        for item in rows(conn, 'SELECT id, entity_type, entity_id, event_type, payload_json, created_at, created_by FROM activity_log ORDER BY created_at DESC, id DESC LIMIT ?', (args.activity_limit,)):
            try:
                item['payload'] = json.loads(item['payload_json']) if item.get('payload_json') else None
            except json.JSONDecodeError:
                item['payload'] = item.get('payload_json')
            recent_activity.append(item)
        recent_sessions = rows(conn, 'SELECT ws.id, ws.task_id, ws.session_type, ws.started_at, ws.planned_minutes, ws.final_human_minutes, ws.final_agent_minutes, t.title AS task_title, p.title AS project_title FROM work_sessions ws LEFT JOIN tasks t ON t.id = ws.task_id LEFT JOIN projects p ON p.id = t.project_id ORDER BY ws.started_at DESC, ws.id DESC LIMIT ?', (args.session_limit,))
        since = (datetime.now(timezone.utc) - timedelta(days=7)).replace(microsecond=0).isoformat()
        time_summary = {
            'all_time': rows(conn, 'SELECT COUNT(*) AS sessions_total, SUM(CASE WHEN ended_at IS NULL THEN 1 ELSE 0 END) AS open_sessions, COALESCE(SUM(final_human_minutes), 0) AS human_minutes_total, COALESCE(SUM(final_agent_minutes), 0) AS agent_minutes_total FROM work_sessions')[0],
            'last_7d': rows(conn, 'SELECT COUNT(*) AS sessions_total, COALESCE(SUM(final_human_minutes), 0) AS human_minutes_total, COALESCE(SUM(final_agent_minutes), 0) AS agent_minutes_total FROM work_sessions WHERE started_at >= ?', (since,))[0],
        }
        task_scope_counts = {
            'independent_open': rows(conn, "SELECT COUNT(*) AS count FROM tasks WHERE project_id IS NULL AND status NOT IN ('done', 'archived')")[0]['count'],
        }

    data = {
        'title': args.title,
        'generated_at': now_iso(),
        'summary_counts': summary_counts,
        'projects': projects,
        'project_views': project_views,
        'current_projects': current_projects,
        'tasks_by_project': tasks_by_project,
        'task_views': task_views,
        'standalone_views': standalone_views,
        'task_scope_counts': task_scope_counts,
        'waiting_on_input': waiting_on_input,
        'recent_activity': recent_activity,
        'recent_sessions': recent_sessions,
        'time_summary': time_summary,
        'local_output_path': str(local_output_path),
        'primary_output_path': str(out_path),
        'dropbox_mirror_path': str(dropbox_mirror_path) if dropbox_mirror_path else None,
    }

    pages = build_pages(data)

    targets = {out_path.parent, local_output_path.parent}
    if dropbox_mirror_path:
        targets.add(dropbox_mirror_path.parent)

    for target in targets:
        write_pages(target, pages)
        write_pwa_assets(target)

    print(json.dumps({
        'output_path': str(out_path),
        'primary_output_path': str(out_path),
        'local_output_path': str(local_output_path),
        'db_path': str(db_path),
        'generated_at': data['generated_at'],
        'dropbox_mirror_path': str(dropbox_mirror_path) if dropbox_mirror_path else None,
        'dropbox_mirror_written': bool(dropbox_mirror_path),
        'pages_written': sorted(pages.keys()),
    }, indent=2))


if __name__ == '__main__':
    main()
