"""Synthetic evaluation only: capture validation inputs, never install this in the app."""
import datetime,hashlib,json,sys
from pathlib import Path
from unittest.mock import patch
from app.engine import Engine
from app.answer_validation import validate_answer

out=Path(sys.argv[1]);out.mkdir(exist_ok=False)
root=Path.cwd()
engine=Engine({'llm_backend':'llamacpp','llm_url':'http://127.0.0.1:8091/v1','kiwix_enabled':False})
model=engine.llm(force=True)
if model is None:raise SystemExit('Model unavailable; no fallback-only diagnostic run permitted')
result={'warning':'Synthetic test drafts may contain unsafe advice. These are validation inputs, not user guidance.', 'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'model':model.describe(),'options':model.options(),'files_sha256':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in ['app/engine.py','app/claim_validation.py','app/answer_validation.py','app/action_patterns.py','app/compression_claims.py','app/claim_links.py','app/transport_claims.py','app/patient_facts.py','app/data/guidance.json','config/retrieval-topics.json']},'results':[]}
base=root/'tests/evals/emergency_advice/baselines/snakebite-2026-11-26'
requests=[]
for name in ['final-live-english-run.json','final-live-multilingual-run.json']:
 requests.extend(json.loads((base/name).read_text())['results'])
for row in requests:
 captures=[]
 def inspect(answer,sources,question,lang='en',history=None):
  rendered,report=validate_answer(answer,sources,question,lang,history)
  captures.append({'draft':answer,'sources':sources,'validation':report})
  return rendered,report
 request=row['request']
 with patch.object(engine,'llm',return_value=model),patch('app.engine.validate_answer',side_effect=inspect):
  answer,sources,done=engine.answer_text(request['q'],request['lang'],history=request.get('history',[]),use_kiwix=False)
 result['results'].append({'id':row['id'],'trial':row['trial'],'request':request,'answer':answer,'sources':sources,'done':done,'validation_inputs':captures})
 (out/'inspection.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(row['id'],row['trial'],done['mode'],done.get('reason'),flush=True)
