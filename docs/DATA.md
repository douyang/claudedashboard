# Dashboard data

The artifact database holds the collections below. All timestamps are UTC.

## Data planes and access

| Plane | Where | Who reads and writes |
|---|---|---|
| The board owner | `jobs`, `projects`, `sessions`, `syncs`, `ticks`, `meta` at the top level | The board owner only. |
| A person | `data/users/<id>/profile/<collection>` with the same collection names, and the document `data/users/<id>/profile` | That person and the board owner. |
| The person registry | `join/<id>` | That person and the board owner. |

`<id>` is the person's user id on the board. In `ArtifactData`, write `data/users/me/...` and the platform resolves `me` to the writer. The page declares the rules that enforce this (see the README). The page never trusts an `owner` field in a document. A document's owner is the plane it was read from.

The collections below have the same fields on every plane.

## `projects/<slug>`

The registry. One document per project.

| Field | Meaning |
|---|---|
| `name` | The project's own name. The board shows the first repository instead, else `folder`, else this name. Job rows that use this name keep their project. |
| `aliases` | Other names that job rows use for this project. |
| `where` | `cloud` or `local`. The project's sessions decide its place on the board; this field counts only for a project with no session. |
| `surface` | For example `Claude Code · cloud` or `Cowork`. |
| `sessions` | Session ids that belong to the project. |
| `repos` | `owner/repo` strings. The first one names the project on the board. All appear as links on the card. |
| `folder` | The folder name of a project that has no repository, for example a Cowork project. |
| `artifacts` | Links shown on the project card. |
| `status` | `active`, `paused` or `done`. `paused` and `done` make the project inactive. |
| `pinned` | `true` keeps the project active. |
| `color` | A fixed colour slot, 1 to 16. Slots 1 to 8 are the eight categorical hues; 9 to 16 are the same hues at a second lightness step, and the 16-slot order passes the palette validator on adjacent pairs in both modes. The 16 projects with the latest activity hold a slot each: a registry colour stays while its project is among them, and a project without one takes the lowest free slot. The rest draw in grey as Other. |
| `lastActivityAt` | Set by a reporting session. A registry edit does not set it. |

### How the board names a project

The first rule that applies to a session:

1. A registry document lists the session in `sessions`: the session belongs to that project.
2. The session has a repository: it belongs to the project of its first repository.
3. The session has a `folder`: it belongs to the project of that folder.
4. The session has a `project` field: that name.
5. Otherwise the session forms a project named by its title.

The title of a registry project is its first repository, else its `folder`, else its `name`. Repository names compare without regard to case, and the registry's spelling wins. Registry documents with the same title are one project. The old `name` and every alias still reach the project, so older job rows keep it.

## `sessions/<session id>`

One document per session. `repos` (`owner/repo` strings) and `folder` decide the project, as above. `tok` counts input, cache reads, cache writes and output. `usd` is the cost at API list prices. `partial: true` marks a floor. When the Claude Code Remote connector answers, the live figures replace the stored ones for the board owner's cloud sessions.

A local session (one that no hourly reading lists) writes this document as its report: `status`, `updatedAt`, and the counts that `skills/token-dashboard/scripts/local_usage.py` reads from its own transcript, with `src: "transcript"`: `tok`, `out`, `calls`, `untimed` (tokens that Claude Code counted but whose call records the transcript no longer holds), `since`, `lastAt`, `pts` (`[epoch seconds, tokens so far]`: the last total in each 10-minute bucket with model calls, and the total before each bucket that follows a gap), and `usd` and `usdAt` from Claude Code's own cost record when the transcript holds one. The page draws `pts` as readings. The script reads only ids, times and token counts, and the report holds no text.

## `syncs/<epoch seconds>`

One document per hourly sync. A scheduled routine calls `list_sessions`, runs `scripts/ccr_sync_doc.py`, and writes the result. Fields: `at`, `src`, `by` (the id of the session that took the reading, when the script can tell), `turn` on a running session (below), `sessions` (id, title, status, bucket, model, createdAt, updatedAt, tok, out, usd, repos, and `via: "get"` on a Cowork session that the sync read with `get_session` because the listing leaves it out), and `quota` (the limit state of the most recently updated session). The page reads the last 8 days. The newest sync of each person supplies that person's cloud sessions when the page cannot read Claude Code Remote itself, for example when the connector answers `blocked_by_policy`. The sync stores no message text and no task summaries.

`turn` holds the tokens that the session's reported total does not hold yet, read from the session's events. Claude Code adds an ended turn to that total late, sometimes hours late, and it can add an earlier turn first. So the count runs on through the ends of turns, also after the session stops running. When the total grows, the growth takes the oldest counted calls first and the rest stays in the count; `since` and `pts` move with it. A count whose oldest calls are more than a day old is dropped. The script reads the last three readings. A newer count can start after the last call of an older count that still has tokens outside the total. Then the older count continues. Fields: `since`, `tok` (its tokens so far, input, cache and output), `out` (a floor until the turn ends), `calls`, `lastAt` and `lastMsg` (where the next reading continues), `pts` (`[epoch seconds, tokens so far]`, one per 10 minutes) and `partial` (a floor: the read stopped before the start of the turn or the last counted call, at the 30-page cap, at a page with no event list, or where the events ended first). The script takes these counts from each event page and deletes the page; no text is stored. The page adds `tok` to the session's reported total and draws the points.

`bucket` is Claude Code's own state: `working`, `blocked` (waits on a person), `review_ready`, `completed` or `failed`.

## `daily/<UTC day>`

The ledger. One entry per UTC day, written by the sync at the day's first reading and never replaced: the board keeps the first one. Fields: `day`, `at`, `src`, `cols` (id, title, status, tok, out, usd, createdAt, repo, via), and `rows`, one array per session with the totals at that reading. An entry is about 4 KB for 22 sessions. The page reads every entry, so the ledger never leaves the window.

