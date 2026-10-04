# Claude activity dashboard

This repository is the source of the board https://claude.ai/artifact/DLbfexxF2FECgcQ7Xy2jA4. The README describes the layout, the publish steps and the access rules.

## The `sync` message

A routine sends the message `sync` to the usage-sync session every hour (UTC minute 26). On `sync`, do only this:

1. Run `git pull --ff-only` in this checkout. Ignore a failure.
2. Follow `docs/SYNC.md` with these values:
   - board URL: `https://claude.ai/artifact/DLbfexxF2FECgcQ7Xy2jA4`
   - collection: `syncs`
   - daily collection: `daily`
   - script: `scripts/ccr_sync_doc.py` in this checkout (skip the step that saves it to `/tmp`)
3. Reply with one line.

Do not edit code, open pull requests, publish the artifact, or write other documents during a sync. Do not read task summaries. Read session events only as `docs/SYNC.md` says: the script takes token counts and times from them and deletes the pages, and no text leaves them. The board stores counts, titles and links only.

## Missed syncs

A routine message that arrives while this session works on another turn waits until that turn ends. The sync of 06:26 UTC on 4 Oct arrived at 06:52 this way, so the board had no reading from 05:35 to 06:40.

- At the end of every turn that is not a sync, read the newest `syncs` document. If its `at` is more than 70 minutes old, run the sync before the reply, and add its line to the reply.
- If a `sync` arrives less than 30 minutes after the newest reading, do not run it again. Reply with one line that names that reading.

## Rules for changes

- `docs/INVITE.md`, `docs/SYNC.md`, `scripts/ccr_sync_doc.py`, `skills/claude-dashboard/SKILL.md` and `skills/claude-dashboard/scripts/local_usage.py` are the source of the text that the page gives to other people. After you edit one, run `python3 scripts/embed_assets.py`.
- Never write a rate from tokens that no two readings at most 3 hours apart place in time. The one exception is a turn that every hourly reading in it saw running. The README explains why.
- The repository is public. Add no real session ids, session titles, transcripts or other people's data. Fixtures are synthetic. `data/projects.json` already lists real project names: treat it as exposed.
- Run `NODE_PATH=$(npm root -g) node tests/check.mjs` before you publish.
