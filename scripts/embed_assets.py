#!/usr/bin/env python3
"""Embed the instruction sources in dashboard/index.html.

The board page builds the "Add a person's Claude" instructions and the skill
file in the browser. It reads these sources from one JSON block between the
markers <!-- assets:start --> and <!-- assets:end -->:

  invite  docs/INVITE.md                 the paste-once setup text
  sync    docs/SYNC.md                   the hourly sync procedure
  script  scripts/ccr_sync_doc.py        the script that the sync procedure runs
  skill   skills/claude-dashboard/SKILL.md
  localUsage  skills/claude-dashboard/scripts/local_usage.py   the script that local sessions run

The files are the source of truth. Do not edit the block by hand.

Usage:
  python3 scripts/embed_assets.py          rewrite the block
  python3 scripts/embed_assets.py --check  exit 1 when the block is out of date
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, 'dashboard', 'index.html')
SOURCES = {
    'invite': 'docs/INVITE.md',
    'sync': 'docs/SYNC.md',
    'script': 'scripts/ccr_sync_doc.py',
    'skill': 'skills/claude-dashboard/SKILL.md',
    'localUsage': 'skills/claude-dashboard/scripts/local_usage.py',
}
START, END = '<!-- assets:start -->', '<!-- assets:end -->'


def read(rel):
    txt = open(os.path.join(ROOT, rel), encoding='utf-8').read()
    lines = txt.split('\n')
    if lines and lines[0].startswith('<!-- Template.'):
        txt = '\n'.join(lines[1:])
    return txt


def block():
    data = {k: read(v) for k, v in SOURCES.items()}
    # "<" is escaped so the text can never close the script element early.
    body = json.dumps(data, ensure_ascii=False, indent=0).replace('<', '\\u003c')
    return f'{START}\n<script type="application/json" id="assets">{body}</script>\n{END}'


def main():
    page = open(PAGE, encoding='utf-8').read()
    m = re.search(re.escape(START) + r'[\s\S]*?' + re.escape(END), page)
    if not m:
        sys.exit(f'markers {START} and {END} not found in {PAGE}')
    new = page[:m.start()] + block() + page[m.end():]
    if '--check' in sys.argv:
        if new != page:
            print('dashboard/index.html is out of date: run python3 scripts/embed_assets.py')
            sys.exit(1)
        print('assets block is current')
        return
    open(PAGE, 'w', encoding='utf-8').write(new)
    print(f'embedded {", ".join(SOURCES)} ({len(new) - len(page):+d} bytes)')


if __name__ == '__main__':
    main()
