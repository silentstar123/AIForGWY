---
name: gui-operator
description: 用截图、文字框和鼠标键盘操作没有接口的桌面程序、游戏或网页；在虚拟屏画布上按文字或坐标点击，动作后复核。用户要求操作界面、点某个按钮、在游戏里操作时使用。
whenToUse: 用户要求在桌面程序、游戏或网页上点击、输入、拖拽，或说“看着屏幕操作”“帮我点一下”时。
---

# GUI 操作

## 先选通道

1. 网页优先 `browser.py`（CDP 元素级）：`goto`、`click`、`text`、`fill`、`shot`，不用截图猜坐标。
2. OA 收文走 HTTP（`shouwen.py`），根本不开界面。
3. 只有没有元素接口的桌面程序、游戏、远程画面才用本技能。

## 画布

```powershell
python specialty/virtualscreen/virtualscreen.py ensure     # ready / extended / needs-*
python specialty/screen/screen.py place --window "<标题>" --virtual --maximize --apply
```

一次只操作一个窗口。`--virtual` 自动解析画布编号，不要假设是 2 或 3；`ensure` 返回 `needs-restart` 或 `needs-install` 时，按 `virtual-screen` 技能里的管理员命令处理。

## 看

```powershell
python specialty/vision/vision.py wait --virtual --timeout 5   # 界面在动时先等稳定
python specialty/vision/vision.py shot --virtual --out shot.png --grid --ocr
```

读同名 `shot.json`：`ocr[]` 每项有 `index`、`text`、`center`、`box`，`center` 是图片坐标。有网格时按 100px 刻度核对位置。找不到文字框时用模板匹配：

```powershell
python specialty/vision/vision.py find --image shot.png --template icon.png
```

环境自检：`python specialty/vision/vision.py doctor` 会检查 mss、OCR、画布编号和一次真实截图。

画布上有桌宠时，截图/点击前先让它隐身，避免挡住目标：

```powershell
python specialty/pet/pet.py hide
python specialty/vision/vision.py shot --virtual --out shot.png --grid --ocr
python specialty/pet/pet.py show
```

## 动

```powershell
python specialty/vision/vision.py click-text --shot shot.json --text "登录" --yes
python specialty/vision/vision.py click --shot shot.json --x 400 --y 57 --yes
python specialty/vision/vision.py click --shot shot.json --x 400 --y 57 --double --yes
python specialty/vision/vision.py click --shot shot.json --x 400 --y 57 --button right --yes
python specialty/vision/vision.py type --text "deepseek" --yes
python specialty/vision/vision.py key --combo ctrl+a --yes
python specialty/vision/vision.py scroll --shot shot.json --x 900 --y 500 --dy -3 --yes
python specialty/vision/vision.py drag --shot shot.json --x1 100 --y1 100 --x2 400 --y2 300 --yes
python specialty/vision/vision.py choose-file --path "G:\图片\1.jpg" --yes
```

跨屏拖动加 `--raw`。`scroll` 带 `--shot --x --y` 时先把鼠标移到目标位置再滚，避免滚到别的窗口。`choose-file` 处理系统文件对话框（上传图片/附件必用）：它点输入框、全选、粘贴路径、回车；直接改输入框文本不会触发对话框校验。

## 规矩

1. 先演练后执行：动作命令不加 `--yes` 只回显目标；确认坐标合理再加。
2. 动作前自动校验：`click`/`click-text`/`drag` 会重新截一块区域比对，画面变化超过阈值就拒绝；确实要强制执行才加 `--force`。
3. 动作后必须复核：重新 `shot`，或用 `diff --a before.png --b after.png` 确认画面变了、变对了。
4. 窗口挪动就重截：报“重新 shot”时不要绕开。
5. 文字优先：能用 `click-text` 就不报坐标；OCR 找不到再目测网格。
6. 不可逆动作先问：删除、提交、支付、发送消息，先向用户确认，再 `--yes`。
7. 节奏：每次点击间隔至少 300ms；动画界面先 `wait` 再截图。

## 动画与游戏

```powershell
python specialty/vision/vision.py speed --virtual --frames 30
python specialty/vision/vision.py watch --virtual --seconds 5 --fps 10 --out-dir frames
```

本机 1920×1080 实测约 30fps（mss 采集）。`watch` 只保存明显变化的帧，并回报 `maxChange`/`avgChange`。回合制、棋牌、点击类可行；动作游戏受模型反应速度限制，不要承诺实时对战。

## 本地视觉模型

本机已装 `qwen2.5vl:3b`（2.16GB，全量在 GPU）：冷启动约 100 秒，热推理 0.7 秒。

```powershell
python specialty/vision/vision.py ask --image shot.png --prompt "这个页面下一步该做什么？"
```

用它做“看懂画面、判断下一步”的判断；**不要用它给坐标**——实测 1920×1080 上找地址栏会偏到页面中部。定位一律走 OCR 的 `ocr[].center` 或 `click-text`。模型冷启动时先把一次 `ask` 当成预热，别把 100 秒算进操作超时。

## 记录

每步保留 `shot.png` + `shot.json`；结束时把关键截图、点击位置和复核结果写进答复，便于用户追溯。
