这份 `README.md` 文档是专门为你最终完善的 **ICMP9 自动签到脚本** 设计的。它详细说明了项目功能、配置方法（特别是 GitHub Actions Secrets）以及运行效果。

请在你的仓库根目录下创建一个名为 `README.md` 的文件，并将以下内容复制进去。

---

# ✈️ ICMP9 自动签到脚本 (DrissionPage 版)

这是一个基于 Python 和 [DrissionPage](https://github.com/g1879/DrissionPage) 开发的 ICMP9 面板自动签到脚本。专门针对 **Cloudflare Turnstile (5秒盾)** 进行优化，能够在 GitHub Actions 环境下稳定运行，并发送包含**现场截图**和**详细数据**的 Telegram 通知。

## ✨ 主要功能

*   **🛡️ 强力过盾**：使用 DrissionPage 模拟真实浏览器行为，自动处理 Cloudflare 人机验证。
*   **🤖 自动签到**：
    *   自动登录 (支持 ID/Name 定位)。
    *   自动处理登录后的弹窗/遮罩层。
    *   自动点击侧边栏和签到按钮。
    *   支持“未签到”和“已签到”两种状态的判断。
*   **📸 截图存证**：
    *   登录成功后自动截图。
    *   签到完成/读取数据后自动截图。
    *   支持中文截图（环境已配置中文字体）。
*   **📊 数据抓取**：精准提取今日奖励、累计获得、累计签到天数、连续签到天数。
*   **📱 Telegram 通知**：推送详细的文字报告以及 **2张现场截图**。

## 📂 文件结构

*   `icmp9_cf_checkin.py`: 核心 Python 脚本。
*   `.github/workflows/icmp9_cf_checkin.yml`: GitHub Actions 配置文件。

## 🚀 部署方法 (GitHub Actions)

无需自备服务器，直接利用 GitHub 免费资源运行。

### 1. Fork 本仓库
点击右上角的 **Fork** 按钮，将本仓库复制到你的 GitHub 账号下。

### 2. 配置环境变量 (Secrets)
进入你 Fork 后的仓库，依次点击：
`Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`。

添加以下必须变量：

| 变量名 | 是否必须 | 说明 | 示例值 |
| :--- | :---: | :--- | :--- |
| `ICMP9_EMAIL` | ✅ | 你的登录邮箱 | `user@example.com` |
| `ICMP9_PASSWORD` | ✅ | 你的登录密码 | `password123` |
| `TELEGRAM_BOT_TOKEN` | ✅ | TG 机器人的 Token | `123456:ABC-DEF...` |
| `TELEGRAM_CHAT_ID` | ✅ | 你的 TG 用户 ID | `12345678` |

> **多账号支持 (可选)**：
> 如果你有多个账号，可以不设置 `ICMP9_EMAIL/PASSWORD`，而是设置 `ICMP9_ACCOUNTS`，格式为：`邮箱1:密码1,邮箱2:密码2`。

### 3. 启用 Workflow
1.  点击仓库顶部的 **Actions** 标签。
2.  如果不显示工作流，点击绿色按钮 **I understand my workflows, go ahead and enable them**。
3.  脚本默认设置在 **每天北京时间 10:00 (UTC 02:00)** 自动运行。

### 4. 手动触发测试
在 **Actions** 页面，点击左侧的 `ICMP9 Auto Checkin`，然后点击右侧的 **Run workflow** 按钮即可立即运行测试。

## 🔔 通知示例

脚本运行完成后，你的 Telegram 机器人会发送如下消息和两张图片：

**文字消息：**
```text
✈️ ICMP9 签到报告
--------------------
👤 ***
STATUS: 今日已签到
🎁 今日奖励: *** GB
📊 累计获得: *** GB
🗓 累计签到: *** 天
🔥 连续签到: *** 天
--------------------
```

**图片附件：**
1.  `***登录成功截图.png`
2.  `***签到状态截图.png`

## 🛠️ 本地运行 (可选)

如果你想在本地电脑运行调试：

1.  **安装 Chrome 浏览器**。
2.  **安装 Python 依赖**：
    ```bash
    pip install DrissionPage requests
    ```
3.  **配置环境变量** (Linux/Mac 示例)：
    ```bash
    export ICMP9_EMAIL="你的邮箱"
    export ICMP9_PASSWORD="你的密码"
    # 可选通知配置
    export TELEGRAM_BOT_TOKEN="xxx"
    export TELEGRAM_CHAT_ID="xxx"
    ```
4.  **运行脚本**：
    ```bash
    python icmp9_cf_checkin.py
    ```

## ❓ 常见问题排查

**Q: 脚本运行失败，如何查看原因？**
A: 在 GitHub Actions 的运行页面底部，找到 **Artifacts** 区域，下载 `debug-evidence` 压缩包。里面包含了脚本运行时的截图和网页源码，可以直观地看到是卡在验证码、登录页还是其他地方。

**Q: 截图里中文显示为方框 (□□□)？**
A: 确保你的 `.yml` 文件中包含了安装中文字体的步骤 (`fonts-noto-cjk`)。提供的最新版 YAML 已包含此配置。

**Q: Cloudflare 验证一直不通过？**
A: 脚本已内置鼠标轨迹模拟和重试机制。如果依然失败，可能是 GitHub 的 IP 被暂时风控，建议等待一段时间自动恢复，或尝试手动登录一次该账号。

## ⚠️ 免责声明

*   本脚本仅供学习和交流使用，请勿用于非法用途。
*   使用本脚本可能存在账号被封禁的风险（虽然已尽力模拟真人操作），作者不对任何账号损失负责。
