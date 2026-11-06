# 公务员办公版

这个工作区只做公务员日常办公：收文、公文起草与审核、材料整理、会议纪要、桌面操作与留痕。**不包含**社交平台发布、多账号运营、桌宠和语音模块。

## 能做

- **收文**：查待签收、按日汇总清单、给拟办准备材料（`specialty/shouwen`）；
- **公文**：通知/请示/报告/函/纪要/批复起草与审核，套版式生成 docx（`specialty/gongwen`）；
- **事务文书**：方案、简报、拟办、讲话提纲、总结、督办单（`office-draft` 技能）；
- **依据**：写根据段、核对文件名/文号/条款，不编造（`policy-basis`）；
- **会议**：材料整理成结论先行提纲或纪要底稿（`meeting-brief`）；
- **桌面**：截图 OCR、按文字点击、摆窗口、虚拟屏（`gui-operator`、`virtual-screen`）；
- **留痕**：每件活有步骤、产出、报告（`specialty/work`）。

## 规矩

1. 发文字号、发文机关、成文日期、签批只使用用户给出的内容，不猜、不补；
2. 法规、文件、文号必须可核对，查不到就标“待核实”；
3. 删除只进回收站，不做永久删除；
4. 发送、发布、覆盖、报批前停下来等人确认；
5. 不收发与工作无关的社交平台内容，不做多账号运营；
6. 涉密材料不上传外网；Key、密码只留本机。

## 案例库

`specialty/gongwen/cases/` 存着从本机高质量公文里抽出的版式和篇目，写之前先看：

```powershell
python specialty\gongwen\case_lib.py brief --kind 通知
python specialty\gongwen\case_lib.py match --kind 报告 --keyword <关键词>
```

标题字体字号、正文字体字号、首行缩进、页边距都按 `brief` 返回的来；结构参考参考篇目的标题层级。案例库含本机路径和摘录，只在本地用，不外传。

## 目录

```
.dsh/skills/          办公技能（公文、收文、Office、桌面、留痕）
specialty/gongwen/    公文生成、格式检查、转发
specialty/shouwen/    收文查收、清单、通知
specialty/work/       工作台：步骤、产出、报告
specialty/screen/     屏幕/窗口枚举、截图、摆位
specialty/vision/     截图 OCR、点击、输入、等待
specialty/virtualscreen/ 虚拟屏开关（需要本机已装 VDD 和 helper）
specialty/deliver/doctor.py  自检
```

## 验证

```powershell
python specialty\deliver\doctor.py
python specialty\gongwen\test_docx.py
python specialty\gongwen\test_forward.py
python specialty\shouwen\test_core.py
python specialty\shouwen\test_shouwen.py
python specialty\work\test_work.py
```
