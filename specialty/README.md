# 公务员办公特化

这个检出在 DeepSeek Harness 之上加了公文技能和检查脚本。`packages/` 保持上游原样。

## 模块

| 目录 | 作用 |
| --- | --- |
| [`gongwen/`](gongwen/) | 公文骨架、检查、Word 生成、省文件转发、公文案例库 |
| [`shouwen/`](shouwen/) | 收文查收、清单、配置、aTrust 提醒、微信推送 |
| [`screen/`](screen/) | 显示器/窗口画布：枚举、截图、摆位、点击 |
| [`vision/`](vision/) | 图像操作：网格、OCR 框、按图坐标点击/输入、模板匹配 |
| [`browser/`](browser/) | CDP 元素级浏览器操作 |
| [`virtualscreen/`](virtualscreen/README.md) | 虚拟屏识别与一次性启用 |
| [`pet/`](pet/README.md) | 指挥桌宠「大肥鱼」：说话、接话、看画面、停手 |
| [`voice/`](voice/README.md) | 本机语音输入：SAPI 听写、唤醒词 |
| [`work/`](work/README.md) | 工作台：拆步骤、留痕、收尾出报告 |
| [`ops/`](ops/README.md) | 多账号运营台：账号登记、任务队列、限额排班、四屏监看 |
| [`deliver/`](deliver/README.md) | 现场交付：自检 doctor、部署脚本、演示脚本、交接手册 |

## 启动后会用到的技能

| 技能 | 什么时候用 |
| --- | --- |
| `gongwen-draft` | 起草通知、请示、报告、函、纪要、批复 |
| `gongwen-review` | 审别人给的稿 |
| `office-draft` | 方案、简报、拟办、讲话提纲、总结、督办、办文单 |
| `meeting-brief` | 一页纸汇报、把会议记录收成纪要 |
| `policy-basis` | 写「根据……」，核对文号和条款 |
| `shouwen` | 查收 OA 待签收、按日汇总收文清单、准备拟办 |
| `gui-operator` | 截图+OCR+鼠标键盘操作桌面程序、游戏或网页 |
| `virtual-screen` | 准备/修复虚拟画布，缺驱动时引导安装 |
| `pet-bridge` | 指挥桌宠说话、接话、看画面、停手 |
| `voice-input` | 本机麦克风听人说话，支持唤醒词 |
| `desk-work` | 像坐班一样接活、拆步、干活、交活 |
| `ops-fleet` | 多账号登记、批量任务、限额排班、四屏监看 |

技能在 `.dsh/skills/`。在本仓库根目录启动 `dsh`，项目根就是这里，技能会被带上。

## 现场交付

```powershell
python specialty/deliver/doctor.py                 # 11 项环境自检
powershell -File specialty\deliver\deploy.ps1      # 装依赖 + 自检
powershell -File specialty\deliver\demo.ps1        # 自检→画布→摆窗→输入→截图
```

细节和交接清单见 [deliver/README.md](deliver/README.md)。

## 现在就能跑的检查

在仓库根目录：

```powershell
node specialty/gongwen/check.mjs scaffold 请示 --title "关于购置办公设备的请示" --recipient "市局"
node specialty/gongwen/check.mjs lint 请示 --file 草稿.md
node specialty/gongwen/check.mjs facts --file 草稿.md
node specialty/gongwen/check.mjs review 请示 --file 草稿.md
node specialty/gongwen/check.mjs diff --left 原稿.md --right 改稿.md
node specialty/gongwen/self-check.mjs
```

文种还可以是方案、简报、拟办、讲话、总结、督办、办文。`scaffold` 只给空骨架。`review` 把结构检查和文号、日期、金额放在一份结果里。`diff` 只列出两份稿不一样的文号、日期和金额。`lint` 或 `review` 退出码 `0` 表示结构项过了，`1` 表示有缺项。

## 重点文库

从 `G:\办公\办公` 和 `G:\高技术` 里学本人写法，先于案例库使用：

```powershell
python specialty/gongwen/key_lib.py build
python specialty/gongwen/key_lib.py style
python specialty/gongwen/key_lib.py brief --kind 通知
python specialty/gongwen/key_lib.py match --kind 报告 --keyword 场景汇
```

数据在 `specialty/gongwen/cases/key/`，含本机路径和摘录，只在本地，已加入 `.gitignore`。

## 公文案例库

从本机高质量公文里抽版式和结构，写材料先照着来：

```powershell
python specialty/gongwen/case_lib.py scan
python specialty/gongwen/case_lib.py brief --kind 通知
python specialty/gongwen/case_lib.py match --kind 报告 --keyword 场景汇
python specialty/gongwen/case_lib.py show <id>
```

