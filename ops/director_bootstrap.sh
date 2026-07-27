#!/usr/bin/env bash
# Everything a newly appointed Director must know, gathered from the live system
# rather than from anybody's memory.
#
# Run it, read all of it, then post your bootstrap record. Nothing here writes.
#
#   bash ops/director_bootstrap.sh
#
# Why this file exists: on 2026-07-27 a Director broke twelve rules in one day,
# and every one of them was a rule he had written into AGENTS.md himself, some
# of them hours earlier. Recalling the constitution is not the same as reading
# it. This script does not summarise the rules - it points you at them and then
# shows you the state they apply to.

set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO" || exit 1

KEY="$HOME/.ssh/culineire_linode"
HOST_ROOT="root@80.85.84.156"
SITE="https://culineire.ie"

line() { printf '\n=== %s ===\n' "$1"; }

line "1. YOU ARE THE DIRECTOR. READ THESE, IN THIS ORDER, IN FULL"
cat <<'TXT'
  1. AGENTS.md                                  <- the constitution
       section 1  : roles, and who commands whom
       section 8  : deploy authority and the gates that never move
       section 9  : where tests run, and the 50% ceiling on production
       section 17 : what a Director is forbidden to do, and why each one is there
  2. docs/CHEF_BATTLE_PRODUCT_CONTRACT_2D.md
  3. docs/CURRENT_EXECUTION_PLAN.md
  4. docs/TECHNICAL_STANDARDS.md

  Read section 17 slowly. It is not advice. Every line is a mistake that was
  actually made, and section 17.16 requires you to re-read sections 8 and 17
  from the file before EVERY deploy you ever authorise.
TXT
printf '\n  constitution version on disk: '
grep -m1 '^  version:' AGENTS.md | sed 's/.*"\(.*\)"/\1/'
printf '  prohibitions in section 17 : '
grep -c '^### 17\.' AGENTS.md

line "2. THE JOB, IN FOUR LINES"
cat <<'TXT'
  You do not touch code. You plan, order, and verify by artifact.
  An order that was not carried out is YOUR error, not the agent's.
  A report is not an artifact. A commit hash on a remote is.
  The Owner judges the product by his SCREEN. You cannot see the Arena at all.
TXT

line "3. GIT: WHERE THE TRUTH IS RIGHT NOW"
# A linked worktree records its .git path in the host OS's own form, so a
# Windows-created worktree is unreadable to WSL's git and prints nothing at all.
# Blank lines here would read as "no branches, nothing pending", which is the
# most dangerous thing this script could say. Fail loudly instead.
if git rev-parse --git-dir >/dev/null 2>&1; then
  GIT_OK=1
  git fetch origin --quiet 2>/dev/null
  echo "main tip     : $(git log -1 --format='%h %ci %s' origin/main 2>/dev/null)"
  echo "your branch  : $(git branch --show-current 2>/dev/null)  @ $(git rev-parse --short HEAD 2>/dev/null)"
  echo "working tree : $(git status --short | wc -l) changed path(s)"
else
  GIT_OK=0
  cat <<'TXT'
  !! GIT IS NOT READABLE FROM THIS SHELL.
  !! This worktree was created by the other OS, so its .git pointer does not
  !! resolve here. Sections 3 and 5 below are BLANK, and blank does not mean
  !! empty - it means unknown. Re-run this script from the shell that owns the
  !! worktree (PowerShell for a Windows checkout, WSL for a Linux one) before
  !! you conclude anything about branches or pending work.
TXT
fi

line "4. WHAT IS ACTUALLY DEPLOYED (never assume main == production)"
ssh -o ConnectTimeout=15 -o BatchMode=yes -i "$KEY" "$HOST_ROOT" \
  'cd /srv/culineire/current && echo -n "server HEAD  : " && sudo -u deploy git log -1 --format="%h %s"' 2>/dev/null \
  || echo "server HEAD  : (ssh unavailable from here)"
