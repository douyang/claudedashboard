#!/usr/bin/env node
/* End-to-end checks of dashboard/index.html against the synthetic fixtures, in Chromium with a stub of window.claude.
 *
 *   NODE_PATH=$(npm root -g) node tests/check.mjs
 *
 * The fixtures' clock is 2026-10-04T00:25:00Z. The stub applies the same access rules as the published board:
 * the owner reads all; a person reads and writes only data/users/<id>/ and join/<id>.
 */
import { open } from '../scripts/preview.mjs';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const DB = new URL('./fixtures/db', import.meta.url).pathname;
const NOW = '2026-10-04T00:25:00Z';
let failed = 0;
const check = (name, ok, detail = '') => { console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${ok ? '' : `  ${detail}`}`); if (!ok) failed += 1; };
const rows = (page) => page.evaluate(() => Object.fromEntries([...document.querySelectorAll('#ptable tr')].slice(1).filter((r) => !r.classList.contains('sep')).map((r) => {
  const c = [...r.children].map((x) => x.innerText.trim().replace(/\s+/g, ' '));
  const tt = r.querySelector('.tt');
  return [tt ? tt.innerText.trim() : c[0], c];
})));
const headsOf = (page) => page.evaluate(() => [...document.querySelectorAll('#ptable tr')][0].querySelectorAll('th').length
  ? [...[...document.querySelectorAll('#ptable tr')][0].querySelectorAll('th')].map((th) => (th.firstChild ? th.firstChild.textContent : '').trim().toUpperCase()) : []);
const notesText = (page) => page.evaluate(() => (document.getElementById('notes-list') || {}).innerText || '');

/* ---- owner view ---- */
{
  const s = await open({ db: DB, now: NOW, viewer: 'owner', width: 1100 });
  const p = s.page;
  check('owner: page loads without errors', s.problems.length === 0, s.problems.join(' | '));
  const heads = await headsOf(p);
  const col = (n) => heads.indexOf(n);
  const R = await rows(p);
  check('density: the table has no Share column, which repeated the Tokens column', heads.length > 5 && !heads.includes('SHARE'), heads.join(','));
  const atlas = R['owner/atlas-port'], harbor = R['owner/harbor-docs'], model = R['owner/quarterly-model'];
  check('owner: the running project shows measured use in the last hour', atlas && atlas[col('1 H')] !== '—', JSON.stringify(atlas));
  check('owner: the idle project with 9 B lifetime tokens shows no use in the last hour', harbor && harbor[col('1 H')] === '—', JSON.stringify(harbor));
  check('owner: the idle project shows no use in 24 h', harbor && harbor[col('24 H')] === '—', JSON.stringify(harbor));
  check('owner: the project idle for two days shows no use in 24 h', model && model[col('24 H')] === '—', JSON.stringify(model));
  check('owner: last token use of the two-day idle project is in hours or days', model && /^\d+ (h|d)$/.test(model[col('LAST USE')]), JSON.stringify(model));
  const pills = await p.evaluate(() => Object.fromEntries([...document.querySelectorAll('.proj-card')].map((c) => [c.querySelector('h2').innerText.trim(), c.querySelector('.pill').innerText.trim()])));
  check('owner: the running project reads Working now', /^working now$/i.test(pills['owner/atlas-port']), JSON.stringify(pills));
  check('owner: the idle project reads Idle', /^idle$/i.test(pills['owner/harbor-docs']), JSON.stringify(pills));

  /* ---- names: a project is named after its repository, else its folder, else its own name ---- */
  const cards = await p.evaluate(() => Object.fromEntries([...document.querySelectorAll('.proj-card')].map((c) => [c.querySelector('h2').innerText.trim(), c.innerText])));
  check('names: a registry project shows its repository, not its old label', !!atlas && !R['Atlas port'] && !R['Harbor docs'] && !R['Quarterly model'], Object.keys(R).join(' | '));
  check('names: a job row that uses the old label keeps its project', /Import the 2024 archive/.test(cards['owner/atlas-port'] || ''), Object.keys(cards).join(' | '));
  check('names: two registry entries with one repository are one project, whatever the case',
    !!harbor && !R['Harbor notes'] && !R['Owner/Harbor-Docs'] && harbor[col('SESSIONS')].startsWith('2') && /Outline the migration notes/.test(cards['owner/harbor-docs'] || ''), JSON.stringify(harbor));
  check('names: a Cowork project with a folder and no repository is named after the folder',
    !!R.Studio && !R['Studio work'] && /\blocal\b/i.test(R.Studio[0]) && R.Studio[col('TOKENS')] === '12 M+', JSON.stringify(R.Studio));
  check('names: a Cowork session with a folder and no registry entry forms a project named after the folder',
    !!R['Field notes'] && /\blocal\b/i.test(R['Field notes'][0]) && /^3(\.0)? M\+$/.test(R['Field notes'][col('TOKENS')]), JSON.stringify(R['Field notes']));
  check('names: repository names that differ in case are one project',
    !!R['priya/figures'] && !R['Priya/Figures'] && R['priya/figures'][col('SESSIONS')].startsWith('3'), JSON.stringify(R['priya/figures']));
  check('names: a session with no repository and no folder keeps its own name', !!R['Untracked scratch work'] && /not in registry/i.test(R['Untracked scratch work'][0]), Object.keys(R).join(' | '));
  /* ---- reader: the session that takes the hourly reading runs because it reads; that is not work ---- */
  check('reader: the session that took the reading does not make its project work', /^idle$/i.test(pills['priya/figures']) && /^working now$/i.test(pills['owner/atlas-port']), JSON.stringify(pills));
  const sl = await p.evaluate(() => { const c = [...document.querySelectorAll('.proj-card')].find((x) => x.querySelector('h2').innerText.trim() === 'priya/figures'); const d = c && c.querySelector('details.sessions'); if (!d) return ''; d.open = true; return d.innerText; });
  check('reader: its row says that it took the reading, and the count shows no running session', /Took the hourly reading/.test(sl) && !/running/i.test(sl.split('\n')[0]), sl.slice(0, 200));
  /* ---- turns: Claude Code reports a running session's tokens only when its turn ends ---- */
  const lt = R['owner/long-turn'];
  check('turns: the tokens of a finished turn spread over the readings it ran through', !!lt && /^[56]\d M$/.test(lt[col('1 H')]), JSON.stringify(lt));
  const pn = await p.evaluate(() => (document.getElementById('pending-note') || {}).innerText || '');
  check('turns: a turn that still runs is named as not counted yet', /Not counted yet/.test(pn) && /owner\/pending-turn/.test(pn) && /unchanged since/.test(pn), pn);
  const hatch = await p.evaluate(() => document.querySelectorAll('#density-plot rect.pending').length);
  await (await p.$('#density-plot .seg')).hover();
  const tipGaps = await p.evaluate(() => [...document.querySelectorAll('.dtip:not([hidden]) .tr')].map((r) => { const k = r.querySelector('.k'), v = r.querySelector('.v'); return k && v ? Math.round(v.getBoundingClientRect().left - k.getBoundingClientRect().right) : -1; }));
  check('chart: the hover keeps a space between each project name and its rate', tipGaps.length > 0 && tipGaps.every((g) => g >= 6), JSON.stringify(tipGaps));
  await p.mouse.move(0, 0);
  check('turns: the chart hatches the running turn instead of showing zero', hatch > 0, String(hatch));
  const prow = await p.evaluate(() => { const c = [...document.querySelectorAll('.proj-card')].find((x) => x.querySelector('h2').innerText.trim() === 'owner/pending-turn'); const d = c && c.querySelector('details.sessions'); if (!d) return ''; d.open = true; return d.innerText; });
  check('turns: its session row says that the total has not changed', /total unchanged since/.test(prow), prow.slice(0, 200));
  const own = await p.evaluate(() => [...document.querySelectorAll('.proj-card h2 .own')].map((e) => e.innerText));
  check('names: the owner of a repository reads in a lighter tone', own.length > 0 && own.includes('owner/'), own.join(','));
  const kp = await p.evaluate(() => document.getElementById('kpis').innerText);
  const k24 = await p.evaluate(() => { const d = [...document.querySelectorAll('#kpis .kpi')].find((x) => /^last 24 h/i.test(x.querySelector('.k').textContent)); return d ? d.innerText : ''; });
  check('owner: the 24 h figure says how much of the window it measured', /\d+% measured/.test(k24), k24);
  const nt = await notesText(p);
  check('owner: tokens used before the first reading are stated, not placed in an hour', /untimed/.test(kp) && /before the first reading/.test(nt), kp);
  const note = await p.evaluate(() => { const n = document.getElementById('livenote'); return { text: n.innerText, warn: n.classList.contains('warn') }; });
  check('owner: a blocked live read is explained and does not warn', /live read off/.test(note.text) && !note.warn && /blocks the Claude Code Remote tool/.test(nt), JSON.stringify(note));
  /* ---- density: each caveat once, in numbered notes; no sentence that repeats a figure ---- */
  /* textContent: a superscript in a closed session list carries its number too, but innerText reads it as empty */
  const fns = await p.evaluate(() => [...document.querySelectorAll('sup.fn')].map((x) => [x.dataset.note, x.textContent.trim(), (x.querySelector('a') || {}).getAttribute ? x.querySelector('a').getAttribute('href') : '']));
  const lis = await p.evaluate(() => [...document.querySelectorAll('#notes-list li')].map((li) => li.id));
  const firstSeen = []; for (const [k] of fns) if (!firstSeen.includes(k)) firstSeen.push(k);
  check('notes: each superscript carries the number of its note, in page order, and every note is cited',
    fns.length > 0 && fns.every(([k, n, href]) => +n === firstSeen.indexOf(k) + 1 && href === `#note-${k}`) && JSON.stringify(lis) === JSON.stringify(firstSeen.map((k) => `note-${k}`)), JSON.stringify({ fns: fns.slice(0, 6), lis }));
  const bodyText = await p.evaluate(() => document.body.innerText);
  check('density: no narration and no sentence that repeats the chips', !/Every project, its sessions|projects are working now\.|Measured, last 24 h|Across projects|The hourly sync reads them/.test(bodyText),
    (bodyText.match(/Every project, its sessions|projects are working now\.|Measured, last 24 h|Across projects|The hourly sync reads them/) || [''])[0]);
  const words = (bodyText.match(/\S+/g) || []).length;
  check('density: the owner view of the fixtures stays under 1,400 words (1,690 before the rewrite)', words < 1400, String(words));
  const qrow = await p.evaluate(() => { const r = document.querySelector('.row.is-queued'); return r ? { one: r.classList.contains('one'), bar: !!r.querySelector('.bar'), tail: (r.querySelector('.tail') || {}).innerText || '' } : null; });
  check('density: a queued job takes one line, with its figures at the right and no empty bar', !!qrow && qrow.one && !qrow.bar && /queued/.test(qrow.tail), JSON.stringify(qrow));
  const sel = await p.evaluate(() => { const x = document.querySelector('#f-project select'); return x ? x.options.length : 0; });
  check('density: the project filter is one dropdown', sel > 3, String(sel));
  const people = await p.evaluate(() => [...document.querySelectorAll('#people tr')].slice(1).map((r) => r.children[0].innerText.replace('Rename', '').trim()));
  check('owner: the people table lists everyone', people.join(',') === 'David C,Drew,Priya', people.join(','));
  await p.click('button[data-key="f-person:u_drew"]');
  await p.waitForTimeout(300);
  const names = await p.evaluate(() => [...document.querySelectorAll('.proj-card h2')].map((h) => h.innerText.trim()));
  check('owner: the person filter shows only that person', names.length > 0 && names.every((n) => /clinic.scheduler|faq.site/i.test(n)), names.join(','));

  await p.click('button[data-key="f-person:add"]');
  await p.fill('#inv-name', 'Sam');
  await p.waitForTimeout(200);
  const text = await p.inputValue('#inv-text');
  check('invite: no placeholder is left in the text', !/\{\{|\}\}/.test(text), text.match(/\{\{[A-Z_]+\}\}/)?.[0]);
  check('invite: the text names the person and the private path', /Sam/.test(text) && text.includes('data/users/me/profile/syncs'));
  check('invite: the text carries the sync script and the hourly routine', text.includes('def main') && text.includes('cron_expression: "0 * * * *"'));
  check('invite: the text is a size a person can paste', text.length > 3000 && text.length < 30000, String(text.length));   // about 6,000 tokens at most
  await p.click('#inv-copy');
  await p.waitForTimeout(200);
  const clip = await p.evaluate(() => navigator.clipboard.readText().catch(() => ''));
  check('invite: the copy button puts the whole text on the clipboard', clip === text);
  await p.click('#inv-skill');
  await p.waitForTimeout(300);
  const saved = await p.evaluate(() => window.__saved);
  check('invite: the skill file is saved as one zip', saved.length === 1 && saved[0].filename === 'token-dashboard.zip');
  if (saved[0]) {
    const f = path.join(os.tmpdir(), 'check-skill.zip');
    fs.writeFileSync(f, Buffer.from(saved[0].b64, 'base64'));
    const lu = new URL('../skills/token-dashboard/scripts/local_usage.py', import.meta.url).pathname;
    const out = execFileSync('python3', ['-c', `import zipfile,sys;z=zipfile.ZipFile('${f}');assert z.testzip() is None;t=z.read('token-dashboard/SKILL.md').decode();print(z.namelist()[0]);print('Person: Sam' in t);n='token-dashboard/scripts/local_usage.py';print(n in z.namelist() and z.read(n)==open('${lu}','rb').read())`]).toString().trim().split('\n');
    check('invite: the zip is valid, holds the skill and the local usage script, and names the person', out[0] === 'token-dashboard/SKILL.md' && out[1] === 'True' && out[2] === 'True', out.join(' | '));
  }

  /* ---- history: the ledger, sessions that left the listing, long ranges, CSV ---- */
  await p.click('button[data-key="f-person:all"]');
  await p.waitForTimeout(250);
  const writes = await p.evaluate(() => window.__writes);
  const day3 = writes.find((x) => x[1] === 'daily/2026-10-03');
  check('history: the owner page fills a completed day that has no ledger entry', !!day3 && day3[0] === 'set' && day3[2].at === '2026-10-03T22:26:00Z' && day3[2].rows.length === 6, JSON.stringify(day3 && [day3[1], day3[2].at, day3[2].rows.length]));
  check('history: it fills the same day in a person\'s subtree, and not the open day', writes.some((x) => x[1] === 'data/users/u_drew/profile/daily/2026-10-03') && !writes.some((x) => /daily\/2026-10-04$/.test(x[1])));
  if (day3) {
    const f = path.join(os.tmpdir(), 'check-day3.json');
    fs.writeFileSync(f, JSON.stringify(day3[2]));
    const out = execFileSync('python3', [new URL('../scripts/ccr_sync_doc.py', import.meta.url).pathname, '--from-sync', path.join(DB, 'syncs', '1791066360.json'), path.join(os.tmpdir(), 'check-day3-py.json')]);
    const py = JSON.parse(fs.readFileSync(path.join(os.tmpdir(), 'check-day3-py.json'), 'utf8'));
    check('history: the page and scripts/ccr_sync_doc.py make the same ledger entry', JSON.stringify(py) === JSON.stringify(day3[2]) || (JSON.stringify(Object.entries(py).sort()) === JSON.stringify(Object.entries(day3[2]).sort())), String(out));
  }
  const kp2 = await p.evaluate(() => document.getElementById('kpis').innerText);
  check('history: All tokens counts the session that Claude Code no longer lists', /no longer listed/.test(kp2), kp2.split('\n').slice(0, 3).join(' | '));
  check('history: Last 30 days comes from the ledger', /LAST 30 D\n[\d.]+ [MB]/.test(kp2), kp2);
  const rows2 = await rows(p);
  check('history: the project of the removed session stays in the table with its tokens', rows2['owner/retired-experiment'] && rows2['owner/retired-experiment'][col('TOKENS')] === '405 M', JSON.stringify(rows2['owner/retired-experiment']));
  for (const range of ['720', 'all']) {
    await p.click(`button[data-key="density-range:${range}"]`);
    await p.waitForTimeout(250);
    const g = await p.evaluate(() => ({ h: document.getElementById('density-h').innerText, cap: document.getElementById('density-cap').innerText, sub: document.getElementById('density-sub').innerText,
      ledger: !!document.querySelector('#density-sub sup[data-note="ledger"]'), segs: document.querySelectorAll('#density-plot .seg').length }));
    check(`history: the ${range === 'all' ? 'All' : '30 d'} range shows tokens per day from the ledger`, /^per day$/i.test(g.h) && /day bars/.test(g.cap) && /\/day/.test(g.sub) && g.segs > 0 && g.ledger, JSON.stringify(g).slice(0, 260));
    const tall = await p.evaluate(() => { const svg = document.querySelector('#density-plot svg'); const h = svg.viewBox.baseVal.height; const st = {}; for (const x of svg.querySelectorAll('.seg')) st[x.dataset.i] = (st[x.dataset.i] || 0) + x.getBBox().height; return Math.max(0, ...Object.values(st)) / h; });
    check(`history: the tallest ${range === 'all' ? 'All' : '30 d'} bar reaches into the plot, not a sliver at its base`, tall > 0.4, tall.toFixed(2));
  }
  await p.click('button[data-key="density-range:48"]');
  await p.click('#exp-daily');
  await p.waitForTimeout(400);
  await p.click('#exp-hourly');
  await p.waitForTimeout(400);
  const files = await p.evaluate(() => window.__saved.filter((f) => /^claude-usage-/.test(f.filename)).map((f) => [f.filename, f.b64]));
  const csv = (name) => { const f = files.find((x) => x[0] === name); return f ? Buffer.from(f[1], 'base64').toString('utf8').replace(/^﻿/, '') : ''; };
  const daily = csv('claude-usage-daily.csv'), hourly = csv('claude-usage-hourly.csv');
  const dlines = daily.trim().split('\r\n');
  check('csv: the daily file has the header and one row per session per ledger day', dlines[0] === 'day,person,session_id,title,repo,status,tokens_total,tokens_since_previous_reading,output_tokens_total,cost_usd_total,reading_utc' && dlines.length === 1 + 5 + 5 + 6 + 6 + 2, `${dlines.length} lines`);
  check('csv: a title with a comma and a quote is quoted', daily.includes('"Weekly ""export"", v2"'));
  check('csv: a title that starts with = cannot start a spreadsheet formula', daily.includes('"\'=SUM(1,1) test"') && !/(^|,)=SUM/m.test(daily));
  check('csv: growth is blank at a first reading and exact after', /2026-09-30,David C,session_01HARBOR1,[^\n]*,8600000000,,/.test(daily) && /2026-10-01,David C,session_01HARBOR1,[^\n]*,8800000000,200000000,/.test(daily));
  const hlines = hourly.trim().split('\r\n');
  check('csv: the hourly file has one row per session per reading, for everyone', hlines.length === 1 + 18 + 6 + 4, `${hlines.length} lines`);
  check('csv: the hourly file names each person', /,Drew,/.test(hourly) && /,Priya,/.test(hourly) && /,David C,/.test(hourly));
  await s.close();
}

