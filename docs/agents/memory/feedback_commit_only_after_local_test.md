# No Commits Until Local is Clean

Before committing to git, ALL of the following must be true:
- `python manage.py check` passes with 0 issues
- `python manage.py migrate` — no unapplied migrations
- All changes are tested/verified locally
- `git status` reviewed to confirm nothing unexpected is staged

**Never commit "to be tested later on prod."**
