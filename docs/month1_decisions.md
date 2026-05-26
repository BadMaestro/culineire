# Month 1 Decisions

This document records Month 1 choices that should not be re-litigated by
external tooling unless the project context changes.

## Structured Data

- Recipe JSON-LD is implemented in `recipes/templatetags/recipe_schema.py`.
- Article JSON-LD is implemented in `articles/views.py`.
- Breadcrumb JSON-LD exists on recipe and article detail pages.
- Production HTML has been checked for one recipe and one article.
- Google Rich Results validation still needs manual re-checks after each deploy.

## Image Optimisation

Decision: do not add `django-imagekit` yet.

Reason:

- The project already validates JPG, PNG, and WebP uploads.
- Adding a new image pipeline now would create migration/deployment risk before
  there is enough traffic data.
- Prefer this order:
  1. Audit PageSpeed/Core Web Vitals on production.
  2. Encourage or convert new uploads to WebP through a dedicated, tested flow.
  3. Add CDN/media optimisation when traffic justifies it.

## Ads

Decision: wait before adding Ezoic scripts or ad placeholders.

Reason:

- Month 1 priority is traffic and content quality.
- Premature ads can hurt UX and Core Web Vitals.
- When ads start, use only restrained placements: after intro, between method
  and tips, and footer.

## Affiliate Links

Decision: do not refactor ingredients into an `Ingredient` model in Month 1.

Reason:

- Ingredients are currently a `TextField`, one ingredient per line.
- An affiliate model should work alongside text ingredients first.
- A future design can map optional product links to recipe + ingredient label
  without forcing a risky content migration.

## Content Automation

- `generate_recipe.py` exists and saves AI-assisted output as draft/pending only.
- Batch generation exists through `--batch`.
- Real API usage requires `ANTHROPIC_API_KEY`.
- Human review remains required before approval.
