# 深圳航空机票价格监控脚本

本项目是一个使用 Python 编写的脚本，旨在监控特定深圳航空航班的机票价格，并通过 PushPlus 推送通知。脚本设计为可以通过 GitHub Actions 定时自动运行，同时也支持在本地环境中通过配置文件运行。

## ✨ 功能特性

* **自动监控**: 利用 GitHub Actions 实现定时（例如每30分钟）自动抓取指定深航航班页面的价格信息。
* **价格提取**: 解析航班搜索结果页面，提取目标航班的当前最低票价。
* **PushPlus 推送**: 将查询到的价格信息或查询状态通过 PushPlus 发送到微信或其他配置的渠道。
* **灵活配置**: 支持通过环境变量 (GitHub Actions) 或本地 JSON 文件 (`config.local.json`) 进行配置。
* **本地运行**: 方便在本地进行测试和调试。

## 🚀 快速开始

### 准备工作

1. **PushPlus Token**: 注册并登录 [PushPlus 官网](https://www.pushplus.plus/)，在“首页”获取你的 Token。
2. **目标航班信息**: 确定你想要监控的航班号和对应的深圳航空查询 URL。
    * 例如，访问深圳航空官网，搜索你需要的航班，复制浏览器地址栏中的 URL。
    * 记下你要监控的航班号（`ZH****`）。

### 配置与运行

#### 方式一：使用 GitHub Actions (推荐)

1. **Fork 本仓库**: 点击本仓库右上角的 "Fork" 按钮。
2. **设置 Secrets**:
    * 在你 Fork 后的仓库页面，点击 "Settings" -> "Secrets and variables" -> "Actions"。
    * 点击 "New repository secret"。
    * 创建一个名为 `PUSHPLUS_TOKEN` 的 Secret，值为你的 PushPlus Token。
    * **(可选)** 如果你想修改监控的航班号或 URL，可以考虑：
        * 直接修改 `.github/workflows/monitor.yml` 文件中的 `env` 部分。
        * 或者，同样在 Actions Secrets/Variables 中创建 `FLIGHT_NUMBER` 和 `TARGET_URL`。如果创建了这些 Secrets/Variables，它们会覆盖掉 workflow 文件中 `env` 部分的默认值。
3. **启用 Actions**:
    * 在你 Fork 后的仓库页面，点击 "Actions" 标签页。
    * 如果看到提示 "Workflows aren't running on forks by default"，点击 "I understand my workflows, go ahead and enable them"。
4. **运行**:
    * Action 会根据 `.github/workflows/monitor.yml` 中定义的 `schedule` 自动定时运行。
    * 你也可以在 "Actions" 页面，选择 "深圳航空机票价格监控" workflow，点击 "Run workflow" -> "Run workflow" 来手动触发一次。

#### 方式二：在本地运行

1. **克隆仓库**:

    ```bash
    git clone https://github.com/你的用户名/你的仓库名.git
    cd 你的仓库名
    ```

2. **安装依赖**:

    ```bash
    pip install -r requirements.txt
    ```

    或者 (如果使用 Python 3):

    ```bash
    python3 -m pip install -r requirements.txt
    ```

3. **创建本地配置文件**:
    * 复制 `config.local.example.json` 并重命名为 `config.local.json`。
    * 编辑 `config.local.json`，填入你的 `PUSHPLUS_TOKEN`、目标 `FLIGHT_NUMBER` 和 `TARGET_URL`。

    ```json
    {
      "PUSHPLUS_TOKEN": "你的PushPlus Token",
      "FLIGHT_NUMBER": "你要监控的航班号",
      "TARGET_URL": "深圳航空航班查询页面的完整URL"
    }
    ```

    * **注意**: `config.local.json` 已被添加到 `.gitignore` 中，不会被提交到 Git 仓库。
4. **运行脚本**:

    ```bash
    python monitor.py
    ```

    或者 (如果使用 Python 3):

    ```bash
    python3 monitor.py
    ```

## ⚙️ 配置说明

脚本通过以下方式获取配置信息，优先级从高到低：

1. **环境变量** (主要用于 GitHub Actions):
    * `PUSHPLUS_TOKEN`: 你的 PushPlus 用户令牌 (必需)。
    * `FLIGHT_NUMBER`: 你要监控的航班号 (必需)。
    * `TARGET_URL`: 深圳航空航班查询页面的完整 URL (必需)。
2. **本地配置文件** (`config.local.json`):
    * 如果环境变量不完整，脚本会尝试从此文件加载。文件内容应为 JSON 格式，包含 `PUSHPLUS_TOKEN`, `FLIGHT_NUMBER`, `TARGET_URL` 三个键。

## ⚠️ 注意事项

* **网站结构变更**: 航空公司网站的页面结构可能会发生变化，这可能导致脚本解析失败。如果脚本停止工作，请检查网站结构是否已更改，并相应地更新 `monitor.py` 中的解析逻辑。
* **请求频率**: GitHub Actions 的 cron 调度是近似的，不保证精确到秒。请勿设置过于频繁的请求（例如小于5分钟），以免给目标网站带来不必要的负担或触发反爬虫机制。当前配置为30分钟一次，是相对合理的频率。
* **IP 地址**: GitHub Actions 的运行 IP 可能变化，频繁请求可能会被目标网站识别。
* **免责声明**: 本脚本仅供学习和个人使用，请勿用于非法用途。使用本脚本可能产生的任何风险或后果由使用者自行承担。请遵守深圳航空网站的使用条款。

## 贡献

欢迎提出 Issue 或 Pull Request 来改进此项目。
