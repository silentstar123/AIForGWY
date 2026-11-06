# 工作台

把一件活拆成步骤、留痕、收尾出报告；有桌宠时开工/收工弹个气泡。

```powershell
python specialty/work/work.py start --title "处理今日收文"
python specialty/work/work.py step --note "查收今日文件" --artifact G:\...\清单.md
python specialty/work/work.py status
python specialty/work/work.py finish --summary "已收 6 件，转发出 1 份"
python specialty/work/work.py report
```

每次会话一个目录：`specialty/work/sessions/<时间戳>/session.json`，`report` 把标题、步骤、产出、截图排成一份 Markdown。`--no-pet` 关掉气泡。

## 用途

- 让 agent 像坐班的人一样：先知道要干什么，再做，做完给一份能看的交代；
- 长任务中途有记录，失败时知道停在哪一步；
- 产出文件路径写进记录，用户可以直接打开。

## 边界

- 会话目录只是记录，不是数据备份；真正的产出留在原位置。
- 气泡是可选装饰，桌宠没开就静默跳过。
