---
name: feedback-no-local-testing
description: "UPDATED 2026-07-04: local dev server and full local development ARE allowed when a task needs it (screenshots, verification, baselines); owner still does final testing on prod"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 54e34f70-f718-4f1f-a375-9e6d18758d42
---

**Superseded rule (2026-07-04).** The old rule "never run local dev server / preview tools" is lifted. Owner said: "сделай копию всего сайта на локальный диск и делай разработку на нём если нужно" — full local development is allowed and expected when a step requires it (baseline screenshots, visual verification, query measurements, phase-plan requirements). If a step needs a login, log in with a local test account or ask the owner to log in.

**What remains true:** the owner still does the final acceptance testing on production himself. Don't burn excessive time/tokens on redundant local verification for trivial template tweaks — but never treat local testing as *forbidden* or report it as a blocker. Local dev server, preview tools, screenshots, test client — all allowed.

**How to apply:** when a task (e.g. Arena Master Console phase plans) requires screenshots or browser verification, run the local dev server against a local test DB and do it. Never write "заблокировано — локальный сервер запрещён" again.

See [[feedback-deploy-authorization]] — deploy is still owner-only.