/* ---- a turn longer than 3 h that every hourly reading saw running ---- */
{
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'board-turn-'));
  fs.cpSync(DB, dir, { recursive: true });
  const base = JSON.parse(fs.readFileSync(path.join(DB, 'syncs', '1791066360.json'), 'utf8'));      // the 22:26 reading
  const lt = base.sessions.find((x) => x.id === 'session_01TURN001');
  for (const hh of ['19', '20', '21']) {
    const at = `2026-10-03T${hh}:26:00Z`;
    fs.writeFileSync(path.join(dir, 'syncs', `${Date.parse(at) / 1000}.json`), JSON.stringify({ at, src: 'routine', sessions: [{ ...lt, updatedAt: at }] }));
  }
  const s = await open({ db: dir, now: NOW, viewer: 'owner', width: 1100 });
  const heads = await headsOf(s.page);
  const r = (await rows(s.page))['owner/long-turn'], c = (n) => heads.indexOf(n);
  check('turns: a turn longer than 3 h that every reading saw running places its tokens over the turn',
    !!r && r[c('24 H')] === '120 M' && /^2\d M$/.test(r[c('1 H')]), JSON.stringify(r));
  await s.close();
  fs.rmSync(dir, { recursive: true, force: true });
}

/* ---- the sync script records which session took the reading ---- */
{
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'board-by-'));
  const answer = path.join(dir, 'ls1.txt');
  fs.writeFileSync(answer, JSON.stringify({ ccr: { data: [{ id: 'session_01TESTABC', title: 'T', session_status: 'SESSION_STATUS_RUNNING', created_at: '2026-10-04T00:00:00Z', updated_at: '2026-10-04T00:10:00Z', external_metadata: { usage: { input_tokens: 1, output_tokens: 1 } } }] } }));
  const run = (env) => { execFileSync('python3', [new URL('../scripts/ccr_sync_doc.py', import.meta.url).pathname, answer, path.join(dir, 'out.json'), '--at', '2026-10-04T00:15:00Z'], { env: { PATH: process.env.PATH, ...env } }); return JSON.parse(fs.readFileSync(path.join(dir, 'out.json'), 'utf8')); };
  check('script: the reading names the session that took it, from the cloud environment', run({ CLAUDE_CODE_REMOTE_SESSION_ID: 'cse_01TESTABC' }).by === 'session_01TESTABC');
  check('script: without the environment variable the reading names no session', !('by' in run({})));
  fs.rmSync(dir, { recursive: true, force: true });
}

