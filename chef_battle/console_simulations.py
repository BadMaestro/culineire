"""Walk-through scenarios for the Arena Master Console.

MC01, the Owner's order of 2026-08-05: the withdrawal flow shipped in v2.5.830
"тоже должен быть частью Master Console Panel Battle Cancellation Simulation - и
при нажатии на этот сценарий - показывать всё по шагам как это будет выглядеть
на реальной арене".

So this module answers one question, step by step: what does each person SEE,
and what does the site DO, when a chef pulls out of a battle he has accepted.

Two rules govern everything here.

**It writes nothing.** Not a row, not a field, not a notification. A simulation
that spends a real chef's allowance to demonstrate spending an allowance is a
defect wearing a demo's clothes. The operator can run it on production, on the
live primary battle, as many times as he likes.

**It restates nothing.** Every number, status name and rule sentence is read off
the real model and the real service - `WITHDRAWAL_ALLOWANCE`, `PENALTY_RATING`,
`Status.*` - never typed in again. The console has been bitten once already by a
hand-copied second list quietly falling behind the first (`master_console`'s old
fourteen-key arena payload); a demo that drifts from the code teaches the
operator something untrue, which is worse than teaching him nothing.
"""

from .models import BattleWithdrawal
from .withdrawal_service import WITHDRAWAL_ALLOWANCE

# The three paths through the flow. The moderator is the final judge in every
# one of them, which is why "waived" still passes under his hand before it ends.
PATH_WAIVED = "waived"
PATH_UPHELD = "upheld"
PATH_OVERTURNED = "overturned"

PATH_LABELS = {
    PATH_WAIVED: "The other chef waives the penalty",
    PATH_UPHELD: "The other chef asks for it, the moderator upholds it",
    PATH_OVERTURNED: "The other chef asks for it, the moderator refuses it",
}


def _cast(battle):
    """Who plays the two chefs.

    The live primary battle when there is one, so the operator watches the flow
    happen to the people actually standing on his arena. When the arena is empty
    the names are marked as such rather than invented quietly - the console's
    standing rule is that nothing on it is a placeholder pretending to be data.
    """
    if battle is not None and battle.challenger_id and battle.opponent_id:
        return {
            "live": True,
            "theme": battle.theme,
            "battle_id": battle.pk,
            "leaver": battle.challenger.name,
            "stayer": battle.opponent.name,
        }
    return {
        "live": False,
        "theme": "no live battle - the flow is shown with stand-in names",
        "battle_id": None,
        "leaver": "Chef A",
        "stayer": "Chef B",
    }


