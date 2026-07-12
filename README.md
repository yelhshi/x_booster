# X (Twitter) 发帖监控

监控指定 X 账户是否发布新帖子，有新帖时自动发送邮件通知。通过 GitHub Actions 实现 24 小时免费运行。

## 工作原理

```
GitHub Actions (每8小时触发)
    │
    ▼
monitor.py ──► X API v2 ──► 获取最近推文
    │
    ▼
对比 state.json 中的上次记录 ID
    │
    ├── 有新推文 ──► 发送邮件通知 ──► 更新 state.json
    │
    └── 无新推文 ──► 仅更新 state.json
```

## 快速开始

### 第 1 步: 获取 X API Bearer Token

1. 前往 [X Developer Portal](https://developer.twitter.com/en/portal/dashboard)
2. 注册/登录，申请 **Free** 套餐
3. 创建一个 Project + App
4. 在 App 设置中进入 **Keys and Tokens** 页面
5. 生成 **Bearer Token** 并记录下来

> **免费额度**: 每月 100 次请求。本脚本每天运行 3 次 ≈ 90 次/月，刚好够用。

### 第 2 步: 配置邮件通知 (Gmail 为例)

1. 登录 Gmail → 设置 → 查看所有设置 → **账号和导入** → **Google 账号设置**
2. 安全 → 两步验证 (先开启) → **应用专用密码**
3. 选择 "邮件" + "其他"，生成一个 16 位密码，记录下来
4. 这个密码就是 `SMTP_PASS`


> QQ 邮箱、163 邮箱等也支持 SMTP，对应修改 SMTP 服务器地址即可。

### 第 3 步: 推送到 GitHub 并配置 Secrets

1. 在 GitHub 创建一个新仓库 (可以设为 Private 私有)
2. 把本文件夹推送到仓库:

```bash
cd x_monitor
git init
git add .
git commit -m "初始化 X 监控脚本"
git branch -M main
git remote add origin git@github.com:yelhshi/x_booster.git
git push -u origin main
```

3. 进入 GitHub 仓库 → **Settings** → **Secrets and variables** → **Actions**
4. 点击 **New repository secret**，逐一添加以下 Secrets:

| Secret 名称 | 说明 | 示例值 |
|---|---|---|
| `X_BEARER_TOKEN` | X API Bearer Token | `AAAAAAAAAAAAAAAAAAAA...` |
| `SMTP_HOST` | SMTP 服务器 | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP 端口 | `465` |
| `SMTP_USER` | 发件邮箱 | `yourname@gmail.com` |
| `SMTP_PASS` | 邮箱密码/应用密码 | `xxxxxxxxxxxxxxxx` |
| `NOTIFY_EMAIL` | 收通知的邮箱 | `yourname@gmail.com` |

### 第 4 步: 修改监控目标

编辑 [.github/workflows/monitor.yml](.github/workflows/monitor.yml)，找到第 46 行:

```yaml
TARGET="请替换为要监控的用户名"
```

把 `请替换为要监控的用户名` 改成你要监控的 X 用户名（不含 @）。

提交并推送:

```bash
git add .github/workflows/monitor.yml
git commit -m "设置监控目标"
git push
```

### 第 5 步: 验证

1. 进入 GitHub 仓库 → **Actions** → 选择 **X 发帖监控** workflow
2. 点击 **Run workflow** → 输入目标用户名 → **Run workflow** 手动触发一次
3. 查看运行日志，确认一切正常

首次运行不会发邮件（它需要先记录当前最新推文作为基准），从第二次运行开始发现有新帖就会通知。

## 调整检查频率

编辑 [.github/workflows/monitor.yml](.github/workflows/monitor.yml) 的 `cron` 字段:

```yaml
on:
  schedule:
    - cron: "0 */8 * * *"   # 每 8 小时
    # 其他例子:
    # - cron: "0 */4 * * *"  # 每 4 小时 (月 180 次，超出免费额度)
    # - cron: "0 0,12 * * *" # 每天 2 次 (UTC 0:00 和 12:00)
    # - cron: "*/30 * * * *" # 每 30 分钟 (仅限付费 API)
```

> ⚠️ 免费 API 每月只有 100 次请求，请根据频率计算月消耗量。

## 监控多个账户

如果想监控多个账户，有两种方式:

**方式 1**: 复制 workflow 文件，修改目标用户名
**方式 2**: 修改脚本支持多账户（需要稍微改动 `monitor.py`）

## 其他通知方式

如果想用其他通知方式替换邮件，可以参考以下改动:

- **Telegram**: 替换 `send_email()` 为 Telegram Bot API 调用
- **企业微信/飞书**: 替换为对应的 Webhook
- **Pushover/Pushbullet**: 替换为对应的推送 API

## 文件结构

```
x_monitor/
├── monitor.py                 # 主监控脚本
├── requirements.txt           # Python 依赖
├── state.json                 # 状态文件 (记录上次推文 ID)
├── .github/
│   └── workflows/
│       └── monitor.yml        # GitHub Actions 定时任务
└── README.md                  # 本文件
```
