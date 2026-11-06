import { scaffold, lint, facts, formatFacts, formatReview, diffFacts } from './logic.mjs'

function expect(cond, message) {
  if (!cond) throw new Error(message)
}

const plan = scaffold({ kind: '方案', title: '统计工作实施方案' })
expect(plan.ok && plan.text.includes('目标') && plan.text.includes('步骤'), '方案骨架缺目标或步骤')
const planLint = lint('方案', plan.text.replace('二、范围\n做：【待填】\n不做：【待填】\n\n', ''))
expect(!planLint.ok && planLint.issues.some((item) => item.includes('范围')), '删掉范围后应该报缺项')

const brief = lint('简报', '导语：今日完成培训。\n数据来源：签到表。\n')
expect(brief.ok, `简报应通过：${brief.issues.join('、')}`)

const request = scaffold({ kind: '请示', title: '关于购置办公设备的请示', recipient: '市局' })
expect(lint('请示', request.text).ok, '请示骨架的结构项应通过')

const extracted = formatFacts(facts('依据国发〔2024〕1号，于2024年5月1日安排3万元。还有【待填】。'))
expect(extracted.includes('国发〔2024〕1号'), '没抽出文号')
expect(extracted.includes('2024年5月1日'), '没抽出日期')
expect(extracted.includes('3万元'), '没抽出金额')
expect(extracted.includes('【待填】'), '没抽出待填')

const summary = scaffold({ kind: '总结', title: '统计工作总结' })
expect(summary.ok && lint('总结', summary.text).ok, '总结骨架的结构项应通过')
const chase = scaffold({ kind: '督办', title: '购置设备督办单' })
expect(chase.text.includes('完成标志') && lint('督办', chase.text).ok, '督办骨架的结构项应通过')

const doubled = formatReview('请示', `${request.text}\n拟请批准购置打印机。\n请批准增加预算。\n见附件。\n`)
expect(doubled.includes('一文一事'), '多处请求批准应提示一文一事')
expect(doubled.includes('附件'), '写了附件但没有名称时应提示')
const copied = lint('通知', '关于开会的通知\n\n抄送：\n\n请遵照执行。\n待办文系统填写\n')
expect(copied.notes.some((item) => item.includes('抄送')), '第一处机关行是抄送时应提示')

const slip = scaffold({ kind: '办文', title: '购置设备办文单' })
expect(slip.text.includes('办理结果') && lint('办文', slip.text).ok, '办文单骨架的结构项应通过')
const loud = lint('通知', '关于开会的通知\n\n办公室：\n\n请准时参加！\n待办文系统填写\n')
expect(loud.notes.some((item) => item.includes('感叹号')), '感叹号应提示')
const many = lint('请示', '关于购置的请示\n\n市局、县局：\n\n妥否，请批示。\n待办文系统填写\n')
expect(many.notes.some((item) => item.includes('一个主送')), '多个主送应提示')
const compared = diffFacts('依据国发〔2024〕1号，安排3万元。', '依据国发〔2024〕2号，安排3万元。')
expect(compared.includes('只在第一份：国发〔2024〕1号'), '应列出第一份独有的文号')
expect(compared.includes('只在第二份：国发〔2024〕2号'), '应列出第二份独有的文号')
expect(!compared.includes('3万元'), '相同金额不应列出')

process.stdout.write('gongwen self-check ok\n')