数据在 `specialty/gongwen/cases/`，含本机路径和摘录，只在本地，已加入 `.gitignore`。

## 按本机样本生成 Word

版式取自本机四份样本，写在 `specialty/gongwen/format.json`：A4，上 3.5、下 3.5、左 2.7、右 2.7 厘米；发文机关标志和标题用方正小标宋简体二号（22pt），正文用仿宋_GB2312 三号（16pt），行距固定 28pt，首行缩进 2 字符；署名和成文日期右对齐；页码在页脚居中为 `— 1 —`。

```powershell
python specialty/gongwen/gongwen_docx.py template 转发通知 --out spec.json
python specialty/gongwen/gongwen_docx.py build spec.json --out 转发通知.docx
python specialty/gongwen/gongwen_docx.py inspect 样本.docx --out dump.txt
python specialty/gongwen/gongwen_docx.py learn 'G:\办公\办公\20261027 创新平台转发通知' 'G:\办公\办公\20260911 未来产业转发' --out learned.json
```

`template` 的文种和 `check.mjs` 一致。`转发通知` 只要给 `sources`（被转发文件的标题和文号）、`sourceOrgan`、`purpose`，标题和「……现转发给你们，请认真贯彻执行。」会自动拼好；多份文件用「和」连接，内层书名号自动转成〈〉。

版式选项：标题超过 20 字自动断行（`titleCharsPerLine` 可调，`titleLines` 可完全手排）；上行文给 `signer`，发文字号和「签发人：」排在同一行、姓名用楷体；`redLine` 为真时在发文字号下加红色反线；`cc`、`printer`、`printDate` 生成版记（抄送一条，印发机关和日期一条，带上下分隔线）。`inspect` 打印样本的页面、页边距、字体、字号、行距，用来核对 `format.json`。`check` 反过来核对一份现成的 docx：页面、边距、正文和标题的字体字号、行距、缩进、页码域，逐项报出偏差，不合格退出码为 1。

`learn` 扫一批 docx，按正文字数统计出出现最多的字体、字号、行距、缩进和页边距，给出候选值；加 `--write` 写回 `format.json`，写前备份成 `format.backup.json`。用本机 11 份样本跑出来的结果是：A4，上 3.5、下 3.5、左 2.7、右 2.7 厘米，正文仿宋_GB2312 三号，行距 29.2pt（转发类样本是 28pt），首行缩进 32pt。默认仍按转发类样本的 28pt 渲染。

## 收一份省文件，转下去

省文件在收文目录里先挑出来，再打成一个可以直接发的包：

```powershell
python specialty/shouwen/shouwen.py provincial --days 7
python specialty/gongwen/forward.py --source "<上面清单里的 path>" --out-dir .\转发包 `
    --document-no "廊发改技术〔2026〕369号" --recipients "各县（市、区）发改局" `
    --doc-date "2026年10月29日" --purpose "强化产业技术工程化中心建设"
```

`forward.py` 从省文件里抽标题、来文文号、发文机关：docx 能直接读；有文字层的 PDF 也能读；扫描件先看有没有文字层，没有就用本机 `rapidocr_onnxruntime` 识别前 3 页（`--ocr-pages` 调整，`--no-ocr` 关闭），再从中抽标题和文号。OCR 不可用时退回文件名。生成的包里有 `转发通知.docx`、`附件1 <省文件标题>.<ext>`、`转发通知.spec.json` 和 `转发说明.md`，说明里列出哪些字段是推出来的、哪些还要核对。多份省文件就给多个 `--source`，标题和正文里的书名号会自动处理成《…〈…〉…》。

OCR 的边界：识别结果只作线索，文号、标题仍要在 `转发说明.md` 里逐条核对；一页 200dpi 约 2–6 秒，默认只读前 3 页。

## 收文

查收现在有两套实现，共用同一份 `config.json`、`downloaded_ids.json`、文件命名和 `fetch_docs.lock`：

- `specialty/shouwen/fetch.py`：harness 内实现，登录、翻页、取详情、下载、去重、写状态，默认走这套；
- `fetch_docs.py`：原来那份，定时任务继续用，`fetch --legacy` 可回退。

数据目录在 `specialty/shouwen/settings.json`，也可以用 `--home` 或 `SHOUWEN_HOME` 覆盖。

