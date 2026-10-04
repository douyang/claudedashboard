#!/usr/bin/env python3
"""Make one hourly sync document from Claude Code Remote list_sessions answers.

Usage:
  python3 scripts/ccr_sync_doc.py ANSWER_FILE [ANSWER_FILE ...] OUT.json [--daily DAILY.json] [--at 2026-10-03T23:00:00Z]
  python3 scripts/ccr_sync_doc.py --from-sync SYNC.json DAILY.json

Each ANSWER_FILE is one list_sessions answer saved to a file. Pass every page
of the listing. The last path is the output file.

The output is one document for the board's `syncs` collection:
{at, src, by, sessions: [{id, title, status, bucket, model, createdAt, updatedAt, tok, out, usd, repos}], quota}
`by` is the id of the session that ran this script, read from the cloud environment (CLAUDE_CODE_REMOTE_SESSION_ID,
or --by). A session that reads the board is running because it reads, so the board does not count its running state
or its updates as work. The script leaves `by` out when it cannot tell which session it runs in.
`tok` counts input, cache reads, cache writes and output. `quota` is the limit
state of the most recently updated session. The script does not read the
session transcripts or the task summaries: the board stores no message text.

With --daily the script also writes the day's ledger entry for the board's
`daily` collection: {day, at, cols, rows}, one row per session with the totals
at this reading. The board keeps the first reading of each UTC day, so a
second write to the same day is refused and the first one stays. The ledger
keeps usage after a session leaves the listing and after the hourly syncs
move out of the page's 8-day window. --from-sync makes the same entry from a
sync document that already exists, to fill a gap.

The script prints one JSON line: doc_id (the read time in epoch seconds),
day (the UTC day of the read), sessions, tok, and `more`. When `more` is true, the last page was full: call list_sessions
again with `after_id` set to `after_id` and add that answer to the list.
A new document per sync needs no if_version, so a scheduled run writes it
with one ArtifactData `set`. The collection decides whose sync it is: the
board owner writes `syncs`; every other person writes
`data/users/me/profile/syncs`, which only that person and the owner can read.
"""
import argparse, datetime as dt, json, os, sys, time

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


def self_id():
    """The id of the session that runs this script: "cse_..." in the cloud environment, "session_..." in the listing."""
    v = os.environ.get('CLAUDE_CODE_REMOTE_SESSION_ID', '')
    return 'session_' + v[4:] if v.startswith('cse_') else v if v.startswith('session_') else ''


def iso(epoch):
    return dt.datetime.fromtimestamp(epoch, dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


DAILY_COLS = ['id', 'title', 'status', 'tok', 'out', 'usd', 'createdAt', 'repo']


def daily_doc(sync):
    """The ledger entry of a UTC day, from one sync document: the totals at that reading."""
    rows = [[r['id'], r['title'], r['status'], r['tok'], r['out'], r['usd'], r['createdAt'], (r.get('repos') or [''])[0]]
            for r in sync['sessions']]
    return {'day': sync['at'][:10], 'at': sync['at'], 'src': sync.get('src', 'routine'), 'cols': DAILY_COLS, 'rows': rows}


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
    ap.add_argument('--daily', help='also write the ledger entry of this reading to this file')
    ap.add_argument('--from-sync', help='make the ledger entry from this existing sync document; the one path is the output')
    ap.add_argument('--by', help='id of the session that took the reading; default: this session, from the environment')
    a = ap.parse_args()
    if a.from_sync:
        if len(a.paths) != 1:
            sys.exit('give the output file')
        doc = daily_doc(json.load(open(a.from_sync)))
        json.dump(doc, open(a.paths[0], 'w'), ensure_ascii=False)
        print(json.dumps({'day': doc['day'], 'sessions': len(doc['rows'])}))
        return
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
    by = a.by or self_id()
    if by:
        doc['by'] = by
    if quota:
        doc['quota'] = quota
    json.dump(doc, open(out, 'w'), ensure_ascii=False)
    if a.daily:
        json.dump(daily_doc(doc), open(a.daily, 'w'), ensure_ascii=False)
    more = last_n >= PAGE
    print(json.dumps({'doc_id': str(at), 'day': doc['at'][:10], 'sessions': len(rows), 'tok': sum(r['tok'] for r in rows),
                      'more': more, 'after_id': last_id if more else None}))


if __name__ == '__main__':
    main()