/* ---- the sync script reads running turns from event pages: counts and times only, then deletes the pages ---- */
{
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'board-ev-'));
  const S = new URL('../scripts/ccr_sync_doc.py', import.meta.url).pathname;
  const py = (...a) => JSON.parse(execFileSync('python3', [S, ...a]).toString().trim().split('\n').pop());
  const ev = (at, mid, cr) => ({ created_at: at, assistant: { internal_anthropic_catchall: { message: { id: mid, content: [{ type: 'text', text: 'PRIVATE WORDS' }],
    usage: { input_tokens: 2, cache_read_input_tokens: cr, cache_creation_input_tokens: 10, output_tokens: 5 } } } } });
  const page = (f, data, more, first) => fs.writeFileSync(path.join(dir, f), `<other-session nonce="n">\n${JSON.stringify({ ccr: { data, has_more: more, first_id: first, last_id: 'z' } })}\n</other-session>`);
  const sync = { at: '2026-10-04T05:30:00Z', src: 'routine', by: 'session_R', sessions: [
    { id: 'session_A', title: 'A', status: 'running', tok: 1000, repos: [] }, { id: 'session_R', title: 'R', status: 'running', tok: 7, repos: [] }] };
  fs.writeFileSync(path.join(dir, 'sync.json'), JSON.stringify(sync));
  const plan = py('turns-plan', path.join(dir, 'sync.json'));
  check('events: the plan reads running sessions and skips the session that reads', JSON.stringify(plan.sessions) === '["session_A"]', JSON.stringify(plan));
  page('p1.txt', [ev('2026-10-04T05:20:00Z', 'm3', 100), ev('2026-10-04T05:20:01Z', 'm3', 100), ev('2026-10-04T05:28:00Z', 'm4', 200)], true, 'cur1');
  const a1 = py('turns-add', 'session_A', path.join(dir, 'p1.txt'));
  page('p2.txt', [ev('2026-10-04T04:50:00Z', 'm1', 999), { created_at: '2026-10-04T04:55:00Z', result: {} }, ev('2026-10-04T05:05:00Z', 'm2', 50)], true, 'cur2');
  const a2 = py('turns-add', 'session_A', path.join(dir, 'p2.txt'));
  check('events: paging goes on until the end of the previous turn', a1.more === true && a1.before_id === 'cur1' && a2.more === false, JSON.stringify([a1, a2]));
  check('events: each page is deleted after the script reads it', !fs.existsSync(path.join(dir, 'p1.txt')) && !fs.existsSync(path.join(dir, 'p2.txt')));
  const m = py('turns-merge', path.join(dir, 'sync.json'));
  const out = JSON.parse(fs.readFileSync(path.join(dir, 'sync.json'), 'utf8'));
  const turn = out.sessions[0].turn;
  check('events: the turn counts each model call once, and only calls after the previous turn ended', m.turn_tok === 3 * 17 + 50 + 100 + 200 && turn.calls === 3 && turn.since === '2026-10-04T05:05:00Z', JSON.stringify(turn));
  check('events: no text from the events reaches the sync document', !/PRIVATE/.test(fs.readFileSync(path.join(dir, 'sync.json'), 'utf8')) && !('turn' in out.sessions[1]));
  /* the next reading: the same turn still runs, so it continues from the last counted call */
  fs.writeFileSync(path.join(dir, 'prev.json'), JSON.stringify(out));
  fs.writeFileSync(path.join(dir, 'next.json'), JSON.stringify({ ...sync, at: '2026-10-04T06:30:00Z', sessions: [sync.sessions[0]] }));
  py('turns-plan', path.join(dir, 'next.json'), '--prev', path.join(dir, 'prev.json'));
  page('q1.txt', [ev('2026-10-04T05:28:01Z', 'm4', 200), ev('2026-10-04T06:00:00Z', 'm5', 300)], true, 'c9');
  const q = py('turns-add', 'session_A', path.join(dir, 'q1.txt'));
  py('turns-merge', path.join(dir, 'next.json'));
  const t2 = JSON.parse(fs.readFileSync(path.join(dir, 'next.json'), 'utf8')).sessions[0].turn;
  check('events: the next reading continues the turn without counting a call twice', q.more === false && t2.tok === turn.tok + 317 && t2.calls === 4 && t2.since === turn.since, JSON.stringify([q, t2.tok, t2.calls]));
  /* Claude Code adds a turn's tokens to the session total late. A reading after the turn ended and a new one began,
     with the old total, keeps the ended turn: it counts through the result event back to the last reading */
  fs.writeFileSync(path.join(dir, 'prev2.json'), fs.readFileSync(path.join(dir, 'next.json')));
  fs.writeFileSync(path.join(dir, 'third.json'), JSON.stringify({ ...sync, at: '2026-10-04T07:35:00Z', sessions: [sync.sessions[0]] }));
  py('turns-plan', path.join(dir, 'third.json'), '--prev', path.join(dir, 'prev2.json'));
  page('r1.txt', [ev('2026-10-04T07:30:00Z', 'm7', 700), { created_at: '2026-10-04T07:10:00Z', result: {} }, ev('2026-10-04T06:30:00Z', 'm6', 600), ev('2026-10-04T06:00:00Z', 'm5', 300)], true, 'c10');
  const rr = py('turns-add', 'session_A', path.join(dir, 'r1.txt'));
  py('turns-merge', path.join(dir, 'third.json'));
  const t3a = JSON.parse(fs.readFileSync(path.join(dir, 'third.json'), 'utf8')).sessions[0].turn;
  check('events: a turn that ended while Claude Code still reports the old total stays in the count',
    rr.more === false && !!t3a && t3a.tok === t2.tok + 617 + 717 && t3a.calls === 6 && t3a.since === turn.since, JSON.stringify([rr, t3a && t3a.tok, t3a && t3a.calls]));
  /* the session is idle now and its total has still not changed: the reading still carries its unreported turns */
  fs.writeFileSync(path.join(dir, 'prev3.json'), fs.readFileSync(path.join(dir, 'third.json')));
  fs.writeFileSync(path.join(dir, 'fourth.json'), JSON.stringify({ ...sync, at: '2026-10-04T08:35:00Z', sessions: [{ ...sync.sessions[0], status: 'idle' }] }));
  const plan4 = py('turns-plan', path.join(dir, 'fourth.json'), '--prev', path.join(dir, 'prev3.json'));
  if (plan4.sessions.length) {
    page('s1.txt', [{ created_at: '2026-10-04T08:00:00Z', result: {} }, ev('2026-10-04T07:50:00Z', 'm8', 800), ev('2026-10-04T07:30:00Z', 'm7', 700)], false, 'c11');
    py('turns-add', 'session_A', path.join(dir, 's1.txt'));
  }
  py('turns-merge', path.join(dir, 'fourth.json'));
  const t4 = JSON.parse(fs.readFileSync(path.join(dir, 'fourth.json'), 'utf8')).sessions[0].turn;
  check('events: an idle session whose total Claude Code has not updated keeps its unreported turns',
    JSON.stringify(plan4.sessions) === '["session_A"]' && !!t4 && !!t3a && t4.tok === t3a.tok + 817, JSON.stringify([plan4, t4 && t4.tok]));
  /* a turn longer than the page cap: the read stops after 30 pages and marks the turn partial */
  fs.writeFileSync(path.join(dir, 'cap.json'), JSON.stringify({ ...sync, sessions: [sync.sessions[0]] }));
  py('turns-plan', path.join(dir, 'cap.json'));
  let n = 0, last = null;
  do {
    n += 1;
    page(`c${n}.txt`, [ev(new Date(Date.parse('2026-10-04T05:29:00Z') - n * 60000).toISOString().replace('.000Z', 'Z'), `k${n}`, 0)], true, `cc${n}`);
    last = py('turns-add', 'session_A', path.join(dir, `c${n}.txt`));
  } while (last.more && n < 40);
  py('turns-merge', path.join(dir, 'cap.json'));
  const t3 = JSON.parse(fs.readFileSync(path.join(dir, 'cap.json'), 'utf8')).sessions[0].turn;
  check('events: a turn longer than 30 pages stops after 30 and reads as a floor', n === 30 && t3.partial === true && t3.calls === 30 && t3.tok === 30 * 17, JSON.stringify([n, t3.calls, t3.tok, t3.partial]));
  fs.rmSync(dir, { recursive: true, force: true });
}

