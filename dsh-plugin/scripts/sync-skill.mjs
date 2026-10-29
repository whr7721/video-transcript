import {cpSync,existsSync,mkdirSync} from 'node:fs'
import {fileURLToPath} from 'node:url'
const source=fileURLToPath(new URL('../skills/shiwen',import.meta.url))
const canonical=fileURLToPath(new URL('../../skills/shiwen',import.meta.url))
// In a clone copy the canonical skill; inside a packed package keep its bundle.
if(existsSync(canonical)){mkdirSync(source,{recursive:true});cpSync(canonical,source,{recursive:true})}
else if(!existsSync(source))throw Error('Missing packaged Shiwen skill')
