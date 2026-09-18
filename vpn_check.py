#!/usr/bin/env python3
"""macOS VPN diagnostics using Python's standard library and system curl."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import math
from pathlib import Path
import re
import statistics
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
TARGETS = [('百度', 'https://www.baidu.com/'),
           ('Cloudflare', 'https://speed.cloudflare.com/__down?bytes=0'),
           ('Google', 'https://www.google.com/generate_204'),
           ('GitHub', 'https://github.com/')]
FORMAT = '%{http_code}|%{time_namelookup}|%{time_connect}|%{time_appconnect}|%{time_starttransfer}|%{time_total}|%{size_download}|%{speed_download}'


def run(args, timeout=8):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, '', 'command timed out'
    except OSError as exc:
        return 127, '', str(exc)


def curl_args(url, proxy, timeout):
    args = ['/usr/bin/curl', '-q', '--silent', '--show-error', '--connect-timeout', '4',
            '--max-time', str(timeout), '--max-filesize', str(32 * 1024 * 1024),
            '--header', 'Cache-Control: no-cache', '--output', '/dev/null', '--write-out', FORMAT]
    args += ['--noproxy', '', '--proxy', proxy] if proxy else ['--noproxy', '*']
    return args + [url]


def parse_probe(output, exit_code):
    row = {'exit_code': exit_code, 'status': 0, 'dns_ms': None, 'connect_ms': None,
           'tls_ms': None, 'ttfb_ms': None, 'total_ms': None, 'bytes': 0, 'bytes_per_second': 0}
    try:
        parts = output.strip().split('|')
        if len(parts) != 8:
            return row
        values = [float(v) for v in parts]
        if not all(math.isfinite(v) and v >= 0 for v in values):
            return row
        row.update(status=int(values[0]), dns_ms=values[1]*1000, connect_ms=values[2]*1000,
                   tls_ms=values[3]*1000, ttfb_ms=values[4]*1000, total_ms=values[5]*1000,
                   bytes=int(values[6]), bytes_per_second=values[7])
    except ValueError:
        pass
    return row


def success(row):
    return row['exit_code'] == 0 and 200 <= row['status'] < 400


def summarize(rows):
    good = [r for r in rows if success(r)]
    times = sorted(r['ttfb_ms'] for r in good)
    variations = [abs(a['ttfb_ms']-b['ttfb_ms']) for a, b in zip(rows, rows[1:]) if success(a) and success(b)]
    return {'samples': len(rows), 'successes': len(good),
            'transport_failures': sum(r['exit_code'] != 0 or r['status'] == 0 for r in rows),
            'http_rejections': sum(r['exit_code'] == 0 and r['status'] >= 400 for r in rows),
            'http_statuses': dict(Counter(str(r['status']) for r in rows)),
            'median_ttfb_ms': round(statistics.median(times), 1) if times else None,
            'p95_ttfb_ms': round(times[math.ceil(len(times)*0.95)-1], 1) if times else None,
            'variation_ms': round(statistics.mean(variations), 1) if variations else None}


def download_mbps(row, expected_bytes):
    if success(row) and row['status'] == 200 and row['bytes'] == expected_bytes:
        return row['bytes_per_second'] * 8 / 1_000_000
    return None


def probe(url, proxy, timeout=8):
    code, out, err = run(curl_args(url, proxy, timeout), timeout+2)
    return {**parse_probe(out, code), 'at': datetime.now().astimezone().isoformat(), 'error': err.strip()[:250]}


def controller_client():
    # Read only the controller address and token. Never persist configuration or token.
    try:
        source = (Path.home() / 'Library/Application Support/io.github.clash-verge-rev.clash-verge-rev/clash-verge.yaml').read_text()
        def scalar(key):
            match = re.search(r'^' + re.escape(key) + r':\s*(.*)$', source, re.M)
            return match[1].strip().strip('\"\'') if match else ''
        address, secret = scalar('external-controller'), scalar('secret')
        if not re.fullmatch(r'127\.0\.0\.1:\d+', address):
            return lambda path: {}
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        def get(path):
            try:
                request = urllib.request.Request('http://' + address + path,
                    headers={'Authorization': 'Bearer ' + secret} if secret else {})
                with opener.open(request, timeout=2) as response:
                    return json.load(response)
            except (OSError, ValueError):
                return {}
        return get
    except OSError:
        return lambda path: {}


def snapshot(controller):
    code, proxy, _ = run(['/usr/sbin/scutil', '--proxy'])
    _, route, _ = run(['/sbin/route', '-n', 'get', 'default'])
    _, cisco, _ = run(['/opt/cisco/secureclient/bin/vpn', 'state'])
    config = controller('/configs')
    return {'at': datetime.now().astimezone().isoformat(),
            'system_proxy': '\n'.join(line.strip() for line in proxy.splitlines() if re.search(r'(?:Enable|Port|Proxy)\s*:', line)),
            'default_route': '\n'.join(line.strip() for line in route.splitlines() if 'gateway:' in line or 'interface:' in line),
            'cisco': re.findall(r'state:\s*([^\r\n]+)', cisco)[-1:] or ['unknown'],
            'clash': {'available': bool(config), 'mode': config.get('mode'),
                      'tun': config.get('tun', {}).get('enable'), 'port': config.get('mixed-port')},
            'proxy_query_exit': code}


def observe_paths(controller):
    hosts = {'www.baidu.com', 'speed.cloudflare.com', 'www.google.com', 'github.com'}
    return [{'host': c.get('metadata', {}).get('host'), 'chains': c.get('chains', []),
             'rule': c.get('rule'), 'rulePayload': c.get('rulePayload')}
            for c in controller('/connections').get('connections', [])
            if c.get('metadata', {}).get('host') in hosts]


def ping_gateway(route):
    match = re.search(r'gateway:\s*([\d.]+)', route)
    if not match:
        return {'available': False, 'reason': 'No IPv4 default gateway'}
    code, out, err = run(['/sbin/ping', '-n', '-c', '20', '-i', '1', '-W', '1000', match[1]], 28)
    loss = re.search(r'([\d.]+)% packet loss', out)
    rtt = re.search(r'= ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+) ms', out)
    return {'available': bool(loss), 'exit_code': code, 'packets_requested': 20,
            'loss_percent': float(loss[1]) if loss else None,
            'rtt_min_avg_max_stddev_ms': [float(x) for x in rtt.groups()] if rtt else None,
            'error': err.strip()[:200]}


def report_markdown(data):
    def num(v):
        return '未测得' if v is None else f'{v:.1f}'
    lines = ['# VPN 测试报告', '', f"测试开始：{data['started']}；总耗时：{data['elapsed_seconds']:.0f} 秒。", '',
             f"代理入口：`{data['proxy']}`；Clash 状态：`{json.dumps(data['before']['clash'], ensure_ascii=False)}`。", '',
             '“经代理”表示明确连接所选代理入口；Clash Rule 模式仍可能让目标走 DIRECT，实际路径见下文。', '',
             '## 网页响应与短时稳定性', '',
             '| 目标 / 路径 | 成功 / 样本 | 传输失败 | HTTP 拒绝 | 首字节中位数 ms | P95 ms | 相邻波动 ms |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for name, rows in data['probes'].items():
        s = summarize(rows)
        lines.append(f"| {name} | {s['successes']}/{s['samples']} | {s['transport_failures']} | {s['http_rejections']} | {num(s['median_ttfb_ms'])} | {num(s['p95_ttfb_ms'])} | {num(s['variation_ms'])} |")
    lines += ['', '首字节时间包含新连接建立、TLS、代理和网站处理时间，不等于 ping 延迟。HTTP 4xx/5xx 单独计数。波动为连续成功样本的首字节耗时差绝对值均值，不等于网络 RTT jitter。', '',
              '## 定量下载', '', '| 路径 | 测试体积 MiB | 实收 MiB | 平均 Mbps | HTTP / curl |', '| --- | ---: | ---: | ---: | --- |']
    for row in data['downloads']:
        lines.append(f"| {row['path']} | {row['expected_bytes']/1048576:.0f} | {row['bytes']/1048576:.2f} | {num(row['mbps'])} | {row['status']} / {row['exit_code']} |")
    lines += ['', '下载为到 Cloudflare 的单连接样本，含连接开销；只对完整成功下载计算 Mbps，不是线路带宽上限。未测上传速度或 UDP 丢包。', '',
              '## 本地网络与连接状态', '', '```json', json.dumps({'before': data['before'], 'after': data['after'], 'gateway_ping': data['gateway_ping']}, ensure_ascii=False, indent=2), '```', '',
              '网关 ping 仅反映本地网络路径；网关也可能限制 ICMP。它不能代表 VPN 节点丢包。', '',
              '## 观测到的 Clash 分流', '', '```json', json.dumps(data['paths'], ensure_ascii=False, indent=2), '```', '',
              '分流记录来自采样时仍活跃的连接；相同域名可能包含其他应用的请求。未捕获不表示直连，也不表示经过节点。', '',
              '## 结果边界', '',
              '- 短时无失败不能证明全天稳定。建议同一节点运行 10–30 分钟，并在卡顿时复测。',
              '- “绕过代理”只绕过 HTTP/SOCKS 代理设置；TUN/其他 VPN 路由仍可能接管流量。',
              '- 代理请求的 DNS/TCP 时间通常对应本地代理入口，不能解释为海外节点的 DNS/TCP 延迟。',
              '- 本轮仅发起测试流量和只读查询，不切换节点，不修改系统设置。', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='VPN Check：macOS 代理状态、HTTP 稳定性、网关丢包与定量下载')
    parser.add_argument('--rounds', type=int, default=12)
    parser.add_argument('--interval', type=float, default=5, help='各轮起点的最小间隔秒数；慢请求会延长周期')
    parser.add_argument('--proxy', help='HTTP 或 socks5h 本地代理；默认从 Clash 或系统检测')
    parser.add_argument('--download-mib', type=int, choices=range(0, 33), default=10, metavar='0..32', help='每条路径单次下载体积，0 跳过，默认两次/路径')
    parser.add_argument('--events', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    def announce(message, data=None, progress=0, event='progress', report_id=None):
        if args.events:
            print(json.dumps({'event': event, 'message': message, 'progress': progress,
                              'data': data, 'report_id': report_id}, ensure_ascii=False), flush=True)
        else:
            print(message, flush=True)
    if not 1 <= args.rounds <= 10000 or not 0 <= args.interval <= 3600:
        parser.error('rounds 须为 1..10000，interval 须为 0..3600')
    controller = controller_client()
    before = snapshot(controller)
    port = before['clash']['port']
    if not port:
        match = re.search(r'HTTPPort\s*:\s*(\d+)', before['system_proxy'])
        host = re.search(r'HTTPProxy\s*:\s*(\S+)', before['system_proxy'])
        if match and host and host[1] in ('127.0.0.1', 'localhost'):
            port = int(match[1])
    proxy = args.proxy or (f'http://127.0.0.1:{port}' if port else None)
    if not proxy or not re.fullmatch(r'(?:http|socks5h)://(?:127\.0\.0\.1|localhost):\d{1,5}', proxy):
        parser.error('未检测到本地代理。请用 --proxy http://127.0.0.1:端口 指定；需在正常系统环境运行。')
    start = time.monotonic()
    data = {'started': datetime.now().astimezone().isoformat(), 'proxy': proxy, 'before': before,
            'probes': {}, 'downloads': [], 'paths': []}
    jobs = [(f'{name} / {label}', url, p) for name, url in TARGETS for label, p in [('绕过代理', None), ('经代理', proxy)]]
    data['probes'] = {name: [] for name, _, _ in jobs}
    announce(f'已连接代理 · 即将开始 {args.rounds} 轮检测', data, 3)
    with ThreadPoolExecutor(max_workers=10) as pool:
        ping = pool.submit(ping_gateway, before['default_route'])
        for i in range(args.rounds):
            tick = time.monotonic()
            futures = [(name, pool.submit(probe, url, p)) for name, url, p in jobs]
            time.sleep(0.25)
            data['paths'].extend(observe_paths(controller))
            for name, future in futures:
                data['probes'][name].append(future.result())
            if ping.done():
                data['gateway_ping'] = ping.result()
            data['elapsed_seconds'] = round(time.monotonic()-start, 1)
            announce(f'网页响应检测 {i+1}/{args.rounds}', data, 5 + (i+1)/args.rounds * (65 if args.download_mib else 85))
            if i+1 < args.rounds:
                time.sleep(max(0, args.interval-(time.monotonic()-tick)))
        data['gateway_ping'] = ping.result()
        if args.download_mib:
            size = args.download_mib * 1048576
            # Alternate paths to reduce bias from network changes over time.
            for repetition in range(2):
                for label, p in [('绕过代理', None), ('经代理', proxy)]:
                    url = f'https://speed.cloudflare.com/__down?bytes={size}&nonce={time.time_ns()}'
                    future = pool.submit(probe, url, p, 25)
                    time.sleep(0.25)
                    data['paths'].extend(observe_paths(controller))
                    row = future.result()
                    row.update(path=label, expected_bytes=size, mbps=download_mbps(row, size))
                    data['downloads'].append(row)
                    data['elapsed_seconds'] = round(time.monotonic()-start, 1)
                    announce(f'下载检测 · {label} {repetition+1}/2', data, 70 + len(data['downloads'])*6)
    data['paths'] = list({json.dumps(x, sort_keys=True): x for x in data['paths']}.values())
    data['after'] = snapshot(controller)
    data['elapsed_seconds'] = round(time.monotonic()-start, 1)
    folder = ROOT / 'reports' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    folder.mkdir(parents=True, exist_ok=False)
    (folder / 'report.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    (folder / 'report.md').write_text(report_markdown(data))
    announce(f'报告已保存：{folder / "report.md"}', data, 100, 'complete', folder.name)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n已停止。未完成的本轮没有生成完整报告。')
        raise SystemExit(130)