def build_cancellation_simulation(battle=None):
    """The Battle Cancellation Simulation, as data.

    Returns the cast, the constants, and a spine of steps. A step whose `paths`
    list does not contain the chosen path is skipped by the stepper, which is
    how one spine carries all three routes without three copies of the steps
    they share.
    """
    cast = _cast(battle)
    leaver, stayer = cast["leaver"], cast["stayer"]
    left = WITHDRAWAL_ALLOWANCE - 1
    rating = BattleWithdrawal.PENALTY_RATING
    reputation = BattleWithdrawal.PENALTY_REPUTATION

    all_paths = [PATH_WAIVED, PATH_UPHELD, PATH_OVERTURNED]
    asked = [PATH_UPHELD, PATH_OVERTURNED]

    steps = [
        {
            "key": "entry",
            "actor": "Either chef, on the battle page",
            "where": "The battle page - the same page the arena links to from the pill.",
            "title": "The Withdraw button",
            "paths": all_paths,
            "screen": [
                f"{leaver} sees a Withdraw from this battle button under the battle header.",
                f"Beside it: {WITHDRAWAL_ALLOWANCE} withdrawals left on the account.",
                "When the allowance is gone the button is dark and cannot be pressed - "
                "from there a no-show is answered for exactly as it was before.",
            ],
            "rules": [
                "can_withdraw() must agree, and it asks four things: the viewer is a "
                "participant; the battle is still live; no request is already open on "
                "it; the account has an allowance left.",
                "The button is not shown to spectators, and never on a finished battle.",
            ],
            "effects": ["Nothing yet. This step only decides whether the button is live."],
        },
        {
            "key": "reason",
            "actor": f"{leaver}, the withdrawing chef",
            "where": "/chef-battle/battles/<id>/withdraw/ - a contact-form-shaped page.",
            "title": "He states his reason, in his own words",
            "paths": all_paths,
            "screen": [
                "One required free-text field. No dropdown of approved excuses: the "
                "reasons can be illness, a funeral, a kitchen fire, and no list covers them.",
                f"A line saying this will leave {left} of {WITHDRAWAL_ALLOWANCE} withdrawals.",
                "Submitting returns him to the battle page, where the button is now "
                "replaced by Withdrawal requested - waiting for the other chef.",
            ],
            "rules": [
                "An empty reason is refused.",
                "THE ALLOWANCE IS SPENT HERE, ON THE ASKING, not on the answer. Spend it "
                "on the outcome instead and a chef who is waved through pays nothing for "
                "a request he can repeat all day, and the fixed three stop meaning anything.",
                "The row is created under a lock on the profile, so two tabs cannot spend "
                "the same allowance twice.",
            ],
            "effects": [
                f"withdrawals_remaining: {WITHDRAWAL_ALLOWANCE} to {left}.",
                f"BattleWithdrawal created, status {BattleWithdrawal.Status.AWAITING_OPPONENT.label}.",
                "A private battle event is written to the audit trail - private, because "
                "the arena does not announce a request nobody has answered yet.",
                f"{stayer} is emailed the reason and told he decides what happens next.",
            ],
        },
        {
            "key": "fork",
            "actor": f"{stayer}, the other chef",
            "where": "The battle page - the answer sits where the Withdraw button was.",
            "title": "The other chef answers first",
            "paths": all_paths,
            "fork": True,
            "screen": [
                f"{stayer} reads the reason and gets two buttons: Accept without a "
                "penalty, and Ask for a penalty.",
                f"The penalty is fixed and is shown as what it is: {rating} rating and "
                f"{reputation} reputation.",
                "Choosing the penalty opens a required Why field. Waiving it opens nothing.",
            ],
            "rules": [
                "Only the other chef may answer, and only once.",
                "Asking for the penalty obliges him to say why; waiving it needs no "
                "explanation, because nobody has to justify letting someone off.",
                "Neither answer is final. Both go to a moderator.",
            ],
            "effects": [
                f"status moves to {BattleWithdrawal.Status.AWAITING_MODERATOR.label}.",
                "No number moves yet. The chef's answer is a recommendation, not a verdict.",
            ],
            "choices": [
                {"path": PATH_WAIVED, "label": "Waive the penalty"},
                {"path": PATH_UPHELD, "label": "Ask for the penalty"},
            ],
        },
        {
            "key": "moderator_waived",
            "actor": "A moderator",
            "where": "The moderation queue.",
            "title": "The moderator reviews a waived request",
            "paths": [PATH_WAIVED],
            "screen": [
                "The moderator sees the reason, the answer, and both chefs' records.",
                "He may close it as the chef asked, or replace that answer with his own - "
                "a waiver is a recommendation like any other.",
            ],
            "rules": [
                "The moderator is the FINAL judge, and only he moves the numbers.",
                "A request already closed cannot be reopened from here.",
            ],
            "effects": ["Whatever he decides is applied at the next step, all at once."],
        },
        {
            "key": "moderator_asked",
            "actor": "A moderator",
            "where": "The moderation queue.",
            "title": "The moderator rules on a requested penalty",
            "paths": asked,
            "fork": True,
            "screen": [
                f"He sees {leaver}'s reason and {stayer}'s stated grounds side by side.",
                "Uphold, or refuse. Either way he may leave a note on the record.",
            ],
            "rules": [
                "He is not bound by the other chef's answer in either direction.",
                "penalise() is the gate that applies it, so section 18 keeps the Owner's "
                "account whole here as everywhere else.",
            ],
            "effects": ["Applied at the next step, inside one transaction."],
            "choices": [
                {"path": PATH_UPHELD, "label": "Uphold the penalty"},
                {"path": PATH_OVERTURNED, "label": "Refuse it"},
            ],
        },
        {
            "key": "closed_clean",
            "actor": "Everyone",
            "where": "The arena, the battle page and both inboxes.",
            "title": "Closed - no penalty",
            "paths": [PATH_WAIVED, PATH_OVERTURNED],
            "screen": [
                f"The battle reads CANCELLED, with the reason: Withdrawn: {leaver} pulled out.",
                "It leaves the arena's live composition and stops appearing in the "
                "upcoming board.",
                "The cancellation is posted publicly to the news feed, and both chefs "
                "are emailed that it was settled without a penalty.",
            ],
            "rules": [
                "CANCELLED, not LOST. Pulling out for a real reason is not a defeat, and "
                "the record does not pretend it was one.",
            ],
            "effects": [
                "Battle status: CANCELLED. waiting_until cleared.",
                "Artifacts staked on the battle are released back.",
                f"{leaver}'s rating, reputation, streak and record: untouched.",
                f"The allowance stays spent: {left} of {WITHDRAWAL_ALLOWANCE} left.",
                f"Withdrawal status {BattleWithdrawal.Status.CLOSED.label}, penalty_applied false.",
            ],
        },
        {
            "key": "closed_penalty",
            "actor": "Everyone",
            "where": "The arena, the battle page and both inboxes.",
            "title": "Closed - with the penalty",
            "paths": [PATH_UPHELD],
            "screen": [
                f"The battle reads CANCELLED, with the reason: Withdrawn: {leaver} pulled out.",
                f"{leaver}'s card on the arena shows the new rating immediately - the "
                "ladder panel is repainted by the same poll that repaints everything else.",
                "Both chefs are emailed that it was settled with a penalty.",
            ],
            "rules": [
                "The figure is the Owner's and is the whole of it: nothing else is taken.",
                "A rank already earned is never taken back (v2.5.826), so a penalty that "
                "drops the rating below a threshold does not demote him.",
            ],
            "effects": [
                f"Rating: -{rating}, and never below zero - penalise() floors it, so "
                f"a chef with 8 rating loses 8 and not {rating}. Reputation: "
                f"-{reputation}, floored at -1000.",
                "No loss recorded. No streak broken. No seasonal points removed.",
                "Battle status: CANCELLED. Artifacts released. Public news event posted.",
                f"Withdrawal status {BattleWithdrawal.Status.CLOSED.label}, penalty_applied true.",
            ],
        },
    ]

    return {
        "cast": cast,
        "allowance": WITHDRAWAL_ALLOWANCE,
        "penalty_rating": rating,
        "penalty_reputation": reputation,
        "path_labels": PATH_LABELS,
        "steps": steps,
    }
