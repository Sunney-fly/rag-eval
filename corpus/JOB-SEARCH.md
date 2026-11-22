# 求职岗位采集 + 简历匹配（jarvis-hub 工具 `job_search`）

2026-10-25 接入。目标：对贾维斯说「帮我找匹配的岗位」，它去 BOSS/51job 抓岗位，
用本地简历打分排序，给出列表。

## 架构

```
贾维斯（语音/聊天）
  → 中枢工具 job_search（tools.d/job-search.yaml）
  → Tailscale 内网 http://100.64.0.10:8766/api
  → Windows 本机 job 服务（_work/jobs/job_service.py，零第三方依赖）
       ├─ Edge 无头渲染（--dump-dom）抓 51job / BOSS 搜索页，正则解析 DOM
       └─ 中枢 /v1/chat/completions + 本地简历 → 打分排序
```

为什么放在 Windows 本机：
- 招聘站按 IP 识别机房流量，**不能放服务器**（get_jobs 作者也明确写了）；
- 51job 有阿里云 WAF，纯 HTTP 请求拿到的是 JS 挑战页，必须真实浏览器渲染；
- BOSS 需要登录态，本机 Edge 用户目录天然可用。

## 前置

1. 本机 Tailscale 在线（服务只绑 `100.64.0.10:8766`，不暴露公网）。
2. 启动服务（双击即可，无窗口）：
   `D:\Users\sun\DSH\_work\jobs\start-jobs.vbs`
   （开机自启：把该快捷方式放进 `shell:startup`）
3. BOSS 需登录一次（51job 不需要）：
   ```powershell
   & "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --user-data-dir="D:\Users\sun\DSH\_work\jobs\boss-profile" https://www.zhipin.com
   ```
   在弹出的窗口里扫码登录，登录态保存在该专用 profile，不影响主浏览器。
4. 简历路径：`D:\Codex\out\resume\经历库.md`（可在 `_work/jobs/config.json` 改）。

## 用法

对贾维斯说：
- 「帮我找杭州的 Java 岗位」→ 工具 `search`（platform=51job, city=杭州）
- 「用我的简历看看哪些最匹配」→ `match`（返回分数 + 匹配理由 + 缺口）
- 「上次匹配结果」→ `list`

本地命令行（排错用）：
```powershell
$env:PYTHONHOME=''; $env:PYTHONPATH=''
python D:\Users\sun\DSH\_work\jobs\job_service.py status
python D:\Users\sun\DSH\_work\jobs\job_service.py search 51job Java 杭州 0   # 0=读到底
python D:\Users\sun\DSH\_work\jobs\job_service.py match 10
```

51job 城市码（`config.json` 里可扩）：上海 020000、杭州 080200、绍兴 080500、嘉兴 080700。
其他城市留空 city（走网站 IP 定位）。BOSS 城市码暂未接，靠网站默认定位。

## 「读到底」怎么做的

51job 单个搜索组合**只给 2 页**（第 3 页会回到第 1 页，实测 p3 == p1），也就是每个
「关键词 × 城市」最多约 40 条。所以真正的「读完」= 多组合聚合：

- `search(pages=0)`：单组合读到没有新岗位（默认上限 10 页，遇到重复即停）
- `crawl`：按 `config.json` 的 `keywords` × `cities` 循环，组合间随机停 2–5 秒，
  按「标题+公司」去重后一次落盘（默认 5 个关键词 × 2 个城市 = 10 组合，约 8–10 分钟）

想覆盖更多：编辑 `_work/jobs/config.json` 的 `keywords` / `cities` 数组即可，
每个新组合多约 40 条；也可在调用时直接传 `keywords` / `cities`（逗号分隔）。

## 实测（2026-10-25）

- 51job 单组合「Java @ 杭州」：20 条/页，翻到第 3 页返回重复 → 稳定 40 条
- `crawl("Java,全栈" × "杭州")`：**41 条去重**，31.3s
- 41 条简历打分：**16.9s**，Top1 74 分（全栈开发，Java+MySQL+SpringBoot+前端）
- 中枢侧 `job_search` 已注册：`load_config_tools('/app/tools.d') → ['douyin_spark','hitokoto','job_search']`

## 风险与边界

- **只读不投**：不自动打招呼/投递，避免 BOSS 风控（code 36 账户异常 / 32 临时封禁）。
- 频率：单次读全即可；同一批关键词不要短时间反复刷（建议间隔 ≥30 分钟），
  页间已加 2–5 秒随机延迟。Edge 渲染失败会明确报错，不静默。
- 前程无忧岗位量偏少、作者社区反馈「没什么活人」；如效果差可换猎聘（get_jobs 维护中）。
- 页面结构会变：解析是正则匹配 `joblist-item`（51job）/ `job-card-wrapper`（BOSS），
  改版时需要更新 `job_service.py` 的 `RE` / `RE_BOSS`。
- 工具 URL 写死 Tailscale IP `100.64.0.10`；换机器/换 node 要同步改 yaml。

## BOSS 风控实录（2026-10-25，重要）

扫码登录成功，但**无头/CDP 自动访问立刻触发 BOSS 风控**：页面被重定向到
`zp/passport/zp/verify.html?...&code=36`，标题「安全验证 —— 您的账号可能存在异常访问行为」。
截图：`D:\Users\sun\DSH\_work\jobs\boss-shot.png`。

`code 36` 是 BOSS 的账户异常标记（`boss-auto-job` README 也写明）。处理（来自其文档 + 官方验证页）：
1. 用**普通（有界面）**浏览器打开 zhipin.com，点「点击按钮进行验证」完成滑块；
2. 随便找个岗位发一条消息（给 BOSS「真人」信号）；
3. 等 10–30 分钟再访问，不要连续重试（连续会升级成 code 32 临时封禁）。

应对措施（已实现，默认先别用）：
- `job_service.py` 的 BOSS 分支已改成 **CDP 渲染**（`cdp_render.py`，标准库实现），
  不再用会卡死的 `--dump-dom`；
- `config.json` 里 `boss_headless` 可设 `false` → 用**有界面** Edge 采集（可见窗口，更像真人）；
- `boss_wait` 控制页面等待秒数（默认 10s）。
- **建议**：BOSS 保持「手动为主、自动为辅」，等风控解除且至少间隔 30 分钟再试一次；
  51job 不受影响，可继续自动「读到底 + 打分」。