```powershell
python specialty/shouwen/shouwen.py status
python specialty/shouwen/shouwen.py digest --format md
python specialty/shouwen/shouwen.py provincial --days 7
python specialty/shouwen/shouwen.py fetch --probe        # 只登录、翻页、计数，不下载
python specialty/shouwen/shouwen.py fetch --manual       # 真查收，和定时任务互斥
python specialty/shouwen/shouwen.py fetch --manual --no-push   # 不发通知、不推微信
python specialty/shouwen/shouwen.py fetch --legacy       # 回退到原脚本
python specialty/shouwen/shouwen.py config show          # 密码、webhook 打码
python specialty/shouwen/shouwen.py config check         # 只校验必填项和取值范围
python specialty/shouwen/shouwen.py config set workdays=1-5 lookback_days=7 --dry-run
python specialty/shouwen/shouwen.py doctor               # 目录可写、配置、状态、锁、上次错误
python specialty/shouwen/shouwen.py atrust --check       # 检测内网，掉线时开客户端并弹窗
python specialty/shouwen/shouwen.py watch --interval 900 # 前台定时查收，Ctrl+C 停止
```

`--probe` 和 `--dry-run` 不写文件、不动状态，适合先看窗口里有多少件。真查收会先抢 `fetch_docs.lock`，和定时任务互斥；状态写法和原脚本一致，两边交替跑不会重复收文。`status` 读 `_scanned`、`last_error.txt` 和锁文件。

`config set` 只改非口令字段（时段、工作日、回溯天数、微信开关等），写前做完整校验并备份成 `config.backup.json`；`oa_password`、`atrust_password`、`wecom_webhook` 这类字段直接拒绝，仍走原配置向导。

`watch` 在前台按间隔查收，遵守 `workdays` 和 `work_hour_*`；`--once` 只跑一轮，适合挂到计划任务或 `dsh` 的后台任务里。它和 `fetch` 用同一个锁和状态。

`atrust` 负责连通检测与登录提醒：内网不通时打开 aTrust 客户端并弹窗等待。`fetch` 和 `watch` 默认不弹模态框（agent 场景会卡住），失败时在错误里提示运行 `atrust`。

推送都在 harness 里：企微 webhook 在 `notify.py`，个人微信发群在 `wechat.py`（Windows UI 自动化，需已登录微信，非 Windows 或缺少 pywin32 时安静跳过）。

## 可选工具插件

仓库执行过 `pnpm install` 和 `pnpm run build` 之后，可以用：

```powershell
pnpm dsh web --patch ./specialty/gongwen/cordis.patch.yml
```

插件提供 `gongwen_scaffold`、`gongwen_lint`、`gongwen_facts`、`gongwen_review` 和 `gongwen_diff`，规则和命令行脚本相同。没构建之前，用上面的 `node` 和 `python` 命令即可。

## 屏幕画布（GUI 操作）

把一块显示器或一个窗口当成独立画布，一次只截一块，坐标在同一块里回算：

```powershell
python specialty/screen/screen.py list
python specialty/screen/screen.py capture --monitor 2 --out shot.png
python specialty/screen/screen.py capture --window "记事本" --out win.png
python specialty/screen/screen.py place --window "记事本" --monitor 2 --size 1200x800 --apply
python specialty/screen/screen.py click --window "记事本" --x 100 --y 120 --yes
```

`capture --window` 截的是客户区（去掉标题栏和边框），图片坐标加上客户区原点就是屏幕坐标，`click --x/--y` 用的就是图片坐标。`place` 默认只演练，`--apply` 才真的移窗口；`click` 默认只回显目标坐标，`--yes` 才点。

用第二块屏（本机 `1600x900 @ (1920,0)`）当 agent 专用画布时，先 `place --apply` 把目标程序摆过去，再截图；用户主屏不受影响。

## 图像操作画布（视觉）

给视觉模型用的截图与鼠标键盘工具，一次只看一个窗口/显示器：

```powershell
python specialty/vision/vision.py doctor
python specialty/vision/vision.py wait --virtual --timeout 5
python specialty/vision/vision.py shot --virtual --out shot.png --grid --ocr
python specialty/vision/vision.py click-text --shot shot.json --text "登录" --yes
python specialty/vision/vision.py click --shot shot.json --x 320 --y 180 --yes
python specialty/vision/vision.py click --shot shot.json --x 320 --y 180 --double --yes
python specialty/vision/vision.py click --shot shot.json --x 320 --y 180 --button right --yes
python specialty/vision/vision.py type --text "你好" --yes
python specialty/vision/vision.py key --combo ctrl+a --yes
python specialty/vision/vision.py scroll --shot shot.json --x 900 --y 500 --dy -3 --yes
python specialty/vision/vision.py choose-file --path "G:\图片\1.jpg" --yes
python specialty/vision/vision.py trace --tail 10
python specialty/vision/vision.py find --image shot.png --template icon.png
python specialty/vision/vision.py speed --virtual --frames 30
python specialty/vision/vision.py watch --virtual --seconds 5 --fps 10 --out-dir frames
python specialty/vision/vision.py ask --image shot.png --prompt "下一步点哪里？"
```

