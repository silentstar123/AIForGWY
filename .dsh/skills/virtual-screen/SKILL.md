---
name: virtual-screen
description: 准备、修复和使用常驻虚拟屏；自己决定开几块、零 UAC 扩容、设分辨率、把窗口摆到第 N 块画布。用户要求开虚拟屏、多开画布、把程序分到不同屏、或 GUI 操作前准备画布时使用。
whenToUse: 用户说“开虚拟屏”“开两块屏”“把浏览器和文档分开”“画布没了”“改虚拟屏分辨率”，或做 GUI 操作前需要确认画布时。
---

# 虚拟屏

目标是让 agent 自己把画布准备好，不需要用户记命令。

## 先看状态，再决定开几块

```powershell
python specialty/virtualscreen/virtualscreen.py count
python specialty/virtualscreen/virtualscreen.py ensure
```

`count` 返回 `{"configured": N, "actual": M}`：配置是打算开几块，实际是现在真有几块。两者不一致就说明差一次设备重启。

`ensure` 的 `stage`：

- `ready`：已有可用虚拟屏，`canvas.index` 是显示器编号；
- `extended`：刚才自动执行了 `DisplaySwitch /extend`；
- `needs-restart`：驱动在、监视器未激活；
- `needs-install`：没有虚拟显示驱动。

## 决定开几块（优先零 UAC）

```powershell
python specialty/virtualscreen/virtualscreen.py set-count 2 --apply --helper
python specialty/virtualscreen/virtualscreen.py count
```

本机已装 SYSTEM 小助手 `DSHDisplayHelper`，`--helper` 会写标志文件，计划任务在一分钟内重启显示设备并扩展桌面，**不弹 UAC**。实测约 58 秒。

没有小助手时：

```powershell
# 装一次，需要管理员窗口
powershell -ExecutionPolicy Bypass -File specialty\virtualscreen\install-helper.ps1

# 或者退而求其次
set-count N --apply --elevate   # 弹一次 UAC
set-count N --apply --ask       # 让桌宠气泡向人求授权
```

`needs-helper` / `needs-admin` 时把命令原样交给用户，不要循环重试。

## 多块画布怎么用

```powershell
python specialty/virtualscreen/virtualscreen.py canvas --index 1
python specialty/virtualscreen/virtualscreen.py canvas --index 2
python specialty/screen/screen.py place --window "记事本" --virtual --virtual-index 2 --maximize --apply
python specialty/screen/screen.py capture --virtual --virtual-index 2 --out shot.png
```

- `--virtual` 自动解析编号，不要假设是 2 或 3；
- `--virtual-index N` 选第 N 块虚拟屏；
- 摆完看返回的 `actual` 坐标，确认窗口真的落在画布上。

## 改分辨率（按设备名）

VDD 新屏默认 800×600。多块屏时按设备名分别改，位置也要错开：

```powershell
python specialty/screen/screen.py list
python specialty/screen/screen.py set --display '\\.\DISPLAY36' --width 1920 --height 1080 --x 3520 --y 0
python specialty/screen/screen.py set --display '\\.\DISPLAY37' --width 1920 --height 1080 --x 5440 --y 0
```

只接受 `vdd_settings.xml` 里列出的档位（800×600、1366×768、1920×1080、2560×1440、3840×2160）；要别的档位得改 XML 再重启设备。

## 收回去

```powershell
python specialty/virtualscreen/virtualscreen.py set-count 1 --apply --helper
```

同样约一分钟生效。不想要小助手：`Unregister-ScheduledTask DSHDisplayHelper`（管理员）。

## 常用配方

### 一块屏，把工作区收回来

```powershell
python specialty/virtualscreen/virtualscreen.py set-count 1 --apply --helper
python specialty/virtualscreen/virtualscreen.py count
```

### 两块屏，浏览器和文档分开放

```powershell
python specialty/virtualscreen/virtualscreen.py set-count 2 --apply --helper
python specialty/virtualscreen/virtualscreen.py count          # 等 actual=2
python specialty/screen/screen.py list                          # 看 3、4 号虚拟屏的设备名
python specialty/screen/screen.py set --display '\\.\DISPLAY36' --width 1920 --height 1080 --x 3520 --y 0
python specialty/screen/screen.py set --display '\\.\DISPLAY37' --width 1920 --height 1080 --x 5440 --y 0
python specialty/screen/screen.py place --window "Microsoft Edge" --virtual --virtual-index 1 --maximize --apply
python specialty/screen/screen.py place --window "记事本" --virtual --virtual-index 2 --maximize --apply
```

设备名每次重启可能变，以 `screen.py list` / `virtualscreen.py status` 当时的输出为准；摆完用 `capture --virtual --virtual-index N` 复核。

### 三块、四块

同样流程，`set-count 3` 或 `set-count 4`，再按设备名依次设 3520 / 5440 / 7360 的 x 坐标（每块 1920 宽）。VDD 最多 4 块。

### 截图/操作前让桌宠隐身

```powershell
python specialty/pet/pet.py hide
python specialty/vision/vision.py shot --virtual --virtual-index 2 --out shot.png --grid --ocr
python specialty/pet/pet.py show
```

### 摆完复核

```powershell
python specialty/screen/screen.py list
python specialty/vision/vision.py shot --virtual --virtual-index 2 --out check.png
python specialty/pet/pet.py show
```

## 排错

| 现象 | 处理 |
|---|---|
| `count` 配置 2、实际 1 | 差一次重启：`set-count 2 --apply --helper`（会按实际数判断） |
| `needs-helper` | 管理员跑 `install-helper.ps1` 一次 |
| `request-restart` 超时 | 查 `DSHDisplayHelper` 是否在跑；`helper-status` 看标记 |
| 新屏 800×600 | 按设备名 `screen.py set` 改分辨率 |
| `ensure` 返回 `needs-restart` | 用 `--helper` 或管理员 `setup.ps1 -Action restart` |
| 虚拟屏突然消失 | 重新 `ensure`，重截图；不要沿用旧 `shot.json` |

## 规矩

1. GUI 任务开始前先 `count`/`ensure`，不要假设虚拟屏一直在；
2. 需要几块就先说清楚，改完用 `count` 确认 `actual` 到位；
3. 画布编号从 `canvas` 取，或直接用 `--virtual`/`--virtual-index`；
4. `--helper` 最多等两分钟；超时就如实报，不要反复写标志；
5. 截图前确认窗口确实在画布上（`place` 返回的 `actual`）。
