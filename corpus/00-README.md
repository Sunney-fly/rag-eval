# jarvis-hub —— 个人版贾维斯

一台国内云服务器做"大脑"，手机和电脑共用的个人 AI 助手中枢。目标是超过豆包手机：**有记忆、会主动推送、能真正动手执行任务**，接近 J.A.R.V.I.S. 的体验。

## 当前状态

- ✅ **代码全部完成**：core 中枢 + 10 个内置工具 + 三层"自己装工具"机制 + 长期记忆 + 定时调度 + 微信推送 + 语音 + 成本记账
- ✅ **测试通过**：55 项 pytest 全绿（Agent 循环/故障切换/工具注册/记账/API/动态工具三层机制）
- ⏳ **待部署**：买好 4C8G 国内 VPS 后，按 [docs/DEPLOY.md](docs/DEPLOY.md) 一键部署

## 特性

- 🧠 **自建中枢（core）**：Agent 工具循环（规划→执行→检查），真正"办事"而不只是聊天
- 🔄 **模型主备切换**：DeepSeek 主 + Qwen/GLM 备用，主模型故障自动切换，不中断服务
- 🛠️ **自己装工具（三层机制）**：①写 YAML 配置工具 ②接 MCP 生态 ③一句话让它自己写代码装工具（安全闸+双模型审查+确认模式），见 [docs/TOOLS.md](docs/TOOLS.md)
- 🧩 **内置工具**：网页搜索、网页抓取、天气、日历、邮件、便签、提醒、Playwright 渲染
- 🗄️ **长期记忆**：Postgres + pgvector，事实抽取入库 + 检索注入，跨设备同一份记忆
- ⏰ **主动性**：定时早间简报 + 事件提醒，通过**微信（WxPusher）**主动推送
- 🎙️ **语音闭环**：云端 STT（FunASR）+ TTS（MiniMax/Edge-TTS），OpenAI 兼容音频接口
- 💰 **成本控制**：每次调用记账、月度预算超支告警
- 🔒 **安全**：Tailscale 私网，不暴露公网端口，免备案、免域名
- 📱 **Android 端**：Open WebUI PWA + 语音 + 微信推送 + 日历订阅（DAVx5）+ Tasker 联动

## 架构

```
云服务器 VPS（4C8G，Docker Compose）
├── core      自建中枢（FastAPI + Agent 循环 + 调度 + 记忆 + 记账）
├── postgres  Postgres16 + pgvector（会话/记忆/任务/账本）
├── webui     Open WebUI（现成前端，手机 PWA 入口）
├── searxng   搜索聚合（bing/baidu/duckduckgo）
├── radicale  CalDAV 日历（手机 DAVx5 订阅）
├── browser   Playwright 渲染服务
├── uptime-kuma  监控告警
└── caddy    （可选）Tailscale HTTPS，解锁手机麦克风
```

## 快速开始

1. 买一台国内 VPS（Ubuntu 22.04+，4C8G）
2. 按 **[docs/DEPLOY.md](docs/DEPLOY.md)** 部署（约 30 分钟）
3. 手机按 **[docs/ANDROID.md](docs/ANDROID.md)** 接入

## 文档

| 文档 | 内容 |
|---|---|
| [docs/PLAN.md](docs/PLAN.md) | 项目规划与决策记录 |
| [docs/DEPLOY.md](docs/DEPLOY.md) | VPS 部署指南（国内直连版） |
| [docs/ANDROID.md](docs/ANDROID.md) | 手机端接入与 Tasker 联动 |
| [docs/TOOLS.md](docs/TOOLS.md) | 工具扩展：YAML 配置 / MCP / 自我写码三层机制 |
| [docs/OPERATIONS.md](docs/OPERATIONS.md) | 日常运维、备份、监控、排障 |
| [docs/COST.md](docs/COST.md) | 成本构成与省钱建议 |

## 目录结构

```
jarvis-hub/
├── core/            # 自建中枢（Python/FastAPI）
│   ├── src/core/    # 源码：agent/tools(含dynamic三层工具)/memory/scheduler/push/voice
│   └── tests/       # pytest 测试（55 项）
├── tools/           # 工具服务：searxng/radicale/browser/caddy
├── tools.d/         # 动态工具：*.yaml 配置工具 + generated/(自我写码产物) + pending/
├── mcp.json         # MCP 服务器配置
├── scripts/         # 部署/备份/HTTPS 脚本
├── docs/            # 文档
├── docker-compose.yml
├── .env.example
└── Makefile
```

## 开发

```bash
cd core
pip install -e ".[dev]"
pytest -q        # 本地跑测试（不需要数据库和外部 API）
```
