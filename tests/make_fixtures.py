#!/usr/bin/env python3
"""Write the synthetic fixtures in tests/fixtures/db. The names and numbers are invented.

The board owner has three projects that mirror three real situations:
  Atlas port     runs now; its tokens grow between every hourly sync
  Harbor docs    idle: 9 B lifetime tokens, nothing moves between syncs, its session updated 80 min ago
  Quarterly model idle for two days: 1.2 B lifetime tokens
Drew and Priya each have a private subtree that only they and the owner read.
The owner also has a daily ledger for 30 Sep to 2 Oct. It holds a session that the newest sync no longer lists,
and two titles that stress the CSV export (a comma and a quote, and a leading "=").
Oct 3 has hourly readings and no ledger entry, so the page must fill it.
The fixtures' clock is 2026-10-04T00:25:00Z.
"""
import datetime as dt, json, os, shutil

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', 'db')
U = dt.timezone.utc
iso = lambda t: t.strftime('%Y-%m-%dT%H:%M:%SZ')
at = lambda *a: dt.datetime(*a, tzinfo=U)


def put(col, doc_id, doc):
    d = os.path.join(ROOT, col)
    os.makedirs(d, exist_ok=True)
    json.dump(doc, open(os.path.join(d, f'{doc_id}.json'), 'w'), indent=1, ensure_ascii=False)