A completed day that has hourly readings but no entry gets one from the page, made from the day's first reading. `scripts/ccr_sync_doc.py --from-sync SYNC.json DAILY.json` makes the same entry.

The ledger keeps three things that the hourly readings cannot:
- Usage per day for the 30 d, 90 d and All ranges, after the hourly readings leave the 8-day window.
- A session that Claude Code no longer lists. The board counts its last known totals and marks it "No longer listed".
- A durable copy for the CSV export.

## `ticks/<session id>~<UTC day>`

Usage snapshots. `pts` is an array of `[epoch seconds, cumulative tokens]`. One document per session per day keeps the database far below its 25,000-document limit.

## `jobs/<id>`

One row per task. The dashboard's "Posting from another Claude session" panel lists the fields.

## `meta/board`, `meta/quota`

`meta/board` holds a note. `meta/quota` holds the board owner's account limit as Claude Code reports it. Everyone else stores the same fields as the object `quota` in the document `data/users/<id>/profile`.

## `join/<id>`

Written by a person when they open the board: `name`, `joinedAt`, `seenAt`. The board owner adds `label`, the name that the board shows. The board lists a person under People from this document.

## How the page computes its figures

- **Points.** For each session, the page builds a series of `[time, cumulative tokens]`: zero at `createdAt` for a cloud session, every sync and snapshot, and the current total at `updatedAt` (or at the live read time for a running session). The series never decreases.
- **Measured tokens.** Between two consecutive points at most 3 hours apart, the page spreads the growth evenly over the time between them. Growth across a longer gap is **unplaced**: the tokens are in the totals and in no hour. Equal totals at both ends count as measured zero, whatever the gap.
- **Turns.** Claude Code reports a running session's tokens only when a turn ends, so readings inside a turn show the same total. When the total grows, the page drops the readings that an hourly sync took while the session ran with that total, back to the last reading that saw it idle or saw the total change. The growth then spreads over the whole turn. A turn longer than 3 hours places its tokens too, when no two readings in it are more than 3 hours apart and it lasts at most a day. When the hourly sync read the running turn from the session's events, its points take the place of the flat readings, so the chart shows the turn's real hours. A turn that runs with no event counts is not a measured zero: the chart hatches it and the figures name it as not counted yet.
- **Windows.** The last hour, 24 hours and 7 days end at the newest reading. Each says how long the readings cover inside it. A rate divides the measured tokens by that covered time.
- **Limit tiles.** Claude Code reports only the limit that applies at the time: the 5-hour window or the 7-day window. The page keeps the latest report of each window. The 5-hour tile shows while its reset is ahead. The 7-day tile shows only after Claude Code reported a 7-day limit; the trailing 7 days are the Last 7 d figure. Each tile counts from its reset less its length to the newest reading. Until a reading falls in a window, the tile says so. Last 5 h is a trailing window like the others. The cost is each session's reported dollars per token times its measured tokens, marked ≈. Claude Code reports no share of either limit, so the tiles show none.
- **Days.** Last 30 days and the 30 d, 90 d and All ranges accept readings at most 26 hours apart. Hourly readings keep their own time. A pair of ledger readings places its tokens in the UTC day of the earlier reading. A gap longer than 26 hours places nothing.
- **Sessions that left.** A session that appears in the hourly readings or the ledger but not in the newest listing keeps its last known totals, marked "No longer listed". Its tokens stay in All tokens and cost.
- **Last token use.** The end of the last interval in which a session's total grew. A project takes the latest of its sessions.
- **Cost.** At API list prices, as Claude Code reports it, in whole dollars. A project with tokens but no reported cost (a Cowork session) gets the account's dollars per token, marked with ≈.
- **Open jobs.** What the open jobs still need: each running or queued job adds its `tokEst` less its `tok`. A job with a time estimate and no `tokEst` adds the project's measured rate times its time left. A job with neither adds nothing, and the board says so. Cost uses the project's own dollars per token. The board shows this sum, not the total plus it: the total has its own figure.
- **End times.** A running job ends when its `done` count, at its rate so far (`rate`, or `done` over the time since `startedAt`), reaches `total`, or at `startedAt` plus `estSec`. A queued job takes `estSec`. A job with neither has no time estimate, and its project and the top line say so. The board takes no time from `tokEst`: a session's token rate covers all its jobs at once.
- **Working now.** A running session, or a running job that reported in the last 30 minutes. The session that took the newest hourly reading (`by`) does not count: it runs because it reads. Its updates do not count as activity either. Its tokens and cost count as usual.
- **Active.** Working now, an open job, or any activity in the last 72 hours. `status` and `pinned` override this.
- **Cloud or local.** A session is cloud when an hourly reading or the ledger lists it (a row without `via: "get"`), or its report came from its own `get_session` call (`src: "ccr"`). A row with `via: "get"` is a Cowork session that the sync read by id: it stays local, and its readings place its tokens like a cloud session's. Every other session is local: Cowork, CLI, desktop, IDE and scheduled runs, which only their own reports show. A session's own `where` and `surface` do not decide it: a Cowork session can look like a cloud session from inside. A project with sessions takes their place (cloud, local, or both); a project without one takes its registry `where`, else its job rows' surfaces.
- **Silent local sessions.** A local session that reported `running` and then sent no report for 45 minutes reads "No report for …" and does not count as Working now. Its project reads No report instead of Idle. A local session reports at least every 30 minutes while it works.
- **Colours.** Each project draws in its slot in the chart, the table, and on its card. The 16 projects with the latest activity hold a slot each: a registry `color` stays while its project is among them, and the others take the free slots, latest activity first. The bars stack in slot order.
