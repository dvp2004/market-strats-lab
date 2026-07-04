# Market Strats Lab safety controls

- Work only inside the currently opened repository.
- Never run git clean, reset, restore, checkout, add, commit, push,
  stash, merge, rebase or cherry-pick.
- Preserve all unrelated dirty-working-tree changes.
- Never retrieve or refresh market data unless explicitly instructed.
- Do not select mutable latest files.
- Do not access excluded credential, state or private-data paths.
- Run focused tests before the full suite.
- Never stage or commit changes.
- Distinguish pre-existing dirty paths from agent-created changes.