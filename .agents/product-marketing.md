# Product Marketing Context

**Document version:** v1
**Last updated:** 2026-09-18
**Basis:** Current implementation. Audience and positioning are working assumptions, not market research.

## Product overview

VPN Check is a local macOS dashboard for comparing web requests through a proxy and with HTTP/SOCKS proxy settings bypassed. It combines HTTP timing, bounded downloads, local gateway ICMP samples, and observed Clash routes. It is a small open-source developer utility, not a VPN provider or hosted monitoring service. No account or paid product is part of the tool.

## Audience and jobs

Mac users with Clash Verge or a local proxy who notice slow pages or intermittent connectivity. Their immediate job is to get a repeatable report before changing nodes or proxy mode. A second job is to inspect a longer sample window and compare saved runs. B2B purchasing personas are not applicable.

## Problem and positioning

A single speed number does not explain why a domestic page slows down through a global proxy or why some sites fail while others work. VPN Check puts paired requests and their outcomes in one view. It helps narrow the next investigation; it does not automatically establish a root cause or fix network configuration.

## Alternatives

Browser speed tests, manual curl/ping commands, longer-running uptime monitors, and server-to-server throughput tools cover adjacent needs. No head-to-head benchmark has been performed. Avoid claims that this tool is faster, more accurate, or a replacement for those projects.

## Differentiation and benefits

- Paired requests make path differences visible without manually toggling the system proxy.
- A bounded 40 MiB download mode makes expected data usage clear.
- Explicit HTTP rejection and transport failure counts avoid interpreting every failure as packet loss.
- Local history and JSON export make reruns inspectable.
- A visibly labelled synthetic demo lets people inspect the interface before connecting their proxy.

## Objections and boundaries

| Question | Answer |
| --- | --- |
| Does it work everywhere? | The measurement backend targets macOS. Python 3.10+ is required; no pip/npm install is needed. |
| Does it alter my VPN? | It does not change nodes, routing, DNS or subscriptions. |
| Does bypassing proxy prove direct routing? | No. TUN or another system tunnel may still intercept it. |
| Are measurements private? | Reports are local. Public test hosts receive ordinary measurement requests; reports can include gateway addresses and node names. |
| Does it find the cause automatically? | It presents evidence and limited conditional hints, not a root-cause guarantee. |

Not for maximum-line-rate certification, UDP VPN loss measurement, uploads, mobile devices, or permanent monitoring.

## Switching dynamics

Push: unexplained slow pages and disconnected command output. Pull: one button and two paths in the same report. Habit: clicking a familiar speed-test page. Anxiety: installation effort, unexpected data usage, and exposing proxy details. Address with a no-VPN demo, three-command start, bounded traffic, and clear local-report handling.

## Voice and language

Direct, practical, calm, evidence-based. Use: compare paths, start a check, inspect response time, save a report. Avoid: instant diagnosis, guaranteed fix, fastest node, VPN packet-loss proof, completely offline. No testimonials, customer counts, or conversion gains are available. Do not publish private conversation excerpts as testimonials.

## Proof

Capabilities are backed by `vpn_check.py`, `web_server.py`, frontend code, and automated tests. README imagery uses synthetic data and is labelled accordingly. Local smoke runs established that measurement and report saving worked on one Mac; do not publish personal network records or claim broad compatibility from them. CI results can be cited only after the workflow passes on the published revision.

## Goals and page structure

Primary action: clone the repository and run a local check. Secondary action: open the synthetic demo without an active proxy. README order: clear one-liner, preview, requirements/start commands, what the two modes answer, interpretation boundaries, further docs. No analytics, email signup, messaging or social publishing is part of this release.

## Copy decisions

Selected: “VPN 卡顿，先看两条路径的差别。” Leads with the observed pain and the actual mechanism.
Alternative: “给你的代理连接做一次对照检查。” More literal but less memorable.
Alternative: “网速、响应、波动，放在一份本地报告里。” Useful feature summary, less specific about the differentiator.
Primary CTA: “开始检测”; secondary: “先看演示”. These are choices for clarity, not validated conversion improvements.

## Workflow source

Applied [marketingskills](https://github.com/coreyhaines31/marketingskills/tree/5b2c0007766c6a1cf1d53fd8fc73e979e0821022): product-marketing, copywriting, cro. User authorized publication to the public `rzr002/vpn-check` repository.

## Changelog

- v1 (2026-09-18) — Establish implementation-backed positioning and first-run flow for the first public GitHub release.
