# CulinEire Prompt Library

These prompts are templates for assisted drafting. They do not publish content.
Generated site content must be reviewed by a human before approval.

## Recipe Draft Prompt

Create a CulinEire recipe draft for: `{dish_name}`.

Return strict JSON with these keys only:

```json
{
  "title": "",
  "short_description": "",
  "category": "",
  "difficulty": "easy",
  "prep_time_minutes": 0,
  "cook_time_minutes": 0,
  "servings": 4,
  "calories": null,
  "ingredients": [],
  "method": [],
  "tips": "",
  "irish_context": "",
  "author_commentary": "",
  "allergens": [],
  "source_title": "",
  "source_author": "",
  "source_url": "",
  "source_note": ""
}
```

Rules:

- Use current `Recipe` field names.
- `category` must match one existing `Recipe.Category` value or label.
- `ingredients` must be a list of strings, one ingredient per line.
- `method` must be a list of clear step strings.
- `allergens` must use only the known allergen keys.
- Do not invent image ownership or image URLs.
- Include attribution notes if the draft is adapted or inspired.
- Keep the tone warm, practical, and grounded in Irish food culture.

## Article Draft Prompt

Create a CulinEire article draft for: `{topic}`.

Return title, excerpt, body, source details, and any related recipe suggestion.
Use markdown-style `##` headings in the body. Do not include raw HTML.

## Telegram Post Prompt

Write a short Telegram post for this published CulinEire recipe:

- Title: `{title}`
- Description: `{short_description}`
- URL: `{url}`

Keep it concise, warm, and non-clickbait. Include the URL once.

## Instagram Caption Prompt

Write an Instagram caption for this CulinEire recipe:

- Title: `{title}`
- Description: `{short_description}`
- Irish context: `{irish_context}`

Include 5-10 relevant hashtags. Avoid exaggerated health or heritage claims.

## TikTok Script Prompt

Write a 60-second TikTok script for this CulinEire recipe:

- Title: `{title}`
- Key ingredients: `{ingredients}`
- Method summary: `{method}`

Use a practical voiceover structure with a short hook, 3-5 cooking beats, and a
closing line that points viewers to CulinEire for the full recipe.
