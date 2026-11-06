const STATUTORY = ['通知', '请示', '报告', '函', '纪要', '批复']
const OFFICE = ['方案', '简报', '拟办', '讲话', '总结', '督办', '办文']
const KINDS = [...STATUTORY, ...OFFICE]

const ENDINGS = {
  通知: '请遵照执行。',
  请示: '妥否，请批示。',
  报告: '特此报告。',
  函: '请予函复。',
  纪要: '请按纪要分工落实。',
  批复: '请遵照执行。',
}

const OFFICE_LABELS = {
  方案: ['目标', '范围', '步骤', '负责人', '时限'],
  简报: ['导语', '数据来源'],
  拟办: ['来文', '拟办意见', '承办人'],
  讲话: ['场合', '听众'],
  总结: ['完成情况', '问题', '下一步', '负责人', '时限'],
  督办: ['督办事项', '来源', '承办', '时限', '完成标志'],
  办文: ['来文机关', '来文标题', '来文文号', '拟办意见', '承办', '反馈'],
}

export function listKinds() {
  return KINDS.slice()
}

function heading(kind, title) {
  if (title?.trim()) return title.trim()
  if (kind === '纪要') return '关于【事由】的会议纪要'
  if (kind === '方案') return '【事由】实施方案'
  if (kind === '简报') return '【事由】简报'
  if (kind === '拟办') return '【来文标题】拟办意见'
  if (kind === '讲话') return '在【场合】上的讲话提纲'
  if (kind === '总结') return '【事由】工作总结'
  if (kind === '督办') return '【事项】督办单'
  if (kind === '办文') return '【来文标题】办文单'
  return `关于【事由】的${kind}`
}

function officeBody(kind, title) {
  const lines = [heading(kind, title), '']
  if (kind === '方案') {
    lines.push(
      '一、目标',
      '【要达成的结果，写成可以核对的句子。】',
      '',
      '二、范围',
      '做：【待填】',
      '不做：【待填】',
      '',
      '三、步骤',
      '1. 【步骤】。负责人：【待填】。完成时限：【待填】。',
      '',
      '四、风险',
      '【风险、影响、谁处理。没有就写待核实。】',
    )
  } else if (kind === '简报') {
    lines.push(
      '导语：【何时、何地、何事、结果。只写已核对的事实。】',
      '',
      '【主体。数据和引语都要能指回来源。】',
      '',
      '数据来源：【待填】',
    )
  } else if (kind === '拟办') {
    lines.push(
      '来文标题：【待填】',
      '来文文号：【用户没给就写“无”】',
      '收文日期：【待填】',
      '',
      '拟办意见：',
      '1. 建议【承办处室】于【时限】前【动作】。',
      '',
      '承办人：【待填】',
    )
  } else if (kind === '总结') {
    lines.push(
      '一、完成情况',
      '【只写已经发生的事，带用户给出的日期。没做完的写进问题，不要写成完成。】',
      '',
      '二、问题',
      '【问题。没有就写待核实。】',
      '',
      '三、下一步',
      '1. 【事项】。负责人：【待填】。完成时限：【待填】。',
    )
  } else if (kind === '督办') {
    lines.push(
      '督办事项：【待填】',
      '来源：【会议纪要或批示。用户没给就写待核实。】',
      '承办单位：【待填】',
      '完成时限：【待填】',
      '完成标志：【怎样算办完】',
    )
  } else if (kind === '办文') {
    lines.push(
      '来文机关：【待填】',
      '来文标题：【待填】',
      '来文文号：【用户没给就写无】',
      '收文日期：【待填】',
      '',
      '拟办意见：',
      '1. 建议【承办处室】于【时限】前【动作】。',
      '',
      '承办处室：【待填】',
      '反馈时限：【待填】',
      '办理结果：【未反馈前不要写成已办结】',
    )
  } else {
    lines.push(
      '场合：【待填】',
      '听众：【待填】',
      '',
      '开头：【这次要解决什么。一两句。】',
      '一、【第一点】',
      '二、【第二点】',
      '结尾：【要求写到人。不替领导编表态。】',
    )
  }
  return lines
}

