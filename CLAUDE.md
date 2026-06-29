# CulinEire Project Rules

Use this file as the source of truth before applying tasks from external tools.
Check the current code first, because older roadmaps may describe fields or files
that no longer match the project.

## Current Stack

- Django 5.2
- Custom CMS for recipes, articles, moderation, monitoring, messaging, collection,
  legal pages, newsfeed, and sandbox tools
- Main app root: `CulinEire`

## Real Recipe Fields

The `Recipe` model uses these current field names:

- `title`
- `slug`
- `short_description` - not `description`
- `hero_image` - not `cover_image`
- `hero_image_alt_text`
- `author` - `ForeignKey(RecipeAuthor)`
- `category` - `CharField` with `Recipe.Category` choices, not a `Category` model
- `prep_time_minutes`
- `cook_time_minutes`
- `servings`
- `calories`
- `difficulty`
- `ingredients` - `TextField`, one ingredient per line
- `method` - `TextField`, step-by-step method
- `tips`
- `irish_context`
- `author_commentary`
- `allergens`
- `source_type`, `source_title`, `source_author`, `source_url`, `source_note`
- `image_rights_status`, `image_rights_note`
- `confirmed_own_work`, `confirmed_image_rights`, `confirmed_rules`
- `status` - `draft`, `pending`, `approved`, `NEEDS_CHANGES`, `rejected`
- soft delete fields: `is_deleted`, `deleted_at`, `deleted_by`

There is currently no separate `Ingredient` model. Do not introduce one for
affiliate links or automation without an explicit architecture decision.

## Real Article Fields

The `Article` model uses:

- `title`
- `slug`
- `author` - `ForeignKey(RecipeAuthor)`
- `excerpt`
- `category` - `CharField` with `Article.Category` choices
- `body`
- `hero_image`
- `hero_image_alt_text`
- `published`
- `related_recipe`
- `status`
- source, confirmation, moderation, image rights, and soft delete fields

## Do Not Overwrite Existing Work

Do not replace these implementations without first checking the current files:

- Recipe Schema: `recipes/templatetags/recipe_schema.py`
- Article JSON-LD: `articles/views.py`
- Breadcrumb JSON-LD: recipe/article detail templates
- Sitemap and robots: `config/views.py`
- Recipe image cleanup signals: `recipes/signals.py`
- Article image cleanup signals: `articles/signals.py`
- Newsfeed publish signals: `newsfeed/signals.py`

When adding new signal behavior, preserve existing handlers. Prefer small service
functions plus tests over large rewrites.

## Content Automation Rules

- AI-generated recipes must be saved as `draft` or `pending`; never auto-publish.
- Generated recipes must set source/attribution fields.
- Generated recipes must not claim image rights for images that do not exist.
- Map generated categories to existing `Recipe.Category` values.
- Map allergens to the existing allergen keys in `recipes.models.ALLERGEN_CHOICES`.
- Leave human review in the workflow before publication.

## Hero Image Positioning — LOCKED. DO NOT TOUCH WITHOUT EXPLICIT OWNER PERMISSION.

The `object-position` of all hero background images is **permanently locked** at
`center 60%` across the entire site. This was calibrated by the project owner and
must never be changed by any agent, in any session, for any reason.

**Locked files and values — do not modify these lines:**

| File | Selector | Value |
|------|----------|-------|
| `static/css/hero_switcher.css` | `.hero--home .hero__slide img` | `center 60%` |
| `static/css/content_cards.css` | `.hero--articles .hero__background img` | `center 60%` |
| `static/css/content_cards.css` | `.hero--recipes .hero__background img` | `center 60%` |
| `static/css/content_cards.css` | `.hero--recipe-list .hero__background img` | `center 60%` |
| `static/css/pinch.css` | `.hero--pinch .hero__background img` | `center 60%` |
| `static/css/newsfeed.css` | `.hero--news .hero__background img` | `center 60%` |
| `static/css/sponsors.css` | `.hero--sponsors .hero__background img` | `center 60%` |
| `static/css/monitoring.css` | `.hero--monitoring .hero__background img` | `center 60%` |
| `static/css/authoring.css` | `.hero--article-form`, `hero--recipe-form`, `hero--pinch-form` | `center 60%` |
| `static/css/auth.css` | `.hero--legal .hero__background img` | `center 60%` |
| `static/css/auth.css` | `.hero--inbox .hero__background img` | `center 60%` |
| `static/css/base.css` | `.hero--author-profile .hero__background img` | `center 60%` |

**Intentional exceptions (also locked — do not change):**

| File | Selector | Value | Reason |
|------|----------|-------|--------|
| `static/css/base.css` | `.hero--recipe-detail .hero__background img` | `center center` | User-uploaded food photos |
| `static/css/auth.css` | `.hero--login .hero__background img` | `center 40%` | Kitchen-light composition |
| `static/css/auth.css` | `.hero--contact .hero__background img` | `center 44%` | Sea-view composition |

If a task requires touching any hero CSS file, check this list first.
If a `object-position` value on a hero image differs from this table, do NOT
"fix" it silently — report it to the owner and wait for approval.

## External Integrations

Secrets must come from environment variables and must not be committed:

- `ANTHROPIC_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHANNEL_ID`

Pinterest, Buffer, Instagram, TikTok, and Telegram account setup are external
steps. Code can support them, but account verification and token creation happen
outside the repository.
