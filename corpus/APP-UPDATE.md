# App 自动更新 + 网站下载

两条渠道共用同一个 APK：

- **App 内自动更新**：打开贾维斯自动问中枢「最新版本」，比当前版本新就弹窗下载安装。
- **网站直接下载**：<https://nanmount-r-ain.cn/download/>（公开，支持断点续传）。

## 版本查询是公开接口

`GET /v1/app/version` **不需要令牌**（2026-10-24 起）。原因：新安装的 App 还没有令牌，
如果版本查询也要鉴权，就会陷入「没令牌 → 查不了更新 → 装不上带引导的新版」死循环。
它只返回版本号、大小、SHA256 和下载地址，不泄露任何隐私。

## 账号体系（2026-10-26 更新：不再需要安装码）

APK 仍然不内置任何密钥。首次使用**直接注册**（用户名 + 密码，无需安装码），之后
用户名密码登录，会话 90 天有效；菜单「退出登录」/「修改密码」。

- 接口：`GET /v1/auth/status`（公开）、`POST /v1/auth/register`（**仅在没有账号时开放一次**，注册后 409 锁死）、
  `POST /v1/auth/login`、`GET /v1/auth/me`、`POST /v1/auth/logout`、`POST /v1/auth/password`
- 存储：`users`（PBKDF2-SHA256 21 万轮加盐）、`auth_sessions`（只存 token 的 sha256，可吊销、过期即删）
- 兼容：旧 `AUTH_TOKEN` 继续可用（应急/脚本）；App 侧 `Prefs.authToken()` 优先会话 token
- **风险（用户已知悉）**：APK 公开可下载且注册不设码 → 未注册前谁先装谁就能抢注。
  注册一次即锁；建议装完立刻注册。要恢复「必须凭码」只需在 `auth_register` 里加回 `install_code` 校验。
- 启动顺序：**先检查更新**，更新弹窗显示时不再叠加登录提示（登录提示延后 2.5 秒且会被跳过）。

## 组件

| 端 | 位置 | 作用 |
|---|---|---|
| 中枢 | `GET /v1/app/version`（需 AUTH_TOKEN） | 返回 `release/app-release.json`，没发布过就返回 `versionCode=0` |
| 中枢 | `GET /v1/app/download`（需 AUTH_TOKEN） | 下发 `release/app.apk`（App 自更新用） |
| 中枢 | `docker-compose.yml` 挂载 `./release:/app/release:ro` | 发布目录 |
| 站点 | `/var/www/nanmount/download/index.html` | 公开下载页 <https://nanmount-r-ain.cn/download/> |
| 站点 | `nanmount-server.py` 的 `_serve_apk` | `GET /download/jarvis.apk` 公开下发，支持 Range 206 |
| App | `AppUpdater.java` | 启动/手动检查、弹窗、下载、`FileProvider` 安装 |
| App | `MainActivity.onCreate` | 自动检查一次（点过「稍后」的版本不再打扰） |
| App | `SettingsActivity` → 「检查更新」 | 手动检查，必定给结果 |

## 发布新版本

```powershell
cd D:\Users\sun\DSH\jarvis-app
$env:JAVA_HOME="D:\android\jbr"; $env:ANDROID_HOME="D:\SDK"
C:\Users\sun\.gradle\wrapper\dists\gradle-9.5.0-bin\bvnork1r7n8i6kp5cnkibsc9q\gradle-9.5.0\bin\gradle.bat assembleDebug

$env:JARVIS_UPLOAD_SECRET = "<服务器 .env 的 APP_UPLOAD_SECRET>"
cd D:\Users\sun\DSH\jarvis-hub
powershell -NoProfile -File scripts\publish-app.ps1
# 可选：-Apk <路径> -Note "更新说明"
```

**快通道（默认）**：`POST https://nanmount-r-ain.cn/v1/app/release`，走 443，约 10MB/s
（实测 49MB 用 4.5s）。服务器端同时写 `release/app.apk` 与网站 `download/jarvis.apk`，
并生成 `app-release.json`。需要 `X-Jarvis-Upload` 头（= `APP_UPLOAD_SECRET`），
更新说明走 `X-Jarvis-Note`（URL 编码，避免中文进 query 被拒），并且必须带 `Expect:` 关掉
100-continue（Python 反代处理不好）。

**慢通道（自动回退）**：没有 secret 或 HTTPS 失败时，回退到 scp（走 Tailscale）。
注意 Tailscale 在没有直连时会走 DERP 中继（本机实测 85–150KB/s，49MB ≈ 5 分钟）。

脚本从 Gradle 的 `output-metadata.json` 读 `versionCode/versionName`，算 SHA256 与大小，
一次传**两处**：`release/app.apk`（App 自更新）与 `/var/www/nanmount/download/jarvis.apk`（网站）。
**不需要重启**：中枢每次请求现读 JSON，站点 `_serve_apk` 现读文件。

## 更新器行为（2026-10-24 参考 Obtainium / APK-MultiUpdate 改进）

| 行为 | 实现 |
|---|---|
| 版本判定 | 以服务端 `versionCode` 与 `BuildConfig.VERSION_CODE` 比较，与文件名无关 |
| 自动检查节流 | 6 小时一次（`Prefs.lastUpdateCheckAt`）；手动「检查更新」不受限 |
| 更新包来源 | `app-release.json` 的 `apkUrl` 用**网站公开直链**（`https://nanmount-r-ain.cn/download/jarvis.apk`），不再依赖中枢令牌 |
| 下载校验 | 下完算 SHA-256 与 JSON 里的 `sha256` 比对，不一致删包报错 |
| 下载失败 | 自动重试 1 次（1.2s 后重来），仍失败才提示 |
| 安装权限 | 缺「安装未知应用」时挂起待装包并跳设置；回到 App 由 `AppUpdater.onResume` 自动续装 |
| 安装方式 | `FileProvider` + `ACTION_VIEW` 拉起系统安装器（与 Obtainium 一致；无 root/Shizuku 需求） |

发布脚本里的 `-Domain` 参数决定 `apkUrl` 的绝对地址（默认 `nanmount-r-ain.cn`），换域名时要一起改。



## 验证清单（发布后）

```powershell
curl.exe -sI https://nanmount-r-ain.cn/download/jarvis.apk
# 期望：200 + Content-Length = APK 字节数 + Content-Type: application/vnd.android.package-archive

curl.exe -s -r 0-1023 -D - -o NUL https://nanmount-r-ain.cn/download/jarvis.apk
# 期望：206 Partial Content + Content-Range: bytes 0-1023/<总长>

# App 更新接口（带令牌）：/v1/app/version 返回同样的 versionCode
```

## 版本号规则

`versionCode` = 构建时刻的分钟级时间戳（`build.gradle.kts`），每次构建必然变大，
手机上才能覆盖安装。发布后 App 里能看到 `v1.1.1024.2049` 这类版本号。

## 注意

- 首次更新时系统会要求「允许安装未知应用」；本次起给完权限回到 App 会**自动续装**，不用再点检查。
- APK 走 HTTPS + 证书固定，与 App 其他请求同一条链路；更新包已做 SHA-256 校验。
- 用户点「稍后」记的是**版本号**，同一版本不再自动弹；发更高版本会重新提示。
- 发布前确认 APK 里没有令牌：
  `python -c "print(b'6a6ac1f411c7e55c' in open('app-debug.apk','rb').read())"` 应为 `False`。
