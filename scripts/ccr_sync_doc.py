#!/usr/bin/env python3
"""Make one hourly sync document from Claude Code Remote list_sessions answers.

Usage:
  python3 scripts/ccr_sync_doc.py ANSWER_FILE [ANSWER_FILE ...] OUT.json [--at 2026-10-03T23:00:00Z]

Each ANSWER_FILE is one list_sessions answer saved to a file. Pass every page
of the listing. The last path is the output file.

The output is one document for the board's `syncs` collection:
{at, src, sessions: [{id, title, status, bucket, model, createdAt, updatedAt, tok, out, usd, repos}], quota}
`tok` counts input, cache reads, cache writes and output. `quota` is the limit
state of the most recently updated session. The script does not read the
session transcripts or the task summaries: the board stores no message text.

The script prints one JSON line: doc_id (the read time in epoch seconds),
sessions, tok, and `more`. When `more` is true, the last page was full: call list_sessions
again with `after_id` set to `after_id` and add that answer to the list.
A new document per sync needs no if_version, so a scheduled run writes it
with one ArtifactData `set`. The collection decides whose sync it is: the
board owner writes `syncs`; every other person writes
`data/users/me/profile/syncs`, which only that person and the owner can read.
"""
import argparse, datetime as dt, json, sys, time

PAGE = 100


def load_sessions(path):
    txt = open(path).read()
    i = txt.find('{"ccr"')
    if i < 0:
        cands = [x for x in (txt.find('{'), txt.find('[')) if x >= 0]
        if not cands:
            sys.exit(f'no JSON in {path}')
        i = min(cands)
    d, _ = json.JSONDecoder().raw_decode(txt[i:])
    last = None
    if isinstance(d, dict):
        c = d.get('ccr') or d
        last = c.get('last_id')
        d = c.get('data') or d.get('data') or d.get('sessions') or []
    return d, last


def iso(epoch):
    return dt.datetime.fromtimestamp(epoch, dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def row(s):
    em = s.get('external_metadata') or {}
    u = em.get('usage') or {}
    tok = sum(int(u.get(k) or 0) for k in ('input_tokens', 'cache_read_tokens', 'cache_write_tokens', 'output_tokens'))
    return {
        'id': s['id'], 'title': s.get('title') or s['id'],
        'status': str(s.get('session_status') or '').lower().replace('session_status_', '') or 'idle',
        'bucket': str(s.get('status_bucket') or '').lower().replace('session_status_bucket_', ''),
        'model': em.get('last_served_model') or s.get('configured_model') or '',
        'createdAt': s.get('created_at'), 'updatedAt': s.get('updated_at'),
        'tok': tok, 'out': int(u.get('output_tokens') or 0), 'usd': round(float(u.get('cost_usd') or 0), 2),
        'repos': [((x.get('git_repository') or {}).get('url') or '').replace('https://github.com/', '')
                  for x in (s.get('session_context') or {}).get('sources', []) if (x.get('git_repository') or {}).get('url')],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('paths', nargs='+', help='one or more list_sessions answer files, then the output file')
    ap.add_argument('--at', help='UTC time of the list_sessions read; default now')
    a = ap.parse_args()
    if len(a.paths) < 2:
        sys.exit('give at least one answer file and the output file')
    *answers, out = a.paths
    at = int(dt.datetime.fromisoformat(a.at.replace('Z', '+00:00')).timestamp()) if a.at else int(time.time())
    rows, seen, quota, latest, last_n, last_id = [], set(), None, '', 0, None
    for path in answers:
        page, last_id = load_sessions(path)
        last_n = len(page)
        for s in page:
            if not isinstance(s, dict) or not s.get('id') or s['id'] in seen:
                continue
            seen.add(s['id'])
            rows.append(row(s))
            rl = (s.get('external_metadata') or {}).get('rate_limit_info')
            if rl and (s.get('updated_at') or '') > latest:
                latest = s.get('updated_at') or ''
                quota = {'status': rl.get('status'), 'type': rl.get('rateLimitType'),
                         'resetsAt': iso(rl['resetsAt']) if rl.get('resetsAt') else None,
                         'overage': bool(rl.get('isUsingOverage')), 'asOf': latest}
    doc = {'at': iso(at), 'src': 'routine', 'sessions': rows}
    if quota:
        doc['quota'] = quota
    json.dump(doc, open(out, 'w'), ensure_ascii=False)
    more = last_n >= PAGE
    print(json.dumps({'doc_id': str(at), 'sessions': len(rows), 'tok': sum(r['tok'] for r in rows),
                      'more': more, 'after_id': last_id if more else None}))


if __name__ == '__main__':
    main()
