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

## Publish

1. Edit `dashboard/index.html`.
2. Run a syntax check on the inline script:

   ```sh
   python3 -c "s=open('dashboard/index.html').read(); open('/tmp/c.js','w').write(s.split('<script>')[1].split('</script>')[0])" && node --check /tmp/c.js
   ```

3. Publish the file to the artifact URL with the Artifact tool. Declare the capabilities `db` and `mcp` (`Claude Code Remote`, tool `list_sessions`).

If another session published a newer version, merge its changes into this file before you publish.

## Install the skills

The skills in `skills/` are the source. Claude does not install them automatically.

1. Zip each skill folder, for example `cd skills && zip -r claude-dashboard.zip claude-dashboard`.
2. In claude.ai, open Settings, then Capabilities, then Skills.
3. Upload `claude-dashboard.zip`. Replace `david-dev-style` with the new zip.
