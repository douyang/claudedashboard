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
task summaries, and from session events it keeps only token counts and times:
the board stores no message text.

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
with one ArtifactData `set`.

Claude Code reports a running session's tokens only when a turn ends. Three
subcommands add the tokens of the turn that runs now, from the session's events
(list_events, kinds assistant and result). An event page holds message text;
turns-add reads only ids, times and token counts from it, then deletes it. The
board stores no text.
  turns-plan SYNC.json [--prev PREV.json]   list the running sessions to read
  turns-add SESSION_ID PAGE_FILE            add one page, newest first; print more and before_id
  turns-merge SYNC.json                     write `turn` into each running session of SYNC.json
Cowork sessions do not appear in list_sessions, but get_session answers for them by
id. Two subcommands add them to the reading, each row marked via: get:
  local-ids SYNC.json SESSIONS_DIR          print the ids of sessions that report to the
                                            board (saved session documents) and that the listing lacks
  add-local SYNC.json [--daily DAILY.json] ANSWER_FILE ...
                                            add each get_session answer as a row; delete the files
A get_session answer holds a task summary; add-local keeps only the row fields.
`turn` is {since, tok, out, calls, lastAt, lastMsg, pts, partial}: the tokens
of the turns that the reported total does not hold yet (output is a floor until
a turn ends), and [epoch seconds, tokens so far] points, one per 10 minutes.
PREV.json, the newest sync document already on the board, lets the count
continue from where the last reading stopped. Claude Code adds an ended turn
to the reported total late, sometimes hours late, so while that total stays
the same the count runs on through the ends of turns. The collection decides whose sync it is: the
board owner writes `syncs`; every other person writes
`data/users/me/profile/syncs`, which only that person and the owner can read.
"""
import argparse, datetime as dt, glob, json, os, re, sys, time

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


TURN_CAP = 30       # event pages per session per sync; a longer turn is a floor until the next sync
BUCKET = 600        # seconds; turn points keep the last total in each 10-minute bucket
STATE = '/tmp/turns.json'


def load_page(path):
    """One list_events answer: (events, has_more, first_id)."""
    txt = open(path).read()
    i = txt.find('{"ccr"')
    d, _ = json.JSONDecoder().raw_decode(txt[i if i >= 0 else txt.find('{'):])
    c = d.get('ccr') or d
    return c.get('data') or [], bool(c.get('has_more')), c.get('first_id')


def turns_plan(sync_path, prev_path):
    sync = json.load(open(sync_path))
    prev = {}
    if prev_path and os.path.exists(prev_path):
        p = json.load(open(prev_path))
        p = p.get('data', p) if isinstance(p.get('data'), dict) else p
        prev = {r['id']: r for r in p.get('sessions', []) if isinstance(r, dict) and r.get('id')}
    state = {}
    for r in sync['sessions']:
        if r['id'] == sync.get('by') or r.get('via') == 'get':     # no events from a Cowork session: they refuse a cloud caller
            continue
        o = prev.get(r['id']) or {}
        # Claude Code adds the tokens of ended turns to the session total late, sometimes hours late. While the
        # reported total stays the same, the turn counts of the last reading are still outside it: carry them,
        # also for a session that no longer runs.
        keep = o.get('turn') if isinstance(o.get('turn'), dict) and o.get('tok') == r['tok'] else None
        if r['status'] != 'running' and not keep:
            continue
        state[r['id']] = {'prev': keep, 'calls': {}, 'pages': 0, 'partial': False}
    json.dump(state, open(STATE, 'w'))
    print(json.dumps({'sessions': list(state)}))


def turns_add(sid, page_path):
    state = json.load(open(STATE))
    st = state[sid]
    events, more, first = load_page(page_path)
    os.remove(page_path)
    st['pages'] += 1
    prev = st['prev'] or {}
    stop = False
    for e in sorted(events, key=lambda x: x.get('created_at') or '', reverse=True):
        at = e.get('created_at') or ''
        if 'result' in e:                       # the end of a turn
            if not prev:                        # no carried counts: the reported total holds that turn
                stop = True
                break
            continue                            # carried counts: the reported total does not hold it yet
        if prev.get('lastAt') and at <= prev['lastAt']:
            stop = True
            break
        m = ((e.get('assistant') or {}).get('internal_anthropic_catchall') or {}).get('message') or {}
        mid, u = m.get('id'), m.get('usage') or {}
        if mid and mid == prev.get('lastMsg'):    # the newest call that the last reading counted
            stop = True
            break
        if not mid:
            continue
        tok = sum(int(u.get(k) or 0) for k in ('input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens', 'output_tokens'))
        old = st['calls'].get(mid)
        st['calls'][mid] = [min(at, old[0]) if old else at, max(tok, old[1] if old else 0), max(int(u.get('output_tokens') or 0), old[2] if old else 0)]
    go = more and not stop and st['pages'] < TURN_CAP
    if more and not stop and not go:
        st['partial'] = True
    json.dump(state, open(STATE, 'w'))
    print(json.dumps({'more': go, 'before_id': first if go else None}))


def turns_merge(sync_path):
    sync = json.load(open(sync_path))
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    rows = {r['id']: r for r in sync['sessions']}
    told = 0
    for sid, st in state.items():
        prev = st['prev']
        calls = sorted(st['calls'].items(), key=lambda kv: kv[1][0])
        if not calls and not prev:
            continue
        tok, out, pts = (prev or {}).get('tok', 0), (prev or {}).get('out', 0), [list(p) for p in (prev or {}).get('pts', [])]
        for mid, (at, t, o) in calls:
            tok += t
            out += o
            sec = int(dt.datetime.fromisoformat(at.replace('Z', '+00:00')).timestamp())
            if pts and pts[-1][0] // BUCKET == sec // BUCKET:
                pts[-1] = [sec, tok]
            else:
                pts.append([sec, tok])
        turn = {'since': (prev or {}).get('since') or (calls[0][1][0][:19] + 'Z'), 'tok': tok, 'out': out,
                'calls': (prev or {}).get('calls', 0) + len(calls),
                'lastAt': calls[-1][1][0] if calls else prev['lastAt'], 'lastMsg': calls[-1][0] if calls else prev['lastMsg'], 'pts': pts}
        if st['partial'] or (prev or {}).get('partial'):
            turn['partial'] = True
        if sid in rows:
            rows[sid]['turn'] = turn
            told += tok
    json.dump(sync, open(sync_path, 'w'), ensure_ascii=False)
    if os.path.exists(STATE):
        os.remove(STATE)
    print(json.dumps({'sessions': len([r for r in sync['sessions'] if 'turn' in r]), 'turn_tok': told}))


def local_ids(sync_path, ses_dir):
    """The ids of sessions that report to the board (saved session documents in ses_dir) and that the listing lacks.
    list_sessions leaves out Cowork sessions, but get_session answers for them by id."""
    have = {r['id'] for r in json.load(open(sync_path))['sessions']}
    ids = []
    for f in sorted(glob.glob(os.path.join(ses_dir, '**', '*.json'), recursive=True)):
        sid = os.path.basename(f)[:-len('.json')]
        if re.fullmatch(r'session_[A-Za-z0-9]+', sid) and sid not in have and sid not in ids:
            ids.append(sid)
    print(json.dumps({'ids': ids}))


def add_local(sync_path, answers, daily_path=None):
    """Add get_session answers to the reading, each row marked via: get. An answer holds a task summary and other
    text; the script keeps only the fields of row() and deletes the file."""
    sync = json.load(open(sync_path))
    have = {r['id'] for r in sync['sessions']}
    added = 0
    for path in answers:
        txt = open(path).read()
        os.remove(path)
        i = txt.find('{"ccr"')
        if i < 0:
            i = txt.find('{')
        try:
            d, _ = json.JSONDecoder().raw_decode(txt[i:]) if i >= 0 else ({}, 0)
        except ValueError:
            continue
        s = d.get('ccr') if isinstance(d.get('ccr'), dict) else d
        if not isinstance(s, dict) or not str(s.get('id', '')).startswith('session_') or s['id'] in have:
            continue
        r = row(s)
        r['via'] = 'get'
        sync['sessions'].append(r)
        have.add(s['id'])
        added += 1
    json.dump(sync, open(sync_path, 'w'), ensure_ascii=False)
    if daily_path:
        json.dump(daily_doc(sync), open(daily_path, 'w'), ensure_ascii=False)
    print(json.dumps({'added': added, 'tok': sum(r['tok'] for r in sync['sessions'] if r.get('via') == 'get')}))


def iso(epoch):
    return dt.datetime.fromtimestamp(epoch, dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


DAILY_COLS = ['id', 'title', 'status', 'tok', 'out', 'usd', 'createdAt', 'repo', 'via']


def daily_doc(sync):
    """The ledger entry of a UTC day, from one sync document: the totals at that reading."""
    rows = [[r['id'], r['title'], r['status'], r['tok'], r['out'], r['usd'], r['createdAt'], (r.get('repos') or [''])[0], r.get('via', '')]
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
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'turns-plan':
        args = sys.argv[2:]
        prev = args[args.index('--prev') + 1] if '--prev' in args else None
        return turns_plan(args[0], prev)
    if cmd == 'turns-add':
        return turns_add(sys.argv[2], sys.argv[3])
    if cmd == 'turns-merge':
        return turns_merge(sys.argv[2])
    if cmd == 'local-ids':
        return local_ids(sys.argv[2], sys.argv[3])
    if cmd == 'add-local':
        args = sys.argv[2:]
        daily = args[args.index('--daily') + 1] if '--daily' in args else None
        files = [a for i, a in enumerate(args[1:], 1) if a != '--daily' and args[i - 1] != '--daily']
        return add_local(args[0], files, daily)
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
