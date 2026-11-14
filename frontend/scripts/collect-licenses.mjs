// Copies the licence files of every production dependency (fonts included) into
// dist/licenses, so the shipped bundle carries its notices. Run after `vite build`.
import { execFileSync } from 'node:child_process'
import { copyFileSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { join, relative } from 'node:path'

const out = join('dist', 'licenses')
mkdirSync(out, { recursive: true })
const paths = execFileSync('npm', ['ls', '--omit=dev', '--all', '--parseable'], {
  encoding: 'utf8',
})
  .split('\n')
  .filter((p) => p.includes('node_modules'))
const index = []
for (const dir of [...new Set(paths)].sort()) {
  const pkg = JSON.parse(readFileSync(join(dir, 'package.json'), 'utf8'))
  const files = readdirSync(dir).filter((f) => /^(licen[cs]e|copying|notice)/i.test(f))
  const name = relative('node_modules', dir.slice(dir.lastIndexOf('node_modules'))).replaceAll(
    '/',
    '__',
  )
  files.forEach((f) => copyFileSync(join(dir, f), join(out, `${name}--${f}`)))
  index.push(`${pkg.name} ${pkg.version} — ${pkg.license ?? 'see files'}`)
}
writeFileSync(join(out, 'INDEX.txt'), `${index.join('\n')}\n`)
console.log(`licenses: ${index.length} packages`)
