# Dashboard data

The artifact database holds six collections. All timestamps are UTC.

## `projects/<slug>`

The registry. One document per project.

| Field | Meaning |
|---|---|
| `name` | The project name on the board. |
| `aliases` | Other names that job rows use for this project. |
| `where` | `cloud` or `local`. When absent, the board derives it from the sessions and job surfaces. |
| `surface` | For example `Claude Code · cloud` or `Cowork`. |
| `sessions` | Session ids that belong to the project. |
| `repos`, `artifacts` | Links shown on the project card. |
| `status` | `active`, `paused` or `done`. `paused` and `done` make the project inactive. |
| `pinned` | `true` keeps the project active. |
| `color` | A fixed colour slot, 1 to 8. A project without one draws in grey as Other. Eight is the most colours a chart can keep apart for readers with colour-vision deficiency. |
| `lastActivityAt` | Set by a reporting session. A registry edit does not set it. |

## `sessions/<session id>`

One document per session. `tok` counts input, cache reads, cache writes and output. `usd` is the cost at API list prices. `partial: true` marks a floor. When the Claude Code Remote connector answers, the live figures replace the stored ones for cloud sessions.

## `syncs/<epoch seconds>`

One document per hourly sync. A scheduled routine calls `list_sessions`, runs `scripts/ccr_sync_doc.py`, and writes the result. Fields: `at`, `src`, `sessions` (id, title, status, createdAt, updatedAt, tok, out, usd, repos), and `quota` (the limit state of the most recently updated session). The page reads the last 8 days. The newest sync supplies the cloud session totals when the page cannot read Claude Code Remote itself, for example when the connector answers `blocked_by_policy`.

## `ticks/<session id>~<UTC day>`

Usage snapshots. `pts` is an array of `[epoch seconds, cumulative tokens]`. One document per session per day keeps the database far below its 25,000-document limit.

## `jobs/<id>`

One row per task. The dashboard's "Posting from another Claude session" panel lists the fields.

## `meta/board`, `meta/quota`

`meta/board` holds a note. `meta/quota` holds the account limit state as Claude Code reports it.

## How the page computes its figures

- **Points.** For each session, the page builds a series of `[time, cumulative tokens]`: zero at `createdAt` for a cloud session, every snapshot, and the current total at `updatedAt` (or at the live read time for a running session). The series never decreases.
- **Tokens in a time range.** Between two points, the page spreads the tokens evenly over the time between them. A gap longer than 3 hours counts as "spread"; the page shows the share of spread tokens.
- **Cost.** At API list prices, as Claude Code reports it, in whole dollars. A project with tokens but no reported cost (a Cowork session) gets the account's dollars per token, marked with ≈.
- **At the end of the open jobs.** Each running or queued job adds its `tokEst` less its `tok`. A job with a time estimate and no `tokEst` adds the project's current rate (last hour, else the 24-hour average) times its time left. A job with neither adds nothing, and the board says so. Cost uses the project's own dollars per token.
- **Colours.** Each project draws in its registry slot in the chart, the table, and on its card. The bars stack in slot order.
- **Active project.** An open job, a running session, or any activity in the last 72 hours. `status` and `pinned` override this.
- **Cloud or local.** The registry `where` first. Else Claude Code cloud sessions and `Claude Code · web` rows count as cloud, and `Cowork` and `CLI` rows count as local.
