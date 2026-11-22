# 成本说明

## 固定成本（VPS）

| 配置 | 参考价 |
|---|---|
| 4C8G 轻量应用服务器（阿里云/腾讯云活动价） | ¥50–100/月 |
| 流量/带宽 | 轻量通常含 5M 峰值带宽，够用 |

## 变动成本（API，按量付费）

| 用途 | 服务 | 参考单价 |
|---|---|---|
| 对话（主） | DeepSeek-V3 | 输入 ¥2/百万token，输出 ¥8/百万token |
| 对话（备） | 通义 Qwen-Plus / GLM-4-Plus | ¥4–20/百万token |
| 记忆向量 | SiliconFlow BGE-M3 | ¥0.5/百万token，几乎免费 |
| 语音转写 | SiliconFlow FunASR | 约 ¥0.001–0.01/分钟，新用户有免费额度 |
| 语音合成 | Edge-TTS | **免费**（默认） |
| 语音合成（可选） | MiniMax | 约 ¥0.01–0.05/分钟 |
| 天气 | 和风天气 | 免费（1000 次/天） |
| 推送 | WxPusher | 免费 |

## 典型月账单估算

个人重度使用（每天 50 轮对话 + 简报 + 提醒 + 偶尔语音）：

- DeepSeek API：¥10–30
- STT/TTS/Embedding：¥2–10（Edge-TTS 免费能省一大块）
- **合计：约 ¥70–150/月（含 VPS）**

## 智能路由（最大省钱项）

中枢内置**双档模型路由**：每条指令先分类，小事走便宜档，大事才走强档。

| 场景 | 走的档 | 示例 |
|---|---|---|
| 寒暄、闲聊、简单问答 | 便宜档（可免费） | "你好"、"谢谢"、"1+1 等于几" |
| 多步任务、创作、代码、分析 | 强档 | "帮我写方案"、"分析数据"、"装个新工具" |
| 后台记忆抽取 / 代码审查 / 分类判官 | 便宜档 | 自动发生，你无感知 |

配置（.env）：

```
MODEL_POLICY=smart                    # smart=自动分档 | fixed=全走强档
CHEAP_PROVIDER=siliconflow            # 便宜档服务商
CHEAP_MODEL=Qwen/Qwen2.5-7B-Instruct  # 免费模型；也可换 qwen-turbo / glm-4-flash 等
```

- **便宜档推荐 SiliconFlow 免费模型**（Qwen2.5-7B-Instruct 免费），注册 cloud.siliconflow.cn 填 `SILICONFLOW_API_KEY` 即生效
- 未配置便宜档时自动退化：全部走强档（不影响使用，只是不省）
- 强档故障会自动切便宜档兜底，反之亦然，服务不断
- 效果验证：演示页每条回复下方显示"模型: xxx"，聊天记录里能直接看到哪些走了便宜档

> 说明：DeepSeek 本身已经很便宜，便宜档省下的绝对值有限；当强档换成 Claude/GPT 等贵模型时，这个路由省的会非常可观。

## 省钱开关（按需在 .env 调整）

| 手段 | 配置 |
|---|---|
| 语音合成免费 | `TTS_PROVIDER=edge`（默认） |
| 智能路由 | `MODEL_POLICY=smart` + 免费便宜档（见上） |
| 换便宜模型 | `PRIMARY_MODEL=deepseek`（已是低价）；`QWEN_MODEL=qwen-turbo` 更省 |
| 降低早间简报成本 | 简报固定每天 1 次，也可 `DAILY_BRIEFING=false` |
| 预算硬上限提醒 | `MONTHLY_BUDGET_CNY=50`，超了微信告警（不会停机，防呆） |

## 账单查询

```bash
curl -H "Authorization: Bearer $AUTH_TOKEN" http://localhost:8000/v1/cost/summary
# 返回：当月总额、按服务商/模型分项、token 用量
```
