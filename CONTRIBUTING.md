# Contributing

Small fixes and reproducible bug reports are welcome. Measurement code targets macOS; the synthetic demo can be used to review the UI without a proxy.

```bash
python3 web_server.py --demo --port 8877 --open
python3 -m unittest discover -s tests -v
node --check public/app.js  # optional local syntax check; Node is not a runtime dependency
bash -n 打开检测面板.command
bash -n 开始检测.command
```

Tests use temporary files and local loopback servers. They do not run public speed tests. Add regression coverage for measurement classification, cancellation, and API behavior changes. Keep HTTP rejection distinct from transport failure, and unknown metrics distinct from zero.

When filing an issue, include the macOS/Python version, expected and actual behavior, and a minimal reproduction. Prefer synthetic examples; remove gateway addresses, node names, credentials and private routing details from logs.

Do not add real reports, tokens or subscription configuration. Repository screenshots must be visibly marked as synthetic when generated from demo data.
