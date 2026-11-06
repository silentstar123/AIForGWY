import { defineTool } from '@deepseek-ai/dsh-tools'
import { scaffold, lint, formatLint, facts, formatFacts, formatReview, diffFacts, listKinds } from './logic.mjs'

export const name = 'gongwen'
export const inject = ['tools']

const kindDescription = `文种，必须是：${listKinds().join('、')}`

export function apply(ctx) {
  ctx.tools.register(defineTool({
    name: 'gongwen_scaffold',
    description: '生成通知、请示、报告、函、纪要、批复、方案、简报、拟办或讲话提纲的骨架。文号、机关和日期留空，不编造。',
    parameters: {
      kind: { type: 'string', required: true, description: kindDescription },
      title: { type: 'string', required: false, description: '公文标题。不填则按文种生成带【事由】的标题。' },
      recipient: { type: 'string', required: false, description: '主送机关。不填则保留占位。' },
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(args) {
      return scaffold(args).text
    },
  }))

  ctx.tools.register(defineTool({
    name: 'gongwen_lint',
    description: '检查公文草稿缺了哪些结构项。不判断事实是否真实，只查文种、主送、结语和日期这些体例位置。',
    parameters: {
      kind: { type: 'string', required: true, description: kindDescription },
      text: { type: 'string', required: true, description: '完整草稿。' },
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(args) {
      return formatLint(lint(args.kind, args.text))
    },
  }))

  ctx.tools.register(defineTool({
    name: 'gongwen_facts',
    description: '从草稿里抽出文号、日期、金额和待填项，供核对来源。不判断这些内容真假。',
    parameters: {
      text: { type: 'string', required: true, description: '完整草稿。' },
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(args) {
      return formatFacts(facts(args.text))
    },
  }))

  ctx.tools.register(defineTool({
    name: 'gongwen_review',
    description: '一次给出结构缺项和文号、日期、金额、待填项。不判断事实真假，也不代替签发。',
    parameters: {
      kind: { type: 'string', required: true, description: kindDescription },
      text: { type: 'string', required: true, description: '完整草稿。' },
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(args) {
      return formatReview(args.kind, args.text)
    },
  }))

  ctx.tools.register(defineTool({
    name: 'gongwen_diff',
    description: '比较两份草稿里的文号、日期和金额，列出只出现在其中一份的项。不判断哪一份是对的。',
    parameters: {
      left: { type: 'string', required: true, description: '第一份草稿。' },
      right: { type: 'string', required: true, description: '第二份草稿。' },
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(args) {
      return diffFacts(args.left, args.right)
    },
  }))
}
