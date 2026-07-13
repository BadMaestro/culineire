# chef_battle fixtures

## ⚠️ `battle_artifacts.json` blanks artifact images on loaddata

`battle_artifacts.json` seeds 200 artifacts (pk 1–200) but **omits the `image`
field**. `manage.py loaddata battle_artifacts.json` overwrites each row by PK, so
the missing `image` is reset to its model default (`""`). Every run therefore
**blanks `Artifact.image` for pk 1–200**, orphaning the generated image files
that still sit in `media/chef_battle/artifacts/`.

This already happened once (2026-07-01, during the Irish-myth artifact rename).

### If you must run this loaddata

Run the recovery command immediately after — it re-points blank-image artifacts
at their existing on-disk files by PK (no regeneration, idempotent):

```
python manage.py loaddata battle_artifacts.json
python manage.py relink_artifact_images
```

### Better: don't use loaddata for content-only edits

To change only names/descriptions on live artifacts, prefer a targeted
`.update()` (or a small data migration) that touches just those fields, so the
`image` field is never overwritten in the first place.
