const assert = require('assert'), fs = require('fs'), vm = require('vm');
const source = fs.readFileSync('web/app.js','utf8');
const context = vm.createContext({lang:'en', esc:s=>String(s??'').replace(/[<>&"]/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'}[c])), t:s=>s,
  document:{createElement:()=>({innerHTML:'',className:''})}});
const start=source.indexOf('  function retrievalLabel(');
assert(start>=0,'retrieval UI must exist');
vm.runInContext(source.slice(start,source.indexOf('  async function ask(question)')),context);
const report={libraries:[{name:'medicine',status:'success',attempts:[{status:'success'}],index:{state:'partially_indexed'}}],conflicts:[{resolution:'unresolved',explanation:'References differ.'}]};
const summary=context.retrievalSummary(report,[{kind:'kiwix',context_omitted:true}]);
assert(summary.includes('0'));
assert(summary.includes('disagree'));
assert(summary.includes('partially indexed'));
assert(context.retrievalSummary({status:'failed',libraries:[{name:'medicine',status:'success'}],fetches:[{status:'http_error'}]},[]).includes('Article fetch failures: 1'));
assert(context.retrievalSummary({status:'zero_hits',libraries:[{name:'medicine',status:'success',hits:1}],fetches:[{status:'rejected'}]},[]).includes('no relevant passage'));
assert(context.retrievalSummary({status:'no_selection',libraries:[]},[]).includes('none selected'));
const children=[];context.renderSources({appendChild:n=>children.push(n)},[
 {kind:'kiwix',n:1,doc_title:'Medicine',section:'Treatment',link:'/content/a#x',issued:'2026-10',context_omitted:false},
 {kind:'kit',n:2,doc_title:'Local',section:'Procedure',doc_id:'aid',anchor:'a',context_omitted:true,omission_reason:'context_budget'}]);
assert(children[0].innerHTML.includes('<details'));
assert(children[0].innerHTML.includes('2026-10'));
assert(children[0].innerHTML.includes('Not used'));
assert(children[0].innerHTML.includes('Context limit'));
console.log('retrieval UI tests passed');
