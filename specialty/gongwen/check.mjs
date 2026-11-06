import { readFileSync } from 'node:fs'
import { scaffold, lint, formatLint, facts, formatFacts, formatReview, diffFacts, listKinds } from './logic.mjs'

function arg(name) {
  const index = process.argv.indexOf(name)
  if (index === -1 || index + 1 >= process.argv.length) return ''
  return process.argv[index + 1]
}

function readBody() {
  const file = arg('--file')
  if (file) return readFileSync(file, 'utf8')
  return readFileSync(0, 'utf8')
}

const command = process.argv[2]
const kind = process.argv[3]

if (command === 'scaffold') {
  const result = scaffold({ kind, title: arg('--title'), recipient: arg('--recipient') })
  process.stdout.write(result.text + '\n')
  process.exit(result.ok ? 0 : 2)
}

if (command === 'lint') {
  const result = lint(kind, readBody())
  process.stdout.write(formatLint(result) + '\n')
  process.exit(result.ok ? 0 : 1)
}

if (command === 'facts') {
  process.stdout.write(formatFacts(facts(readBody())) + '\n')
  process.exit(0)
}

if (command === 'diff') {
  const left = arg('--left')
  const right = arg('--right')
  if (!left || !right) {
    process.stderr.write('用法：node specialty/gongwen/check.mjs diff --left 原稿.md --right 改稿.md\n')
    process.exit(2)
  }
  process.stdout.write(diffFacts(readFileSync(left, 'utf8'), readFileSync(right, 'utf8')) + '\n')
  process.exit(0)
}

if (command === 'review') {
  const body = readBody()
  const result = lint(kind, body)
  process.stdout.write(formatReview(kind, body) + '\n')
  process.exit(result.ok ? 0 : 1)
}

process.stderr.write(`用法：node specialty/gongwen/check.mjs scaffold <${listKinds().join('|')}> --title "标题" --recipient "主送"\n`)
process.stderr.write(`      node specialty/gongwen/check.mjs lint <文种> --file 草稿.md\n`)
process.stderr.write(`      node specialty/gongwen/check.mjs facts --file 草稿.md\n`)
process.stderr.write(`      node specialty/gongwen/check.mjs review <文种> --file 草稿.md\n`)
process.stderr.write(`      node specialty/gongwen/check.mjs diff --left 原稿.md --right 改稿.md\n`)
process.exit(2)
