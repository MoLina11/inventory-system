# 🏠 出入库管理系统 — 本地部署指南

## 方案说明

在你的 Windows/Mac 电脑上运行服务，手机通过内网穿透访问。

**完全免费，无需绑卡，永不休眠。**

---

## 第一步：安装 Python（如果已有可跳过）

1. 打开 https://www.python.org/downloads/
2. 下载最新版 Python 3
3. 安装时勾选 **「Add Python to PATH」**

验证安装：打开命令行，输入 `python --version`，显示版本号即成功。

---

## 第二步：下载项目文件

从 GitHub 下载所有文件到你的电脑：
👉 https://github.com/MoLina11/inventory-system

点击绿色 **「Code」** 按钮 → **「Download ZIP」** → 解压到桌面

或者用 `/workspace/local-deploy/` 目录下的文件。

---

## 第三步：启动服务

### Windows 用户
双击 `启动.bat`

### Mac 用户
```bash
cd 项目目录
chmod +x 启动.sh
./启动.sh
```

启动后访问 http://localhost:8001

---

## 第四步：让手机也能访问（内网穿透）

### 方法一：同一 WiFi（最简单）

电脑和手机连同一个 WiFi，手机浏览器访问 `http://电脑IP:8001`

查看电脑 IP：
- Windows: 命令行输入 `ipconfig`，找 IPv4 地址
- Mac: 命令行输入 `ifconfig | grep inet`

---

### 方法二：免费内网穿透（任何网络都能访问）

使用免费的 **bore** 工具：

#### 1. 下载 bore
打开 https://github.com/ekzhang/bore/releases 下载对应系统版本

#### 2. 运行穿透
```bash
bore local 8001 --to bore.pub
```

会得到一个公网地址，比如 `bore.pub:12345`，手机用这个地址就能访问。

---

### 方法三：cpolar（国内推荐，更稳定）

1. 打开 https://www.cpolar.com 注册（免费）
2. 下载客户端安装
3. 运行：`cpolar http 8001`
4. 会得到一个公网地址

---

## 保持长期运行

- 电脑不关机就行
- 或者用旧电脑/树莓派 24 小时跑
- 把 `启动.bat` 加入开机自启动

---

## 文件清单

| 文件 | 说明 |
|------|------|
| server.py | 后端服务 |
| inventory-web.html | 前端页面 |
| data.json | 数据文件（所有出入库数据） |
| zxing.min.js | 扫码库 |
| requirements.txt | Python 依赖 |
| 启动.bat | Windows 一键启动 |
| 启动.sh | Mac 一键启动 |

---

## 数据备份

定期备份 `data.json` 文件即可。复制到 U 盘或网盘就是完整备份。
