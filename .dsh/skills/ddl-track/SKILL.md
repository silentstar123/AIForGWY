# ddl-track：DDL 任务台账

记录波洛每天要办的事：一次性的 deadline、常态性的周期工作。数据只存本机
`specialty/ddl/tasks.json`，不外传。

## 什么时候记

日常对话里波洛提到"要办某件事""X 号之前要交""每月几号要搞一下"时，随手记下来，
不要等专门吩咐。一条任务记一件事，标题用波洛自己的说法，短一点。

## 命令

```powershell
python specialty/ddl/ddl.py add "任务标题" --due 2026-11-09            # 一次性，截止日必填
python specialty/ddl/ddl.py add "任务标题" --recur 每月10号           # 周期：每月10号 / 每周一 / 每天 / 每年11月9日
python specialty/ddl/ddl.py add "任务标题" --due 2026-11-09 --note 还差4个科室
python specialty/ddl/ddl.py today                                     # 今天该办什么（含逾期和3天内临近）
python specialty/ddl/ddl.py list                                      # 全部任务
python specialty/ddl/ddl.py done t003                                 # 画勾；也可以用 list 里的序号
python specialty/ddl/ddl.py remove t003                               # 删除
```

## 规矩

1. 日期不清就问，不要猜："下周交"要确认到具体日期再记；
2. 周期任务的口径：每月 N 号、每周几、每天、每年几月几日，说不全就追问；
3. 画勾只认波洛亲口确认，不要替他勾；
4. 每天 10:00 有定时任务弹出对账（见工作区任务卡"每日 DDL 对账"），那次对话里
   波洛说"完成了"就直接 done，说新任务就直接 add；
5. tasks.json 只在本机用，不外传、不上 GitHub。

## 测试

```powershell
python specialty/ddl/test_ddl.py
```
