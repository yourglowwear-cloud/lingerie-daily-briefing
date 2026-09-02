# 情趣内衣行业每日资讯简报（GitHub Actions 云端版）

每天北京时间 8:00 自动搜集过去 24 小时情趣内衣行业全球动态，筛选 5-8 条最有价值信息，按重要性排序，生成 HTML 邮件发送到指定邮箱。

完全运行在 GitHub 云端，不依赖本地电脑开关机。

---

## 快速开始（5 步）

### 第 1 步：创建 GitHub 仓库

1. 登录 [GitHub](https://github.com)
2. 点击右上角 `+` → `New repository`
3. 仓库名：`lingerie-daily-briefing`（可自定义）
4. 选择 `Public` 或 `Private` 均可
5. 勾选 `Add a README file`（可选）
6. 点击 `Create repository`

### 第 2 步：上传文件

将本项目的以下文件上传到仓库根目录：

```
lingerie-daily-briefing/
├── .github/
│   └── workflows/
│       └── daily-briefing.yml    ← 定时任务配置
├── main.py                        ← 主程序
├── requirements.txt               ← Python 依赖
└── README.md                      ← 本说明文件
```

上传方式：
- 网页端：仓库页面点击 `Add file` → `Upload files`，拖拽上传
- 注意：`.github/workflows/` 目录需要手动创建路径

### 第 3 步：配置 Secrets（邮箱信息）

在仓库页面：

1. 点击 `Settings`（设置）
2. 左侧菜单找到 `Secrets and variables` → `Actions`
3. 点击 `New repository secret`，依次添加以下 5 个变量：

| Secret 名称 | 值（示例） | 说明 |
|---|---|---|
| `SENDER_EMAIL` | `117213197@qq.com` | 发件人邮箱 |
| `SENDER_PASSWORD` | `gbgibptfxdjfbihb` | 邮箱授权码（非登录密码） |
| `RECEIVER_EMAILS` | `117213197@qq.com,yourglowwear@gmail.com` | 收件人邮箱，多个用逗号分隔 |
| `SMTP_SERVER` | `smtp.qq.com` | SMTP 服务器地址 |
| `SMTP_PORT` | `465` | SMTP 端口（QQ邮箱SSL用465） |

> **QQ 邮箱授权码获取**：QQ邮箱 → 设置 → 账户 → POP3/IMAP/SMTP服务 → 开启SMTP → 生成授权码

### 第 4 步：手动测试一次

1. 点击仓库顶部的 `Actions` 标签
2. 左侧选择 `情趣内衣行业每日资讯`
3. 点击 `Run workflow` → 选择 `main` 分支 → 点击 `Run workflow`
4. 等待 1-2 分钟，查看运行状态
5. 运行成功后检查邮箱是否收到邮件

### 第 5 步：确认定时任务

- 配置的 cron 为 `0 0 * * *`（UTC 时间），即**北京时间每天 8:00** 自动运行
- 无需电脑开机，GitHub 云端自动执行

---

## 工作原理

```
每天 8:00 (北京时间)
    ↓
GitHub Actions 触发
    ↓
启动 Ubuntu 虚拟机 + Python 3.11
    ↓
安装 ddgs 等依赖
    ↓
main.py 执行：
  1. DuckDuckGo 搜索中英文行业新闻（过去24小时）
  2. 按URL去重
  3. 按价值评分排序（品牌/政策/展会/市场规模等维度）
  4. 取前8条生成HTML邮件
  5. 通过SMTP发送到指定邮箱
    ↓
你收到邮件 📧
```

---

## 常见问题

### Q: 收不到邮件怎么办？
1. 检查 `Actions` 页面的运行日志，看哪一步报错
2. 确认 Secrets 配置正确（授权码不是登录密码）
3. 检查邮箱垃圾箱/广告邮件文件夹
4. QQ邮箱可能需要在设置中开启SMTP服务

### Q: 搜索结果太少或质量不高？
编辑 `main.py` 中的 `keywords` 列表，添加更多关键词，或调整 `max_per_keyword` 参数。

### Q: 想修改发送时间？
编辑 `.github/workflows/daily-briefing.yml` 中的 `cron` 值：
- 北京时间 = UTC + 8
- 例：北京时间 9:00 → UTC 1:00 → `cron: '0 1 * * *'`

### Q: GitHub Actions 免费吗？
免费。公开仓库无限使用，私有仓库每月有 2000 分钟免费额度，本任务每天运行约 1 分钟，完全够用。

### Q: 如何停止任务？
- 临时停止：仓库 `Settings` → `Actions` → `Disable Actions`
- 永久删除：删除仓库或删除 workflow 文件

---

## 文件说明

| 文件 | 作用 |
|---|---|
| `main.py` | 主程序：搜索、筛选、生成邮件、发送 |
| `requirements.txt` | Python 依赖包列表 |
| `.github/workflows/daily-briefing.yml` | GitHub Actions 定时任务配置 |
| `README.md` | 使用说明 |
