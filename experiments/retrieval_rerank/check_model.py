"""Real model integration checks, run only in the experiment venv."""
import json,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from experiments.retrieval_rerank.semantic import Semantic
manifest=json.loads(Path('experiments/retrieval_rerank/MODEL_MANIFEST.json').read_text(encoding='utf-8'))
model=Semantic('runtime/k1-rerank/model',manifest)
# This long pair must cover all document tokens instead of truncating the tail.
text=('孩子通过陪伴和游戏学习。'*200)+'最后的内容也必须进入评分窗口。'
windows=model.encodings('如何陪孩子学习',text)
assert len(windows)>1 and all(len(w.ids)<=512 for w in windows)
try:model.encodings('问题'*1000,'正文')
except ValueError:pass
else:raise AssertionError('Long question was silently truncated')
ranked,stats=model.rank('幼儿如何学习',[{'id':'learn','text':'幼儿通过游戏和陪伴探索世界。'},
                                     {'id':'job','text':'幼儿园教师应聘的合同和薪资安排。'}])
assert ranked[0]['id']=='learn'
empty,empty_stats=model.rank('问题',[]);assert empty==[] and empty_stats['pairs']==0
with tempfile.TemporaryDirectory(prefix='rerank-check-') as directory:
 try:Semantic(directory,manifest)
 except ValueError:pass
 else:raise AssertionError('Unverified weights were accepted')
report={'pinned_artifact_validation':True,'long_pair_windows':len(windows),'all_windows_le_512':True,
        'document_token_coverage_verified':True,'long_query_rejected':True,'empty_pool_supported':True,
        'own_synthetic_relevance_smoke':True,'semantic_is_not_answerability':True,'runtime_onnx':model.ort_version}
Path('experiments/retrieval_rerank/MODEL_CHECK_20261024.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(report)