`shot` 先对干净画面做 OCR，再叠加坐标网格和文字框，同时写一份同名 `.json`，记录截图区域在屏幕上的位置和每个文字框的中心。窗口标题可能重名，`--hwnd` 按句柄精确截取；`screen.py list` 现在会显示每块屏的 DPI。`click`/`drag` 用图片坐标，按 `.json` 映射回屏幕，并检查窗口有没有挪动；跨屏拖动加 `--raw` 直接给屏幕绝对坐标。`click-text` 按 OCR 文字点，不用自己算坐标。

文件上传用 `choose-file`：找到 `#32770` 对话框，点输入框、全选、粘贴路径、回车；实测能让记事本打开指定文件。不要用 `SetWindowText` 改对话框——那样不触发校验，打开按钮不会亮。

稳定性相关的几个约定：动作前会重新截一块比对，画面变化超过阈值就拒绝，只有加 `--force` 才强制执行；动画界面先 `wait` 等稳定；`scroll` 可带 `--shot --x --y` 先定位再滚；`doctor` 自检采集、OCR、画布；每个动作写进 `specialty/vision/traces/YYYYMMDD.jsonl`，`trace` 可回看。所有会动鼠标键盘的命令默认只演练，加 `--yes` 才执行。

`speed` 测截图帧率（本机 1920×1080 用 mss 约 30fps）；`watch` 按帧率观察变化，只保存变动帧，用于动画和游戏；`ask` 把截图交给本地 Ollama 视觉模型。

本机已装 `qwen2.5vl:3b`（2.16GB，全量在 GPU）：冷启动约 100 秒，热推理 0.7 秒。它能描述画面、判断页面类型，但**坐标接地不可靠**——实测让它在 1920×1080 上找地址栏，给的是页面中部的坐标。所以定位仍用 OCR 文字框或 `click-text`，模型只负责“下一步做什么”这类判断。

## 虚拟屏（常驻画布）

```powershell
python specialty/virtualscreen/virtualscreen.py ensure
python specialty/virtualscreen/virtualscreen.py count
python specialty/virtualscreen/virtualscreen.py set-count 2 --apply
python specialty/virtualscreen/virtualscreen.py canvas --index 2
python specialty/screen/screen.py place --window "<程序>" --virtual --virtual-index 2 --maximize --apply
python specialty/vision/vision.py shot --virtual --virtual-index 2 --out shot.png
```

`ensure` 幂等：已启用直接返回 `ready`；没扩展就自动 `DisplaySwitch /extend`；驱动在但没激活、或完全没驱动时，给出对应的管理员命令（`--install` 可触发 UAC）。`canvas` 给画布编号和矩形；`--virtual` 让 `screen`/`vision` 自动解析编号，不用记是第几块屏。

`count` 报告“配置了几块 / 实际激活几块”；`set-count N` 改 VDD 配置（最多 4 块），`--apply` 会尝试重启显示设备——**重启设备要管理员**，没有权限时命令会把要执行的 `pnputil` 原样打出来；`--elevate` 弹一次 UAC，`--helper` 走已安装的 SYSTEM 小助手（零 UAC，本机已验证），`--ask` 让桌宠弹气泡向人求授权。`ensure --monitors N` 是“不够就自动补到 N 块”。改完数量后用 `--virtual-index N` 选第 N 块画布。

`status` 标出每块适配器是虚拟还是物理、有没有启用、挂了几块监视器；`set` 改虚拟屏分辨率。

细节和失败后的备选路线见 [virtualscreen/README.md](virtualscreen/README.md)。

## 测试

依赖：Python 3.10 以上，`python-docx`、PyMuPDF（`fitz`）；扫描件 OCR 另需 `rapidocr_onnxruntime`。缺 OCR 时自动退回文件名，不影响生成。

```powershell
python specialty/gongwen/test_docx.py
python specialty/gongwen/test_forward.py
python specialty/shouwen/test_core.py
python specialty/shouwen/test_fetch.py
python specialty/shouwen/test_shouwen.py
python specialty/shouwen/test_atrust.py
python specialty/screen/test_screen.py
python specialty/browser/test_browser.py
python specialty/vision/test_vision.py
python specialty/virtualscreen/test_virtualscreen.py
node specialty/gongwen/self-check.mjs
```

这些只读临时目录和生成的 docx，`test_fetch` 用假 OA 客户端，不联网。

## 不要做的事

不编发文字号、机关、日期和印章。用户没给出来源的文件，稿子里标「待核实」。

收文这边：不打印 `config.json` 里的账号密码，不删改收文文件，不改 `downloaded_ids.json`；内网不通时报告 `last_error.txt` 的原文。
