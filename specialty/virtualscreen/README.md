# 虚拟屏幕（常驻画布）

把 agent 的画面固定到一块**常驻虚拟屏**上，用户主屏不受影响。Windows 对虚拟屏和物理屏一视同仁，[screen.py](../screen/screen.py) 和 [vision.py](../vision/vision.py) 不用改。

## 现状检测

```powershell
python specialty/virtualscreen/virtualscreen.py status
python specialty/virtualscreen/virtualscreen.py require
```

`status` 列出显示适配器，标出虚拟/物理、是否启用、挂了几块监视器；`require` 在没有启用中的虚拟屏时退出码为 1。

## 一次性启用（需要管理员）

本机已装向日葵的虚拟显示驱动（`OrayIddDriver`），设备在，但监视器数为 0。以管理员身份运行一次：

```powershell
powershell -ExecutionPolicy Bypass -File specialty/virtualscreen/setup.ps1 -Action status
powershell -ExecutionPolicy Bypass -File specialty/virtualscreen/setup.ps1 -Action restart
```

- 只重启已装的虚拟显示设备，让驱动重新创建监视器，**不安装新驱动**。
- 如果重启后显示器数量没变，说明该驱动只在远程会话里创建监视器；改用向日葵客户端的“扩展屏”，或安装 [Virtual Display Driver](https://github.com/VirtualDrivers/Virtual-Display-Driver) 后重启。

## 安装 VDD（常驻方案）

Oray 的虚拟显示设备只有在向日葵远程会话里才创建监视器，重启设备不会多出屏幕。要常驻，用 Virtual Display Driver：

```powershell
powershell -ExecutionPolicy Bypass -File specialty\virtualscreen\install-vdd.ps1 -Action status
powershell -ExecutionPolicy Bypass -File specialty\virtualscreen\install-vdd.ps1 -Action install
```

脚本做的事：下载官方 release（25.7.23）、校验 SHA256、校验 Authenticode 签名（SignPath Foundation）、复制到 `C:\VirtualDisplayDriver`、用本机 devcon 建 `Root\MttVDD` 设备。卸载用 `-Action remove`。

装完如果桌面还没多出屏幕（设备在、监视器未激活），脚本会自动执行 `DisplaySwitch.exe /extend`。本机实测：扩展后得到 `\\.\DISPLAY25`，默认 800×600，可用 `set` 改到 1920×1080。

## 决定开几块

```powershell
python specialty/virtualscreen/virtualscreen.py count
python specialty/virtualscreen/virtualscreen.py set-count 2            # 只改配置
python specialty/virtualscreen/virtualscreen.py set-count 2 --apply    # 尝试重启设备
python specialty/virtualscreen/virtualscreen.py set-count 2 --apply --elevate  # 弹一次 UAC
python specialty/virtualscreen/virtualscreen.py set-count 2 --apply --helper   # 零 UAC（需先装小助手）
```

改 `<count>` 不需要管理员；让新数量生效要重启显示设备。三条路：

1. `--elevate`：弹一次 UAC，本人点“是”；
2. `--helper`：写一个标志文件，由 SYSTEM 计划任务在一分钟内重启设备，不再弹 UAC；
3. `--ask`：需要权限时让桌宠弹气泡向在场的人求授权。

### 零 UAC：装一次小助手（本机已验证）

管理员窗口跑一次（只需一次）：

```powershell
powershell -ExecutionPolicy Bypass -File specialty\virtualscreen\install-helper.ps1
```

它会：把 `display-helper.ps1` 复制到 `C:\ProgramData\DSHDisplay`（脚本目录 ACL 只留 SYSTEM/Administrators）、建一个 `queue` 子目录（Users 可写标志、读结果）、写 `queue\installed.json` 标记、注册计划任务 `DSHDisplayHelper`（SYSTEM，每 1 分钟检查一次）。

之后不需要管理员：

```powershell
python specialty/virtualscreen/virtualscreen.py helper-status
python specialty/virtualscreen/virtualscreen.py set-count 2 --apply --helper
python specialty/virtualscreen/virtualscreen.py count
```

实测：`set-count 2 --apply --helper` 等了 58 秒返回 `applied`，出现 `\\.\DISPLAY36`、`\\.\DISPLAY37` 两块虚拟屏。

两块屏各自改分辨率（按设备名，不是编号）：

```powershell
python specialty/screen/screen.py set --display '\\.\DISPLAY36' --width 1920 --height 1080 --x 3520 --y 0
python specialty/screen/screen.py set --display '\\.\DISPLAY37' --width 1920 --height 1080 --x 5440 --y 0
python specialty/screen/screen.py place --window "记事本" --virtual --virtual-index 2 --maximize --apply
```

`request-restart` 写 `queue\restart.flag`，助手执行 `pnputil /restart-device` + `DisplaySwitch /extend`，结果写 `queue\result.json`，Python 侧轮询拿到结果。

安全边界：计划任务只做“重启显示设备 + 扩展桌面”，不执行任意命令；脚本目录只有 SYSTEM 和管理员能改，队列目录只允许写标志/读结果。不想要了用 `Unregister-ScheduledTask DSHDisplayHelper` 删掉。

## 启用之后

```powershell
python specialty/virtualscreen/virtualscreen.py status   # 应显示 virtualActive: true
python specialty/virtualscreen/virtualscreen.py set --width 1920 --height 1080
python specialty/screen/screen.py list                    # 找到虚拟屏编号
python specialty/screen/screen.py place --window "记事本" --monitor 2 --maximize --apply
python specialty/vision/vision.py shot --monitor 2 --out shot.png --grid --ocr
```

## 边界

- `setup.ps1` 需要管理员；普通会话跑会被 `#Requires` 拒绝。
- 脚本以 **UTF-8 BOM** 保存：Windows PowerShell 5.1 没有 BOM 会按 GBK 读中文，导致解析报错；编辑时不要去掉 BOM。
- 重启显示设备可能让窗口短暂闪烁，不会丢数据。
- 驱动升级或向日葵退出后，虚拟屏可能消失；`require` 会先报错，避免点到空坐标。
