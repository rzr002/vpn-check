"""Deterministic synthetic example. No machine configuration or real measurements."""
from copy import deepcopy


def make_demo():
    before = {'at': '2026-01-01T12:00:00+08:00',
              'system_proxy': 'HTTPEnable : 1\nHTTPPort : 7897\nHTTPProxy : 127.0.0.1',
              'default_route': 'gateway: 192.0.2.1\ninterface: demo0',
              'cisco': ['未连接（演示）'], 'proxy_query_exit': 0,
              'clash': {'available': True, 'mode': 'global', 'tun': False, 'port': 7897}}
    probes = {}
    variation = [0, 16, -9, 38, 120, 24, -11, 55, 9, -8, 22, 3]
    base = {'百度': (150, 920), 'Cloudflare': (640, 340), 'Google': (None, 295), 'GitHub': (None, 410)}
    for host, times in base.items():
        for path, ms in zip(('绕过代理', '经代理'), times):
            rows = []
            for i, delta in enumerate(variation):
                ok = ms is not None
                ttfb = ms + delta if ok else None
                rows.append({'at': f'2026-01-01T12:00:{i*5:02d}+08:00',
                             'exit_code': 0 if ok else 28, 'status': 200 if ok else 0,
                             'dns_ms': 1 if ok else 4, 'connect_ms': 3 if ok else 0,
                             'tls_ms': ttfb * .6 if ok else 0, 'ttfb_ms': ttfb,
                             'total_ms': ttfb + 12 if ok else 4000, 'bytes': 512 if ok else 0,
                             'bytes_per_second': 0, 'error': '' if ok else 'Synthetic connection timeout'})
            probes[f'{host} / {path}'] = rows
    downloads = [{'path': path, 'expected_bytes': 10485760, 'bytes': 10485760,
                  'mbps': mbps, 'status': 200, 'exit_code': 0}
                 for path, mbps in [('绕过代理', 62.4), ('经代理', 28.4), ('绕过代理', 61.6), ('经代理', 29.2)]]
    return {'synthetic': True, 'started': before['at'], 'proxy': 'http://127.0.0.1:7897',
            'before': before, 'after': deepcopy(before), 'probes': probes, 'downloads': downloads,
            'elapsed_seconds': 84, 'gateway_ping': {'available': True, 'loss_percent': 0,
                'rtt_min_avg_max_stddev_ms': [2.1, 4.2, 8.8, 1.2], 'packets_requested': 20},
            'paths': [{'host': host, 'chains': ['Demo node', 'GLOBAL'], 'rule': '', 'rulePayload': ''}
                      for host in ['www.baidu.com', 'speed.cloudflare.com', 'www.google.com', 'github.com']]}
