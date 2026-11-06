# DeepSeek Harness · 公务员办公版

一套只服务公文办公的工作区：收文、拟办、转发、材料、会议纪要、桌面操作，全部本地留痕。不含社交发布、多账号运营、桌宠和语音。

## 怎么打开

1. 打开 **DeepSeek Harness**；
2. 把工作区/工作目录切到 `G:\dsh-gongwu`（或在启动器里选择这个文件夹）；
3. 直接说需求，技能会自动匹配。

> 这台机器上的桌面版 DSH 已装好；本目录不包含 DSH 源码，只包含办公能力和技能。

## 常用说法

| 你说 | 它会 |
|---|---|
| 查一下今天收了什么文件 | 列收文清单、汇总、标待办 |
| 把这份省文件转给各县区 | 抽标题文号，套本单位版式生成转发通知 docx |
| 写一份关于开展…的通知 | 按公文格式起草，检查文种、主送、结语 |
| 帮我核一下这份稿子 | 按公文规范挑错，标事实缺口 |
| 把会议材料整理成纪要 | 结论先行，列议定事项和责任单位 |
| 给这份请示写依据段 | 只引用能核对的文件，查不到标待核实 |
| 把浏览器放第二块虚拟屏 | 摆窗口、截图、按文字点击 |

## 能做什么

- **收文**：待签收、按日清单、拟办素材、承办台账；
- **公文**：通知、请示、报告、函、纪要、批复的起草、改写、审核、转发；
- **事务文书**：方案、简报、拟办意见、讲话提纲、工作总结、督办单；
- **桌面**：截图 OCR、按文字点击、输入、等文字、窗口摆位、虚拟屏；
- **留痕**：每件活有 session 目录，步骤、产出、报告都能回看。

## 重点文库（本人写法）

从 `G:\办公\办公` 和 `G:\高技术` 里选出 45 篇本人常写的公文，整理了版式、开头结尾、段长和高频表达：

```powershell
python specialty\gongwen\key_lib.py style
python specialty\gongwen\key_lib.py brief --kind 通知
python specialty\gongwen\key_lib.py match --kind 报告 --keyword 场景汇
```

写之前先看 `style`（平均段长、常用开头结尾）和 `brief`（版式、篇目样例），再动笔。

## 公文案例库

本机另有 41 篇通用高质量公文，按文种抽好了版式和结构：

```powershell
python specialty\gongwen\case_lib.py brief --kind 通知
python specialty\gongwen\case_lib.py match --kind 报告 --keyword 场景汇
python specialty\gongwen\case_lib.py show <id>
```

转发省文件用 `--kind 转发通知`（6 篇）：标题方正小标宋 22pt、正文仿宋_GB2312 16pt、首行缩进 32pt、页边距 3.5/3.5/2.7/2.7。两个库都只存路径、版式和摘录，只在本地，不外传。

## 自检和测试

```powershell
python specialty\deliver\doctor.py
python specialty\gongwen\test_docx.py
python specialty\gongwen\test_forward.py
python specialty\shouwen\test_core.py
python specialty\shouwen\test_shouwen.py
python specialty\work\test_work.py
python specialty\vision\test_vision.py
python specialty\screen\test_screen.py
python specialty\virtualscreen\test_virtualscreen.py
```

## 边界

- 文号、机关、日期、签批只用你给的内容；
- 法规和文件先核对再引用，不编造；
- 删除只进回收站；
- 发送、报批、覆盖前会停下来问你；
- 涉密材料不上传外网，模型调用按单位规定执行。

## 和“开发版”的区别

| | 公务员办公版 | 开发版 |
|---|---|---|
| 技能 | 公文/收文/Office/桌面/留痕 | 全部，含运营、桌宠、语音 |
| 代码 | 只保留办公模块 | 全仓库 + 插件 |
| 用途 | 日常办公 | 开发、演示、交付 |

更细的操作说明见 `使用说明.txt` 和 `AGENTS.md`。
