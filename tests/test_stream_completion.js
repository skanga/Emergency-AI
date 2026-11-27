// Exercise the real ask flow with a stream that ends without a completion event.
const assert = require('assert'), fs = require('fs'), vm = require('vm');
const source = fs.readFileSync('web/app.js', 'utf8');
async function check(completed, sourcesSupplied = true, failed = false) {
  const errors = [];
  let cancelled = 0;
  const out = {innerHTML: '', classList: {remove() {}}, appendChild: n => errors.push(n.textContent)};
  const nodes = {}, metadata = [];
  const bubble = {querySelector: () => out, appendChild: n => metadata.push(n.textContent)};
  const message = {querySelector: () => bubble, scrollIntoView() {}};
  let reads = 0;
  const retrievalEvents = [];
  const displayOrder = [];
  const stream = 'event: retrieval\ndata: {"conflicts":[{"resolution":"unresolved"}]}\n\n' + 'event: sources\ndata: [{"n":1,"kind":"guidance","fallback_evidence":true}]\n\n' + 'event: token\ndata: "Partial answer"\n\n' +
    (failed ? 'event: error\ndata: {"error":"connection failed"}\n\n' : completed ? 'event: done\ndata: ' + JSON.stringify({mode: 'llm', seconds: 1, sources_supplied: sourcesSupplied}) + '\n\n' : '');
  const context = vm.createContext({busy: false, lang: 'en', chatHistory: [], librarySelection: null,
    $: s => s === '#welcome' ? null : (nodes[s] ??= {checked: false, scrollHeight:100,clientHeight:100,scrollTop:0}),
    modelSwitching: () => false, addMsg: () => message, esc: s => s, t: s => s, md: s => {displayOrder.push('token'); return s;},
    renderSources() {displayOrder.push('sources');}, renderRetrieval(container, report) { retrievalEvents.push(report); }, renderModels() {}, document: {createElement: () => ({})}, TextDecoder, Date,
    requestAnimationFrame: () => 1, cancelAnimationFrame() {cancelled++;},
    fetch: async () => ({ok: true, body: {getReader: () => ({read: async () => reads++ ?
      {done: true} : {done: false, value: Buffer.from(stream)}})}})});
  vm.runInContext(source.slice(source.indexOf('  function updateChat('),
    source.indexOf('  // ---------------- sidebar search')), context);
  await context.ask('Question');
  assert(cancelled > 0, 'Pending frame is cancelled on terminal render');
  if (failed) {
    assert(out.innerHTML.includes('Partial answer'));
    assert(errors[0].includes('connection failed'));
    assert.equal(context.chatHistory.length, 0);
    return;
  }
  assert.equal(context.chatHistory.length, 2);
  assert(displayOrder.indexOf('sources') < displayOrder.indexOf('token'));
  assert.equal(retrievalEvents[0].conflicts[0].resolution, 'unresolved');
  assert(context.chatHistory[1].content.includes('Partial answer'));
  assert.equal(out.innerHTML.includes('Interrupted response'), !completed);
  assert.equal(context.chatHistory[1].content.includes('Interrupted response'), !completed);
  assert.equal(metadata[0].includes('modeLlm'), completed && sourcesSupplied);
  assert.equal(metadata[0].includes('modeUngrounded'), completed && !sourcesSupplied);
}
(async () => { await check(false); await check(true); await check(true, false); await check(false, true, true); })().catch(e => {console.error(e); process.exitCode = 1;});
