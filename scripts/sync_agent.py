#!/usr/bin/env python3
"""Helpers for the sub-agent that runs the hourly sync (docs/SYNC_AGENT.md). They run scripts/ccr_sync_doc.py.

Usage:
  python3 scripts/sync_agent.py plan LS_FILE [LS_FILE ...] --at T [--dir /tmp]
  python3 scripts/sync_agent.py runs TR_FILE [--dir /tmp]
  python3 scripts/sync_agent.py rows [--dir /tmp]

They use the files of docs/SYNC.md in --dir: sync.json, daily.json, ses/ (the saved session documents),
prev/ (the saved earlier readings), rl.txt (a rate-limit event page), gs<N>.txt (the get_session count fields),
and plan.json.

plan makes the reading from the list_sessions answers, saves plan.json, and prints it as one JSON line:
  age_min, newest   the age in minutes at T and the doc id of the newest earlier reading; null when there is none
  skip              the reply when that reading is less than 30 minutes old; absent otherwise
  doc_id, day, sessions, tok, more, after_id   from the reading; sessions and tok count the listing only
  ids               the sessions that report to the board and that the listing lacks: read them with get_session.
                    A session document marked `gone` is left out: get_session no longer finds that session.
  turns             the sessions whose turns docs/SYNC.md steps 12 and 13 read

runs adds the scheduled tasks that start a fresh session for each run. The listing leaves out such runs. TR_FILE
holds the list_triggers answer, or one line per task with id, name, persist_session and last_run.session_id. runs
saves the new runs in plan.json and prints one JSON line: ids, the Cowork ids of plan and the session of each new
run, and runs, the number of new runs. A task's newest run is new when no earlier reading counted it and nothing
else covers it: the listing, a session document or the Cowork ids. A counted run that was running then is read again.

rows adds the limit shares from rl.txt and the gs<N>.txt files to the reading, checks the rows, and prints one
JSON line: limits (the output of ccr_sync_doc.py limits, when rl.txt exists), added, checked, dropped, kept, runs and
line, the reply. Run it again after each further rate-limit page; it reads each page once. The sync copies the count fields of each get_session answer by hand. A
Claude Code session total never falls, and it changes only together with updated_at. A get_session row that
breaks either rule against the newest earlier reading holds a copy error: rows drops it and writes the ledger
entry again. A missing row is better than a wrong one: the board measures across the gap.
Each scheduled task has one row (via: trigger, id: the task id) that carries the totals of its counted runs from
reading to reading, so the ledger keeps them. rows adds each new run to its task's row, with runs (the count),
lastRun (the session id) and last (the run's own totals).
"""
import argparse
import datetime as dt
import glob
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ccr_sync_doc import daily_doc, row  # noqa: E402

DOC = os.path.join(HERE, 'ccr_sync_doc.py')
SKIP_MIN = 30
TASK = 'trigger'        # the `via` of a scheduled task's row


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


def unwrap(o):
    return o.get('data') if isinstance(o, dict) and isinstance(o.get('data'), dict) else o


def saved_docs(d):
    """The saved session documents, {doc id: fields}."""
    out = {}
    for f in glob.glob(os.path.join(d, 'ses', '**', '*.json'), recursive=True):
        try:
            o = unwrap(json.load(open(f)))
        except (OSError, ValueError):
            continue
        if isinstance(o, dict):
            out[os.path.basename(f)[:-len('.json')]] = o
    return out


def answer(path):
    """The first JSON object in a saved tool answer, out of its "ccr" envelope; None when there is none."""
    txt = open(path, encoding='utf-8', errors='replace').read()
    i = txt.find('{"ccr"')
    i = i if i >= 0 else txt.find('{')
    try:
        o = json.JSONDecoder().raw_decode(txt[i:])[0] if i >= 0 else None
    except ValueError:
        return None
    return (o['ccr'] if isinstance(o.get('ccr'), dict) else o) if isinstance(o, dict) else None


def tasks(path):
    """The scheduled tasks in a list_triggers answer, or in a file with one task per line."""
    a = answer(path)
    if a and isinstance(a.get('data'), list):
        return [t for t in a['data'] if isinstance(t, dict)]
    out = []
    for ln in open(path, encoding='utf-8', errors='replace'):
        try:
            t = json.loads(ln) if ln.strip().startswith('{') else None
        except ValueError:
            continue
        if isinstance(t, dict):
            out.append(t)
    return out


def task_rows(d):
    """The row of each scheduled task, from the newest earlier reading that holds it."""
    rows = {}
    for _, p in earlier(d):
        doc = unwrap(json.load(open(p)))
        for r in doc.get('sessions') or []:
            if isinstance(r, dict) and r.get('via') == TASK and r.get('id'):
                rows.setdefault(r['id'], r)
    return rows


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
    saved = saved_docs(d)
    out['ids'] = [i for i in json.loads(run('local-ids', sync, os.path.join(d, 'ses')))['ids'] if not (saved.get(i) or {}).get('gone')]
    out['turns'] = json.loads(run('turns-plan', sync, *[x for _, p in prev for x in ('--prev', p)]))['sessions']
    out['at'] = a.at
    json.dump(out, open(os.path.join(d, 'plan.json'), 'w'))
    print(json.dumps(out))


