#!/usr/bin/env python3
"""Make one hourly sync document from a Claude Code Remote list_sessions answer.

Usage:
  python3 scripts/ccr_sync_doc.py LIST_SESSIONS_FILE OUT.json [--at 2026-10-03T23:00:00Z]

The output is one document for the dashboard's `syncs` collection:
{at, src, sessions: [{id, title, status, createdAt, updatedAt, tok, out, usd, repos}], quota}
`tok` counts input, cache reads, cache writes and output. `quota` is the limit
state of the most recently updated session. The script prints the doc id
(the read time in epoch seconds), the session count and the total tokens.
A new document per sync needs no if_version, so a scheduled run can write it
with one ArtifactData `set`.
"""
import argparse, datetime as dt, json, sys, time


def load_sessions(path):
    txt = open(path).read()
    i = txt.find('{"ccr"')
    if i < 0:
        cands = [x for x in (txt.find('{'), txt.find('[')) if x >= 0]
        if not cands:
            sys.exit('no JSON in the list_sessions file')
        i = min(cands)
    d, _ = json.JSONDecoder().raw_decode(txt[i:])
    if isinstance(d, dict):
        d = (d.get('ccr') or {}).get('data') or d.get('data') or d.get('sessions') or []
    return d


def iso(epoch):
    return dt.datetime.fromtimestamp(epoch, dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('list_sessions')
    ap.add_argument('out')
    ap.add_argument('--at', help='UTC time of the list_sessions read; default now')
    a = ap.parse_args()
    at = int(dt.datetime.fromisoformat(a.at.replace('Z', '+00:00')).timestamp()) if a.at else int(time.time())
    rows, quota, latest = [], None, ''
    for s in load_sessions(a.list_sessions):
        em = s.get('external_metadata') or {}
        u = em.get('usage') or {}
        tok = sum(int(u.get(k) or 0) for k in ('input_tokens', 'cache_read_tokens', 'cache_write_tokens', 'output_tokens'))
        rows.append({
            'id': s['id'], 'title': s.get('title') or s['id'],
            'status': str(s.get('session_status') or '').lower().replace('session_status_', '') or 'idle',
            'createdAt': s.get('created_at'), 'updatedAt': s.get('updated_at'),
            'tok': tok, 'out': int(u.get('output_tokens') or 0), 'usd': round(float(u.get('cost_usd') or 0), 2),
            'repos': [((x.get('git_repository') or {}).get('url') or '').replace('https://github.com/', '')
                      for x in (s.get('session_context') or {}).get('sources', []) if (x.get('git_repository') or {}).get('url')],
        })
        rl = em.get('rate_limit_info')
        if rl and (s.get('updated_at') or '') > latest:
            latest = s.get('updated_at') or ''
            quota = {'status': rl.get('status'), 'type': rl.get('rateLimitType'),
                     'resetsAt': iso(rl['resetsAt']) if rl.get('resetsAt') else None,
                     'overage': bool(rl.get('isUsingOverage')), 'asOf': latest}
    doc = {'at': iso(at), 'src': 'routine', 'sessions': rows}
    if quota:
        doc['quota'] = quota
    json.dump(doc, open(a.out, 'w'), ensure_ascii=False)
    print(json.dumps({'doc_id': str(at), 'sessions': len(rows), 'tok': sum(r['tok'] for r in rows)}))


if __name__ == '__main__':
    main()