export function scaffold({ kind, title, recipient }) {
  if (!KINDS.includes(kind)) {
    return { ok: false, text: `文种必须是：${KINDS.join('、')}` }
  }
  if (OFFICE.includes(kind)) {
    return { ok: true, text: officeBody(kind, title).join('\n') }
  }
  const to = recipient?.trim() || '【主送机关】'
  const lines = [heading(kind, title), '', kind === '纪要' ? '时间：【待填】' : `${to}：`]
  if (kind === '纪要') {
    lines.push('地点：【待填】', '主持人：【待填】', '出席：【待填】', '列席：【待填】', '', '议定事项：', '1. 【事项】。负责人：【待填】。完成时限：【待填】。')
  } else if (kind === '批复') {
    lines.push('', '《【来文标题】》（【来文文号，无则删除本括号】）收悉。', '', '【同意 / 原则同意 / 不同意】。【执行要求】。', '', ENDINGS[kind])
  } else {
    lines.push('', '【缘由：为什么现在办这件事。事实只写已核对的内容。】', '', '【事项】', '1. 【谁，在何时前，做什么】。', '', ENDINGS[kind])
  }
  lines.push('', '【发文机关，待办文系统填写】', '【成文日期，待办文系统填写】')
  return { ok: true, text: lines.join('\n') }
}

function requireLabels(body, labels, issues) {
  for (const label of labels) {
    if (!body.includes(label)) issues.push(`缺少「${label}」`)
  }
}

function commonNotes(kind, body, notes) {
  if (/附件/.test(body) && !/附件[:：]\s*\S/.test(body)) {
    notes.push('写了「附件」，但没有「附件：」后面的名称')
  }
  if (kind === '请示') {
    const asks = body.match(/拟请|请予批准|请批准|一并请示/g) || []
    if (asks.length > 1) notes.push('请示里有多处请求批准，确认是不是一文一事')
  }
}

export function lint(kind, text) {
  const issues = []
  const notes = []
  if (!KINDS.includes(kind)) {
    return { ok: false, issues: [`文种必须是：${KINDS.join('、')}`], notes: [] }
  }
  const body = String(text || '').replace(/^\uFEFF/, '').trim()
  if (!body) return { ok: false, issues: ['草稿是空的'], notes: [] }

  if (OFFICE.includes(kind)) {
    requireLabels(body, OFFICE_LABELS[kind], issues)
    if (kind === '讲话' && !/一、|1[.．]/.test(body)) issues.push('讲话提纲没有分点')
    if (kind === '简报' && /请批示|请批复/.test(body)) notes.push('简报里出现了请示结语')
    if (/待核实|待填|待办文系统填写/.test(body)) notes.push('稿中仍有待填或待核实标记，送审前要逐条消掉或留给用户')
    commonNotes(kind, body, notes)
    return { ok: issues.length === 0, issues, notes }
  }

  if (!body.includes(kind === '纪要' ? '纪要' : kind)) {
    issues.push(`标题或正文里没有文种「${kind === '纪要' ? '纪要' : kind}」`)
  }
  if (kind === '纪要') {
    requireLabels(body, ['时间', '地点', '出席', '议定'], issues)
  } else if (!/^.*[：:]\s*$/m.test(body)) {
    issues.push('没有主送行（机关名加冒号）')
  } else if (/^抄送/m.test(body) && /^抄送.*[：:]\s*$/m.test((body.match(/^.*[：:]\s*$/m) || [''])[0])) {
    notes.push('第一处机关行是抄送。主送应单独写在前面')
  }
  if (kind !== '纪要' && !/\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日|待办文系统填写/.test(body)) {
    issues.push('没有成文日期，也没有「待办文系统填写」')
  }
  if (/[！!？?]/.test(body)) notes.push('正文里有问号或感叹号，确认法定公文是否保留')
  if (kind === '请示') {
    const recipientLine = (body.match(/^.*[：:]\s*$/m) || [''])[0]
    if (/[、,，]/.test(recipientLine)) notes.push('请示的主送行里有多个机关，确认是不是只报一个主送')
  }
  if (kind === '请示' && !/请批示|请批复/.test(body)) issues.push('请示缺少「请批示」或「请批复」')
  if (kind === '请示' && /特此报告|报告如下/.test(body)) notes.push('请示里出现了报告用语，确认没有把两件公文写在一起')
  if (kind === '报告' && /请批示|请批复/.test(body)) notes.push('报告里出现了请示结语。报告不请求批复')
  if (kind === '函' && !/函复|函告|商请|此函/.test(body)) notes.push('函的结尾没有「请予函复」「函告」「商请」或「此函」')
  if (kind === '批复' && !/收悉/.test(body)) issues.push('批复没有引述来文（常见写法是先写来文标题再写「收悉」）')
  if (/【[^】]{0,8}\d{4}〕\d+号】/.test(body)) notes.push('稿里有占位文号。正式文号只能换成用户给出的编号')
  if (/待核实|待填|待办文系统填写/.test(body)) notes.push('稿中仍有待填或待核实标记，送审前要逐条消掉或留给用户')
  commonNotes(kind, body, notes)
  return { ok: issues.length === 0, issues, notes }
}

