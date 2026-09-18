#!/usr/bin/env python3
"""Loopback-only UI for the existing VPN Check measurement process."""
import argparse
import copy
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import sys
import threading
from urllib.parse import urlsplit
import webbrowser

from vpn_check import controller_client, snapshot

ROOT = Path(__file__).resolve().parent
MODES = {'quick': ['--rounds', '12', '--interval', '5', '--download-mib', '10'],
         'stability': ['--rounds', '60', '--interval', '10', '--download-mib', '0']}


class BusyError(Exception):
    pass


class CheckManager:
    def __init__(self, root=ROOT):
        self.root = root
        self.lock = threading.RLock()
        self.process = None
        self.token = secrets.token_urlsafe(32)
        self.current = {'id': None, 'status': 'idle', 'progress': 0, 'data': None,
                        'message': '准备就绪', 'report_id': None, 'started_at': None, 'mode': None}

    def state(self):
        with self.lock:
            return copy.deepcopy(self.current)

    def network(self):
        return snapshot(controller_client())

    def start(self, mode):
        if mode not in MODES:
            raise ValueError('请选择快速诊断或稳定性测试')
        with self.lock:
            if self.current['status'] in ('running', 'stopping'):
                raise BusyError('已有检测正在运行')
            process = subprocess.Popen([sys.executable, '-u', str(self.root / 'vpn_check.py'),
                '--events', *MODES[mode]], cwd=self.root, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, start_new_session=True)
            self.process = process
            self.current = {'id': secrets.token_hex(8), 'status': 'running', 'progress': 1,
                'data': None, 'message': '读取本机代理状态…', 'report_id': None,
                'started_at': datetime.now().astimezone().isoformat(), 'mode': mode}
            threading.Thread(target=self._collect, args=(process,), daemon=True).start()
            return self.state()

    def _collect(self, process):
        completed = False
        tail = ''
        with process.stdout:
            for line in process.stdout:
                try:
                    event = json.loads(line)
                    if not isinstance(event, dict) or event.get('event') not in ('progress', 'complete'):
                        continue
                except ValueError:
                    tail = line.strip()[-300:]
                    continue
                with self.lock:
                    if self.process is not process or self.current['status'] == 'stopping':
                        continue
                    if event.get('data') is not None:
                        self.current['data'] = event['data']
                    self.current['progress'] = event.get('progress', 0)
                    self.current['message'] = event.get('message') or '正在检测'
                    if event['event'] == 'complete':
                        completed = True
                        self.current['report_id'] = event.get('report_id')
        code = process.wait()
        with self.lock:
            if self.process is not process:
                return
            if self.current['status'] == 'stopping':
                self.current.update(status='cancelled', message='检测已停止 · 当前数据仅为部分样本')
            elif code == 0 and completed:
                self.current.update(status='complete', progress=100, message='检测完成 · 报告已保存')
            else:
                self.current.update(status='failed', message=tail or '检测未完成，请确认代理已开启后重试')
            self.process = None

    def stop(self):
        with self.lock:
            process = self.process
            if process is None or self.current['status'] not in ('running', 'stopping'):
                return self.state()
            self.current.update(status='stopping', message='正在停止检测…')
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        return self.state()

    def report(self, report_id):
        if not re.fullmatch(r'\d{8}-\d{6}-\d{6}', report_id):
            raise ValueError('无效的报告编号')
        path = self.root / 'reports' / report_id / 'report.json'
        if path.resolve().parent.parent != (self.root / 'reports').resolve():
            raise ValueError('无效的报告路径')
        return json.loads(path.read_text())

    def history(self):
        rows = []
        for path in sorted((self.root / 'reports').glob('*/report.json'), reverse=True)[:100]:
            try:
                data = self.report(path.parent.name)
                rows.append({'id': path.parent.name, 'started': data['started'],
                             'elapsed_seconds': data.get('elapsed_seconds'),
                             'proxy': data.get('proxy'), 'downloads': bool(data.get('downloads'))})
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return rows


