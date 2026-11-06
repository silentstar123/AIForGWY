# 使用手册（日常怎么用）

这套东西不是新 App，是在 DeepSeek Harness 上加了一层“办公/桌面/运营”的能力。用法还是**用中文说需求**，它自己挑技能和工具。

## 一、打开

| 要什么 | 怎么做 |
|---|---|
| 主界面 | 打开 DeepSeek Harness（本机 Web GUI：<http://127.0.0.1:50125>） |
| 桌宠 | 双击 `G:\deepseek-harness\游戏陪伴\启动大肥鱼.bat` |
| 自检 | `python specialty/deliver/doctor.py` |

## 二、日常办公（最常用）

直接在对话框里说，例如：

| 你说 | 它会 |
|---|---|
| 查一下今天收了什么文件 | 跑 `shouwen`，列清单/汇总 |
| 把 20261026 7 号文转给各县区 | 抽标题文号，生成转发通知 docx |
| 写一份关于开展…的通知 | 按公文格式起草（标题、主送、正文、版记） |
| 把这份报告挪到桌面 | 文件操作，删除只进回收站 |
| 帮我制定下周工作计划 | 读最近收文，出排期表并落成 md |

产出的文件在 `specialty/work/sessions/<时间>/`，每次都有工作记录。

## 三、桌面与虚拟屏

| 你说 | 它会 |
|---|---|
| 开两块虚拟屏 | `set-count 2 --apply --helper`，约一分钟，无 UAC |
| 把浏览器放第二块屏 | `place --virtual --virtual-index 2` |
| 把虚拟屏收成一块 | `set-count 1 --apply --helper` |
| 截图/操作前让桌宠隐身 | `pet.py hide`，完事 `show` |

手动命令：

```powershell
python specialty/virtualscreen/virtualscreen.py count
python specialty/virtualscreen/virtualscreen.py set-count 2 --apply --helper
python specialty/screen/screen.py place --window "记事本" --virtual --virtual-index 1 --maximize --apply
python specialty/pet/pet.py hide
```

## 四、桌宠怎么用

- 双击她：聊天；喊「大肥鱼」「肥鱼」：语音对话（模型已装）；
- 对她说「转给 harness：汇总今天收文」：她把活写进队列；
- 托盘右键：「看一眼屏幕」「隐身/现身」「设置」「退出」；
- 命令行：`python specialty/pet/pet.py state|bubble|hide|show|tasks`。

## 五、发小红书（演示过的流程）

直接说：

> 在小红书发一条：deepseek harness还是很有趣

它会：移到虚拟屏 → 打开发布页 → 上传图文 → 填标题正文 → **停在发布前问你** → 你确认后才发。

评论：

> 去刚发的帖子下面评论「好」

## 六、多账号运营

```powershell
python specialty/ops/ops.py account add --name "小红书-01" --daily 2
python specialty/ops/ops.py task add --account "小红书-01" --kind post
python specialty/ops/ops.py plan --limit 4 --screens 2
python specialty/ops/ops.py run --limit 4 --screens 2            # 演练
python specialty/ops/ops.py run --limit 4 --screens 2 --live     # 真开浏览器
```

4 块虚拟屏只用来监看；其余账号按批无头跑。

## 七、模型与 Key

- Key 在各自设置里填：Harness 用界面设置；桌宠右键→设置；
- 办事/视觉用 `deepseek-v4-flash`；桌宠闲聊用 `deepseek-flash`；
- 换模型：设置里改，或 `config.json` 的 `model`（桌宠）/ Harness 的模型选择。

## 八、注意

1. 发布、删除、覆盖这类动作都要你点头；
2. 虚拟屏上限 4 块，改数量等约 1 分钟；
3. 平台批量自动化有封号风险，账号和内容自己把关；
4. 现场交付先跑 `deliver/doctor.py`，再演示 `deliver/demo.ps1`。

---

更细的清单：`specialty/README.md`；现场交付：`specialty/deliver/README.md`；运营台：`specialty/ops/README.md`。
