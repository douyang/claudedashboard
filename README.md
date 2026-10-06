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
| `skills/token-dashboard/` | The skill that makes every Cowork and Claude Code session report to the board. `scripts/local_usage.py` measures a local session from its own transcript. |
| `skills/david-dev-style/` | The dev house style, with section 9 for dashboard reports. |
| `data/projects.json` | The project registry seed for the `projects` collection. |
| `docs/DATA.md` | The database collections, the access rules, and how the page computes its figures. |
| `CLAUDE.md` | What the usage-sync session does when it receives `sync`. |

## What the board keeps

| Data | Kept | Where |
|---|---|---|
| Each hourly reading of every session | until you delete it | `syncs/<epoch>`; the page reads the last 8 days |
| The first reading of each UTC day | for good | `daily/<UTC day>`; the page reads all of them |
| A session that Claude Code no longer lists | its last totals, for good | the ledger |
| Jobs, projects, session reports | in place, latest state | `jobs`, `projects`, `sessions` |

Usage before the first reading has no timestamps. Nobody recorded it, so no chart can place it. It counts in All tokens and cost. The ledger and the hourly readings build the history from the first reading on.

The CSV buttons next to the project table save the data as files: **Daily CSV** (the ledger, with the growth since each session's previous reading) and **Hourly CSV** (the newest 1000 readings of each person). A person exports their own. The owner exports everyone's. A spreadsheet never reads a title that starts with `=`, `+`, `-` or `@` as a formula.

The database holds at most 25,000 documents. Hourly readings add 24 a day for each person, and job rows add more. The sync reply says "Storage is nearly full" at 20,000. Then export the hourly CSV and delete the oldest readings. The ledger keeps the days.

## Who sees what

The page declares these database rules:

| Path | Read | Write |
|---|---|---|
| everything not listed | owner | owner |
| `join/<id>` | that person, and the owner | that person, and the owner |
| `data/users/<id>/...` | that person, and the owner | that person, and the owner |

The board owner's own collections (`jobs`, `projects`, `sessions`, `syncs`, `ticks`, `meta`) stay at the top level. Everyone else writes under `data/users/me/profile/`. The platform resolves `me` to the writer.

A person needs edit access to the board (Share menu, Contributor). The page sends no data from one person to another. The database refuses a read or write outside a person's own subtree.

## How a project is named

The board names a project after its repository: `owner/repo` of the first repository of the project or of its sessions.

- A project without a repository takes the name of its folder, for example a Cowork project.
- A project with neither keeps its own name.
- Two registry entries with the same repository are one project. Repository names compare without regard to case.
- A session that touched several repositories belongs to its first repository. A registry entry can pin it to another project through `sessions`.
- An older name stays valid as an alias. Job rows that use it keep their project.

`docs/DATA.md` lists the rules in order.

## How the figures are measured

- A rate counts only tokens that two readings at most 3 hours apart place in time. The page spreads them evenly between the two readings. One exception: a turn that every hourly reading saw running, with no two readings more than 3 hours apart, spreads its tokens over the whole turn, up to a day.
- Tokens used before the first reading, or between readings further apart, count in All tokens and cost. They count in no hour.
- A window ends at the newest reading and says how much of it the readings cover.
- Claude Code reports a running session's tokens only when a turn ends. Readings inside a turn show the same total. The board does not count them as zero: when the total grows, it spreads the growth over the turn, back to the last reading that saw the session idle or saw its total change.
- The hourly sync reads from each running session's events the token counts and times of each model call that the reported total does not hold yet. Claude Code adds an ended turn to that total late, sometimes hours late, and it can add an earlier turn first. So the count runs on through the ends of turns. When the total grows, the growth takes the oldest counted calls first, and the rest stays in the count. A count whose oldest calls are more than a day old is dropped. A script takes the counts from each event page and deletes the page, so no text reaches the board. A read can stop before the last counted call: after 30 pages, at a page with no event list, or where the events end. The script then marks the count as a floor. The board then draws the turn's real hours. Output tokens arrive when the turn ends; the events give only a floor for them.
- A turn that runs but has no event counts (a read that failed) shows as a hatched band on the chart and in a "Not counted yet" line under the figures.
- **Cloud and local.** A session that `list_sessions` lists is cloud: the hourly sync measures its tokens, state and turns. Every other session is local: Cowork, CLI, desktop, IDE and scheduled runs. The `tags` filter that would list Cowork sessions is served only to OAuth callers, and their events refuse a request from a cloud session, so only their own reports show them. A session's own word for its surface does not decide its place: a Cowork session can look like a cloud session from inside.
- The hourly sync reads each Cowork session that reports to the board with `get_session` by id. It answers with Claude Code's usage total and state, as for a cloud session. The row carries `via: get` and stays local. Such a total can fall short of the session's own count, and the cause is not known. For one Cowork session it read 111.7 M, where the session's own cost tracker read 219.3 M. Subagent calls do not explain the gap: that tracker read 128.4 M without them. In a test, the total of a cloud session held its subagent calls.
- A local session reports at the start, at each milestone, every 30 minutes, when a turn waits on the user, and at the end. Each report carries its state and the counts that `skills/token-dashboard/scripts/local_usage.py` reads from the session's own transcript: tokens, cost, and 10-minute points. The script reads no text into the report.
- A project is **working now** when a session runs or a running job reported in the last 30 minutes. The session that takes the hourly reading does not count: it runs because it reads. Job rows show its real work. It is **active** when it is working, has an open job, or had any report in the last 72 hours. An active project that is not working reads **Idle**. A local session that reported running and then nothing for 45 minutes does not count as working: its project reads **No report**.
- **Last token use** is the end of the last interval in which a session's total grew.
- **Colours.** The 16 projects with the latest activity hold a colour each. Slots 9 to 16 are the eight hues at a second lightness step. A registry `color` stays while its project is among the 16; the rest draw in grey.
- The page states each method and caveat once, as a numbered note at the bottom. A superscript number marks each place a note applies.

Why: an earlier version spread each session's lifetime tokens evenly from its creation to its last update. An idle project with billions of lifetime tokens then showed use in every recent hour. `tests/check.mjs` keeps that case.

## Add a person's Claude

1. Share the board with the person, with edit access.
2. On the board, press **Add a person's Claude**. Type the name. Press **Copy instructions**.
3. Send the text to the person. They paste it into their Claude, Claude Code or Cowork.
4. Ask them to open the board once. They appear under People.

The text makes the person's Claude do these steps once:

1. Read every session of the account with `list_sessions`, and write one `syncs` document and, on the first reading of each UTC day, one `daily` entry to the person's private subtree.
2. Check that the document exists.
3. Create a routine that runs every hour with the same sync as its prompt. The routine wakes the session that made it, so that session must stay alive.
4. Report what it did.

The text sends session ids, titles, status, model, times, repositories, token counts and cost. For a session that runs a turn, it also sends the token counts and times of that turn, read from the session's events. It sends no message text, task summaries or file contents.

Cowork and local CLI sessions do not appear in `list_sessions`. They report through the skill. **Save skill file** builds a zip of the skill for the person. They upload it in claude.ai under Settings, Capabilities, Skills.

A person who opens the board sees their own usage, and a **Set up my Claude** button that gives the same text for themselves.

## The hourly sync

A routine sends `sync` to the usage-sync session at minute 26 of every hour. The session follows `docs/SYNC.md` and writes `syncs/<epoch>`. `CLAUDE.md` holds the values, so the procedure survives a context reset.

After the listing, the sync reads each Cowork session that reports to the board with `get_session`, and the turn that runs now in each running session from its events. Sub-agents do both, which keeps the cost low and keeps the task summaries and messages out of the sync session. The sub-agent that calls `get_session` writes only the count fields of each answer, never the summary. A script keeps only the counts. `scripts/ccr_sync_doc.py turns-add` takes only token counts and times from each event page and deletes the page.

- The routine wakes one session that stays alive. A routine that starts a fresh session each hour does not work: fresh routine sessions do not get the Claude Code Remote tools, so they cannot call `list_sessions`.
- A routine message that arrives while the session works on another turn waits until that turn ends. If the newest reading is then more than 70 minutes old, the session runs the sync at the end of the turn, and it skips a late `sync` that arrives less than 30 minutes after a reading. `CLAUDE.md` holds both rules. The page marks a reading older than 80 minutes as late.
- To stop the sync, disable the routine in claude.ai Routines.
- One test run cost about $0.11 at API list prices.

## If the live read is blocked

The page asks Claude Code Remote for `list_sessions` every 10 minutes. It answers `blocked_by_policy` when the organization blocks that tool for pages. A page cannot change that, and Claude Code Remote does not appear in the owner's list at claude.ai/customize/connectors, so the board gives no steps to turn it on.

The board runs on the hourly syncs, states how old they are, and reads the running turns from the sessions' events. A live read would add nothing that the events do not give, except a reading every 10 minutes instead of every hour. Only the board owner calls the connector. Other people never see a connector prompt.

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

1. Zip each skill folder, for example `cd skills && zip -r token-dashboard.zip token-dashboard`.
2. In claude.ai, open Settings, then Capabilities, then Skills.
3. Upload `token-dashboard.zip`. It replaces the installed `token-dashboard` skill. Replace `david-dev-style` with its new zip too.
