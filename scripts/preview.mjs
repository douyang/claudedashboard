#!/usr/bin/env node
/* Load dashboard/index.html in Chromium with a stub of window.claude, then save screenshots.
 *
 * Usage:
 *   NODE_PATH=$(npm root -g) node scripts/preview.mjs --db tests/fixtures/db --out /tmp/shots
 *
 * Options:
 *   --page FILE     page to load (default dashboard/index.html)
 *   --db DIR        fixtures, one JSON file per document: DIR/<collection>/<doc id>.json
 *   --out DIR       screenshot directory (default /tmp/preview)
 *   --now ISO       fake clock, UTC (default: the newest timestamp in the fixtures)
 *   --widths A,B    viewport widths in px (default 390,1100)
 *   --viewer ROLE   owner (default) or person. A person reads only data/users/<uid>/ and join/<uid>.
 *   --uid ID        the person's id for --viewer person (default u_drew)
 *   --name NAME     the person's display name for --viewer person (default Drew)
 *   --live MODE     blocked_by_policy (default), ok, needs_reauth or none
 *   --click SEL     click a selector before the screenshots (repeatable)
 *
 * The script exits with code 1 when the page throws or logs a console error.
 * Other scripts import open() to drive the page.
 */
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

/* ES modules ignore NODE_PATH, so load Playwright the CommonJS way. */
const { chromium } = createRequire(import.meta.url)('playwright');

function readDb(dir) {
  const docs = {};
  if (!dir) return docs;
  for (const col of fs.readdirSync(dir)) {
    const cdir = path.join(dir, col);
    if (!fs.statSync(cdir).isDirectory()) continue;
    /* a directory name spells a nested collection with "__" for "/", and an id spells "~" as "@" */
    for (const f of fs.readdirSync(cdir)) if (f.endsWith('.json')) docs[`${col.replace(/__/g, '/')}/${f.slice(0, -5).replace(/@/g, '~')}`] = JSON.parse(fs.readFileSync(path.join(cdir, f), 'utf8'));
  }
  return docs;
}

/** Newest ISO timestamp in the fixtures, so a fixture set reads as "just now". */
function newest(docs) {
  let best = 0;
  const walk = (v) => {
    if (typeof v === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(v)) best = Math.max(best, Date.parse(v) || 0);
    else if (Array.isArray(v)) v.forEach(walk);
    else if (v && typeof v === 'object') Object.values(v).forEach(walk);
  };
  walk(docs);
  return best;
}

/** The stub runs in the page, before the page script. */
function stub({ docs, viewer, uid, name, live, liveData }) {
  const store = new Map(Object.entries(docs));
  /* the platform rules, as declared: the owner reads and writes all; a person reads and writes only their own subtree and their join entry */
  const allowed = (p) => viewer === 'owner' || (viewer === 'person' && (p.startsWith(`data/users/${uid}/`) || p === `join/${uid}`));
  const subs = new Set();
  const notify = () => subs.forEach((f) => f());
  const clone = (v) => (v === undefined ? v : JSON.parse(JSON.stringify(v)));
  const snapDoc = (id, data) => ({ id, exists: data !== undefined, data: () => clone(data), metadata: { fromCache: false, hasPendingWrites: false } });
  const ok = (a, op, b) => (op === '>=' ? a >= b : op === '>' ? a > b : op === '<=' ? a <= b : op === '<' ? a < b : op === '!=' ? a !== b : a === b);
  window.__writes = [];
  const docRef = (p) => ({
    id: p.split('/').pop(), path: p,
    get: async () => snapDoc(p.split('/').pop(), allowed(p) ? store.get(p) : undefined),
    set: async (d) => { if (!allowed(p)) throw { code: 'invalid_argument', message: 'not allowed' }; store.set(p, clone(d)); window.__writes.push(['set', p, clone(d)]); notify(); },
    update: async (d) => { if (!allowed(p)) throw { code: 'invalid_argument', message: 'not allowed' }; store.set(p, { ...(store.get(p) || {}), ...clone(d) }); window.__writes.push(['update', p, clone(d)]); notify(); },
    delete: async () => { if (!allowed(p)) throw { code: 'invalid_argument', message: 'not allowed' }; store.delete(p); window.__writes.push(['delete', p]); notify(); },
    onSnapshot: (next) => { const run = () => next(snapDoc(p.split('/').pop(), allowed(p) ? store.get(p) : undefined)); subs.add(run); queueMicrotask(run); return () => subs.delete(run); },
  });
  const coll = (name, filters = []) => {
    const snap = () => {
      const docs2 = [...store.entries()].filter(([k]) => k.startsWith(`${name}/`) && !k.slice(name.length + 1).includes('/') && allowed(k))
        .filter(([, d]) => filters.every(([f, op, v]) => ok(d[f], op, v)))
        .map(([k, d]) => snapDoc(k.slice(name.length + 1), d));
      return { docs: docs2, size: docs2.length, empty: !docs2.length, docChanges: () => [], metadata: { fromCache: false, hasPendingWrites: false } };
    };
    const q = {
      where: (f, op, v) => coll(name, [...filters, [f, op, v]]), orderBy: () => q, limit: () => q,
      get: async () => snap(),
      onSnapshot: (next) => { const run = () => next(snap()); subs.add(run); queueMicrotask(run); return () => subs.delete(run); },
      doc: (id) => docRef(`${name}/${id}`), path: name,
    };
    return q;
  };
  const db = { doc: docRef, collection: (n) => coll(n) };
  const myId = viewer === 'owner' ? 'u_owner' : uid;
  const user = {
    isOwner: async () => viewer === 'owner', canEdit: async () => viewer === 'owner',
    id: async () => myId, can: async () => true,
    me: async () => ({ id: myId, name: viewer === 'owner' ? 'David' : name, isOwner: viewer === 'owner', canEdit: viewer === 'owner' }),
    profiles: async () => ({}),
  };
  window.__saved = [];
  const downloads = {
    save: async ({ filename, data }) => {
      const buf = typeof data === 'string' ? new TextEncoder().encode(data) : new Uint8Array(data instanceof Blob ? await data.arrayBuffer() : data);
      let s = ''; for (const b of buf) s += String.fromCharCode(b);
      window.__saved.push({ filename, size: buf.length, b64: btoa(s) });
      return { status: 'saved' };
    },
  };
  const mcp = live === 'none' ? null : {
    watchTool: (server, tool, input, handler) => {
      window.__watch = { server, tool, input };
      setTimeout(() => {
        if (live === 'ok') handler({ type: 'data', result: { payload: liveData, cache: { storedAt: Date.now() } } });
        else handler({ type: 'error', error: { code: live, message: live } });
      }, 60);
      return () => {};
    },
  };
  const caps = { db, user, downloads, mcp };
  window.claude = { use: async (n) => caps[n] || null };
}

