# 运维手册

## 常用命令（在 VPS 的 /root/jarvis-hub 下）

| 操作 | 命令 |
|---|---|
| 启动/停止 | `docker compose up -d` / `docker compose stop` |
| 状态 | `docker compose ps`（healthy 才算正常） |
| 看日志 | `docker compose logs -f core`（加服务名只看单个） |
| 重启中枢 | `docker compose restart core` |
| 重新构建 | `docker compose up -d --build` |
| 健康检查 | `curl http://localhost:8000/healthz` |

## 备份与恢复

- 每日备份：`scripts/backup.sh`（建议 cron 每天 3:00，见 DEPLOY.md）
- 备份内容：Postgres 全量（会话/记忆/任务/账本/便签）+ 日历数据卷 + WebUI 数据卷，保留 10 天
- 恢复数据库：
  ```bash
  bash scripts/restore.sh backups/jarvis-20250601-030000.sql.gz
  ```
- 恢复日历数据卷：
  ```bash
  docker run --rm -v jarvis_radicale_data:/data -v $PWD/backups:/backup alpine \
    sh -c "rm -rf /data/* && tar xzf /backup/radicale-xxxx.tgz -C /data"
  ```
- **恢复演练**：每季度在另一台机器上跑一次 restore.sh，验证备份可用（P7 验收项）

## 监控告警（Uptime Kuma）

浏览器打开 `http://<VPS的Tailscale IP>:3001` 建号，添加 4 个监控：

| 名称 | 类型 | 目标 |
|---|---|---|
| core 健康 | HTTP(s) | `http://core:8000/healthz` |
| WebUI | HTTP(s) | `http://webui:8080` |
| 搜索 | HTTP(s) | `http://searxng:8080` |
| 浏览器服务 | HTTP(s) | `http://browser:8080/healthz` |

全部选 60 秒间隔，告警渠道配 Webhook 或邮箱。core 的 `/healthz` 返回 `degraded` 时（数据库挂了）也会触发。

## 成本管理

```bash
# 本月账单（-H 里填 .env 的 AUTH_TOKEN）
curl -H "Authorization: Bearer $AUTH_TOKEN" http://localhost:8000/v1/cost/summary
curl -H "Authorization: Bearer $AUTH_TOKEN" "http://localhost:8000/v1/cost/summary?month=2025-06"
```

- 每次模型调用都会记账（含早间简报、记忆抽取）
- 月度超过 `MONTHLY_BUDGET_CNY`（默认 80 元）时微信告警一次，不会中断服务
- 想省钱：`.env` 里调低预算值、把 `PRIMARY_MODEL` 换成更便宜的模型

## 记忆管理

```bash
# 查看中枢记住了什么
curl -H "Authorization: Bearer $AUTH_TOKEN" http://localhost:8000/v1/memory/facts
# 删除某条记忆（id 从上一条命令拿）
curl -X DELETE -H "Authorization: Bearer $AUTH_TOKEN" http://localhost:8000/v1/memory/facts/3
```

## 工具管理（三层装工具机制，详见 docs/TOOLS.md）

```bash
curl -H "$AUTH" http://localhost:8000/v1/tools              # 列出全部工具（含来源）
curl -H "$AUTH" http://localhost:8000/v1/tools/pending      # 待批准的自生成工具
curl -X POST -H "$AUTH" http://localhost:8000/v1/tools/pending/<id>/approve   # 批准
curl -X DELETE -H "$AUTH" http://localhost:8000/v1/tools/pending/<id>         # 拒绝
curl -X DELETE -H "$AUTH" http://localhost:8000/v1/tools/<工具名>              # 卸载（内置不可卸）
curl -X POST -H "$AUTH" http://localhost:8000/v1/tools/reload                 # 重载 yaml/MCP/生成工具
```

- 工具文件在 `tools.d/`（YAML 配置）+ `tools.d/generated/`（自生成）+ `mcp.json`（MCP）
- `.env` 里 `TOOL_INSTALL_MODE=confirm`（默认）表示助手自装工具需你批准；改 `auto` 全自动

## 切换模型

改 `.env` 然后重启 core：

```
PRIMARY_MODEL=qwen      # 主模型换成通义
BACKUP_MODELS=deepseek,glm   # 备用顺序
```

模型故障自动切换不需要人工介入：连接失败/超时/5xx 都会按顺序切到下一个。

### 智能路由（省钱）

- `MODEL_POLICY=smart`（默认）：每条指令自动分档——简单问题走便宜档（CHEAP_PROVIDER/CHEAP_MODEL），复杂任务走强档
- `MODEL_POLICY=fixed`：全部走强档
- 便宜档推荐 SiliconFlow 免费模型，填 `SILICONFLOW_API_KEY` + `CHEAP_PROVIDER=siliconflow` 即生效
- 观察路由效果：`docker compose logs -f core | grep 智能路由`

## 故障排查

| 症状 | 排查 |
|---|---|
| 手机打不开 WebUI | VPS 上 `docker compose ps` 看 webui/core；Tailscale 是否在线（`tailscale status`） |
| 对话报错"均失败" | 三个模型 key 都无效或欠费；`docker compose logs core` 看具体 provider 报错 |
| 工具调用总失败 | 看对应服务：`docker compose logs searxng/radicale/browser` |
| 简报没推送 | `docker compose logs core \| grep 简报`；确认 DAILY_BRIEFING=true、WxPusher 已配 |
| 提醒丢了 | 重启后会自动恢复 pending 任务；查 `docker compose exec postgres psql -U jarvis -c "select id,kind,status,run_at from scheduled_tasks order by created_at desc limit 10;"` |
| 磁盘满了 | `docker system prune -f` 清理无用镜像；备份目录只留 10 天 |

## 日志

- 所有容器日志走 Docker json-file，单文件 10MB × 3 份自动轮转
- core 的日志级别：`docker compose logs core` 里 ERROR 级别需要关注
- 临时调详细：`.env` 加 `LOG_LEVEL=DEBUG` 不适用（core 固定 INFO）；看具体模块日志直接 `docker compose logs core | grep 模块名`