/* ---- the page draws a running turn from its event counts ---- */
{
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'board-turnpts-'));
  fs.cpSync(DB, dir, { recursive: true });
  const f = path.join(dir, 'syncs', '1791073380.json');                       // the 00:23 reading
  const d = JSON.parse(fs.readFileSync(f, 'utf8'));
  const sec = (iso) => Date.parse(iso) / 1000;
  d.sessions.find((x) => x.id === 'session_01PEND001').turn = { since: '2026-10-03T23:30:00Z', tok: 60_000_000, out: 0, calls: 40, lastAt: '2026-10-04T00:20:00Z', lastMsg: 'm',
    pts: [[sec('2026-10-03T23:30:00Z'), 5_000_000], [sec('2026-10-03T23:50:00Z'), 30_000_000], [sec('2026-10-04T00:20:00Z'), 60_000_000]] };
  fs.writeFileSync(f, JSON.stringify(d));
  const s = await open({ db: dir, now: NOW, viewer: 'owner', width: 1100 });
  const heads = await headsOf(s.page);
  const c = (n) => heads.indexOf(n);
  const r = (await rows(s.page))['owner/pending-turn'];
  const notes = await s.page.evaluate(() => ({ turns: (document.getElementById('turns-note') || {}).innerText || '', pend: (document.getElementById('pending-note') || {}).innerText || '' }));
  check('events: the running turn adds its tokens to the session', !!r && r[c('TOKENS')] === '140 M', JSON.stringify(r));
  check('events: the turn places its tokens in the hours they were used', !!r && /^5\d M$/.test(r[c('1 H')]), JSON.stringify(r));
  check('events: the figures name the turn read from events, and not as not counted', /Includes 60 M/.test(notes.turns) && /owner\/pending-turn/.test(notes.turns) && !/owner\/pending-turn/.test(notes.pend), JSON.stringify(notes));
  const row = await s.page.evaluate(() => { const cd = [...document.querySelectorAll('.proj-card')].find((x) => x.querySelector('h2').innerText.trim() === 'owner/pending-turn'); const dd = cd && cd.querySelector('details.sessions'); if (!dd) return ''; dd.open = true; return dd.innerText; });
  check('events: its session row says how much the turn used so far', /60 M so far/.test(row), row.slice(0, 200));
  await s.close();
  fs.rmSync(dir, { recursive: true, force: true });
}

