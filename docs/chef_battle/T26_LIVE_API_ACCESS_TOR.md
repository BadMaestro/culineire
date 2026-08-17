# T26 — TikTok / Instagram Live API access: what the Owner does before any code

This is not an engineering document. It is a sequence of external, non-technical
steps only the Owner can take — business verification, developer accounts, API
applications — none of which an agent can do on his behalf (they require his
own identity, his own business, his own login). Once every item under "What to
send back" exists, T26 (currently BLOCKED, assigned to Bolt) can start.

Written to be done from a phone or tablet, one step at a time, in any order
between the two platforms — they do not depend on each other.

---

## Before you start — have these ready

- **Business name and details**: Bearcave Limited (or CulinÉire, whichever is
  the registered entity behind the site).
- **The live site URL**: https://culineire.ie
- **A one-paragraph description of what you're building**, reusable on both
  platforms. Suggested wording, edit as you like:

  > CulinÉire is a cooking competition platform ("Chef Battles") where
  > registered chefs cook against each other in timed rounds, judged by a
  > public audience. We want to stream the live cooking phase of a battle to
  > TikTok/Instagram so spectators can watch in real time.

- **An email address you check regularly** — platform reviews reply by email,
  sometimes days apart, and you don't want to miss a follow-up question.

---

## Part A — TikTok

1. Go to **developers.tiktok.com** and sign in with (or create) a TikTok
   account for the business, not a personal one.
2. Click **"Manage apps"** → **"Create an app"**.
   - App name: something recognisable, e.g. "CulinÉire Chef Battles".
   - App icon and description: use the paragraph above.
   - Category: pick the closest match (Food/Cooking or Entertainment).
3. Once the app exists, look for **"Add products"** and add:
   - **Login Kit** (needed as a prerequisite for most other products).
   - **Live Streaming API** — this may not appear as a free/self-serve
     toggle. If it doesn't, look for a **"Apply for access"** or **"Contact
     us"** link near it, or a separate **TikTok for Developers partner
     application form**. This is the part that is not guaranteed — TikTok
     grants Live API access selectively, and the application will ask what
     you're building (paste the paragraph above) and why you need it.
4. Fill in the application honestly and submit. **This step alone can take
   1–3 weeks to get a reply.** Nothing else on the TikTok side can proceed
   until you hear back.
5. If TikTok asks for a **redirect URI** or **callback URL** at any point,
   pause and send me that exact field name — it needs to point at something
   real on our server, which is engineering's job, not something to guess on
   a bus.

## Part B — Instagram / Meta

1. Go to **developers.facebook.com** and sign in with (or create) a Facebook
   account tied to the business.
2. Go to **business.facebook.com** and make sure a **Meta Business
   Account** exists for Bearcave Limited / CulinÉire. If Instagram's
   business account isn't already linked here, link it now (Settings →
   Accounts → Instagram accounts).
3. Meta requires **Business Verification** before granting most live/video
   permissions. Under Business Settings → Security Centre →
   **"Start verification"**:
   - You'll be asked for a legal business name, address, and a document
     proving it (company registration, a recent utility bill, etc.).
   - This step is where most delays happen — have a scan/photo of the
     business registration document ready before you start it, so you're
     not hunting for paperwork mid-application.
4. Back in developers.facebook.com, on the CulinÉire app (create one if it
   doesn't exist yet: **"My Apps" → "Create App" → type: Business**):
   - Add the **"Instagram Graph API"** product (not the old, deprecated
     Instagram Basic Display API).
   - Under **App Review**, request the permissions the Live feature needs.
     The exact permission names change occasionally; search Meta's docs for
     **"Instagram Live API permissions"** or **"instagram_content_publish"**
     at the time you do this, since Meta renames these periodically.
   - The App Review form asks the same kind of question TikTok's does: what
     you're building and why (reuse the paragraph above), plus usually a
     short screen-recording demo of the flow — that part needs the actual
     feature built first, so it may have to wait for engineering; note it
     and move on rather than getting stuck on it today.

---

## What to send back once you have it

Send these to me (Carpet, chat, wherever's easiest) as they arrive — no need
to wait for both platforms to finish:

- [ ] TikTok: app created, Client Key + Client Secret
- [ ] TikTok: Live Streaming API application status (submitted / approved /
      rejected — and if rejected, their stated reason)
- [ ] Meta: Business verification status (in progress / verified)
- [ ] Meta: app created, App ID + App Secret
- [ ] Meta: Instagram Graph API added, App Review status for the live/publish
      permission

**Do not paste secrets/keys into a public chat or a screenshot you might
share elsewhere.** Send them the same way you'd send a password — the Carpet
DB message is fine, a public issue tracker is not.

## What happens after

Once even one platform's access is approved, T26 unblocks for that platform
and engineering starts: deciding what actually gets streamed (screen capture
of the arena, a camera feed the chef opts into, or the existing photo
uploads turned into a slideshow-style "live" feed — that's still your call,
not decided yet), then wiring the approved API in.

Nothing above commits you to a cost — both developer programmes are free to
apply to. Some *live* API tiers can carry usage limits or paid tiers at
production scale, which we'll flag before you'd ever hit them, not after.
