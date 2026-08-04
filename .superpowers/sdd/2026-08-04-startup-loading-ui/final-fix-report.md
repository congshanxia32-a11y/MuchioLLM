# Final fix report — 2026-08-04 startup-loading-ui

Worktree:
`W:\UnityProjects\Sanatia\MuchioLLM_dist\MuchioLLM\.worktrees\startup-loading-ui`

Branch:
`codex/startup-loading-ui`

Summary:
- Kept the static HTML startup overlay architecture.
- Made `#workspace` start inert in HTML and synchronized inert removal/restoration through a shared `workspaceShouldBeInert()` / `syncWorkspaceInert()` path so loading/error and the existing tour logic do not fight each other.
- Moved focus to `#startup-loading-retry` when the error state is shown.
- Hardened the ready path so success always hides the overlay: clear stale ready timers first, establish a painted visible frame before applying `is-ready`, and keep a timeout fallback in addition to `transitionend`.
- Preserved `applyBootstrap(d); maybeStartTour();` ordering and kept HTTP/network/JSON failures on the shared retry/error path.
- Extended the static contract test only with focused token checks for the new inert/focus/animation safeguards.

Commands and outputs:

```text
> python test_ui_config.py
ok

> python test_muchio.py
20:18:47 モデル qwen3.6:35b-a3b-mtp-q4_K_M が入っていないので qwen3.5:9b で代用します(設定UIで選び直せます)
20:18:49 モデル qwen3:4b が入っていないので qwen3.6:latest で代用します(設定UIで選び直せます)
20:18:50 返答契約違反を検出: peer_meta,peer_language
20:18:50 返答契約違反を検出: peer_meta,peer_language
20:18:50 返答契約違反を検出: peer_meta,peer_language
20:18:50 返答契約違反を検出: peer_meta,peer_language
20:18:50 表示条件を満たす返答を3回得られなかったため破棄
ok

> git diff --check
warning: in the working copy of 'test_ui_config.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'ui/app.js', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'ui/index.html', LF will be replaced by CRLF the next time Git touches it
```

Files changed:
- `test_ui_config.py`
- `ui/app.js`
- `ui/index.html`