/* ---- local and cloud: the hourly listing decides the place; a local session that stops reporting reads No report ---- */
{
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'board-local-'));
  fs.cpSync(DB, dir, { recursive: true });
  const at = (min) => new Date(Date.parse(NOW) - min * 60000).toISOString().replace('.000Z', 'Z');
  const sec = (iso) => Date.parse(iso) / 1000;
  const put = (col, id, doc) => fs.writeFileSync(path.join(dir, col, `${id}.json`), JSON.stringify(doc));
  /* a Cowork session that calls itself cloud, appears in no reading, and stopped reporting 2 h ago */
  put('sessions', 'session_01GRANTA1', { title: 'Grant A drafts', folder: 'Grant A', where: 'cloud', surface: 'Claude Code · cloud', src: 'report', status: 'running', updatedAt: at(120), createdAt: at(600), partial: true });
  /* a local session that reports now, with counts and points from its transcript */
  put('sessions', 'cowork-grant-b', { title: 'Grant B drafts', folder: 'Grant B', where: 'local', surface: 'Cowork', src: 'transcript', status: 'running', updatedAt: at(5), createdAt: at(300),
    tok: 30_000_000, out: 100_000, calls: 300, since: at(300), lastAt: at(6),
    pts: [[sec(at(300)) - 1, 0], [sec(at(290)), 5_000_000], [sec(at(50)) - 1, 5_000_000], [sec(at(40)), 20_000_000], [sec(at(6)), 30_000_000]] });
  /* a Cowork session whose own report went stale, read by the sync with get_session: generic title, newer state */
  put('sessions', 'session_01GRANTC1', { title: 'Grant C drafts', folder: 'Grant C', where: 'local', surface: 'Cowork', src: 'report', status: 'running', updatedAt: at(100), createdAt: at(400), partial: true });
  {
    const f = path.join(dir, 'syncs', '1791073380.json'), d = JSON.parse(fs.readFileSync(f, 'utf8'));
    d.sessions.push({ id: 'session_01GRANTC1', title: 'Claude.ai E1 upgraded conversation', status: 'idle', bucket: '', model: '', createdAt: at(400), updatedAt: at(3), tok: 50_000_000, out: 400_000, usd: 20, repos: [], via: 'get' });
    fs.writeFileSync(f, JSON.stringify(d));
  }
  for (let i = 1; i <= 6; i += 1) put('sessions', `cowork-extra-${i}`, { title: `Extra ${i}`, folder: `Extra ${i}`, where: 'local', surface: 'Cowork', src: 'report', status: 'idle', updatedAt: at(30 + i), tok: 1_000_000 });
  const s = await open({ db: dir, now: NOW, viewer: 'owner', width: 1100 });
  check('local: the page loads without errors', s.problems.length === 0, s.problems.join(' | '));
  const heads = await headsOf(s.page); const c = (n) => heads.indexOf(n);
  const R = await rows(s.page);
  const pills = await s.page.evaluate(() => Object.fromEntries([...document.querySelectorAll('.proj-card')].map((x) => [x.querySelector('h2').innerText.trim(), x.querySelector('.pill').innerText.trim()])));
  check('local: a session that no reading lists is local, whatever it calls itself', !!R['Grant A'] && /\blocal\b/i.test(R['Grant A'][0]), JSON.stringify(R['Grant A']));
  check('local: a running report with no newer report for 45 min reads No report, not Working now', /^no report$/i.test(pills['Grant A'] || ''), JSON.stringify(pills));
  const row = await s.page.evaluate(() => { const cd = [...document.querySelectorAll('.proj-card')].find((x) => x.querySelector('h2').innerText.trim() === 'Grant A'); const dd = cd && cd.querySelector('details.sessions'); if (!dd) return ''; dd.open = true; return dd.innerText; });
  check('local: its session row says how long it sent no report', /No report for 2 h/.test(row), row.slice(0, 200));
  check('local: a fresh local report counts as Working now', /^working now$/i.test(pills['Grant B'] || ''), JSON.stringify(pills));
  check('local: transcript points place the local tokens in the hours they were used', !!R['Grant B'] && /^2\d M$/.test(R['Grant B'][c('1 H')]) && R['Grant B'][c('24 H')] === '30 M', JSON.stringify(R['Grant B']));
  check('local: a cloud project keeps its place', !!R['owner/atlas-port'] && !/\blocal\b/i.test(R['owner/atlas-port'][0]), JSON.stringify(R['owner/atlas-port']));
  check('local: a Cowork session that get_session read stays local, with its total and its newer state', !!R['Grant C'] && /\blocal\b/i.test(R['Grant C'][0]) && R['Grant C'][c('TOKENS')] === '50 M' && /^idle$/i.test(pills['Grant C'] || ''), JSON.stringify([R['Grant C'], pills['Grant C']]));
  const rowC = await s.page.evaluate(() => { const cd = [...document.querySelectorAll('.proj-card')].find((x) => x.querySelector('h2').innerText.trim() === 'Grant C'); const dd = cd && cd.querySelector('details.sessions'); if (!dd) return ''; dd.open = true; return dd.innerText; });
  check('local: its row keeps the title that the session reported and says the sync read it', /Grant C drafts/.test(rowC) && !/E1 upgraded/.test(rowC) && /read hourly/.test(rowC), rowC.slice(0, 200));
  /* colours: each project among the 16 with the latest activity has its own colour */
  const sw = await s.page.evaluate(() => [...document.querySelectorAll('.proj-card')].map((x) => [x.querySelector('h2').innerText.trim(), x.querySelector('h2 .sw').style.background]));
  const colored = sw.filter(([, b]) => !/other/.test(b)).map(([, b]) => b);
  const total = Object.keys(R).length;
  check('colours: more than 8 projects get distinct colours, and grey only past 16', sw.length > 8 && new Set(colored).size === colored.length
    && sw.length - colored.length <= Math.max(0, total - 16) && colored.some((b) => /--s(9|1[0-6])\)/.test(b)), JSON.stringify(sw));
  await s.close();
  fs.rmSync(dir, { recursive: true, force: true });
}

