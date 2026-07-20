# Always stage untracked files related to the task

Before every commit, check BOTH sections of `git status`:
- `Changes not staged for commit` (modified files)
- `Untracked files` (new files not yet in git)

If any untracked file belongs to the current task (new image, new template,
new static asset, new migration, etc.) — add it to the same commit.

**Never commit a template that references a static file without also
committing that static file.**

Bad pattern:
```
git add templates/... static/css/...
# forgot static/images/hero-profanity.png → file missing on server after deploy
```

Good pattern:
```
git status          # read both sections
git add <all files related to the task, modified AND untracked>
git commit ...
```
