# 工具扩展指南：让中枢自己装工具

中枢支持三层"装工具"机制，从"零代码"到"它自己写代码"：

| 层 | 方式 | 装一个工具的工作量 | 风险 |
|---|---|---|---|
| 1 声明式 | 写一个 YAML | 2 分钟 | 低 |
| 2 MCP | 加一行配置 | 1 分钟（接现成生态） | 低 |
| 3 自我写码 | 和它说一句话 | 0（它自己写+测+装） | 中（多重护栏） |

所有动态工具**热生效，无需重启**（或最多调一次 reload 接口）。

---

## 第一层：声明式工具（tools.d/*.yaml）

### HTTP 类（接任意 API）

```yaml
name: track_express            # snake_case，唯一
description: 查快递单号物流信息
parameters:
  type: object
  properties:
    number: {type: string, description: 快递单号}
  required: [number]
kind: http
http:
  url: https://api.example.com/track
  method: GET                  # 默认 GET，可 POST
  headers: {Authorization: "Bearer 你的key"}
  params_template: {number: "{number}"}   # {参数名} 会被实际值替换
  json_body_template: {q: "{number}"}     # POST 请求体（可选）
  response_path: ".data.results"          # 取响应 JSON 的哪一段（可选，默认整体）
  timeout: 20
```

### 命令类（调用系统命令）

```yaml
name: my_ip
description: 查询本机公网 IP
parameters: {type: object, properties: {}}
kind: command
command:
  cmd: "curl -s https://api.ipify.org"
  timeout: 30
```

装好即用：保存 YAML 后 `POST /v1/tools/reload`（或重启服务）。卸载：删除文件 + reload。

> 项目自带示例：`tools.d/example-hitokoto.yaml`（随机一言，免费公开 API）。

## 第二层：MCP 工具生态（mcp.json）

编辑项目根目录的 `mcp.json`，加一个 server 就是几十个工具：

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/data"]
    },
    "fetch": {
      "command": "uvx",
      "args": ["mcp-server-fetch"]
    }
  }
}
```

VPS 需要装 Node（npx）或 uv（uvx）：`apt install -y nodejs npm` 或 `pip install uv`。

生效：`POST /v1/tools/reload`。示例见 `mcp.json.example`。

> 社区 MCP server 列表：github.com/modelcontextprotocol/servers 等，几百个现成工具可接。

## 第三层：让它自己写工具（一句话装工具）

在聊天里直接说：

> 「帮我接一下快递查询能力」「以后我要能查汇率」

中枢会调用内置的 `install_tool` 元工具：**生成代码 → AST 安全闸 → 第二个模型审查 → 冒烟测试 → 安装**。

### 两种安装模式（.env 配置）

| 模式 | 行为 |
|---|---|
| `TOOL_INSTALL_MODE=confirm`（默认） | 生成+审查通过后**等待你批准**才生效 |
| `TOOL_INSTALL_MODE=auto` | 全部自动（仍过安全闸+审查+冒烟测试） |

### 批准 / 拒绝 / 卸载（管理 API）

```bash
AUTH="Authorization: Bearer $AUTH_TOKEN"

curl -H "$AUTH" http://localhost:8000/v1/tools              # 列出全部工具（含来源）
curl -H "$AUTH" http://localhost:8000/v1/tools/pending      # 查看待批准工具
curl -X POST -H "$AUTH" http://localhost:8000/v1/tools/pending/<id>/approve   # 批准
curl -X DELETE -H "$AUTH" http://localhost:8000/v1/tools/pending/<id>         # 拒绝
curl -X DELETE -H "$AUTH" http://localhost:8000/v1/tools/<工具名>              # 卸载
curl -X POST -H "$AUTH" http://localhost:8000/v1/tools/reload                 # 重载配置
```

## 安全护栏（第三层专属）

1. **AST 白名单闸**：只允许 import json/re/math/datetime/zoneinfo/hashlib/uuid/httpx/base64；禁止 eval/exec/open/魔术属性
2. **双模型审查**：生成者与审查者分开两次调用（`REVIEW_GENERATED_TOOLS=true`）
3. **冒烟测试**：安装前用测试参数真跑一次，失败自动回滚删除
4. **可随时卸载**：生成工具文件在 `tools.d/generated/`，卸载即删文件
5. **确认模式**：默认需要你批准；生成工具能读到 `.env` 里的 API Key（ctx.settings），但拿不到文件系统/进程权限

## 常见问题

| 问题 | 解决 |
|---|---|
| install_tool 说"等待批准" | 调 approve 接口，或 .env 改 `TOOL_INSTALL_MODE=auto` |
| 生成代码没通过安全检查 | 让它重试，或把需求描述得更具体；也可以自己改代码（yaml 方式更稳） |
| MCP server 连接失败 | `docker compose logs core \| grep MCP`；确认 VPS 有 npx/uvx、命令能跑通 |
| reload 后工具没变化 | 确认文件名是 `*.yaml` 且直接放在 tools.d 下（子目录不放配置） |
| 想恢复出厂工具 | 删除 tools.d 下文件 + mcp.json 清空 + reload |
