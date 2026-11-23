# ⏰ 签到管理系统

一个自托管的定时签到工具：在网页里配置签到任务（URL / 请求方法 / 自定义 Headers / Cookie / Body），
由后台调度器每天在指定时间自动发起请求，并把结果记录下来；可选通过 **QQ 官方机器人** 私信推送签到结果。

> ⚠️ 本项目仅用于自动化你自己拥有账号的服务的签到流程。请勿用于绕过他人服务的风控或攻击任何系统。

---

## 功能特性

- 🖥️ **Web 管理界面**：增删改查签到项，开关启用状态，一键手动签到 / 全部签到
- ⏰ **定时调度**：基于 APScheduler 的 Cron 触发，每个签到项可单独设定每日 `HH:MM` 时间
- 🧾 **自定义请求头**：表格化编辑 + JSON 批量导入两种方式，可覆盖默认 UA / Accept 等头
- 📝 **执行日志**：记录每次签到的状态、HTTP 状态码、响应片段（保留最近 50 条，前端每 15 秒刷新）
- 🔔 **QQ 机器人通知**：签到完成后推送成功/失败结果到指定 OpenID
- 📦 **零外部依赖服务**：SQLite 单文件存储，`python app.py` 即可跑起来

---

## 技术栈

| 组件 | 说明 |
|---|---|
| Python | 3.10+（开发环境 3.13） |
| Flask | Web 服务与 REST API |
| APScheduler | 后台定时任务调度 |
| requests | 发起签到 HTTP 请求 |
| SQLite | 签到项 / 通知配置 / 日志存储（`sign.db`） |
| 原生 HTML/CSS/JS | 单页前端（`templates/index.html`），无构建步骤 |

---

## 目录结构

```
facai-timing-sign/
├── app.py                 # Flask 应用入口：路由、API、定时任务注册
├── checker.py             # 签到执行器：发请求、写结果、触发通知
├── db.py                  # SQLite 数据层（items / notify_config / logs）
├── notify.py              # QQ 官方机器人通知
├── openid-helper.mjs      # 获取 QQ 用户 OpenID 的辅助脚本（Node.js）
├── task.sh                # 启动 / 停止 / 重启脚本
├── requirements.txt       # Python 依赖
├── templates/
│   └── index.html         # 前端页面（含样式与脚本）
├── sign.db                # 运行时生成，已 gitignore
└── checkin_log.log        # 运行时日志，已 gitignore
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 直接运行

```bash
python app.py
```

启动后访问 <http://127.0.0.1:10090>。

### 3. 使用脚本管理（Linux / macOS / Git Bash）

```bash
bash task.sh start     # 后台启动
bash task.sh stop      # 停止
bash task.sh restart   # 重启
```

脚本会在自身所在目录执行，PID 写入 `checkin.pid`，运行输出追加到 `checkin_log.log`；
启动失败时会直接打印日志末尾 20 行方便排查。

---

## 使用说明

### 新建签到项

点击右上角 **＋ 新建签到项**，填写：

| 字段 | 说明 |
|---|---|
| 名称 | 任务显示名，留空则为「未命名签到」 |
| 请求 URL | 必填，需以 `http://` 或 `https://` 开头 |
| 请求方法 | `POST` / `GET` / `PUT` / `PATCH` / `DELETE` |
| 每日签到时间 | `HH:MM` 格式，如 `08:30` |
| 自定义 Headers | 见下方说明 |
| Cookie | 原样放入 `Cookie` 请求头 |
| 请求体 Body | 请求正文，留空则不带 body |

### 自定义 Headers

弹窗内提供两个标签页：

- **表格编辑**：每行「名称 / 值」，可增删行；在最后一行按回车可快速新增
- **JSON 批量**：粘贴 JSON 后点「解析并填入表格」，支持两种格式

```json
{ "New-Api-User": "1057", "X-Token": "abc" }
```

```json
[ { "name": "X-Token", "value": "abc" } ]
```

保存时表格内容会被序列化为 JSON 对象存入数据库，并在发送请求时覆盖默认头。
Cookie 字段优先级最高，会单独覆盖 `Cookie` 头。

### 签到与日志

- 表格中「签到」按钮手动触发单个任务；页头「⚡ 全部签到」触发所有**已启用**任务
- 每次执行都会更新任务的上次结果，并写入「最近日志」
- 后台定时任务按每个签到项设定时间自动执行

### QQ 机器人通知

1. 在 [QQ 开放平台](https://q.qq.com) 创建机器人，获取 `AppID` / `AppSecret`，并开通「私聊消息」事件权限
2. 确保本机有 Node.js 18+，下载页面上的 `openid-helper.mjs`
3. 执行 `node openid-helper.mjs <AppID> <AppSecret>`，**60 秒内**用手机 QQ 给机器人发一条私聊
4. 终端打印出的 OpenID 填入「通知设置」并保存，可先点「发送测试消息」验证

---

## 配置项

| 项目 | 位置 | 说明 |
|---|---|---|
| 服务端口 | `app.py` 末尾 `app.run(...)` | 默认 `10090` |
| 监听地址 | 同上 | 默认 `0.0.0.0`（局域网可访问） |
| 日志级别 | `app.py` `logging.basicConfig` | 默认 `INFO` |
| 请求超时 | `checker.py` `requests.request(timeout=15)` | 单次签到超时秒数 |
| 数据库路径 | `db.py` `DB_PATH` | 固定为项目目录下的 `sign.db` |
| 日志文件 | `app.py` `LOG_FILE` | 固定为项目目录下的 `checkin_log.log` |

> 🔐 `sign.db` 中保存了 Cookie、AppSecret 等敏感信息，已加入 `.gitignore`，请勿提交或外发。

---

## API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/items` | 列出所有签到项 |
| POST | `/api/items` | 新建签到项 |
| PUT | `/api/items/<id>` | 更新签到项（支持部分字段） |
| DELETE | `/api/items/<id>` | 删除签到项 |
| POST | `/api/items/<id>/checkin` | 立即签到单项 |
| POST | `/api/checkin/all` | 立即签到所有启用项 |
| GET | `/api/logs` | 最近 50 条日志 |
| GET | `/api/notify` | 读取通知配置 |
| PUT | `/api/notify` | 保存通知配置 |
| POST | `/api/notify/test` | 发送测试通知 |

---

## 常见问题

**启动失败，没有生成 `checkin_log.log`？**
日志配置已提前到所有第三方 import 之前，且使用项目目录下的绝对路径；同时 `task.sh` 会把进程输出写入该日志。
若仍失败，请直接在终端运行 `python app.py` 查看报错（多为缺少依赖）。

**从其他目录执行脚本，找不到 PID / 日志？**
`task.sh` 会自动 `cd` 到脚本所在目录，保证文件位置固定。

**定时任务没触发？**
检查签到项是否启用、时间格式是否为合法 `HH:MM`；非法时间会在启动日志中输出 `定时时间格式非法` 警告。

**端口被占用？**
修改 `app.py` 末尾 `port=10090` 为其他端口，并同步修改 `task.sh` 中提示的访问地址。

---

## 许可

仅供个人学习与自用。
