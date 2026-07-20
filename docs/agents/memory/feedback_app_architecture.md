# App Architecture Rule

Each Django app contains ONLY what belongs to it:
- `recipes/` — everything related to recipes only
- `articles/` — everything related to articles only
- Any new functionality = create a dedicated new app

**Never put unrelated logic into an existing app.**

New apps follow the same standards as existing ones:
- Same design/styling patterns
- Same security patterns (login_required, superuser checks, noindex on admin pages, rate limiting where needed)
- Own `views.py`, `urls.py`, `templates/<appname>/`