/* ---- the local usage script: counts and times from the session's own transcript, never text ---- */
{
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'board-lu-'));
  const S = new URL('../skills/token-dashboard/scripts/local_usage.py', import.meta.url).pathname;
  const proj = path.join(dir, 'projects', '-work-grant');
  fs.mkdirSync(path.join(proj, 'sid-1', 'subagents'), { recursive: true });
  const a = (ts, id, cr, o) => JSON.stringify({ type: 'assistant', timestamp: ts, message: { id, content: [{ type: 'text', text: 'PRIVATE WORDS' }], usage: { input_tokens: 10, cache_read_input_tokens: cr, cache_creation_input_tokens: 100, output_tokens: o } } });
  const main = [JSON.stringify({ type: 'user', timestamp: '2026-10-04T10:00:00Z', message: { content: 'PRIVATE PROMPT' } }),
    a('2026-10-04T10:00:05Z', 'm1', 1000, 5), a('2026-10-04T10:00:06Z', 'm1', 1000, 50), a('2026-10-04T10:04:00Z', 'm2', 2000, 40),
    JSON.stringify({ type: 'cost-state', modelUsage: { x: { inputTokens: 9000, outputTokens: 90, cacheReadInputTokens: 3000, cacheCreationInputTokens: 200 } }, totalCostUSD: 1.234 }),
    a('2026-10-04T13:00:00Z', 'm3', 500, 9)].join('\n') + '\n';
  fs.writeFileSync(path.join(proj, 'sid-1.jsonl'), main);
  fs.writeFileSync(path.join(proj, 'sid-1', 'subagents', 'agent-1.jsonl'), a('2026-10-04T10:02:00Z', 's1', 300, 8) + '\n');
  const raw = execFileSync('python3', [S, '--root', dir]).toString();
  const r = JSON.parse(raw);
  const t = (iso) => Date.parse(iso) / 1000;
  check('local script: each model call counts once, subagents included, plus what Claude Code counted that the transcript lost',
    r.sessionId === 'sid-1' && r.calls === 4 && r.tok === 12909 && r.untimed === 8562 && r.out === 107 && r.usd === 1.23 && r.files === 2, raw);
  check('local script: the points place each bucket of calls, with the total before a bucket that follows a gap',
    JSON.stringify(r.pts) === JSON.stringify([[t('2026-10-04T10:00:05Z') - 1, 8562], [t('2026-10-04T10:04:00Z'), 12290], [t('2026-10-04T13:00:00Z') - 1, 12290], [t('2026-10-04T13:00:00Z'), 12909]]), JSON.stringify(r.pts));
  check('local script: no text leaves the transcript, and the transcript stays unchanged', !/PRIVATE/.test(raw) && fs.readFileSync(path.join(proj, 'sid-1.jsonl'), 'utf8') === main);
  let code = 0, err = '';
  try { execFileSync('python3', [S, '--root', path.join(dir, 'none')], { stdio: 'pipe' }); } catch (e) { code = e.status; err = e.stdout.toString(); }
  check('local script: with no transcript it says so and writes no figure', code === 2 && /no transcript found/.test(err) && !/"tok"/.test(err), `${code} ${err}`);
  fs.rmSync(dir, { recursive: true, force: true });
}

