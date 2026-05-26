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

## External Integrations

Secrets must come from environment variables and must not be committed:

- `ANTHROPIC_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHANNEL_ID`

Pinterest, Buffer, Instagram, TikTok, and Telegram account setup are external
steps. Code can support them, but account verification and token creation happen
outside the repository.
