# 数据与隐私 / Data and privacy

## 本地处理

服务仅监听 `127.0.0.1`。网页资源随代码提供，不加载第三方脚本或字体；代码没有内置分析追踪、结果遥测、注册或订阅功能。

真实检测只读查询系统代理、默认网关、Clash 控制器和可选的 Cisco 客户端状态。Clash 控制器密钥只用于本机控制器认证，不写入报告。不会读取订阅内容作为报告，不会修改节点或系统设置。

## 对外请求

测速并非离线操作。真实检测会向百度、Cloudflare、Google、GitHub 发起公开 HTTPS 请求。目标站点和代理服务能够观察这些请求及其出口地址。下载测速使用 Cloudflare 的公开端点；其服务处理不由本工具控制。

## 报告与分享

本地报告可能包含：检测时间、代理端口、默认网关地址、网络接口、节点名称、分流规则及测试错误信息。`reports/` 默认被 Git 忽略，不会随普通 `git add` 提交。

分享导出的 JSON/Markdown 前，检查网关、节点名称和规则是否适合公开。`--demo` 不读取真实网络信息或报告；仓库截图使用合成样例。

## English summary

The server binds to loopback only. There is no built-in analytics or result-upload feature. Real tests contact public endpoints; those services and your proxy can observe the requests. Local reports can contain timestamps, gateway/interface details, proxy ports, node names and routing rules. Review them before sharing. Reports are git-ignored. Demo mode uses synthetic data and does not inspect local network settings or real history.
