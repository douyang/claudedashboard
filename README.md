# claudedashboard

Source for the Claude activity dashboard: https://claude.ai/artifact/DLbfexxF2FECgcQ7Xy2jA4

The dashboard shows every Claude project, cloud and local. For each project it shows the jobs, the sessions, the tokens, the cost at API list prices, and the token rate. Each person on the board sees their own usage. The board owner sees everyone's.

## Layout

| Path | Contents |
|---|---|
| `dashboard/index.html` | The artifact page. Publish this file to the artifact URL. |
| `docs/INVITE.md` | The text that the board gives to a person to paste into their Claude. A template. |
| `docs/SYNC.md` | The hourly sync procedure. The invite text and the owner's routine use it. A template. |
| `scripts/ccr_sync_doc.py` | Turns `list_sessions` answers into one `syncs` document. |
| `scripts/ccr_to_docs.py` | Turns a `list_sessions` answer into `sessions` and `ticks` documents. A manual importer. |
| `scripts/embed_assets.py` | Copies the invite text, the sync procedure, the sync script and the skill into the page. |
| `scripts/preview.mjs` | Loads the page in Chromium with a stub of `window.claude`, and saves screenshots. |
| `tests/check.mjs` | End-to-end checks of the page against synthetic fixtures. |
| `tests/make_fixtures.py` | Writes the synthetic fixtures. The names and numbers are invented. |
| `skills/claude-dashboard/` | The skill that makes every Cowork and Claude Code session report to the board. |
| `skills/david-dev-style/` | The dev house style, with section 9 for dashboard reports. |
| `data/projects.json` | The project registry seed for the `projects` collection. |
| `docs/DATA.md` | The database collections, the access rules, and how the page computes its figures. |
| `CLAUDE.md` | What the usage-sync session does when it receives `sync`. |

## Who sees what

The page declares these database rules:

| Path | Read | Write |
|---|---|---|
| everything not listed | owner | owner |
| `join/<id>` | that person, and the owner | that person, and the owner |
| `data/users/<id>/...` | that person, and the owner | that person, and the owner |

The board owner's own collections (`jobs`, `projects`, `sessions`, `syncs`, `ticks`, `meta`) stay at the top level. Everyone else writes under `data/users/me/profile/`. The platform resolves `me` to the writer.

A person needs edit access to the board (Share menu, Contributor). The page sends no data from one person to another. The database refuses a read or write outside a person's own subtree.

## How the figures are measured

- A rate counts only tokens that two readings at most 3 hours apart place in time. The page spreads them evenly between the two readings.
- Tokens used before the first reading, or between readings further apart, count in All tokens and cost. They count in no hour.
- A window ends at the newest reading and says how much of it the readings cover.
- A project is **working now** when a session runs or a running job reported in the last 30 minutes. It is **active** when it is working, has an open job, or had any report in the last 72 hours. An active project that is not working reads **Idle**.
- **Last token use** is the end of the last interval in which a session's total grew.

Why: an earlier version spread each session's lifetime tokens evenly from its creation to its last update. An idle project with billions of lifetime tokens then showed use in every recent hour. `tests/check.mjs` keeps that case.

## Add a person's Claude

1. Share the board with the person, with edit access.
2. On the board, press **Add a person's Claude**. Type the name. Press **Copy instructions**.
3. Send the text to the person. They paste it into their Claude, Claude Code or Cowork.
4. Ask them to open the board once. They appear under People.

The text makes the person's Claude do these steps once:

1. Read every session of the account with `list_sessions`, and write one `syncs` document to the person's private subtree.
2. Check that the document exists.
3. Create a routine that runs every hour with the same sync as its prompt. One fresh session runs each time.
4. Report what it did.

The text sends session ids, titles, status, model, times, repositories, token counts and cost. It sends no messages, transcripts, task summaries or file contents.

Cowork and local CLI sessions do not appear in `list_sessions`. They report through the skill. **Save skill file** builds a zip of the skill for the person. They upload it in claude.ai under Settings, Capabilities, Skills.

A person who opens the board sees their own usage, and a **Set up my Claude** button that gives the same text for themselves.

## The hourly sync

A routine sends `sync` to the usage-sync session at minute 26 of every hour. The session follows `docs/SYNC.md` and writes `syncs/<epoch>`. `CLAUDE.md` holds the values, so the procedure survives a context reset.

## If the live read is blocked

The page asks the Claude Code Remote connector for `list_sessions` every 10 minutes. The connector answers `blocked_by_policy` when the organization blocks that tool for pages. A page cannot change that.

To turn the live read on:

1. Open https://claude.ai/customize/connectors and select Claude Code Remote.
2. Under tool permissions, set `list_sessions` to allowed.
3. If allowed is not offered, an organization admin capped the tool. Ask the admin.
4. Reload the board.

Until then the board runs on the hourly syncs and states how old they are. Only the board owner calls the connector. Other people never see a connector prompt.

## Publish

1. Run `python3 scripts/embed_assets.py`.
2. Run the checks:

   ```sh
   python3 scripts/embed_assets.py --check
   python3 -c "s=open('dashboard/index.html').read(); i=s.index('<script>\n(() => {'); open('/tmp/c.js','w').write(s[i+8:s.index('</script>', i)])" && node --check /tmp/c.js
   NODE_PATH=$(npm root -g) node tests/check.mjs
   ```

3. Publish `dashboard/index.html` to the artifact URL with the Artifact tool and these capabilities:

   ```json
   {
     "db": { "rules": [
       { "path": "", "read": "owner", "write": "owner" },
       { "path": "join", "read": "owner", "write": "owner" },
       { "path": "join/{self}", "read": "interact", "write": "interact" },
       { "path": "data/users", "read": "owner", "write": "owner" },
       { "path": "data/users/{self}", "read": "interact", "write": "interact" }
     ] },
     "user": { "scopes": ["profile"] },
     "mcp": { "servers": [{ "server": "Claude Code Remote", "tools": ["list_sessions"] }] },
     "downloads": true
   }
   ```

4. Read the collections with `ArtifactData` and `as_level: "interact"`. The top-level collections must read as empty.

If another session published a newer version, merge its changes into this file before you publish.

## Install the skills

The skills in `skills/` are the source. Claude does not install them automatically. An installed skill applies to every project.

1. Zip each skill folder, for example `cd skills && zip -r claude-dashboard.zip claude-dashboard`.
2. In claude.ai, open Settings, then Capabilities, then Skills.
3. Upload `claude-dashboard.zip`. Replace `david-dev-style` with the new zip.
