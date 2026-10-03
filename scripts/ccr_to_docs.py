#!/usr/bin/env python3
"""Turn a Claude Code Remote list_sessions answer into dashboard documents.

Usage:
  python3 scripts/ccr_to_docs.py LIST_SESSIONS.json OUT_DIR [--at UTC] [--existing DB_DIR] [--registry data/projects.json]

LIST_SESSIONS.json is the tool answer saved to a file. It may carry the
{"ccr": {"data": [...]}} wrapper or be a bare list.
DB_DIR is an ArtifactData list saved with out_dir (DB_DIR/sessions/*.json,
DB_DIR/ticks/*.json). With it, the script appends to existing day documents.
The saved files do not carry versions: add if_version to each entry for a
document that exists, from the version list that the ArtifactData list prints.

The script writes one JSON file per document under OUT_DIR and prints the
ArtifactData batch entries (at most 50 per batch) as JSON lists, one per line.
"""
import json, os, sys, time, argparse, datetime as dt

def load_sessions(path):
    txt = open(path).read()
    i = txt.find('{"ccr"')
    if i < 0:
        i = min([x for x in (txt.find('{'), txt.find('[')) if x >= 0])
    d, _ = json.JSONDecoder().raw_decode(txt[i:])
    if isinstance(d, dict):
        d = (d.get('ccr') or {}).get('data') or d.get('data') or d.get('sessions') or []
    return d

def iso_ms(s):
    return dt.datetime.fromisoformat(s.replace('Z', '+00:00')) if s else None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('list_sessions'); ap.add_argument('out_dir')
    ap.add_argument('--existing'); ap.add_argument('--registry', default='data/projects.json')
    ap.add_argument('--at', help='UTC time of the list_sessions read, as 2026-10-03T23:01:00Z; default now')
    a = ap.parse_args()
    reg = json.load(open(a.registry))
    sid_proj = {s: v['name'] for k, v in reg.items() if isinstance(v, dict) for s in v.get('sessions', [])}
    existing = {}
    if a.existing:
        for col in ('sessions', 'ticks'):
            d = os.path.join(a.existing, col)
            for f in (os.listdir(d) if os.path.isdir(d) else []):
                doc = json.load(open(os.path.join(d, f)))
                existing[(col, f[:-5])] = doc
    now = iso_ms(a.at).timestamp() if a.at else time.time()
    day = dt.datetime.utcfromtimestamp(now).strftime('%Y-%m-%d')
    writes = []
    os.makedirs(os.path.join(a.out_dir, 'sessions'), exist_ok=True)
    os.makedirs(os.path.join(a.out_dir, 'ticks'), exist_ok=True)
    for s in load_sessions(a.list_sessions):
        em = s.get('external_metadata') or {}
        u = em.get('usage') or {}
        tok = sum(int(u.get(k) or 0) for k in ('input_tokens', 'cache_read_tokens', 'cache_write_tokens', 'output_tokens'))
        status = str(s.get('session_status') or '').lower().replace('session_status_', '') or 'idle'
        repos = [((x.get('git_repository') or {}).get('url') or '').replace('https://github.com/', '')
                 for x in (s.get('session_context') or {}).get('sources', [])]
        doc = {
            'title': s.get('title') or s['id'], 'project': sid_proj.get(s['id'], ''), 'where': 'cloud',
            'surface': 'Claude Code · cloud', 'status': status, 'createdAt': s.get('created_at'),
            'updatedAt': s.get('updated_at'), 'tok': tok, 'out': int(u.get('output_tokens') or 0),
            'usd': round(float(u.get('cost_usd') or 0), 2), 'repos': [r for r in repos if r], 'src': 'ccr',
        }
        writes.append(entry('sessions', s['id'], doc, existing, a.out_dir))
        # An idle session's total is final at its updatedAt, which the board already uses.
        # Snapshot only running sessions, at the time of the read.
        if tok and status == 'running':
            at = int(now)
            old = existing.get(('ticks', f"{s['id']}~{day}"))
            pts = list((old or {}).get('data', old or {}).get('pts', [])) if old else []
            if not pts or pts[-1][1] != tok:
                pts.append([at, tok])
            tick = {'sid': s['id'], 'project': sid_proj.get(s['id'], s.get('title', '')), 'day': day, 'pts': pts[-200:],
                    'out': doc['out'], 'usd': doc['usd'], 'src': 'ccr', 'updatedAt': dt.datetime.utcfromtimestamp(at).strftime('%Y-%m-%dT%H:%M:%SZ')}
            writes.append(entry('ticks', f"{s['id']}~{day}", tick, existing, a.out_dir))
    for i in range(0, len(writes), 50):
        print(json.dumps(writes[i:i + 50]))

def entry(col, doc_id, data, existing, out_dir):
    path = os.path.join(out_dir, col, f'{doc_id}.json')
    json.dump(data, open(path, 'w'), indent=1, ensure_ascii=False)
    e = {'op': 'set', 'collection': col, 'doc_id': doc_id, 'file_path': os.path.abspath(path)}
    old = existing.get((col, doc_id))
    if old and old.get('version'):
        e['if_version'] = old['version']
    return e

if __name__ == '__main__':
    main()
