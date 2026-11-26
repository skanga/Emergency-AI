// Guidance sources are inspectable offline and are not broken local-guide links.
const assert = require('assert'), fs = require('fs'), vm = require('vm');
const source = fs.readFileSync('web/app.js', 'utf8');
const boxes = [];
const context = vm.createContext({lang:'en', t:x=>x, retrievalLabel:x=>x,
  esc:x=>String(x ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;'),
  document:{createElement:()=>({})}});
vm.runInContext(source.slice(source.indexOf('  function renderSources('),
                            source.indexOf('  async function ask(')), context);
context.renderSources({appendChild:x=>boxes.push(x)}, [
  {kind:'guidance', n:1, doc_title:'Reference', section:'Safety',
   text:'Read <this> offline', url:'https://example.org/reference', fallback_evidence:true},
  {kind:'guidance', n:2, doc_title:'Reference', section:'Safety',
   text:'Text', url:'javascript:alert(1)'}]);
assert(boxes[0].innerHTML.includes('Read &lt;this> offline'));
assert(boxes[0].innerHTML.includes('https://example.org/reference'));
assert(!boxes[0].innerHTML.includes('javascript:'));
assert(!boxes[0].innerHTML.includes('data-guide'));
assert(boxes[0].innerHTML.includes('Fallback evidence'));