def sess(sid, title, repo, status, bucket, tok, created, updated, usd):
    return {'id': sid, 'title': title, 'status': status, 'bucket': bucket, 'model': 'claude-sonnet-5-5', 'createdAt': iso(created),
            'updatedAt': iso(updated), 'tok': tok, 'out': tok // 90, 'usd': usd, 'repos': [repo]}


shutil.rmtree(ROOT, ignore_errors=True)
syncs = [at(2026, 10, 3, 22, 26), at(2026, 10, 3, 23, 26), at(2026, 10, 4, 0, 23)]
grow = [0, 40_000_000, 95_000_000]
quota = lambda t: {'status': 'allowed', 'type': 'five_hour', 'resetsAt': '2026-10-04T03:00:00Z', 'overage': False, 'asOf': iso(t)}
for t, g in zip(syncs, grow):
    rows = [
        sess('session_01ATLAS01', 'Atlas port: build the importer', 'owner/atlas-port', 'running', 'working', 300_000_000 + g, at(2026, 10, 2, 9), t, round((300e6 + g) * 1e-6, 2)),
        sess('session_01HARBOR1', 'Harbor docs: resume the crawl', 'owner/harbor-docs', 'idle', 'blocked', 9_000_000_000, at(2026, 9, 12, 14), at(2026, 10, 3, 23, 5), 8700.0),
        sess('session_01HARBOR2', 'Harbor docs: first pass', 'owner/harbor-docs', 'archived', 'completed', 1_300_000_000, at(2026, 9, 12, 1), at(2026, 9, 13, 5), 960.0),
        sess('session_01MODEL01', 'Quarterly model: dashboards', 'owner/quarterly-model', 'idle', 'completed', 1_200_000_000, at(2026, 9, 7, 1), at(2026, 10, 1, 21, 30), 1130.0),
    ]
    put('syncs', str(int(t.timestamp())), {'at': iso(t), 'src': 'routine', 'sessions': rows, 'quota': quota(t)})
put('projects', 'atlas-port', {'name': 'Atlas port', 'where': 'cloud', 'surface': 'Claude Code · cloud', 'sessions': ['session_01ATLAS01'], 'repos': ['owner/atlas-port'], 'color': 1})
put('projects', 'harbor-docs', {'name': 'Harbor docs', 'where': 'cloud', 'surface': 'Claude Code · cloud', 'sessions': ['session_01HARBOR1', 'session_01HARBOR2'], 'repos': ['owner/harbor-docs'], 'color': 2})
put('projects', 'quarterly-model', {'name': 'Quarterly model', 'where': 'cloud', 'surface': 'Claude Code · cloud', 'sessions': ['session_01MODEL01'], 'repos': ['owner/quarterly-model'], 'color': 3})
put('jobs', 'atlas-import', {'project': 'Atlas port', 'label': 'Import the 2024 archive', 'status': 'running', 'surface': 'Claude Code · cloud', 'total': 10, 'done': 4,
                             'unit': 'files', 'startedAt': '2026-10-03T22:30:00Z', 'updatedAt': '2026-10-04T00:20:00Z', 'estSec': 14400, 'tokEst': 600_000_000})
put('jobs', 'atlas-schema', {'project': 'Atlas port', 'label': 'Schema draft', 'status': 'done', 'surface': 'Claude Code · cloud', 'startedAt': '2026-10-03T20:00:00Z',
                             'finishedAt': '2026-10-03T21:10:00Z', 'updatedAt': '2026-10-03T21:10:00Z'})
# the daily ledger: the first reading of each UTC day
COLS = ['id', 'title', 'status', 'tok', 'out', 'usd', 'createdAt', 'repo']
def ledger(day, harbor, model, atlas, retire):
    rows = [['session_01HARBOR1', 'Harbor docs: resume the crawl', 'idle', harbor, harbor // 90, round(harbor * 9.6e-7, 2), '2026-09-12T14:00:00Z', 'owner/harbor-docs'],
            ['session_01HARBOR2', 'Harbor docs: first pass', 'archived', 1_300_000_000, 14_000_000, 960.0, '2026-09-12T01:00:00Z', 'owner/harbor-docs'],
            ['session_01MODEL01', 'Quarterly model: dashboards', 'idle', model, model // 90, round(model * 9.4e-7, 2), '2026-09-07T01:00:00Z', 'owner/quarterly-model'],
            ['session_01RETIRE1', 'Weekly "export", v2', 'idle', retire, retire // 90, round(retire * 1.1e-6, 2), '2026-09-20T10:00:00Z', 'owner/retired-experiment'],
            ['session_01FORMULA', '=SUM(1,1) test', 'idle', 5_000_000, 50_000, 6.0, '2026-09-29T10:00:00Z', 'owner/retired-experiment']]
    if atlas:
        rows.append(['session_01ATLAS01', 'Atlas port: build the importer', 'running', atlas, atlas // 90, round(atlas * 1e-6, 2), '2026-10-02T09:00:00Z', 'owner/atlas-port'])
    put('daily', day, {'day': day, 'at': f'{day}T00:26:00Z', 'src': 'routine', 'cols': COLS, 'rows': rows})
ledger('2026-09-30', 8_600_000_000, 1_000_000_000, 0, 400_000_000)
ledger('2026-10-01', 8_800_000_000, 1_150_000_000, 0, 400_000_000)
ledger('2026-10-02', 8_950_000_000, 1_200_000_000, 120_000_000, 400_000_000)
put('meta', 'quota', {'status': 'allowed', 'type': 'five_hour', 'resetsAt': '2026-10-04T03:00:00Z', 'overage': False, 'updatedAt': '2026-10-04T00:23:00Z'})

# Drew: three syncs; one session grows
for t, g in zip(syncs, [0, 30_000_000, 55_000_000]):
    rows = [sess('session_01DREW001', 'Clinic scheduler rebuild', 'drew/clinic-scheduler', 'running' if g else 'idle', 'working' if g else 'completed', 210_000_000 + g,
                 at(2026, 10, 2, 15), t if g else at(2026, 10, 3, 22), round((210e6 + g) * 1.4e-6, 2)),
            sess('session_01DREW002', 'Patient FAQ site', 'drew/faq-site', 'idle', 'review_ready', 96_000_000, at(2026, 10, 1, 9), at(2026, 10, 2, 1), 130.0)]
    put('data__users__u_drew__profile__syncs', str(int(t.timestamp())), {'at': iso(t), 'src': 'routine', 'sessions': rows, 'quota': quota(t)})
put('data__users__u_drew', 'profile', {'quota': {'status': 'allowed', 'type': 'five_hour', 'resetsAt': '2026-10-04T03:00:00Z', 'overage': False, 'updatedAt': '2026-10-04T00:23:00Z'}})
put('join', 'u_drew', {'name': 'Drew', 'joinedAt': '2026-10-03T22:10:00Z', 'seenAt': '2026-10-04T00:20:00Z'})

# Priya: one sync; the owner sees it, Drew does not
put('data__users__u_priya__profile__syncs', '1791073380', {'at': '2026-10-04T00:23:00Z', 'src': 'routine',
    'sessions': [sess('session_01PRIYA01', 'Grant figure pipeline', 'priya/figures', 'idle', 'completed', 77_000_000, at(2026, 10, 1, 9), at(2026, 10, 2, 1), 95.0)]})
put('join', 'u_priya', {'name': 'Priya', 'joinedAt': '2026-10-03T22:40:00Z', 'seenAt': '2026-10-03T22:40:00Z'})
print('wrote', ROOT)
