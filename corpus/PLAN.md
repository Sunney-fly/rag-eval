# 个人版贾维斯 · 项目规划（已定稿）

## 已确认的决策（2025）

| 决策项 | 选择 |
|---|---|
| 手机 | Android |
| 模型 | 云端 API，国内直连（DeepSeek 主 / Qwen、GLM 备） |
| 中枢 | 云服务器 VPS（4C8G）+ 自建 core + 现成前端 Open WebUI |
| 预算 | ¥100–200/月 |
| 开工方式 | 先在本仓库搭好全部代码，买好 VPS 后一键部署 |

## 架构定调

一台国内云服务器做"大脑"；Docker 上跑自建中枢（core）+ Postgres(pgvector) 记忆库 + Open WebUI 前端 + 工具服务；Android 手机通过 Tailscale 私网接入，微信（WxPusher）接收主动推送。全程不暴露公网端口，免备案、免域名。

```
VPS（全部 Docker 化）
├── core      自建中枢：Agent 循环 + 工具注册 + 调度 + 记忆 + 记账 + 语音
├── postgres  会话/事实记忆(pgvector)/任务/成本账本
├── webui     Open WebUI：聊天/PWA/多端入口
├── searxng   搜索聚合    ├── radicale  日历(CalDAV)
├── browser   Playwright 渲染
├── uptime-kuma 监控      └── caddy(可选) Tailscale HTTPS→解锁麦克风
```

## 分阶段路线图（代码侧已全部实现，部署后按序验收）

- **P0 地基**：VPS + Docker + Tailscale + Postgres + Open WebUI + 备份
  验收：手机免翻墙打开 WebUI 正常对话；重装 30 分钟可恢复
- **P1 中枢核心**：OpenAI 兼容接口 + Agent 工具循环 + 会话落库 + 主备切换 + 记账
  验收：能自动调用工具完成任务；杀掉主模型 key 自动切备用
- **P2 工具生态**：搜索/天气/日历/邮件/便签/提醒/浏览器
  验收："查明天杭州天气并写进日历"一条指令端到端完成
- **P3 长期记忆**：事实抽取 + 向量检索注入
  验收：换设备问"我上次说的健身房"能答对；记忆可查看/删除
- **P4 主动性**：定时简报 + 事件提醒 + 微信推送
  验收：每天 8:00 微信收到简报；日程提醒准时到达
- **P5 手机端**：PWA + 语音 + 日历订阅 + Tasker 联动
  验收：锁屏收推送 → 点开 PWA 语音继续追问
- **P6 语音闭环**：STT/TTS 全链路
  验收：3 分钟连续语音对话不丢上下文
- **P7 健全化**：监控告警 + 备份演练 + 成本预警 + 故障排查手册
- **P8 未来**：电脑控制、Home Assistant、视觉、自研 Android App

## 关键设计取舍

1. **流式输出**：v1 用"循环非流式 + 最终答案重新流式生成"的折中方案（成本增加可忽略，架构简单可靠）
2. **数据库**：Postgres + pgvector 单库承载结构化与向量数据，少一个服务少一分故障
3. **推送**：WxPusher（微信）绕开国产 ROM 杀后台和 FCM 问题
4. **语音**：手机录音 → core → 云端 FunASR → LLM → MiniMax/Edge TTS，不依赖浏览器 Web Speech
5. **降级运行**：依赖服务（DB/日历/搜索）挂了 core 不崩，日志告警并跳过对应功能
