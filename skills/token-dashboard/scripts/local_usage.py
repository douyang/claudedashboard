#!/usr/bin/env python3
"""Measure a local session's own token usage from its transcript, for the Claude dashboard.

Usage:
  python3 local_usage.py [--session-id ID] [--root DIR]

Claude Code (CLI, desktop, IDE) and Cowork keep each session's transcript as JSON lines in
<root>/projects/<folder>/<session id>.jsonl, and the transcripts of its subagents in
<root>/projects/<folder>/<session id>/subagents/. <root> is --root, else $CLAUDE_CONFIG_DIR, else ~/.claude.
Without --session-id the script takes the main transcript written most recently: the session that runs the
script writes its own transcript while it works.

The script reads only message ids, times and token counts, and Claude Code's own running totals (the
cost-state records). It never prints message text and it changes no file. It prints one JSON line:
  {sessionId, tok, out, usd, usdAt, calls, since, lastAt, untimed, pts, src, files}
- tok counts input, cache reads, cache writes and output, each model call once.
- usd is Claude Code's own cost figure at usdAt. It is absent when the transcript holds no cost-state record.
- untimed: tokens that Claude Code counted but whose call records the transcript no longer holds. They
  count in tok and in no point.
- pts: [epoch seconds, tokens so far] points. Each 10-minute bucket with model calls gives its last total.
  A bucket after a gap first gives the total before it, so its tokens fall inside the bucket.
"""
import argparse, datetime as dt, glob, json, os, sys

BUCKET = 600
MAX_PTS = 2000
KEYS = ('input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens', 'output_tokens')
TRACKER_KEYS = ('inputTokens', 'cacheReadInputTokens', 'cacheCreationInputTokens', 'outputTokens')


def roots(arg):
    tried = [r for r in ((arg,) if arg else (os.environ.get('CLAUDE_CONFIG_DIR'), os.path.expanduser('~/.claude'))) if r]
    return [r for i, r in enumerate(tried) if r not in tried[:i] and os.path.isdir(os.path.join(r, 'projects'))], tried


def find(where, sid):
    cands = [c for r in where for c in glob.glob(os.path.join(r, 'projects', '*', '*.jsonl'))]
    if sid:
        cands = [c for c in cands if os.path.basename(c)[:-len('.jsonl')] == sid]
    return max(cands, key=os.path.getmtime) if cands else None


def sec(ts):
    try:
        return int(dt.datetime.fromisoformat(str(ts).replace('Z', '+00:00')).timestamp())
    except ValueError:
        return None


def iso(s):
    return dt.datetime.fromtimestamp(s, dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def read(path, calls, trackers):
    """Add the model calls of one transcript to calls; append its cost-state records to trackers, if given."""
    last = None
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if not isinstance(e, dict):
                continue
            at = sec(e['timestamp']) if isinstance(e.get('timestamp'), str) else None
            if at is not None:
                last = at
            if e.get('type') == 'cost-state':
                if trackers is not None:
                    trackers.append((e, last))
                continue
            m = e.get('message') if e.get('type') == 'assistant' else None
            if not isinstance(m, dict) or not m.get('id') or not isinstance(m.get('usage'), dict) or at is None:
                continue
            u = m['usage']
            tok = sum(int(u.get(k) or 0) for k in KEYS)
            out = int(u.get('output_tokens') or 0)
            old = calls.get(m['id'])     # one call writes one line per content block, with the same id
            calls[m['id']] = [min(at, old[0]), max(tok, old[1]), max(out, old[2])] if old else [at, tok, out]


def tracker(trackers):
    """Claude Code's own running totals at its newest cost-state record."""
    if not trackers:
        return None
    e, at = trackers[-1]
    mu = [v for v in (e.get('modelUsage') or {}).values() if isinstance(v, dict)]
    return {'tok': sum(int(v.get(k) or 0) for v in mu for k in TRACKER_KEYS),
            'out': sum(int(v.get('outputTokens') or 0) for v in mu),
            'usd': float(e.get('totalCostUSD') or 0), 'at': at}


def points(calls, start, bucket):
    pts, cum, last_b = [], start, None
    for at, tok, _ in sorted(calls):
        b = at // bucket
        if b != last_b:
            if not pts or at - pts[-1][0] > bucket:
                pts.append([at - 1, cum])    # the total before this bucket
            cum += tok
            pts.append([at, cum])
            last_b = b
        else:
            cum += tok
            pts[-1] = [at, cum]
    return pts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--session-id', help='the transcript file name without .jsonl; default: the newest transcript')
    ap.add_argument('--root', help='the Claude configuration folder; default $CLAUDE_CONFIG_DIR, else ~/.claude')
    a = ap.parse_args()
    where, tried = roots(a.root)
    main_file = find(where, a.session_id)
    if not main_file:
        print(json.dumps({'error': 'no transcript found', 'looked': [os.path.join(r, 'projects') for r in tried]}))
        sys.exit(2)
    sid = os.path.basename(main_file)[:-len('.jsonl')]
    files = [main_file] + sorted(glob.glob(os.path.join(os.path.dirname(main_file), sid, 'subagents', '*.jsonl')))
    calls, trackers = {}, []
    for i, f in enumerate(files):
        read(f, calls, trackers if i == 0 else None)
    rows = list(calls.values())
    c_tok, c_out = sum(r[1] for r in rows), sum(r[2] for r in rows)
    tok, out, doc = c_tok, c_out, {'sessionId': sid}
    tr = tracker(trackers)
    if tr:
        after = [r for r in rows if tr['at'] is not None and r[0] > tr['at']]
        tok = max(c_tok, tr['tok'] + sum(r[1] for r in after))
        out = max(c_out, tr['out'] + sum(r[2] for r in after))
        doc['usd'] = round(tr['usd'], 2)
        if tr['at'] is not None:
            doc['usdAt'] = iso(tr['at'])
    pts = points(rows, tok - c_tok, BUCKET)
    if len(pts) > MAX_PTS:
        pts = points(rows, tok - c_tok, 6 * BUCKET)
    doc.update({'tok': tok, 'out': out, 'calls': len(rows), 'untimed': tok - c_tok, 'src': 'transcript', 'files': len(files)})
    if rows:
        doc['since'], doc['lastAt'] = iso(min(r[0] for r in rows)), iso(max(r[0] for r in rows))
    doc['pts'] = pts
    print(json.dumps(doc))


if __name__ == '__main__':
    main()
