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
