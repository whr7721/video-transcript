"""Local stratified region sample and human-only evaluation, with no model labeling."""
import hashlib
from collections import Counter
import ocr_reading as reading


def sample(items, count=200):
    candidates = []
    for item in items:
        if item.get('kind') != 'images':
            continue
        for row in reading.rules(item):
            candidates.append({**row, 'item_id': item['id'], 'title': item['title'],
                               'asset_name': next((b.get('asset_name') for b in item['blocks'] if b['id'] == row['source_image_id']), None)})
    # Page-based split prevents lines from the same screenshot leaking across splits.
    groups = {}
    for row in candidates:
        key = row['item_id']+':'+str(row['page'])
        row['split'] = 'holdout' if int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) % 5 < 2 else 'development'
        groups.setdefault((row['split'], row['state'], row['uncertain']), []).append(row)
    for group in groups.values():
        group.sort(key=lambda r: reading.digest([r['item_id'], r['id']]))
    result = []
    while groups and len(result) < count:
        for key in list(groups):
            result.append(groups[key].pop(0))
            if not groups[key]:
                del groups[key]
            if len(result) >= count:
                break
    return result


def metrics(rows, labels, decisions):
    confirmed = [(r, labels.get(r['item_id']+':'+r['id'])) for r in rows]
    confirmed = [(r, l) for r, l in confirmed if l and l.get('confirmed') is True and l.get('source_key') == r['source_key']]
    result = {'sample_size': len(rows), 'human_confirmed': len(confirmed), 'pending': len(rows)-len(confirmed), 'splits': {}}
    for split in ('development', 'holdout'):
        subset = [(r, l) for r, l in confirmed if r['split'] == split]
        body = [(r, l) for r, l in subset if l['category'] == 'body']
        noise = [(r, l) for r, l in subset if l['category'] in {'watermark', 'furniture', 'interface'}]
        def state(r):
            return decisions.get(r['item_id']+':'+r['id'], r)['state']
        confusion = Counter((l['category'], decisions.get(r['item_id']+':'+r['id'], r)['category']) for r, l in subset)
        result['splits'][split] = {'n': len(subset), 'body': len(body), 'noise': len(noise),
            'body_excluded': sum(state(r) == 'exclude' for r, _ in body),
            'body_folded': sum(state(r) == 'fold' for r, _ in body),
            'noise_removed': sum(state(r) == 'exclude' for r, _ in noise),
            'body_exclusion_rate': sum(state(r) == 'exclude' for r, _ in body)/len(body) if body else None,
            'body_fold_rate': sum(state(r) == 'fold' for r, _ in body)/len(body) if body else None,
            'noise_removal_rate': sum(state(r) == 'exclude' for r, _ in noise)/len(noise) if noise else None,
            'confusion': [{'actual': a, 'predicted': p, 'n': n} for (a, p), n in sorted(confusion.items())]}
    return result


def prepared():
    import articles
    import store
    path = store.DATA/'ocr-evaluation-sample.json'
    if path.exists():
        import json
        return json.loads(path.read_text(encoding='utf-8'))
    rows = sample(articles.listing())
    # No transient model labels are stored as human truth.
    if rows:
        store.atomic_json(path, rows)
    return rows


def label(item_id, region_id, source_key, category, revision):
    import articles
    import documents
    import store
    with articles.LOCK, store.connect() as db:
        init(db)
        row = next((r for r in prepared() if r['item_id'] == item_id and r['id'] == region_id), None)
        item = articles.get(item_id)
        current = next((r for r in reading.originals(item or {}) if r['id'] == region_id), None)
        if not row or not current or current['source_key'] != source_key or row['source_key'] != source_key:
            raise documents.Conflict('样本原文已变化，未记录标签')
        key = item_id+':'+region_id
        old = db.execute('SELECT revision FROM ocr_human_labels WHERE id=?', (key,)).fetchone()
        if (old[0] if old else 0) != revision:
            raise documents.Conflict('人工标签已更新，请刷新')
        if category not in reading.CATEGORIES:
            raise ValueError('标签类别无效')
        db.execute('INSERT OR REPLACE INTO ocr_human_labels VALUES (?,?,?,?,?)', (key, source_key, category, revision+1, 1))
    return report()


def init(db):
    db.execute('CREATE TABLE IF NOT EXISTS ocr_human_labels (id TEXT PRIMARY KEY, source_key TEXT, category TEXT, revision INTEGER, confirmed INTEGER)')


def report():
    import articles
    import store
    with articles.LOCK, store.connect() as db:
        rows = prepared(); init(db)
        labels = {r['id']: dict(r) for r in db.execute('SELECT * FROM ocr_human_labels')}
        for label in labels.values():
            label['confirmed'] = bool(label['confirmed'])
        items = {r['item_id']: articles.get(r['item_id']) for r in rows}
        # Exclude stale/deleted originals from the denominator, and expose their count.
        valid = {i: {r['id']: r['source_key'] for r in reading.originals(item)} for i, item in items.items() if item}
        active = [r for r in rows if valid.get(r['item_id'], {}).get(r['id']) == r['source_key']]
        comparisons = {}
        for mode in ('all', 'rules', 'ai'):
            decisions = {}
            for ident, item in items.items():
                if not item: continue
                for row in reading.selection(item, 'rules' if mode == 'rules' else 'ai'):
                    decisions[ident+':'+row['id']] = {**row, 'state': 'keep', 'category': 'body'} if mode == 'all' else row
            comparisons[mode] = metrics(active, labels, decisions)
        return {'rows': [{**r, 'label': labels.get(r['item_id']+':'+r['id'])} for r in active],
                'stale_samples': len(rows)-len(active), 'comparisons': comparisons}
