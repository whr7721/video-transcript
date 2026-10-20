// Evaluation only. Packages are installed under ignored runtime/article-eval/node.
const fs = require('fs');
const path = require('path');
const base = path.resolve(__dirname, '../../runtime/article-eval/node/node_modules');
const {parseHTML} = require(path.join(base, 'linkedom'));
const Defuddle = require(path.join(base, 'defuddle'));
(async () => {
  const {document} = parseHTML(fs.readFileSync(process.argv[2], 'utf8'));
  const start = performance.now();
  const result = new Defuddle(document, process.argv[3], {useAsync:false}).parse();
  const root = parseHTML(result.content).document;
  process.stdout.write(JSON.stringify({title:result.title,chars:(root.documentElement?.textContent||'').length,
    images:root.querySelectorAll('img').length,code:root.querySelectorAll('pre').length,
    tables:root.querySelectorAll('table').length,ms:performance.now()-start}));
})().catch(e=>{process.stderr.write(e.message);process.exitCode=1});