class DemoManager(CheckManager):
    """Synthetic UI preview; never read machine settings or launch probes."""
    def __init__(self):
        super().__init__()
        from demo_data import make_demo
        self.current.update(status='complete', progress=100, demo=True, data=make_demo(),
                            message='演示模式 · 合成数据，未发起网络测试')

    def network(self):
        return copy.deepcopy(self.current['data']['before'])

    def start(self, mode):
        raise ValueError('演示模式不执行检测，请在普通模式启动服务')

    def history(self):
        return []

    def report(self, report_id):
        raise ValueError('演示模式不读取本地报告')


def make_server(port, manager):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, status, data, mime='application/json; charset=utf-8'):
            body = json.dumps(data, ensure_ascii=False).encode() if not isinstance(data, bytes) else data
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def allowed(self, mutate=False):
            actual_port = self.server.server_address[1]
            hosts = {f'127.0.0.1:{actual_port}', f'localhost:{actual_port}'}
            if self.headers.get('Host') not in hosts or self.headers.get('Sec-Fetch-Site') == 'cross-site':
                return False
            origin = self.headers.get('Origin')
            if origin and origin not in {'http://' + host for host in hosts}:
                return False
            return not mutate or secrets.compare_digest(self.headers.get('X-VPN-Token', ''), manager.token)

        def do_GET(self):
            if not self.allowed():
                return self.respond(403, {'error': '仅允许本机页面访问'})
            path = urlsplit(self.path).path
            try:
                if path == '/api/state':
                    return self.respond(200, {**manager.state(), 'token': manager.token, 'app': 'vpn-check'})
                if path == '/api/network':
                    return self.respond(200, manager.network())
                if path == '/api/history':
                    return self.respond(200, manager.history())
                if path.startswith('/api/reports/'):
                    return self.respond(200, manager.report(path.removeprefix('/api/reports/')))
                if path == '/api/export':
                    data = manager.state()['data']
                    if data is None:
                        return self.respond(404, {'error': '尚无数据'})
                    return self.respond(200, data)
                assets = {'/': ('index.html', 'text/html; charset=utf-8'),
                          '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                          '/styles.css': ('styles.css', 'text/css; charset=utf-8'),
                          '/favicon.svg': ('favicon.svg', 'image/svg+xml')}
                if path in assets:
                    name, mime = assets[path]
                    return self.respond(200, (ROOT / 'public' / name).read_bytes(), mime)
                return self.respond(404, {'error': '页面不存在'})
            except FileNotFoundError:
                return self.respond(404, {'error': '文件不存在'})
            except (ValueError, OSError):
                return self.respond(400, {'error': '无法读取此项数据'})

        def do_POST(self):
            if not self.allowed(mutate=True):
                return self.respond(403, {'error': '请从本机页面发起检测'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 1024 or self.headers.get('Content-Type') != 'application/json':
                    return self.respond(400, {'error': '无效的请求'})
                self.connection.settimeout(5)
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError('无效的请求')
                if self.path == '/api/start':
                    return self.respond(202, manager.start(body.get('mode')))
                if self.path == '/api/stop':
                    return self.respond(200, manager.stop())
                return self.respond(404, {'error': '接口不存在'})
            except BusyError as exc:
                return self.respond(409, {'error': str(exc)})
            except (ValueError, TypeError):
                return self.respond(400, {'error': '参数无效，请重新选择检测模式'})
            except OSError:
                return self.respond(500, {'error': '无法启动检测，请重启本地工具'})

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8876)
    parser.add_argument('--open', action='store_true')
    parser.add_argument('--demo', action='store_true', help='仅用合成数据预览界面，不执行检测或读取网络配置')
    args = parser.parse_args()
    manager = DemoManager() if args.demo else CheckManager()
    try:
        server = make_server(args.port, manager)
    except OSError:
        print(f'端口 {args.port} 已被占用。请打开现有页面或用 --port 指定另一个端口。', flush=True)
        raise SystemExit(1)
    url = f'http://127.0.0.1:{server.server_address[1]}'
    print(f'VPN Check 已启动：{url}\n关闭此终端会停止网页服务。', flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        manager.stop()
        server.server_close()


if __name__ == '__main__':
    main()