export async function open(opts = {}) {
  const docs = readDb(opts.db);
  const nowMs = opts.now ? Date.parse(opts.now) : (newest(docs) ? newest(docs) + 7 * 60000 : Date.now());
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
  const ctx = await browser.newContext({ viewport: { width: opts.width || 1100, height: opts.height || 900 }, permissions: ['clipboard-read', 'clipboard-write'] });
  const page = await ctx.newPage();
  const problems = [];
  page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`));
  page.on('console', (m) => { if (m.type() === 'error' && !/fonts\.g|ERR_|Failed to load resource/.test(m.text())) problems.push(`console: ${m.text()}`); });
  await page.route(/fonts\.(googleapis|gstatic)\.com/, (r) => r.abort());
  await page.clock.install({ time: new Date(nowMs) });
  const liveData = opts.liveData || null;
  await page.addInitScript(stub, { docs, viewer: opts.viewer || 'owner', uid: opts.uid || 'u_drew', name: opts.name || 'Drew', live: opts.live || 'blocked_by_policy', liveData });
  await page.goto(pathToFileURL(path.resolve(opts.page || 'dashboard/index.html')).href);
  /* the reset that the artifact page adds around the file when it is published */
  await page.addStyleTag({ content: ':root{color-scheme:light;box-sizing:border-box}body{margin:0;padding:0;font:14px -apple-system,BlinkMacSystemFont,sans-serif;background:#faf9f5;color:#141413}img{max-width:100%}[hidden]:not([hidden=until-found i]){display:none!important}' });
  await page.waitForTimeout(opts.wait ?? 900);
  return { page, ctx, browser, problems, nowMs, close: () => browser.close() };
}

async function main() {
  const a = { click: [] };
  const argv = process.argv.slice(2);
  for (let i = 0; i < argv.length; i += 2) {
    const k = argv[i].replace(/^--/, '');
    if (k === 'click') a.click.push(argv[i + 1]); else a[k] = argv[i + 1];
  }
  const out = a.out || '/tmp/preview';
  fs.mkdirSync(out, { recursive: true });
  let bad = 0;
  for (const w of String(a.widths || '390,1100').split(',').map(Number)) {
    const s = await open({ page: a.page, db: a.db, now: a.now, viewer: a.viewer, uid: a.uid, name: a.name, live: a.live, width: w });
    for (const sel of a.click) await s.page.click(sel);
    if (a.click.length) await s.page.waitForTimeout(300);
    const file = path.join(out, `board-${w}.png`);
    await s.page.screenshot({ path: file, fullPage: true });
    const overflow = await s.page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    console.log(`${file}${overflow > 1 ? `  HORIZONTAL OVERFLOW ${overflow}px` : ''}`);
    if (overflow > 1) bad = 1;
    for (const p of s.problems) { console.log(`  ${p}`); bad = 1; }
    await s.close();
  }
  process.exit(bad);
}

if (import.meta.url === pathToFileURL(process.argv[1] || '').href) main();
