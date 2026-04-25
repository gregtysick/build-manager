#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
BUILD_MANAGER_SCRIPT = ROOT / 'scripts' / 'build_manager.py'
RENDER_DASHBOARD_SCRIPT = ROOT / 'scripts' / 'render_dashboard.py'


def run_json_command(command, timeout_seconds=45):
    proc = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
    )
    stdout = (proc.stdout or '').strip()
    stderr = (proc.stderr or '').strip()
    if proc.returncode != 0:
        raise RuntimeError(stderr or stdout or f'command failed: {proc.returncode}')
    if not stdout:
        return {}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f'non-JSON command output: {stdout}') from exc


def summarize_result(result):
    if isinstance(result, dict):
        if result.get('clarification'):
            return False, result['clarification']
        if 'note_id' in result:
            return True, f"Saved note #{result['note_id']}."
        if 'new_title' in result and 'project_id' in result:
            return True, f"Renamed project #{result['project_id']} to {result['new_title']}."
        if 'project_id' in result and 'to_status' in result:
            return True, f"Updated project #{result['project_id']} to {result['to_status']}."
        if 'task_id' in result and 'to_status' in result:
            return True, f"Updated task #{result['task_id']} to {result['to_status']}."
        if 'project_id' in result and 'title' in result:
            return True, f"Created project #{result['project_id']}: {result['title']}."
        if 'task_id' in result and 'title' in result:
            return True, f"Created task #{result['task_id']}: {result['title']}."
        if result.get('message'):
            return True, str(result['message'])
    if isinstance(result, list):
        return True, 'Command ran. Refreshing the dashboard.'
    return True, 'Command ran. Refreshing the dashboard.'


def _as_int(value):
    try:
        if value in (None, ''):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_current_path(raw_path):
    text = str(raw_path or '').strip()
    if not text:
        return ''
    parsed = urlparse(text)
    candidate = (parsed.path or '').strip('/')
    if not candidate:
        return ''
    if not re.fullmatch(r'[A-Za-z0-9._/-]+', candidate):
        return ''
    return candidate


def extract_context(payload):
    return {
        'page': str(payload.get('page') or '').strip() or None,
        'project_id': _as_int(payload.get('project_id')),
        'task_id': _as_int(payload.get('task_id')),
        'current_path': _normalize_current_path(payload.get('current_path')),
        'current_hash': str(payload.get('current_hash') or '').strip() or None,
    }



def build_refresh_target(result, context):
    current_path = context.get('current_path') or 'index.html'
    current_hash = context.get('current_hash') or ''
    if isinstance(result, dict):
        project_id = _as_int(result.get('project_id')) or context.get('project_id')
        if 'project_id' in result and 'title' in result:
            return f'project-{project_id}.html' if project_id else 'projects.html'
        if 'new_title' in result and project_id:
            return f'project-{project_id}.html'
        if result.get('task_id') and project_id:
            return f'project-{project_id}.html#task-{result["task_id"]}'
        if result.get('task_id') and current_hash and current_path.startswith('project-'):
            return f'{current_path}{current_hash}'
        if 'task_id' in result and 'to_status' in result and project_id:
            return f'project-{project_id}.html#task-{result["task_id"]}'
        if 'project_id' in result and 'to_status' in result and project_id:
            return 'projects.html' if result.get('to_status') == 'archived' else f'project-{project_id}.html'
    return f'{current_path}{current_hash}' if current_hash else current_path


class PromptHandler(BaseHTTPRequestHandler):
    server_version = 'BuildManagerPrompt/0.1'

    def _send_json(self, status_code, payload):
        body = (json.dumps(payload, indent=2) + '\n').encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip('/') == '/healthz':
            self._send_json(200, {'ok': True, 'service': 'build-manager-prompt'})
            return
        self._send_json(404, {'ok': False, 'message': 'not found'})

    def do_POST(self):
        if self.path.rstrip('/') != '/prompt':
            self._send_json(404, {'ok': False, 'message': 'not found'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            self._send_json(400, {'ok': False, 'message': 'invalid content length'})
            return
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            self._send_json(400, {'ok': False, 'message': 'invalid JSON body'})
            return
        prompt = str(payload.get('prompt') or payload.get('text') or '').strip()
        if not prompt:
            self._send_json(400, {'ok': False, 'message': 'prompt is required'})
            return
        context = extract_context(payload)

        try:
            result = run_json_command(['python3', str(BUILD_MANAGER_SCRIPT), 'nl', prompt], timeout_seconds=45)
            ok, message = summarize_result(result)
            if not ok:
                self._send_json(200, {
                    'ok': False,
                    'clarification': message,
                    'result': result,
                    'binding': {
                        'scope': 'global-build-manager-runtime',
                        'page_context': context,
                    },
                })
                return
            refresh = run_json_command(['python3', str(RENDER_DASHBOARD_SCRIPT)], timeout_seconds=60)
        except Exception as exc:
            self._send_json(500, {'ok': False, 'message': str(exc)})
            return

        self._send_json(200, {
            'ok': True,
            'prompt': prompt,
            'message': message,
            'result': result,
            'binding': {
                'scope': 'global-build-manager-runtime',
                'page_context': context,
            },
            'refresh': {
                'generated_at': refresh.get('generated_at'),
                'output_path': refresh.get('output_path'),
                'target_path': build_refresh_target(result, context),
            },
        })

    def log_message(self, fmt, *args):
        print(f'[build-manager-prompt] {self.address_string()} - {fmt % args}')


def main():
    parser = argparse.ArgumentParser(description='Build Manager prompt API server')
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8786)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.bind, args.port), PromptHandler)
    print(json.dumps({'ok': True, 'bind': args.bind, 'port': args.port}))
    server.serve_forever()


if __name__ == '__main__':
    main()