printf 'footer live  : '
curl -s --max-time 15 "$SITE/" 2>/dev/null | grep -oE 'v2\.5\.[0-9]+' | head -1 || echo '(unreachable)'
echo "note         : main ahead of the server is NORMAL. Deploying is a separate act."

line "5. AGENT BRANCHES NOT YET IN MAIN (work that exists but is invisible)"
if [ "$GIT_OK" = "1" ]; then
  found=0
  for b in $(git for-each-ref --format='%(refname:short)' refs/remotes/origin/agent 2>/dev/null); do
    if ! git merge-base --is-ancestor "$b" origin/main 2>/dev/null; then
      printf '  %-55s +%s commits\n' "${b#origin/}" "$(git rev-list --count origin/main.."$b" 2>/dev/null)"
      found=1
    fi
  done
  [ "$found" = "0" ] && echo "  (none - every agent branch is already in main)"
else
  echo "  UNKNOWN - git unreadable from this shell, see the warning in section 3."
fi

line "6. THE BOARD - the only instrument that shows the Owner the product"
echo "  page   : $SITE/recipes/moderation/arena-build-plan/"
echo "  source : recipes/views.py, ARENA_RELEASE_STAGES (hardcoded - it only"
echo "           moves when you commit AND deploy; that is why it goes stale)"
printf '  last verified stamp in code : '
grep -m1 'last_verified' recipes/views.py | sed 's/.*"\(.*\)".*/\1/'

line "7. ARE THE AGENTS REACHABLE? (delivery is not receipt - section 17.2)"
ps -eo pid,args 2>/dev/null | grep -a 'inbox_poller' | grep -av grep \
  | while read -r pid rest; do
      fd="$(readlink /proc/"$pid"/fd/1 2>/dev/null)"
      case "$fd" in
        *.log) state="DEAF - stdout goes to a log file, this agent CANNOT be woken";;
        pipe:*) state="ok - stdout is attached, wake possible";;
        *)      state="unknown";;
      esac
      printf '  pid %-7s %-55s %s\n' "$pid" "$(echo "$rest" | grep -oE '[a-z_]+_inbox_poller[^ ]*')" "$state"
    done
echo "  the honest pulse is a changed file, never a read_at flag:"
echo "    find <worktree> -type f -not -path '*/.git/*' -mmin -30 | wc -l"

line "8. HOW TO REACH THE OWNER"
cat <<'TXT'
  Telegram only, and ONLY you listen to it - one poller per channel.
  send: ssh -i ~/.ssh/culineire_linode root@80.85.84.156 \
          '/srv/culineire/scripts/alert.sh "Bolt: ..." 1'
  Sign every message with your name. Answer in his language. Numbers and
  decisions, never a status narration.
TXT

line "9. BEFORE YOU AUTHORISE ANY DEPLOY (section 17.16, not optional)"
cat <<'TXT'
  Re-read AGENTS.md sections 8 and 17 FROM THE FILE. Then the report carries:
    constitution version (read, not recalled) | rules that apply here
    index read: git status --short + git diff --cached --stat
    file count in the commit, matching what the task named
    the base hash this work stands on, verified
    proof the thing does not already exist and is not already deployed
    gates: weight test, focused tests, diff --check
    version bumped | collectstatic run | rollback command
    ONE LINE: what the Owner will see change on his screen
TXT

line "10. THE FIVE THAT COST THE MOST, IF YOU READ NOTHING ELSE"
cat <<'TXT'
  1. Never commit an index you have not read. 475 files were deleted this way.
  2. Never call something missing before searching for it. Finished, deployed
     work was reported as a gap; approving it would have rebuilt what exists.
  3. Never state a product fact from code. "97 references in the template" is
     not "the crowd is live". He opened the page and saw grey dots.
  4. Never report a number without saying what it counts. TIME-WAIT sockets were
     called established; CDN-cached requests were called absent.
  5. Never re-ask a decision he has already made. Execute it and report it done.
TXT

printf '\n=== END. Now post your bootstrap record (AGENTS.md section 3). ===\n\n'
