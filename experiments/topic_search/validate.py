"""Production search acceptance. Original stores are read-only; all writes in runtime."""
import json
import sqlite3
import statistics
import sys
import time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import store
import research
import topic_search as search
from experiments.retrieval import projection, baselines, evaluate

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'runtime/k1-production'
OUT.mkdir(parents=True, exist_ok=True)


def database(name):
    root = OUT/name
    root.mkdir(exist_ok=True)
    # Use distinct files on repeated runs, no recursive delete of any user directory.
    path = root/('acceptance-'+str(time.time_ns())+'.sqlite3')
    return root, path


def seed(topic='acceptance'):
    store.init()
    with store.connect() as db:
        research.init(db)
        db.execute('INSERT INTO research_topics VALUES (?,?,0)', (topic, '验收专题'))


def attach(task, index, topic='acceptance'):
    store.save(task)
    ident = 'acceptance-'+str(index)
    body = task.get('result', {}).get('segments', [])
    job = {'id': ident, 'task_id': task['id'], 'title': task.get('title', ''),
           'context': {'basis': 'original', 'version': 'original',
                       'selection': body[0]['text'][:80] if body else ''}, 'mode': 'manual',
           'status': 'completed', 'stage': 'done', 'created_at': 0, 'question': '验收夹具，非用户笔记',
           'source': task.get('source', {}), 'online': False, 'warnings': ['验收夹具，非用户创建的真实笔记。'],
           'sources': [], 'sections': [], 'usage': []}
    with store.connect() as db:
        db.execute('INSERT INTO research_jobs VALUES (?,?)', (ident, json.dumps(job, ensure_ascii=False)))
        db.execute('INSERT INTO research_notes VALUES (?,?,?,?,?,?,?)', (ident, topic, ident, '', 1, 0, 0))


def regression(docs, dataset):
    # Algorithm parity includes article fixtures; this is NOT article-topic product support.
    records = [{**d, 'category': 'original', 'basis': 'original'} for d in docs]
    root, path = database('parity')
    rows, private = [], []
    baseline = baselines.Baselines(projection.passages(docs))
    try:
        with patch.object(store, 'DATA', root), patch.object(store, 'DB', path):
            seed()
            with patch.object(search, 'projection', return_value=({'id':'acceptance','title':'验收'}, records, [])):
                for case in dataset['cases']:
                    result = search.search('acceptance', case['query'], 'original')
                    hits = [{**h, 'source_uid': h['uid']} for h in result['items'][:5]]
                    old = baseline.search(case['query'], 'bigram_bm25')
                    exact = [(h['source_uid'], h['ranges']) for h in hits] == [(h['source_uid'], h['ranges']) for h in old]
                    assert exact, case['id']
                    rows.append({'id': case['id'], 'category': case['category'], 'top5_exactly_equal': exact,
                                 **evaluate.score(hits, case['gold'])})
                    if case['category'] == 'paraphrase':
                        private.append({'id': case['id'], 'query': case['query'], 'items': hits})
    finally:baseline.close()
    (OUT/'paraphrase-private.json').write_text(json.dumps(private, ensure_ascii=False, indent=2), encoding='utf-8')
    return rows


def real_integration():
    root, path = database('real-corpus')
    review = []
    with patch.object(store, 'DATA', root), patch.object(store, 'DB', path):
        seed()
        for i, (profile, table, ident) in enumerate(projection.SOURCES):
            if table != 'tasks':continue
            original = (ROOT/profile/'tasks.sqlite3').resolve()
            with sqlite3.connect(original.as_uri()+'?mode=ro', uri=True) as db:
                task = json.loads(db.execute('SELECT payload FROM tasks WHERE id=?', (ident,)).fetchone()[0])
            attach(task, i)
        # Test HTTP without startup workers, configured credentials or network.
        from fastapi.testclient import TestClient
        import app
        client = TestClient(app.app)
        queries = json.loads((ROOT/'runtime/k1/user-queries.json').read_text(encoding='utf-8'))
        for i, query in enumerate(queries, 1):
            response = client.get('/api/studio/research/topics/acceptance/search', params={'q':query,'category':'original'})
            assert response.status_code == 200, response.text
            result = response.json()
            for hit in result['items'][:5]:
                ctx = client.post('/api/studio/research/topics/acceptance/search/context', json={k:hit[k] for k in ('hit_id','source_hash')})
                assert ctx.status_code == 200, ctx.text
            review.append({'id': i, 'query': query, 'result': result})
    (OUT/'real-query-private.json').write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding='utf-8')
    return [{'id': r['id'], 'query_hash': search.digest(r['query']), 'candidate_count': r['result']['candidate_count'],
             'top5_contexts_resolve': True} for r in review]


def performance():
    root, path = database('performance')
    with patch.object(store, 'DATA', root), patch.object(store, 'DB', path):
        seed()
        for i in range(50):
            blocks = []
            for j in range(200):
                lead = f'第{i}份第{j}段，缓存与客户交付都需要分别判断，AI工具必须找到真实使用场景。'
                text = (lead+'本段是合成性能边界材料，不是用户笔记。'*30)[:500]
                blocks.append({'text': text, 'start':j*30,'end':j*30+29})
            attach({'id':f'{i:016x}','status':'completed','title':'合成性能样本'+str(i),'result':{'segments':blocks}}, i)
        started = time.perf_counter()
        first = search.search('acceptance', '客户交付', 'original')
        cold = (time.perf_counter()-started)*1000
        with store.connect() as db:
            count = db.execute("SELECT count(*) FROM topic_search_passages WHERE category='original'").fetchone()[0]
        assert count == 10000, count
        times = []
        for i in range(25):
            started = time.perf_counter()
            search.search('acceptance', ['客户交付','AI工具','缓存','普通人如何找到客户','不存在的专题词'][i%5], 'original')
            times.append((time.perf_counter()-started)*1000)
        p95 = sorted(times)[int(.95*(len(times)-1))]
        return {'synthetic': True, 'original_passages': count, 'cold_build_and_query_ms': cold,
                'hot_queries': len(times), 'hot_median_ms': statistics.median(times), 'hot_p95_ms': p95,
                'target_p95_ms': 300, 'target_met': p95 <= 300, 'database_bytes': path.stat().st_size}


if __name__ == '__main__':
    docs, before = projection.load(ROOT)
    dataset = json.loads((ROOT/'experiments/retrieval/cases_v1.json').read_text(encoding='utf-8'))
    assert projection.fingerprint(before) == dataset['corpus_hash']
    evaluate.validate_labels(docs, dataset)
    result = {'frozen_regression': regression(docs, dataset), 'real_queries': real_integration(), 'performance': performance()}
    _, after = projection.load(ROOT)
    assert before == after
    result['original_source_snapshots_unchanged'] = True
    target = ROOT/'experiments/topic_search/RESULTS_20261025.json'
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'regression_cases':len(result['frozen_regression']), 'real_queries':len(result['real_queries']), 'performance':result['performance']}, ensure_ascii=False))