export function formatReview(kind, text) {
  return `${formatLint(lint(kind, text))}\n\n${formatFacts(facts(text))}`
}

const FACT_PATTERNS = [
  ['文号', /[\u4e00-\u9fffA-Za-z]{1,12}[〔\[]\d{4}[〕\]]\s*\d{1,4}\s*号/g],
  ['日期', /\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日/g],
  ['金额', /\d+(?:\.\d+)?\s*(?:万元|亿元|元)/g],
  ['待填', /【[^】\n]{0,40}】/g],
]

export function facts(text) {
  const body = String(text || '').replace(/^\uFEFF/, '')
  const groups = []
  for (const [label, re] of FACT_PATTERNS) {
    const found = [...body.matchAll(re)].map((match) => {
      const text = match[0].replace(/\s+/g, '')
      if (label !== '文号') return text
      return text.replace(/^(?:根据|依据|按照|遵照)/, '')
    })
    const unique = [...new Set(found)]
    if (unique.length) groups.push({ label, items: unique })
  }
  return groups
}

function factMap(text) {
  const grouped = new Map()
  for (const group of facts(text)) grouped.set(group.label, group.items)
  return grouped
}

export function diffFacts(left, right) {
  const a = factMap(left)
  const b = factMap(right)
  const lines = []
  for (const label of ['文号', '日期', '金额']) {
    const leftItems = new Set(a.get(label) || [])
    const rightItems = new Set(b.get(label) || [])
    const onlyLeft = [...leftItems].filter((item) => !rightItems.has(item))
    const onlyRight = [...rightItems].filter((item) => !leftItems.has(item))
    if (!onlyLeft.length && !onlyRight.length) continue
    lines.push(`${label}：`)
    for (const item of onlyLeft) lines.push(`- 只在第一份：${item}`)
    for (const item of onlyRight) lines.push(`- 只在第二份：${item}`)
  }
  if (!lines.length) return '两份草稿抽出的文号、日期、金额一致。'
  return ['两份草稿抽出的事实不一致：', ...lines].join('\n')
}

export function formatFacts(groups) {
  if (!groups.length) return '没有抽出文号、日期、金额或待填项。'
  const lines = ['下列内容必须能指回用户材料：']
  for (const group of groups) {
    lines.push(`${group.label}：`)
    for (const item of group.items) lines.push(`- ${item}`)
  }
  return lines.join('\n')
}

export function formatLint(result) {
  if (!result.ok && result.issues.length && result.notes.length === 0 && result.issues[0].startsWith('文种')) {
    return result.issues[0]
  }
  const lines = [`结果：${result.ok ? '结构项通过' : '有缺项'}`]
  if (result.issues.length) {
    lines.push('缺项：')
    for (const item of result.issues) lines.push(`- ${item}`)
  } else {
    lines.push('缺项：无')
  }
  if (result.notes.length) {
    lines.push('要核对：')
    for (const item of result.notes) lines.push(`- ${item}`)
  }
  return lines.join('\n')
}
