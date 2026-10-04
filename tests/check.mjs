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
const rows = (page) => page.evaluate(() => Object.fromEntries([...document.querySelectorAll('#ptable tr')].slice(1).map((r) => {
  const c = [...r.children].map((x) => x.innerText.trim().replace(/\s+/g, ' '));
  return [c[0].replace(/ · inactive$/, ''), c];
})));

/* ---- owner view ---- */
{
  const s = await open({ db: DB, now: NOW, viewer: 'owner', width: 1100 });
  const p = s.page;
  check('owner: page loads without errors', s.problems.length === 0, s.problems.join(' | '));
  const heads = await p.evaluate(() => [...document.querySelectorAll('#ptable tr')][0].innerText.split('\t').map((x) => x.trim()));
  const col = (n) => heads.indexOf(n);
  const R = await rows(p);
  const atlas = R['Atlas port'], harbor = R['Harbor docs'], model = R['Quarterly model'];
  check('owner: the running project shows measured use in the last hour', atlas && atlas[col('LAST HOUR')] !== '—', JSON.stringify(atlas));
  check('owner: the idle project with 9 B lifetime tokens shows no use in the last hour', harbor && harbor[col('LAST HOUR')] === '—', JSON.stringify(harbor));
  check('owner: the idle project shows no use in 24 h', harbor && harbor[col('24 H')] === '—', JSON.stringify(harbor));
  check('owner: the project idle for two days shows no use in 24 h', model && model[col('24 H')] === '—', JSON.stringify(model));
  check('owner: last token use of the two-day idle project is in hours', model && /\d+ h ago/.test(model[col('LAST TOKEN USE')]), JSON.stringify(model));
  const pills = await p.evaluate(() => Object.fromEntries([...document.querySelectorAll('.proj-card')].map((c) => [c.querySelector('h2').innerText.trim(), c.querySelector('.pill').innerText.trim()])));
  check('owner: the running project reads Working now', /^working now$/i.test(pills['Atlas port']), JSON.stringify(pills));
  check('owner: the idle project reads Idle', /^idle$/i.test(pills['Harbor docs']), JSON.stringify(pills));
  const kp = await p.evaluate(() => document.getElementById('kpis').innerText);
  check('owner: the 24 h figure says how much of the window it measured', /measured .* of 24 h/.test(kp), kp);
  check('owner: tokens used before the first reading are stated, not placed in an hour', /used before the first reading/.test(kp), kp);
  const note = await p.evaluate(() => { const n = document.getElementById('livenote'); return { text: n.innerText, warn: n.classList.contains('warn') }; });
  check('owner: a blocked live read is explained and does not warn', /live read is off/.test(note.text) && !note.warn, JSON.stringify(note));
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
  check('invite: the text is a size a person can paste', text.length > 3000 && text.length < 20000, String(text.length));
  await p.click('#inv-copy');
  await p.waitForTimeout(200);
  const clip = await p.evaluate(() => navigator.clipboard.readText().catch(() => ''));
  check('invite: the copy button puts the whole text on the clipboard', clip === text);
  await p.click('#inv-skill');
  await p.waitForTimeout(300);
  const saved = await p.evaluate(() => window.__saved);
  check('invite: the skill file is saved as one zip', saved.length === 1 && saved[0].filename === 'claude-dashboard.zip');
  if (saved[0]) {
    const f = path.join(os.tmpdir(), 'check-skill.zip');
    fs.writeFileSync(f, Buffer.from(saved[0].b64, 'base64'));
    const out = execFileSync('python3', ['-c', `import zipfile,sys;z=zipfile.ZipFile('${f}');assert z.testzip() is None;t=z.read('claude-dashboard/SKILL.md').decode();print(z.namelist()[0]);print('Person: Sam' in t)`]).toString().trim().split('\n');
    check('invite: the zip is valid, holds the skill, and names the person', out[0] === 'claude-dashboard/SKILL.md' && out[1] === 'True', out.join(' | '));
  }
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
  check('person: the only write is their own join entry', w.length === 1 && w[0] === 'update join/u_drew', w.join(' | '));
  const ui = await p.evaluate(() => ({ people: !document.getElementById('people-wrap').hidden, setup: !!document.querySelector('button[data-key="f-person:add"]'), live: document.getElementById('livenote').innerText }));
  check('person: no people table, and a way to set up their own Claude', !ui.people && ui.setup, JSON.stringify(ui));
  check('person: no live read on the owner connector', !/live read/.test(ui.live), ui.live);
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