/* ---- the sync reads Cowork sessions with get_session: counts only, marked via get ---- */
{
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'board-get-'));
  const S = new URL('../scripts/ccr_sync_doc.py', import.meta.url).pathname;
  const py = (...a) => JSON.parse(execFileSync('python3', [S, ...a]).toString().trim().split('\n').pop());
  fs.writeFileSync(path.join(dir, 'sync.json'), JSON.stringify({ at: '2026-10-04T05:30:00Z', src: 'routine', sessions: [{ id: 'session_A', title: 'A', status: 'running', tok: 1000, out: 1, usd: 0, createdAt: '2026-10-04T00:00:00Z', repos: [] }] }));
  fs.mkdirSync(path.join(dir, 'ses', 'sessions'), { recursive: true });
  for (const id of ['session_A', 'session_01COWORK', 'cowork-notes']) fs.writeFileSync(path.join(dir, 'ses', 'sessions', `${id}.json`), JSON.stringify({ id, data: {} }));
  const ids = py('local-ids', path.join(dir, 'sync.json'), path.join(dir, 'ses'));
  check('get: the sync asks get_session only for reporting sessions that the listing lacks', JSON.stringify(ids.ids) === '["session_01COWORK"]', JSON.stringify(ids));
  const ans = path.join(dir, 'gs1.txt');
  fs.writeFileSync(ans, `<other-session nonce="n">\n${JSON.stringify({ ccr: { id: 'session_01COWORK', title: 'Claude.ai E1 upgraded conversation', session_status: 'SESSION_STATUS_RUNNING', created_at: '2026-10-04T01:00:00Z', updated_at: '2026-10-04T05:29:00Z', post_turn_summary: { status_detail: 'PRIVATE SUMMARY' }, external_metadata: { usage: { input_tokens: 10, cache_read_tokens: 900, cache_write_tokens: 80, output_tokens: 10, cost_usd: 1.5 } } } })}\n</other-session>`);
  const add = py('add-local', path.join(dir, 'sync.json'), '--daily', path.join(dir, 'daily.json'), ans);
  const out = JSON.parse(fs.readFileSync(path.join(dir, 'sync.json'), 'utf8'));
  const row = out.sessions.find((r) => r.id === 'session_01COWORK');
  check('get: add-local adds the Cowork session with its totals, marked via get', add.added === 1 && !!row && row.via === 'get' && row.tok === 1000 && row.usd === 1.5 && row.status === 'running', JSON.stringify([add, row]));
  check('get: no summary text reaches the reading, and the answer file is deleted', !/PRIVATE/.test(fs.readFileSync(path.join(dir, 'sync.json'), 'utf8')) && !fs.existsSync(ans));
  const daily = JSON.parse(fs.readFileSync(path.join(dir, 'daily.json'), 'utf8'));
  check('get: the ledger entry carries the Cowork session and marks it', daily.cols.includes('via') && daily.rows.some((r) => r[0] === 'session_01COWORK' && r[daily.cols.indexOf('via')] === 'get'), JSON.stringify(daily.cols));
  const plan = py('turns-plan', path.join(dir, 'sync.json'));
  check('get: the event step skips Cowork sessions, which refuse a cloud caller', JSON.stringify(plan.sessions) === '["session_A"]', JSON.stringify(plan));
  fs.rmSync('/tmp/turns.json', { force: true });
  fs.rmSync(dir, { recursive: true, force: true });
}

/* ---- the 5-hour and 7-day tiles: tokens and covered time from the same readings, and no hints for fields that nobody reports ---- */
{
  const tiles = async (db) => {
    const s = await open({ db, now: NOW, viewer: 'owner', width: 1100 });
    await s.page.click('button[data-key="f-person:david"]');
    await s.page.waitForTimeout(300);
    const out = await s.page.evaluate(() => ({ body: document.body.innerText, kpis: document.getElementById('kpis').innerText, wins: [...document.querySelectorAll('#density-win .win')].map((w) => w.innerText) }));
    await s.close();
    return out;
  };
  const rate = '[\\d.]+(?: [kMB])?\\/h';
  const a = await tiles(DB);
  const h5 = a.wins.find((x) => /^5-h limit/i.test(x)) || '', d7 = a.wins.find((x) => /^7-day/i.test(x)) || '';
  check('windows: the 5-hour tile says how much of the window the readings measured, the rate, and the cost', new RegExp(`1 h 57 min of 5 h measured · ${rate} · ≈\\$\\d[\\d,]*`).test(h5), JSON.stringify(h5));
  check('windows: no 7-day limit tile repeats the Last 7 d figure when Claude Code reports no weekly limit', !d7 && /LAST 7 D\n[\d.]+ [kMB]/.test(a.kpis) && /LAST 5 H\n[\d.]+ [kMB]/.test(a.kpis), JSON.stringify([d7, a.kpis.slice(0, 300)]));
  check('windows: no hint asks for a field that Claude Code does not report', !/post quota/.test(a.body), (a.body.match(/.*post quota.*/) || [''])[0]);
  /* a new window that no reading reaches yet, and a snapshot after the newest reading */
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'board-win-'));
  fs.cpSync(DB, dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'meta', 'quota.json'), JSON.stringify({ status: 'allowed', type: 'five_hour', resetsAt: '2026-10-04T05:24:00Z', overage: false, updatedAt: '2026-10-04T00:24:00Z' }));
  fs.mkdirSync(path.join(dir, 'ticks'), { recursive: true });
  fs.writeFileSync(path.join(dir, 'ticks', 'session_01ATLAS01~2026-10-04.json'), JSON.stringify({ sid: 'session_01ATLAS01', day: '2026-10-04', pts: [[Date.parse('2026-10-04T00:24:30Z') / 1000, 405_000_000]], src: 'ccr' }));
  const b = await tiles(dir);
  const g5 = b.wins.find((x) => /^5-h limit/i.test(x)) || '';
  check('windows: a limit window that no reading reaches yet says so, instead of tokens at a rate of zero', /\n—\n/.test(g5) && /No reading since it began · next about/.test(g5) && !/ 0\/h|0 s measured/.test(g5), JSON.stringify(g5));
  check('windows: the trailing 5 hours still show a figure then', /LAST 5 H\n[\d.]+ [kMB]/.test(b.kpis), b.kpis.slice(0, 300));
  fs.rmSync(dir, { recursive: true, force: true });
  /* Claude Code reports only the limit that applies: the newest reading names the 7-day limit, near its cap */
  const wdir = fs.mkdtempSync(path.join(os.tmpdir(), 'board-week-'));
  fs.cpSync(DB, wdir, { recursive: true });
  const wf = path.join(wdir, 'syncs', '1791073380.json');
  const wd = JSON.parse(fs.readFileSync(wf, 'utf8'));
  wd.quota = { status: 'allowed_warning', type: 'seven_day', resetsAt: '2026-10-09T05:00:00Z', overage: false, asOf: '2026-10-04T00:23:30Z' };
  fs.writeFileSync(wf, JSON.stringify(wd));
  const w = await tiles(wdir);
  const wk = w.wins.find((x) => /^7-day limit/i.test(x)) || '', w5 = w.wins.find((x) => /^5-h limit/i.test(x)) || '';
  check('limits: a 7-day report near the cap shows as an amber pill and a line that names the window and the reset',
    /Near the limit/i.test(w.body) && /Near the 7-day limit\. Long jobs can stop before the reset, Oct 9/.test(w.body), (w.body.match(/.*limit.*/gi) || []).slice(0, 4).join(' | '));
  check('limits: the 7-day tile counts from its reset less 7 days and says how little of the week the readings measured', /resets Oct 9/.test(wk) && /of 7 d measured/.test(wk) && /Near the limit/.test(wk), JSON.stringify(wk));
  check('limits: the 5-hour window stays from its last report while its reset is ahead', /of 5 h measured/.test(w5) && /\(last report\)/.test(w5), JSON.stringify(w5));
  fs.rmSync(wdir, { recursive: true, force: true });
}

