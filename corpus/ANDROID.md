# Android 手机接入指南

目标：手机成为中枢的"随身终端"——聊天、语音、收推送、看日历，还能通过 Tasker 联动系统。

## 1. 组网（Tailscale）

1. 手机安装 Tailscale App（官网下载或应用商店）
2. 登录与 VPS 相同的账号
3. 打开浏览器访问 `http://<VPS的Tailscale IP>:3000`，能打开 WebUI 即通

## 2. 聊天入口（PWA）

1. Chrome 打开 WebUI 并登录
2. 菜单 → **添加到主屏幕**（Add to Home screen）
3. 桌面出现"中枢"图标，点开即全屏应用体验

> 语音输入需要 HTTPS：先在 VPS 上跑 `scripts/tailscale-https.sh`，然后用
> `https://<主机名>.<tailnet>.ts.net` 安装 PWA，麦克风按钮可用。

## 3. 主动推送（微信）

1. 微信关注「WxPusher 推送服务」公众号
2. 公众号内"我的 → 获取 UID"，把 `UID_xxx` 发给 VPS 的 `.env`（WXPUSHER_UIDS）
3. 之后中枢的早间简报、提醒、成本预警都会出现在微信里——不依赖后台常驻，国产 ROM 杀进程也不影响

## 4. 日历订阅（系统日历看到中枢的日程）

1. 安装 **DAVx5**（F-Droid 或应用商店）
2. 添加账户 → 手动配置（CalDAV）：
   - 服务器地址：`http://<VPS的Tailscale IP>:5232/`
   - 用户名：`jarvis`；密码：`.env` 里的 `RADICALE_PASSWORD`
3. 选择 `jarvis` 日历 → 系统日历 App 即可看到中枢创建的日程

## 5. 语音对话（配合 HTTPS）

- WebUI 的麦克风按钮：说话 → 云端 FunASR 转写 → LLM → TTS 播报
- TTS 默认 Edge-TTS（免费男声）；要更自然的中文声音，`.env` 设 `TTS_PROVIDER=minimax` 并填 MiniMax 密钥

## 6. Tasker 联动（进阶，P5 阶段再玩）

Tasker 是安卓自动化神器，让中枢能"伸手"到手机系统。两个入门示例：

### 示例 A：一键向中枢汇报位置

1. 新建任务 → 添加动作：**Get Location**（GPS）
2. 再添加动作：**HTTP Request**
   - Method: `POST`
   - URL: `http://<VPS的Tailscale IP>:8000/v1/chat/completions`
   - Headers: `Authorization: Bearer <AUTH_TOKEN>`、`Content-Type: application/json`
   - Body: `{"model":"deepseek","messages":[{"role":"user","content":"我现在在 %LOC 附近，帮我看看周边有什么好吃的"}]}`
3. 桌面加 Tasker 快捷方式 → 一键问路

### 示例 B：到点提醒微信推送

直接用 WebUI 对话说"提醒我明早 9 点开会"即可（中枢内置提醒工具），无需 Tasker。

> Tasker/HTTP Request 的 JSON 里变量要用英文变量名（如 %LOC），中文系统注意编码。

## 7. 省电设置

- 设置 → 电池 → 把 **Tailscale** 加入"无限制"白名单（否则后台断了重连慢）
- Chrome/WebUI PWA 无需常驻，推送走微信，不受影响
