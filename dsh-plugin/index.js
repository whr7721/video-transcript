import {existsSync,readFileSync} from 'node:fs'
import {fileURLToPath} from 'node:url'
import {join} from 'node:path'
export const name='shiwen-local'
export const inject=['skills']
export function loadSkill(){
 const dirs=[new URL('./skills/shiwen/',import.meta.url),new URL('../skills/shiwen/',import.meta.url)]
 const directory=dirs.map(u=>fileURLToPath(u)).find(p=>existsSync(join(p,'SKILL.md')))
 if(!directory)throw Error('Shiwen skill missing; run package prepare')
 const raw=readFileSync(join(directory,'SKILL.md'),'utf8'),front=/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/.exec(raw)
 if(!front)throw Error('Invalid Shiwen skill frontmatter')
 const description=/^description:\s*(.+)$/m.exec(front[1])?.[1]
 if(!description)throw Error('Shiwen skill description missing')
 return {name:'shiwen',description,content:raw.slice(front[0].length),source:'bundled',path:join(directory,'SKILL.md'),resourceBase:{kind:'directory',path:directory}}
}
export function apply(ctx){
 ctx.effect(()=>ctx.skills.register(loadSkill()))
}
