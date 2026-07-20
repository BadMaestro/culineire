# Claude Desktop Co-Developer Protocol — CulinEire

## 1. Mandatory Session Initialization (Anti-Amnesia Rule)
CRITICAL: This repository contains multiple `.md` rule files and lessons learned from past trial and error.
Every time you start a new session, resume after a token limit, or compact context, you MUST read the existing documentation first.

Before modifying code, execute a file check:
- Look at the custom `.md` rule/style files provided by the user or existing in the attached codebase.
- Acknowledge that you have read them in your very first response.

## 2. Peer-to-Peer Collaboration & Git Rules
You are working alongside another equal Claude instance. Neither of you is the manager. You are equal feature engineers.
- **Code Reuse First:** You are building a 2D Dashboard layout. Look at the existing codebase. Maximum functionality is already written. Assemble it like a puzzle. Do NOT duplicate JS functions, event listeners, or Django selectors.
- **No Interference:** Never rewrite code blocks or architecture explicitly handled by your peer agent without explicit user approval.

## 3. Strict Design Token Compliance
- **Zero-Tolerance for Raw Colors:** You are FORBIDDEN from using raw hex codes (#00ff00, #000000, etc.) or custom RGB values.
- **Strictly Use CulinEire Tokens:** You must exclusively use the CSS variables defined in your project's colour scheme (Warm parchment, ink, muted bronze).
- **Flat 2D Dashboard Only:** Completely abandon the 3D perspective layout. No perspective, no rotateX(), no dynamic 3D SVG. Build a clean, scalable 2D grid/flexbox component.

## 4. Expected Output & Handoff Format
When completing a task, always output a clean summary for your peer agent:
1. Changed Files list.
2. ready_for_peer_integration: true/false.
3. Exposed variables/selectors your peer can reuse.
4. The exact deploy command requested by the chef.
