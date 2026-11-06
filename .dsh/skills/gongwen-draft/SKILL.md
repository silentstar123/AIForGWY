---
name: gongwen-draft
description: 按常见公文体例起草通知、请示、报告、函、纪要、批复。用户要拟稿、改写或套公文格式时使用。
whenToUse: 用户要起草、续写或按体例改写通知、请示、报告、函、纪要、批复时。
---

# 公文起草

先定文种，再写正文。一文一事。看不准时先确认两件事：要不要对方批复，双方有没有隶属关系。

## 边界

- 发文字号、发文机关标志、成文日期、签发人、印章只用用户已经给出的内容。缺了就写「待办文系统填写」。
- 正文里的政策、数据、文号，用户没给出来源的，标成「待核实」，不要补一个看起来像真的文号或条款号。
- 交稿是可编辑的正文草稿，不做成可直接套红印发的成品，不模仿印章。

## 步骤

0. 找参照：先看重点文库 `python specialty/gongwen/key_lib.py style` 和 `brief --kind <文种>`，学本人的段长、开头结尾和高频表达；重点文库没有的文种，再看 `case_lib.py brief --kind <文种>`。要同类题材的篇目，用 `match --kind <文种> --keyword <关键词>`。案例库只读本地文件，路径和摘录不要外传。
1. 从材料里抽出文种、标题、主送、事项、时限、承办人。缺了就问，不要猜机关名称。
2. 取骨架：`node specialty/gongwen/check.mjs scaffold <文种> --title "标题" --recipient "主送"`
3. 只用用户提供的事实填空。缘由写为什么现在办，事项写谁在何时前做什么，要求写能核对的结果。
4. 自检：`node specialty/gongwen/check.mjs lint <文种> --file <草稿.md>`
5. 再抽事实：`node specialty/gongwen/check.mjs facts --file <草稿.md>`。列出的文号、日期、金额都要能指回用户材料。
6. 脚本报出的缺项，能从材料补上的就补；不能补的列为待用户确认。
7. 要交 Word 时，按 `specialty/gongwen/format.json` 的版式生成：先 `python specialty/gongwen/gongwen_docx.py template <文种> --out spec.json`，填好再 `python specialty/gongwen/gongwen_docx.py build spec.json --out <文件名>.docx`。转发省里文件用 `kind: 转发通知`，给 `sources`、`sourceOrgan`、`purpose`，标题和缘由段会自动生成。新样本先用 `inspect` 核对字号、字体、行距；多份样本可以用 `learn` 统计，不一致就改 `format.json`，不要改脚本。

方案、简报、拟办、讲话用 `office-draft`，不要塞进法定文种。

文种用这六个字之一：通知、请示、报告、函、纪要、批复。

## 案例库

本机 `specialty/gongwen/cases/` 里有从高质量公文里抽出的版式和篇目：

```powershell
python specialty/gongwen/case_lib.py brief --kind 通知
python specialty/gongwen/case_lib.py match --kind 报告 --keyword 场景汇
python specialty/gongwen/case_lib.py show <id>
```

写之前先看 `brief`，按里面的标题字体字号、正文字体字号、首行缩进、页边距来；结构参考 `samples` 里的标题层级。案例库不含全文，只含前 300 字和结构；引用事实时回到原文核对。

## 转发省文件

先看案例库里的转发通知：`python specialty/gongwen/case_lib.py brief --kind 转发通知`。库里 6 篇，标题统一是「关于转发省发改委《……》的通知」，正文先写省文件下发文号，再写「现转发给你们，请……」，附件列省文件，落款和日期右对齐。

**转发通知正文只写一段话：缘由 + 现转发给你们，请……。不要把要求拆成「一、二、三」；需要提要求就接在同一段里。** `gongwen_docx.build` 遇到转发通知里的一、二会直接报错，确实要分条才加 `allowSections: true`。

收到省文件要向下转发时，不要手拼标题和缘由段：

```powershell
python specialty/shouwen/shouwen.py provincial --days 7
python specialty/gongwen/forward.py --source "<省文件>" --out-dir .\转发包 --document-no "<本市文号>" --source-number "<来文文号>" --recipients "<主送>" --doc-date "<成文日期>" --purpose "<一句话目的>" --requirement "<请对方做什么：围绕……于X月X日前反馈>" --contact "<联系人>" --contact-phone "<电话>" --email "<邮箱>"
```

`forward.py` 从省文件抽标题、来文文号和发文机关（docx 直接读；PDF 有文字层就读文字层，扫描件用 OCR 识别前 3 页；OCR 不可用时标题取文件名，文号用 `--source-number` 补）；呈办笺、收文办理单的栏目和批示行会自动过滤；识别出"河北省发展和改革委员会"时标题/正文自动用惯用简称"省发改委"，可用 `--source-organ` 覆盖。`--contact/--contact-phone/--email` 生成落款前的联系人、邮箱行（右对齐），和转发通知末尾的惯例一致。产出 `转发通知.docx`、附件副本、`转发通知.spec.json` 和 `转发说明.md`。标题和「……现转发给你们，请认真贯彻执行。」由脚本拼；文号、成文日期、主送只用给定的，识别不到的写「待核实」。OCR 结果只是线索，`转发说明.md` 里的「待核对」要逐条看。超长标题（40 字以上）不硬断行，交回 Word 自然换行；要手排可在 spec 里给 `titleLines`。

## 各文种怎么写

- 通知：缘由、事项、执行要求。事项用序号，每条有承办对象。
- 请示：写给有权批准的上级。理由、事项分开。结尾用「妥否，请批示。」不要同时写成报告。
- 报告：汇报已经发生或正在发生的情况，不夹带请求批复。结尾用「特此报告。」
- 函：平级或不相隶属机关之间商洽、询问、答复。语气对等。结尾用「请予函复。」「请予支持。」或「特此函复。」
- 纪要：会议名称、时间、地点、主持人、出席写在前面。议定事项每条写负责人和完成时限。
- 批复：先引用户提供的来文标题和文号，再写同意、原则同意或不同意，以及要对方执行的要求。来文文号没有就空着。

## 标题

用「发文机关 + 关于……的 + 文种」。机关名用户没给时，标题里不要编一个。标题单行写、由 Word 自然换行，不手动断行；确需手排时在 spec 里给 `titleLines`。

## 机关称呼

正文叙述用简称：市级称「市发改委」，县（市、区）级称「县/区发改局」（如「广阳区发改局」）。全称（发展和改革委员会/发展和改革局）只保留在发文机关标志、落款和引用文件原标题里。
