const assert = require('assert'), fs = require('fs'), vm = require('vm');
const source = fs.readFileSync('web/app.js', 'utf8');
const context = vm.createContext({});
vm.runInContext(source.slice(source.indexOf('  function normalizeArrows'), source.indexOf('  function md(')), context);
for (const input of ['[see https://example.com](https://example.com)', '[reference [1]](https://example.com)', 'https://example.com/path[1]']) {
  const output = context.inline(input, {cites:true});
  assert.equal((output.match(/<a /g) || []).length, 1, output);
}
const adjacent = context.inline('https://example.com[other](https://other.example)', {});
assert.equal((adjacent.match(/<a /g) || []).length, 2);
assert(!/[\u0000\u0001]/.test(adjacent));
assert(context.inline('[2]', {cites:true}).includes('data-cite="2"'));
assert(context.inline('`https://example.com`', {}).includes('<code>https://example.com</code>'));
assert(!context.inline('[unsafe](javascript:alert)', {}).includes('href='));
assert(context.inline('[guide](first-aid.md#steps)', {}).includes('data-guide="first-aid"'));

const boxes = [];
const sourcesContext = vm.createContext({lang:'en', t:x=>x, retrievalLabel:x=>x, esc:x=>String(x), document:{createElement:()=>({})}});
const scopeStart = source.indexOf('  let sourceSequence');
vm.runInContext(source.slice(scopeStart >= 0 ? scopeStart : source.indexOf('  function renderSources('), source.indexOf('  async function ask(')), sourcesContext);
const a={appendChild:x=>boxes.push(x)}, b={appendChild:x=>boxes.push(x)};
const sources=[{n:1,kind:'guidance',doc_title:'Guide',section:'Steps',text:'text'}];
sourcesContext.renderSources(a,sources);sourcesContext.renderSources(b,sources);sourcesContext.renderSources(a,sources);
const ids=boxes.map(x=>x.innerHTML.match(/id="([^"]+)"/)[1]);
assert.notEqual(ids[0],ids[1]);assert.equal(ids[0],ids[2]);

let writes=0, scrolls=0, html='';
const chat={scrollHeight:1000,clientHeight:200,top:0,get scrollTop(){return this.top;},set scrollTop(v){this.top=v;scrolls++;}};
const out={set innerHTML(v){html=v;writes++;chat.scrollHeight+=100;}};
let next=0;const frames=new Map();
const rendering=vm.createContext({$:()=>chat,md:x=>x,requestAnimationFrame:fn=>{frames.set(++next,fn);return next;},cancelAnimationFrame:id=>frames.delete(id)});
vm.runInContext(source.slice(source.indexOf('  function updateChat('),source.indexOf('  async function ask(')),rendering);
const renderer=rendering.createStreamRenderer(out);
renderer.schedule('one');renderer.schedule('one two');
assert.equal(writes,0);assert.equal(frames.size,1);
renderer.flush();assert.equal(html,'one two');assert.equal(writes,1);assert.equal(scrolls,0);assert.equal(frames.size,0);
chat.top=chat.scrollHeight-chat.clientHeight;
renderer.schedule('done');renderer.flush();assert.equal(html,'done');assert.equal(scrolls,1);
renderer.flush();assert.equal(writes,2);
// A user scrolling away after scheduling but before the frame must stay put.
renderer.schedule('later');chat.top=0;renderer.flush();assert.equal(scrolls,1);
renderer.schedule('frame rendered');
const queued = [...frames.values()]; frames.clear(); queued.forEach(fn => fn());
assert.equal(html, 'frame rendered'); assert.equal(scrolls, 1);
renderer.flush(); assert.equal(writes, 4);
console.log('chat rendering tests passed');
