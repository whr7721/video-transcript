import assert from 'node:assert/strict'
import {test} from 'node:test'
import {existsSync} from 'node:fs'
import {apply,loadSkill} from './index.js'
test('loads local bundle and releases registration on dispose',()=>{
 const skill=loadSkill();assert.equal(skill.name,'shiwen');assert.ok(skill.content.includes('shiwen summarize'));assert.ok(existsSync(skill.path));assert.ok(existsSync(skill.resourceBase.path))
 let registered,dispose,removed=false
 apply({skills:{register(s){registered=s;return ()=>{removed=true}}},effect(fn){dispose=fn()}})
 assert.equal(registered.name,'shiwen');dispose();assert.equal(removed,true)
})
