# 飞书群聊表格自动日报（基于 lark-cli）

本项目用于监控指定飞书群聊，当有人发送 `AI助手问题单日报` 时，自动从飞书多维表格拉取数据、生成 HTML、截图并发送回群聊。全程通过 `lark-cli` 调用，不使用长连接机器人。

## 1. 环境要求
- Windows 10/11
- Python 3.10+（你当前环境为 3.15.2 也可用）
- 已安装并登录 `lark-cli`（`lark-cli whoami` 显示 `tokenStatus: ready`）
- 已加入目标群聊（`chat_id: oc_cd5f1d54c1a5349c06ac0d1dd0050a55`）

## 2. 安装步骤

### 2.1 复制项目
将本项目复制到本地目录，例如 `D:\feishu-daily-report\`

### 2.2 创建虚拟环境（可选但推荐）
```powershell
cd D:\feishu-daily-report
python -m venv .venv
.\.venv\Scripts\activate
```
### 2.3 安装依赖
```powershell
pip install -r requirements.txt
playwright install chromium
```
### 2.4 配置环境变量
复制 .env.example 为 .env
```powershell
copy .env.example .env
```
如需调整群聊、关键词、轮询间隔等可直接修改 .env

## 3. 使用方式
### 3.1 临时测试（前台运行）
```powershell
python main.py
```
在目标群里发送 `AI助手问题单日报`，观察控制台日志和群聊是否收到截图。

### 3.2 后台常驻（推荐 nssm）
下载 nssm (https://nssm.cc/download)，解压后以管理员 PowerShell 运行：
```powershell
# 安装服务
nssm install FeishuDailyReport "C:\Python\pythonw.exe" "D:\feishu-daily-report\main.py"
nssm set FeishuDailyReport AppDirectory "D:\feishu-daily-report"
nssm set FeishuDailyReport DisplayName "Feishu Daily Report Bot"
nssm set FeishuDailyReport Start SERVICE_AUTO_START
nssm set FeishuDailyReport AppStdout "D:\feishu-daily-report\logs\service_stdout.log"
nssm set FeishuDailyReport AppStderr "D:\feishu-daily-report\logs\service_stderr.log"

# 创建日志目录
mkdir D:\feishu-daily-report\logs -Force

# 启动服务
nssm start FeishuDailyReport
```
管理命令：
```powershell
nssm status FeishuDailyReport
nssm stop FeishuDailyReport
nssm restart FeishuDailyReport
nssm remove FeishuDailyReport confirm
```
### 3.3 也可用 pythonw
```powershell
Start-Process pythonw -ArgumentList "main.py" -WorkingDirectory "D:\feishu-daily-report"
```

## 4. 工作原理
1. 每隔 POLL_INTERVAL_SEC 秒调用 `lark-cli im +chat-messages-list` 轮询群消息
2. 过滤 `msg_type == 'text'` 且内容精确等于触发关键词且未处理过的消息
3. 通过多策略解析表格坐标（`base +url-resolve` -> `wiki +node-get` -> 全量遍历 Wiki 空间）
4. 用 `lark-cli base +record-list` 拉取全量多维表格记录
5. 用 Jinja2 生成自包含 HTML，Playwright 截图为 PNG
6. 用 `lark-cli im +messages-send --image` 将截图发送回群聊
7. 仅在发送成功后将 `message_id` 写入 `state/processed_msg_ids.json` 实现去重

## 5. 注意事项
- 权限：如果原始 Wiki 链接对当前账号无权限，resolver 会尝试遍历当前可访问的空间。若目标多维表格不在可访问范围内，将无法拉取数据。需确保账号对目标表格有访问权限。
- 去重：去重是基于 message_id 的，且只在成功发图后才记录，避免因异常重复发送。
- 截图中文：模板已指定中文字体，Playwright 使用 Chromium 一般可正常渲染。
- 常驻：推荐用 nssm 作为 Windows 服务运行，开机自启且更稳定。
- lark-cli 版本：建议使用与你实测环境一致的 lark-cli 版本。

## 6. 常见排查
- `lark-cli: command not found` -> 将 lark-cli 加入 PATH 或在 .env 设置 `LARK_CLI_CMD` 为完整路径
- 无法解析表格 -> 检查账号权限，或改用能访问的 Base 链接并让 `base +url-resolve` 命中
- 截图空白/乱码 -> 确认已安装 `playwright install chromium`，且系统有中文字体
- 重复触发 -> 检查 `state/processed_msg_ids.json` 是否正常写入

## 使用说明

1. 新建 `feishu-daily-report/` 目录，将以上所有文件按结构创建
2. 复制 `.env.example` 为 `.env`
3. 安装依赖：`pip install -r requirements.txt && playwright install chromium`
4. 确认 `lark-cli` 已登录（`lark-cli whoami`）
5. 测试运行：`python main.py`，在群里发 `AI助手问题单日报`
6. 稳定后用 `nssm` 注册为 Windows 服务常驻

> 注：当前环境下原始 Wiki 节点因权限无法直接解析，代码已内置多策略兜底逻辑。一旦权限恢复或目标表格对当前账号可见，流程即可自动走通。
