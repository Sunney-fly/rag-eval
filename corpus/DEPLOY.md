# 部署指南（国内 VPS，直连版）

目标：一台 4C8G Ubuntu 22.04/24.04 的国内 VPS，30 分钟内跑起完整中枢。
全程不需要域名、不需要备案，通过 Tailscale 私网访问。

## 0. 准备清单

| 事项 | 说明 |
|---|---|
| VPS | 4C8G，Ubuntu 22.04+（阿里云/腾讯云轻量均可，约 ¥50–100/月） |
| Tailscale 账号 | tailscale.com 注册（免费），VPS、手机、电脑都登录同一账号 |
| DeepSeek API Key | platform.deepseek.com 注册充值（¥10 起） |
| SiliconFlow API Key | cloud.siliconflow.cn（有免费额度，用于记忆向量 + 语音转写） |
| WxPusher | wxpusher.zjiecode.com 注册（免费，微信推送用） |
| QWeather（可选） | dev.qweather.com 免费申请：API Key + **API Host**（控制台-设置 查看，2026 年起必须用 API Host） |
| MiniMax（可选） | platform.minimaxi.com（更自然的语音合成，不用则走免费 Edge-TTS） |

## 1. VPS 基础初始化

SSH 登录 VPS 后：

```bash
# 1. 安装 Docker（阿里云镜像安装脚本，国内快）
curl -fsSL https://get.docker.com | bash -s docker --mirror Aliyun

# 2. 配置 Docker 镜像加速（国内必须，否则拉不动镜像）
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json > /dev/null <<'EOF'
{
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.1panel.live"
  ]
}
EOF
sudo systemctl daemon-reload && sudo systemctl restart docker

# 3. 安装 Tailscale 并登录（去控制台 approve）
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
tailscale ip -4    # 记下这个 IP，手机/电脑都用它访问

# 4. 安装 htpasswd（生成日历账号用）
sudo apt-get update && sudo apt-get install -y apache2-utils
```

## 2. 上传项目

在**本地 Windows** 上（PowerShell）：

```powershell
cd D:\Users\sun\DSH
pwsh -File jarvis-hub\scripts\upload.ps1 -Ip <VPS的Tailscale IP>
```

或者用 git：

```bash
# VPS 上
git clone <你的仓库> /root/jarvis-hub
```

## 3. 生成密钥 + 填 API Key

```bash
cd /root/jarvis-hub
bash scripts/seed-env.sh
vim .env
```

必填：

```
DEEPSEEK_API_KEY=sk-xxxx
SILICONFLOW_API_KEY=sk-xxxx
WXPUSHER_APP_TOKEN=AT_xxxx
WXPUSHER_UIDS=UID_xxxx（先留空，第 9 步拿到再填）
```

选填：HOME_CITY（天气默认城市，默认 湖州）、QWEATHER_API_KEY（天气）、MINIMAX_API_KEY/MINIMAX_GROUP_ID（语音）、邮箱四项（邮件工具）。

## 4. 一键部署

```bash
bash scripts/deploy.sh
docker compose ps        # 全部应为 running / healthy
docker compose logs -f core   # 观察启动日志，看到"调度器已启动"即成功
```

首次构建要拉镜像 + 装依赖，约 5–10 分钟（browser 服务要下载 Chromium，最慢）。

## 5. 防火墙（重要：只放行 Tailscale）

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow in on tailscale0
sudo ufw allow 22/tcp        # SSH；熟练后可改为只放行 tailscale0
sudo ufw enable
```

## 6. Open WebUI 建号（手机/电脑通用入口）

1. 手机或电脑浏览器打开 `http://<VPS的Tailscale IP>:3000`
2. 注册第一个账号（就是管理员）
3. 回到 VPS：`.env` 里把 `WEBUI_ENABLE_SIGNUP` 改成 `false`，`docker compose up -d webui` 生效
4. WebUI 内"设置 → 连接"会显示 `deepseek` 等模型（就是 core 路由出来的），随便选一个即可对话

## 7. 测试验证（对应 P0–P2 验收）

- [ ] 手机免翻墙打开 WebUI，正常对话
- [ ] "帮我搜索一下杭州明天天气" → 返回真实天气（搜索/天气工具生效）
- [ ] "在日历里创建明天上午 10 点开会" → 提示已创建（日历工具生效）
- [ ] "提醒我 1 分钟后喝水" → 1 分钟后微信收到提醒（推送+调度生效）

## 8. 每日备份

```bash
crontab -e
# 添加：
0 3 * * * cd /root/jarvis-hub && bash scripts/backup.sh >> /var/log/jarvis-backup.log 2>&1
```

## 9. 微信推送（WxPusher）

1. 手机微信搜索关注「WxPusher 推送服务」公众号，点"我的 → 获取 UID"得到 `UID_xxx`
2. 在 wxpusher.zjiecode.com 控制台创建应用，得到 `APP_TOKEN`
3. 填入 `.env` 的 `WXPUSHER_APP_TOKEN` 和 `WXPUSHER_UIDS`（多个 UID 逗号分隔）
4. `docker compose up -d core` 重启生效
5. 测试：`docker compose exec core python -c "import asyncio;from core.push import wxpusher;from core.config import get_settings;asyncio.run(wxpusher.push_text(get_settings(),'中枢上线 ✅'))"`

## 10. 手机端接入

见 [docs/ANDROID.md](ANDROID.md)。核心三步：Tailscale App → 浏览器开 WebUI 加到桌面 → 订阅日历。

## 11. 语音（可选但强烈推荐）

手机浏览器麦克风必须 HTTPS 才能用。Tailscale 提供免费证书：

```bash
bash scripts/tailscale-https.sh <主机名>.<你的tailnet>.ts.net
# 例：bash scripts/tailscale-https.sh jarvis-vps.<你的tailnet>.ts.net
```

之后手机浏览器打开 `https://<该域名>`，语音按钮即可用（转写走 SiliconFlow FunASR，合成走 Edge-TTS/MiniMax）。

## 12. 常见问题

| 问题 | 解决 |
|---|---|
| 拉不动 ghcr.io 镜像（webui） | `.env` 改 `WEBUI_IMAGE=ghcr.nju.edu.cn/open-webui/open-webui:v0.5.20` 重试；或换 `docker.1ms.run` 前缀 |
| core 起不来，日志报 provider | `.env` 至少一个模型 API Key 填对；`docker compose logs core` 看具体报错 |
| 微信收不到推送 | 检查 APP_TOKEN/UID 是否填对；`docker compose logs core \| grep WxPusher` |
| 天气工具报未配置 | 填 `QWEATHER_API_KEY`（dev.qweather.com 免费申请） |
| 语音按钮灰色/没反应 | 必须用 HTTPS 域名访问（第 11 步），HTTP 下浏览器禁麦克风 |
| 日历订阅失败 | 确认 `tools/radicale/users` 已由 deploy.sh 生成；`docker compose logs radicale` |
| 改 .env 不生效 | `docker compose up -d` 重新加载对应服务 |

## 13. 升级

```bash
cd /root/jarvis-hub
# 本地重新上传（upload.ps1）或 git pull
docker compose up -d --build core
```
