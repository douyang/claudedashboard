# claudedashboard

Source for the Claude activity dashboard: https://claude.ai/artifact/DLbfexxF2FECgcQ7Xy2jA4

The dashboard shows every Claude project, cloud and local. For each project it shows the jobs, the sessions, the tokens, the cost at API list prices, and the token velocity.

## Layout

| Path | Contents |
|---|---|
| `dashboard/index.html` | The artifact page. Publish this file to the artifact URL. |
| `data/projects.json` | The project registry seed for the `projects` collection. |
| `scripts/ccr_to_docs.py` | Converts a `list_sessions` answer into `sessions` and `ticks` documents. |
| `scripts/ccr_sync_doc.py` | Converts a `list_sessions` answer into one `syncs` document. The hourly routine runs it. |
| `skills/claude-dashboard/` | The skill that makes every Cowork and Claude Code session report to the board. |
| `skills/david-dev-style/` | The dev house style, with section 9 for dashboard reports. |
| `docs/DATA.md` | The database collections and how the page computes its figures. |

## Data sources

1. **Claude Code cloud sessions.** An hourly routine writes `list_sessions` totals to `syncs/<epoch>`. Where the viewer's connector allows it, the page also reads `list_sessions` live every 10 minutes. Each session carries its own token totals and cost.
2. **Session reports.** Sessions write `sessions/<id>` and `ticks/<id>~<UTC day>`. This is the only record for Cowork and local CLI sessions.
3. **Job rows.** Sessions write `jobs/<id>` for each task, with progress, estimates and token figures.
4. **The project registry.** `projects/<slug>` maps sessions and job names to a project, and records cloud or local.

## Hourly sync

A Claude Code session named "Claude dashboard usage sync" (`session_01DUrUFjVcU4hAjn48SH57kc`) runs `list_sessions` and `scripts/ccr_sync_doc.py`, and writes one `syncs` document. The routine "Claude dashboard hourly usage sync" (`trig_01KWTg8RqfUtRYo3FhjnTAGz`) wakes it at 26 minutes past each hour.

- A routine that starts a fresh session does not work here: fresh routine sessions do not get the Claude Code Remote tools.
- To stop the sync, disable the routine in claude.ai Routines.
- One test run cost about $0.11 at API list prices.

## Publish

1. Edit `dashboard/index.html`.
2. Run a syntax check on every inline script. The page has two: the early skin script and the board script.

   ```sh
   python3 - <<'PY'
   import re, subprocess
   s = open('dashboard/index.html').read()
   for i, js in enumerate(re.findall(r'<script>(.*?)</script>', s, re.S)):
       open(f'/tmp/c{i}.js', 'w').write(js)
       subprocess.run(['node', '--check', f'/tmp/c{i}.js'], check=True)
   PY
   ```

3. Publish the file to the artifact URL with the Artifact tool. Leave out `capabilities`, so that the stored declaration stays: `db` with its access rules, `downloads`, `mcp` (`Claude Code Remote`, tool `list_sessions`) and `user`.

If another session published a newer version, merge its changes into this file before you publish.

## Skins

The board has two skins. The data, the markup and the logic are the same in both.

- **Classic** is the default: the original paper-and-graphite look.
- **Swiss** is a white field, black type, one red accent and a visible 24px grid, from the Swiss Modern preset of [frontend-slides](https://github.com/zarazhangrui/frontend-slides). Archivo carries headings and figures. Nunito carries text.

The viewer picks a skin under Skin in the filter panel. The choice stays in that browser (`localStorage` key `cad.skin`). An early script applies it before the first paint. A browser with no saved choice, or with blocked storage, gets Classic. Classic loads no Archivo or Nunito font file.

The Swiss rules sit in their own style block, scoped to `:root[data-skin="swiss"]`. Classic rules do not change. In Swiss, red marks live work only, black marks a calm state, amber marks a person's turn, and crimson marks a failure. Project colours keep the same 16 slots in both skins.

## Install the skills

The skills in `skills/` are the source. Claude does not install them automatically.

1. Zip each skill folder, for example `cd skills && zip -r claude-dashboard.zip claude-dashboard`.
2. In claude.ai, open Settings, then Capabilities, then Skills.
3. Upload `claude-dashboard.zip`. Replace `david-dev-style` with the new zip.
