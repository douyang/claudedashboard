#!/usr/bin/env python3
"""Helpers for the sub-agent that runs the hourly sync (docs/SYNC_AGENT.md). They run scripts/ccr_sync_doc.py.

Usage:
  python3 scripts/sync_agent.py plan LS_FILE [LS_FILE ...] --at T [--dir /tmp]
  python3 scripts/sync_agent.py rows [--dir /tmp]

Both use the files of docs/SYNC.md in --dir: sync.json, daily.json, ses/ (the saved session documents),
prev/ (the saved earlier readings), rl.txt (a rate-limit event page), gs<N>.txt (the get_session count fields),
and plan.json.

plan makes the reading from the list_sessions answers, saves plan.json, and prints it as one JSON line:
  age_min, newest   the age in minutes at T and the doc id of the newest earlier reading; null when there is none
  skip              the reply when that reading is less than 30 minutes old; absent otherwise
  doc_id, day, sessions, tok, more, after_id   from the reading; sessions and tok count the listing only
  ids               the sessions that report to the board and that the listing lacks: read them with get_session
  turns             the sessions whose turns docs/SYNC.md steps 12 and 13 read

rows adds the limit shares from rl.txt and the gs<N>.txt files to the reading, checks the rows, and prints one
JSON line: limits (the output of ccr_sync_doc.py limits, when rl.txt exists), added, checked, dropped, kept and
line, the reply. Run it again after each further rate-limit page; it reads each page once. The sync copies the count fields of each get_session answer by hand. A
Claude Code session total never falls, and it changes only together with updated_at. A get_session row that
breaks either rule against the newest earlier reading holds a copy error: rows drops it and writes the ledger
entry again. A missing row is better than a wrong one: the board measures across the gap.
"""
import argparse
import datetime as dt
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ccr_sync_doc import daily_doc  # noqa: E402

DOC = os.path.join(HERE, 'ccr_sync_doc.py')
SKIP_MIN = 30


def run(*args):
    """Run one ccr_sync_doc.py command and return its last output line."""
    out = subprocess.run([sys.executable, DOC, *args], check=True, capture_output=True, text=True).stdout
    return (out.strip().splitlines() or [''])[-1]


def error(e):
    """The last line of a failed command's error output."""
    txt = (getattr(e, 'stderr', '') or str(e)).strip().splitlines()
    return txt[-1] if txt else type(e).__name__


def epoch(iso):
    return int(dt.datetime.fromisoformat(iso.replace('Z', '+00:00')).timestamp())


def earlier(d):
    """The saved earlier readings, newest first, as (doc id, path). A doc id is the epoch second of its reading."""
    docs = [(os.path.basename(p)[:-len('.json')], p) for p in glob.glob(os.path.join(d, 'prev', '**', '*.json'), recursive=True)]
    return sorted([x for x in docs if x[0].isdigit()], key=lambda x: int(x[0]), reverse=True)


def plan(a):
    d, prev = a.dir, earlier(a.dir)
    sync = os.path.join(d, 'sync.json')
    out = {'age_min': None, 'newest': None}
    if prev:
        age = (epoch(a.at) - int(prev[0][0])) // 60
        out = {'age_min': age, 'newest': prev[0][0]}
        if age < SKIP_MIN:
            out['skip'] = f'Skipped: syncs/{prev[0][0]} is {age} minutes old.'
    out.update(json.loads(run(*a.answers, sync, '--daily', os.path.join(d, 'daily.json'), '--at', a.at)))
    out['ids'] = json.loads(run('local-ids', sync, os.path.join(d, 'ses')))['ids']
    out['turns'] = json.loads(run('turns-plan', sync, *[x for _, p in prev for x in ('--prev', p)]))['sessions']
    out['at'] = a.at
    json.dump(out, open(os.path.join(d, 'plan.json'), 'w'))
    print(json.dumps(out))


def check(d):
    """Drop the get_session rows that disagree with the newest earlier reading."""
    path = os.path.join(d, 'sync.json')
    sync = json.load(open(path))
    prev = {}
    for _, p in earlier(d):
        doc = json.load(open(p))
        doc = doc.get('data', doc) if isinstance(doc.get('data'), dict) else doc
        if (doc.get('at') or '') < sync['at']:
            prev = doc
            break
    old = {r['id']: r for r in prev.get('sessions', []) if isinstance(r, dict) and r.get('id')}
    keep, checked, dropped = [], 0, 0
    for r in sync['sessions']:
        o = old.get(r['id'])
        if r.get('via') == 'get' and o:
            checked += 1
            same = r.get('updatedAt') == o.get('updatedAt')
            if r['tok'] < int(o.get('tok') or 0) or (same and (r['tok'], r['out'], r['usd']) != (o.get('tok'), o.get('out'), o.get('usd'))):
                dropped += 1
                continue
        keep.append(r)
    sync['sessions'] = keep
    json.dump(sync, open(path, 'w'), ensure_ascii=False)
    json.dump(daily_doc(sync), open(os.path.join(d, 'daily.json'), 'w'), ensure_ascii=False)
    return {'checked': checked, 'dropped': dropped, 'kept': sum(1 for r in keep if r.get('via') == 'get'), 'sync': sync}


def rows(a):
    d = a.dir
    p = json.load(open(os.path.join(d, 'plan.json')))
    out, failed, rl = {}, [], os.path.join(d, 'rl.txt')
    if os.path.exists(rl):                  # limits deletes the page
        try:
            out['limits'] = json.loads(run('limits', os.path.join(d, 'sync.json'), rl))
        except (subprocess.CalledProcessError, ValueError) as e:
            failed.append(f'Rate limits failed: {error(e)}.')
    gs = sorted(glob.glob(os.path.join(d, 'gs*.txt')))
    out['added'] = 0
    if gs:
        try:
            out.update(json.loads(run('add-local', os.path.join(d, 'sync.json'), '--daily', os.path.join(d, 'daily.json'), *gs)))
        except (subprocess.CalledProcessError, ValueError) as e:
            failed.append(f'Cowork rows failed: {error(e)}.')
    c = check(d)
    sync = c.pop('sync')
    out.update(c)
    line = f"Synced {p['sessions']} sessions, {p['tok']:,} tokens at {p['at']}."
    if p['ids']:
        line += f" Cowork: {c['kept']} sessions." if c['kept'] == len(p['ids']) else f" Cowork: {c['kept']} of {len(p['ids'])} sessions."
    w = (sync.get('quota') or {}).get('windows') or {}
    shares = [f'{name} {w[k]["pct"]:g}%' for k, name in (('five_hour', '5 h'), ('seven_day', '7 d')) if isinstance(w.get(k), dict)]
    if shares:
        line += f" Limits: {', '.join(shares)}."
    if c['dropped']:
        line += f" Dropped {c['dropped']} Cowork rows with copy errors."
    if p['turns']:
        line += ' Skipped steps 12 and 13.'
    out['line'] = ' '.join([line] + failed)
    print(json.dumps(out))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    pl = sub.add_parser('plan')
    pl.add_argument('answers', nargs='+', help='the list_sessions answer files')
    pl.add_argument('--at', required=True, help='T, the UTC time of the reading')
    pl.add_argument('--dir', default='/tmp')
    ro = sub.add_parser('rows')
    ro.add_argument('--dir', default='/tmp')
    a = ap.parse_args()
    plan(a) if a.cmd == 'plan' else rows(a)


if __name__ == '__main__':
    main()
