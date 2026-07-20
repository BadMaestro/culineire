# External Setup Checklist

**Status: OPEN — pending owner action on third-party accounts.**

These steps require access to third-party accounts. The repository can support
them, but cannot complete account verification or token creation by itself.

## Pinterest Business and Rich Pins

- Confirm the Pinterest Business account for CulinEire exists.
- Confirm the site verification meta tag is accepted by Pinterest.
- Validate that article/recipe pages expose structured data.
- Enable Rich Pins in Pinterest once verification is complete.

Production already includes a Pinterest domain verification meta tag in
`templates/base.html`.

## Telegram Channel and BotFather

- Create the Telegram channel for CulinEire.
- Use BotFather to create a bot and copy the bot token.
- Add the bot as an administrator to the channel.
- Put the channel username or chat ID in `TELEGRAM_CHANNEL_ID`.
- Put the BotFather token in `TELEGRAM_BOT_TOKEN`.
- Keep both values in environment variables only.

## Instagram and TikTok

- Keep public profile links in `templates/base.html`.
- Use Buffer or a manual approval queue for scheduled posting.
- Do not auto-publish AI-generated captions/scripts without review.

## Buffer

- Connect Instagram and TikTok in Buffer if using scheduled posting.
- Keep generated captions/scripts in a human review queue before scheduling.
