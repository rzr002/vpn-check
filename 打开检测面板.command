#!/bin/bash
cd -- "$(dirname -- "$0")" || exit 1
vpn_check_python="$(command -v python3)"
if [ -z "$vpn_check_python" ] && [ -x "$HOME/miniconda/bin/python3" ]; then
  vpn_check_python="$HOME/miniconda/bin/python3"
fi
if [ -z "$vpn_check_python" ]; then
  echo '没有找到 Python 3。'
  read -r
  exit 1
fi
if /usr/bin/curl -q --noproxy '*' --max-time 2 -fsS http://127.0.0.1:8876/api/state 2>/dev/null | "$vpn_check_python" -c 'import json,sys; sys.exit(0 if json.load(sys.stdin).get("app")=="vpn-check" else 1)' 2>/dev/null; then
  /usr/bin/open http://127.0.0.1:8876
else
  "$vpn_check_python" web_server.py --open
fi