def runs(a):
    d = a.dir
    path = os.path.join(d, 'plan.json')
    p = json.load(open(path))
    have = {r['id'] for r in json.load(open(os.path.join(d, 'sync.json')))['sessions']} | set(saved_docs(d)) | set(p['ids'])
    rows, new = task_rows(d), []
    for f in a.files:
        for t in tasks(f):
            tid = str(t.get('id') or '')
            last = t.get('last_run') if isinstance(t.get('last_run'), dict) else {}
            sid = str(last.get('session_id') or '')
            sid = 'session_' + sid[4:] if sid.startswith('cse_') else sid
            if t.get('persist_session') is not False or not re.fullmatch(r'trig_[A-Za-z0-9]+', tid) or not re.fullmatch(r'session_[A-Za-z0-9]+', sid):
                continue
            o = rows.get(tid) or {}
            if sid in have or any(x['sid'] == sid for x in new) or (o.get('lastRun') == sid and o.get('status') != 'running'):
                continue
            new.append({'trigger': tid, 'name': str(t.get('name') or tid), 'sid': sid})
    p['runs'] = new
    json.dump(p, open(path, 'w'))
    print(json.dumps({'ids': p['ids'] + [x['sid'] for x in new], 'runs': len(new)}))


def scheduled(d, p, answers):
    """Write each scheduled task's row into the reading: its row from an earlier reading, with the run that this sync
    read added. A run read again replaces its own earlier totals. Return the number of runs counted."""
    path = os.path.join(d, 'sync.json')
    sync = json.load(open(path))
    rows, counted = task_rows(d), 0
    done = {r['id']: r for r in sync['sessions'] if r.get('via') == TASK}       # rows runs more than once in a sync
    rows.update(done)
    for x in p.get('runs') or []:
        s = answers.get(x['sid'])
        if not s:
            counted += (done.get(x['trigger']) or {}).get('lastRun') == x['sid']
            continue
        r = row(s)
        usd = float(((s.get('external_metadata') or {}).get('usage') or {}).get('cost_usd') or 0)
        o = dict(rows.get(x['trigger']) or {'id': x['trigger'], 'via': TASK, 'createdAt': r['createdAt'], 'repos': [], 'tok': 0, 'out': 0, 'usd': 0, 'runs': 0})
        again = o.get('lastRun') == x['sid']
        last = o.get('last') if again and isinstance(o.get('last'), dict) else {}
        if r['tok'] < int(last.get('tok') or 0):          # a run's total never falls: the copy is wrong
            continue
        o.update({'title': x['name'], 'status': r['status'], 'bucket': 'working' if r['status'] == 'running' else 'completed',
                  'model': r['model'], 'updatedAt': r['updatedAt'], 'runs': int(o.get('runs') or 0) + (0 if again else 1), 'lastRun': x['sid'],
                  'tok': int(o.get('tok') or 0) - int(last.get('tok') or 0) + r['tok'],
                  'out': int(o.get('out') or 0) - int(last.get('out') or 0) + r['out'],
                  'usd': round(float(o.get('usd') or 0) - float(last.get('usd') or 0) + usd, 4),
                  'last': {'tok': r['tok'], 'out': r['out'], 'usd': round(usd, 4)}})
        rows[x['trigger']] = o
        counted += 1
    sync['sessions'] = [r for r in sync['sessions'] if r.get('via') != TASK] + [r for _, r in sorted(rows.items())]
    json.dump(sync, open(path, 'w'), ensure_ascii=False)
    return counted


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
    want, gs, got = {x['sid'] for x in p.get('runs') or []}, [], {}
    for f in sorted(glob.glob(os.path.join(d, 'gs*.txt'))):
        s = answer(f) if want else None
        if s and s.get('id') in want:                # a run of a scheduled task: its counts go to the task's row
            got[s['id']] = s
            os.remove(f)
        else:
            gs.append(f)
    out['added'] = 0
    if gs:
        try:
            out.update(json.loads(run('add-local', os.path.join(d, 'sync.json'), '--daily', os.path.join(d, 'daily.json'), *gs)))
        except (subprocess.CalledProcessError, ValueError) as e:
            failed.append(f'Cowork rows failed: {error(e)}.')
    out['runs'] = 0
    try:
        out['runs'] = scheduled(d, p, got)
    except (OSError, ValueError, KeyError, TypeError) as e:
        failed.append(f'Scheduled rows failed: {error(e)}.')
    c = check(d)
    sync = c.pop('sync')
    out.update(c)
    line = f"Synced {p['sessions']} sessions, {p['tok']:,} tokens at {p['at']}."
    if p['ids']:
        line += f" Cowork: {c['kept']} sessions." if c['kept'] == len(p['ids']) else f" Cowork: {c['kept']} of {len(p['ids'])} sessions."
    n, m = out['runs'], len(p.get('runs') or [])
    if m:
        line += f" Scheduled: {n} {'run' if n == 1 else 'runs'}." if n == m else f" Scheduled: {n} of {m} runs."
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
    ru = sub.add_parser('runs')
    ru.add_argument('files', nargs='+', help='the list_triggers answer, or the file of one line per task')
    ru.add_argument('--dir', default='/tmp')
    ro = sub.add_parser('rows')
    ro.add_argument('--dir', default='/tmp')
    a = ap.parse_args()
    {'plan': plan, 'runs': runs, 'rows': rows}[a.cmd](a)


if __name__ == '__main__':
    main()
