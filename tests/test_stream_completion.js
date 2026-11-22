// Exercise the real ask flow with a stream that ends without a completion event.
const assert = require('assert'), fs = require('fs'), vm = require('vm');
const source = fs.readFileSync('web/app.js', 'utf8');
async function check(completed, sourcesSupplied = true) {
  const out = {innerHTML: '', classList: {remove() {}}};
  const nodes = {}, metadata = [];
  const bubble = {querySelector: () => out, appendChild: n => metadata.push(n.textContent)};
  const message = {querySelector: () => bubble, scrollIntoView() {}};
  let reads = 0;
  const stream = 'event: token\ndata: "Partial answer"\n\n' +
    (completed ? 'event: done\ndata: ' + JSON.stringify({mode: 'llm', seconds: 1, sources_supplied: sourcesSupplied}) + '\n\n' : '');
  const context = vm.createContext({busy: false, lang: 'en', chatHistory: [], librarySelection: null,
    $: s => s === '#welcome' ? null : (nodes[s] ??= {checked: false}),
    modelSwitching: () => false, addMsg: () => message, esc: s => s, t: s => s, md: s => s,
    renderSources() {}, renderModels() {}, document: {createElement: () => ({})}, TextDecoder, Date,
    fetch: async () => ({ok: true, body: {getReader: () => ({read: async () => reads++ ?
      {done: true} : {done: false, value: Buffer.from(stream)}})}})});
  vm.runInContext(source.slice(source.indexOf('  async function ask(question)'),
    source.indexOf('  // ---------------- sidebar search')), context);
  await context.ask('Question');
  assert.equal(context.chatHistory.length, 2);
  assert(context.chatHistory[1].content.includes('Partial answer'));
  assert.equal(out.innerHTML.includes('Interrupted response'), !completed);
  assert.equal(context.chatHistory[1].content.includes('Interrupted response'), !completed);
  assert.equal(metadata[0].includes('modeLlm'), completed && sourcesSupplied);
  assert.equal(metadata[0].includes('modeUngrounded'), completed && !sourcesSupplied);
}
(async () => { await check(false); await check(true); await check(true, false); })().catch(e => {console.error(e); process.exitCode = 1;});
