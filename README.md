# 🏠 出入库管理系统 — 本地部署指南

## 方案说明

在你的 Windows 电脑上运行服务，用 cpolar 免费内网穿透，手机浏览器打开即可使用。

**完全免费，无需绑卡。**

---

## 第一步：安装 Python

1. 打开 https://www.python.org/downloads/
2. 下载最新版 Python 3
3. 安装时勾选 **「Add Python to PATH」**

验证：命令行输入 `python --version`

---

## 第二步：启动系统

双击 `启动.bat`

浏览器打开 http://localhost:8001 确认能访问

---

## 第三步：安装 cpolar 内网穿透

1. 打开 https://www.cpolar.com 注册（免费，不需绑卡）
2. 下载 Windows 客户端并安装
3. 打开 cpolar，运行：
```
cpolar http 8001
```
4. 会显示一个公网地址，比如 `https://xxxx.cpolar.cn`
5. 手机浏览器打开这个地址就能用了

---

## 扫码说明

点📷按钮 → 打开摄像头 → 实时预览 → 条码对准自动识别

**建议用手机自带浏览器（Chrome/Safari）打开，扫码体验最佳。**

微信内置浏览器对摄像头有限制，扫码会慢。

---

## 保持长期运行

- 电脑不关机就行
- 把 `启动.bat` 加入开机自启动
- cpolar 也设为开机自启

---

## 数据备份

定期备份 `data.json` 文件，复制到 U 盘或网盘。
