#!/bin/bash
cd -- "$(dirname -- "$0")" || exit 1
vpn_check_python="$(command -v python3)"
if [ -z "$vpn_check_python" ] && [ -x "$HOME/miniconda/bin/python3" ]; then
  vpn_check_python="$HOME/miniconda/bin/python3"
fi
if [ -z "$vpn_check_python" ]; then
  echo '没有找到 Python 3，请安装后重试。'
else
  "$vpn_check_python" vpn_check.py "$@"
fi
printf '\n按回车关闭窗口。'
read -r
