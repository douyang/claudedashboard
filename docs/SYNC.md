<!-- Template. The board page and scripts/embed_assets.py fill {{BOARD}}, {{COLLECTION}} and {{SCRIPT}}. -->
Sync the Claude sessions of this account to the board {{BOARD}}. Do only these steps. Do not edit code, open pull requests, or write other documents. Keep the reply to one line.

1. Load the tools. Run ToolSearch with "select:mcp__claude-code-remote__list_sessions,ArtifactData". Skip this step when both tools are loaded.
2. Run `date -u +%Y-%m-%dT%H:%M:%SZ`. Call the result T.
3. Save the script at the end of this text to /tmp/ccr_sync_doc.py. Skip this step when the file exists or when the repository checkout has scripts/ccr_sync_doc.py.
4. Call list_sessions with {"limit": 100}. The tool saves a long answer to a file and gives the path. If the answer arrives inline, write it to /tmp/ls1.txt.
5. Run: python3 /tmp/ccr_sync_doc.py <answer files> /tmp/sync.json --at T
   The script prints one JSON line with doc_id, sessions, tok, more and after_id.
6. If "more" is true, call list_sessions with {"limit": 100, "after_id": "<after_id>"}. Save the answer as the next file (/tmp/ls2.txt, /tmp/ls3.txt, ...). Run step 5 again with every file. Repeat until "more" is false.
7. Call ArtifactData with action "set", url "{{BOARD}}", collection "{{COLLECTION}}", doc_id = the printed doc_id, file_path "/tmp/sync.json". Do not pass if_version. If the set fails because the document exists, stop.
8. Delete the answer files and /tmp/sync.json.
9. Reply with one line: "Synced <sessions> sessions, <tok> tokens at T." If a step fails, reply with one line that names the step and the error, and stop.

The script:

```python
{{SCRIPT}}
```
