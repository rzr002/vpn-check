# VPN Check

面向 macOS 的轻量 VPN/代理诊断工具，使用系统 curl 和 Python 3.10+ 标准库，不需要安装第三方依赖。支持 Clash Verge 自动检测，也可指定本机 HTTP / SOCKS5 代理。

## 网页一键检测

双击 `打开检测面板.command`，浏览器会打开 **http://127.0.0.1:8876**。保留启动服务的终端窗口，然后在页面点击 **开始检测**。

- **快速诊断**：12 轮双路径网页请求 + 40 MiB 下载测试，通常 1–4 分钟。
- **稳定性观察**：60 轮，轮次间隔至少 10 秒；不下载测速文件，通常约 10 分钟。
- 可随时停止；停止后页面保留部分样本，可导出，但不会当成完整报告加入历史。部分样本仅保留到下一轮检测或服务重启。
- 实时显示进度、Google 首字节中位数、成功率、本地网关丢包、下载速度、每站对照与响应曲线。
- 底部可查看最近 100 次已保存报告，历史数据有明确标记；刷新浏览器不会中断当前检测。
- 左侧连接信息是按需采集的快照，切换节点或代理模式后可点“刷新”。

手动启动：

```sh
python3 web_server.py --open
# 默认端口被其他软件占用时
python3 web_server.py --port 8877 --open
```

服务仅监听本机回环地址。关闭终端后需重新双击启动；没有安装后台自启动服务。重复双击启动器会优先打开已运行的检测面板。

## 命令行使用

双击 `开始检测.command`。默认对 4 个网站做 12 轮对照请求，另做 40 MiB 定量下载；通常需要 1–4 分钟，超时会延长测试时间。报告保存在 `reports/时间戳/report.md`，原始数据在同目录 `report.json`。

也可以在本目录运行：

```sh
python3 vpn_check.py
# 连续观察约 10 分钟，暂不下载测速
python3 vpn_check.py --rounds 60 --interval 10 --download-mib 0
# 自己指定代理端口
python3 vpn_check.py --proxy http://127.0.0.1:7897
# SOCKS5，并由代理解析域名
python3 vpn_check.py --proxy socks5h://127.0.0.1:1080
```

测试时保持当前节点和连接方式不变。若想比较节点，手动换节点后重跑；报告会分别保留。按 Ctrl+C 可结束，但中断的本轮不生成完整报告。工具不会修改代理、DNS、路由或订阅，不会自动切换节点。

## 测量内容

- 连接状态：系统代理端口、Clash 控制器可用性、Rule/Global、TUN、公司 Cisco 状态，以及测试前后快照。
- 可用性：百度、Cloudflare、Google、GitHub 的绕过代理 / 经代理对照；HTTP 拒绝和传输失败分别统计。成功仅指入口返回 2xx/3xx，不验证登录或页面资源。
- 响应：首字节耗时中位数、P95、相邻成功请求耗时波动。
- 下载：两条路径各两次固定体积单连接下载；只有 HTTP 200、curl 成功且字节数完全匹配才计算 Mbps。
- 本地网络：向默认网关发 20 个 ICMP 包，记录响应时间及丢包率。
- 分流证据：只读采样 Clash 活跃连接中测试域名的节点链与规则，不导出订阅或认证密钥。

## 必须正确理解

1. 经 Clash 入口不等于经海外节点。Rule 模式可能对测速网站选 DIRECT；报告会显示捕获的分流记录。记录是域名级采样，同域名可能混入其他应用连接，未捕获则保持未知。
2. 绕过代理是 curl 不使用 HTTP/SOCKS 设置；TUN/其他 VPN 仍能接管流量。它不等于关闭 VPN 后的绝对直连。
3. 首字节耗时包含连接、TLS、网站响应；不是纯网络 RTT。代理请求中的 DNS/TCP 时间通常是连接本地代理的开销。
4. HTTP 失败率不是丢包率；网关 ICMP 丢包也不是 VPN 节点丢包。HTTP 403/429 等可能是网站策略。
5. 下载样本是到 Cloudflare 的单连接平均速度，含建立连接开销，不是最大带宽。本工具尚不测上传速度、UDP 丢包、负载下延迟。
6. 12 轮检测只反映采样窗口。看长期稳定性需要 10–30 分钟或更长记录；慢请求会拉长轮次间隔。
7. 在网络受限的沙箱里运行会失真；用本机终端或正常系统网络环境运行。测试请求会抵达公开目标，报告仅保存在本地。

## 可直接使用的开源项目

| 项目 | 适合做什么 | 使用条件 / 注意点 |
| --- | --- | --- |
| [LibreSpeed CLI](https://github.com/librespeed/speedtest-cli) | 上传、下载、延迟、抖动，多测速服务器 | 适合专门测速；确认请求的代理路径，必要时关闭遥测；不能仅凭吞吐量评价稳定性 |
| [Uptime Kuma](https://github.com/louislam/uptime-kuma) | 长期 HTTP/TCP/Ping/DNS 可用率和曲线，支持代理 | 适合长期看断连；部署较重，官方安装平台清单未列 macOS；Docker 内 localhost 与宿主机不同 |
| [Trippy](https://github.com/fujiapple852/trippy) | 可视化路由追踪、延迟、丢包排查 | 测节点 IP/底层线路时有用；普通 HTTP 代理不会转发 ICMP，不能直接代表代理网站体验 |
| [iperf3](https://github.com/esnet/iperf) | 自建 VPN 的端到端 TCP/UDP 吞吐、丢包、抖动 | 需要你控制服务器，在隧道内运行服务端和客户端；HTTP 代理不直接承载 iperf3 |
| [Cloudflare speedtest](https://github.com/cloudflare/speedtest) | 现成浏览器测速引擎，能进一步接入页面 | 可直接用 [Cloudflare 测速页](https://speed.cloudflare.com/)；需确认 Clash 对该域名的分流 |

本工具使用 Cloudflare 公开的下载测试端点，并非官方测速引擎，算法和结果不与官网等同。参考项目资料检查日期：2026-09-18。

## 开发检查

```sh
python3 -m unittest discover -s tests -v
```

## 无需代理的演示

运行 `python3 web_server.py --demo --port 8877 --open` 查看合成样例。演示不读取真实网络配置或历史报告，不发起测速。