/* ---- only the ledger: the range buttons stay, and 30 d reads the ledger ---- */
{
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'board-ledger-'));
  fs.cpSync(DB, dir, { recursive: true });
  for (const d of ['syncs', 'data__users__u_drew__profile__syncs', 'data__users__u_priya__profile__syncs']) fs.rmSync(path.join(dir, d), { recursive: true, force: true });
  const s = await open({ db: dir, now: NOW, viewer: 'owner', width: 1100 });
  const g = await s.page.evaluate(() => ({ hidden: document.getElementById('density').hidden, buttons: document.querySelectorAll('#density-range button').length, sub: document.getElementById('density-sub').innerText }));
  check('ledger only: the range buttons stay when the hourly readings measured nothing', !g.hidden && g.buttons === 6 && /Pick a longer range/.test(g.sub), JSON.stringify(g).slice(0, 200));
  await s.page.click('button[data-key="density-range:720"]');
  await s.page.waitForTimeout(250);
  const segs = await s.page.evaluate(() => document.querySelectorAll('#density-plot .seg').length);
  check('ledger only: 30 d draws the days from the ledger', segs > 0, String(segs));
  await s.close();
  fs.rmSync(dir, { recursive: true, force: true });
}

/* ---- a saved project filter whose project was renamed must not empty the board ---- */
{
  const s = await open({ db: DB, now: NOW, viewer: 'owner', width: 1100 });
  const stored = await s.page.evaluate(() => { try { localStorage.setItem('cad.project', 'A label from before the rename'); return true; } catch (e) { return false; } });
  if (stored) {
    await s.page.reload();
    await s.page.waitForTimeout(900);
    const n = await s.page.evaluate(() => document.querySelectorAll('.proj-card').length);
    check('names: a saved project filter that no longer exists does not empty the board', n > 0, String(n));
  } else console.log('SKIP  names: this browser blocks localStorage for file pages');
  await s.close();
}

/* ---- a person's view ---- */
{
  const s = await open({ db: DB, now: NOW, viewer: 'person', uid: 'u_drew', name: 'Drew', width: 1100 });
  const p = s.page;
  check('person: page loads without errors', s.problems.length === 0, s.problems.join(' | '));
  const body = await p.evaluate(() => document.body.innerText);
  check('person: sees their own projects', /clinic.scheduler/i.test(body) && /faq.site/i.test(body));
  check('person: sees nothing of the owner or of another person', !/Atlas|Harbor|Quarterly|Priya|David C/.test(body.replace(/David C activity board/g, '')), body.match(/Atlas|Harbor|Quarterly|Priya/)?.[0]);
  const w = await p.evaluate(() => window.__writes.map((x) => `${x[0]} ${x[1]}`));
  check('person: every write is in their own subtree or is their own join entry', w.length > 0 && w.every((x) => /^(update join\/u_drew|set data\/users\/u_drew\/)/.test(x)), w.join(' | '));
  check('person: the page filled the ledger day that had hourly readings and no entry', w.includes('set data/users/u_drew/profile/daily/2026-10-03'), w.join(' | '));
  const ui = await p.evaluate(() => ({ people: !document.getElementById('people-wrap').hidden, setup: !!document.querySelector('button[data-key="f-person:add"]'), live: document.getElementById('livenote').innerText }));
  check('person: no people table, and a way to set up their own Claude', !ui.people && ui.setup, JSON.stringify(ui));
  check('person: no live read on the owner connector', !/live read/.test(ui.live), ui.live);
  await p.click('#exp-daily');
  await p.waitForTimeout(400);
  await p.click('#exp-hourly');
  await p.waitForTimeout(400);
  const texts = await p.evaluate(() => window.__saved.filter((f) => /^claude-usage-/.test(f.filename)).map((f) => new TextDecoder().decode(Uint8Array.from(atob(f.b64), (c) => c.charCodeAt(0)))));
  check('person: both exports hold only their own sessions', texts.length === 2 && texts.every((t0) => /session_01DREW/.test(t0) && !/HARBOR|ATLAS|MODEL|PRIYA|RETIRE/.test(t0)), texts.map((t0) => t0.length).join(','));
  await s.close();
}

/* ---- phone width ---- */
for (const viewer of ['owner', 'person']) {
  const s = await open({ db: DB, now: NOW, viewer, uid: 'u_drew', name: 'Drew', width: 390 });
  const overflow = await s.page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  check(`phone width, ${viewer}: no horizontal scroll`, overflow <= 1, `${overflow}px`);
  await s.close();
}

console.log(failed ? `\n${failed} check(s) failed` : '\nall checks passed');
process.exit(failed ? 1 : 0);
