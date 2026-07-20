# ALWAYS push to GitHub after every commit — without exception

## The rule

After EVERY commit (or series of commits), immediately run:
```
git push origin main
```

Then verify:
```
git status
# Must show: "Your branch is up to date with 'origin/main'"
# NOT: "Your branch is ahead of 'origin/main' by N commits"
```

## Why this is critical

- The deploy script pulls from GitHub (`git pull`), NOT from the local machine
- If commits are not pushed, the server deploys OLD code
- The user sees no changes on the live site and assumes the fix didn't work
- This has caused multiple wasted deploy cycles

## The workflow — no exceptions

```
1. git add <files>
2. git commit -m "..."
3. git push origin main        ← MANDATORY, never skip
4. verify: git status → "up to date with origin/main"
5. tell the user it is ready to deploy
```

## Important: git workflow in this project

- The repo lives on the **Windows machine** (this chat environment)
- Claude prepares changes and shows a summary
- The **user says "да, коммит"** to approve
- Then **Claude runs** git add / git commit / git push origin main via Bash tool
- After push, user deploys via `deploy/update.sh` on the Linux server as usual

## Never say "ready to deploy" until git status confirms the branch is up to date with origin.
