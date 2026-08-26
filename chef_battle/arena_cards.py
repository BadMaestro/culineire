"""Battle events become cards in the arena's own chat log.

P3, Owner 2026-08-26 ("Делай p2 отдай болту p3"). The hall watches a fight and
talks about it in the same column; the fight's own moments belong in that
column too, as cards rather than as sentences somebody typed.

NOTHING HERE INVENTS AN EVENT. Every card is written from a ``BattleEvent`` the
game had already recorded for its own reasons - the challenge that was issued,
the reveal that opened voting, the result that was scored - so a card cannot
say something the battle did not do. That is the brief's rule ("no fake data")
and it is also why this module has no ``message`` argument: the sentence is the
event's, and this file only decides which events the hall is shown and where
the card is seated.

WHY THE CARD IS A CHAT ROW. The hall polls one table and pages it by ``id``;
that id is the client's whole cursor. A second table of events would have
needed a second cursor, a merge on every poll, and a rule for what happens when
the two disagree about order. A card is a row in the log that renders
differently, and the seam for that already existed before this file did -
``MESSAGE_RENDERERS`` in arena_chat.js dispatches on ``kind``.

A CARD IS HEARD EVERYWHERE. Reach is the rule for people talking among
themselves in the stands (arena_chat.can_hear); an announcement about the fight
everybody is watching is not that, and the exemption is applied in
``audible_lines`` next to the Admin one it already had.
"""

from __future__ import annotations

import logging

from .models import ArenaChatMessage, ArenaSeat, BattleEvent

logger = logging.getLogger(__name__)


# WHICH EVENTS THE HALL IS SHOWN, and the ones deliberately left out.
#
# BattleEvent carries sixteen types and most of them are bookkeeping: a rank
# promotion, an artifact drop, an operator action. Those belong in the record,
# not in a live room where every card costs a reader the space of three spoken
# lines. The three here are the ones a spectator came for - a fight was called,
# the voting opened, somebody won.
#
# CHALLENGE_ACCEPTED is NOT a card and the omission is deliberate: the
# acceptance is what schedules the battle, and the board directly above the
# chat already announces the scheduled battle by name and by clock. A card
# saying the same thing seconds later is the same fact twice.
CARD_FOR_EVENT = {
    BattleEvent.EventType.CHALLENGE_CREATED: ArenaChatMessage.Kind.CHALLENGE_ISSUED,
    BattleEvent.EventType.BATTLE_REVEALED: ArenaChatMessage.Kind.VOTING_OPEN,
    # BATTLE_COMPLETED and not BATTLE_FINISHED, and the difference is the whole
    # point: FINISHED is emitted for walkovers, forfeits and voids as well, and
    # several of those rows carry no winner at all. COMPLETED is the one the
    # scorer writes when a battle was actually fought to a result, with the
    # winner as actor and the loser as target - which is exactly what the card
    # needs to name. Draws and walkovers are deliberately left cardless until
    # they have a card designed for them rather than borrowing this one.
    BattleEvent.EventType.BATTLE_COMPLETED: ArenaChatMessage.Kind.BATTLE_RESULT,
    # The biathlon, both halves. These two types did not exist before P3: every
    # shot was recorded as BATTLE_STARTED, which is why the hall could not have
    # drawn them however the renderer was written.
    BattleEvent.EventType.INGREDIENT_HIT: ArenaChatMessage.Kind.INGREDIENT_ATTACK,
    BattleEvent.EventType.INGREDIENT_BLOCKED: ArenaChatMessage.Kind.DEFENCE,
}


def _seat_of(author):
    """Where the card is spoken from, when it is spoken by somebody at all.

    A card is heard everywhere, so the seat is not what decides who reads it -
    it is what lets the octagon effects in the rest of P3 know which cell to
    light. A chef who is not seated gets ring 0, cell 0, which no ring uses and
    every consumer already reads as "nowhere in particular".
    """
    if author is None:
        return 0, 0
    seat = (
        ArenaSeat.objects
        .filter(viewer=author, released_at__isnull=True)
        .order_by("-claimed_at")
        .values_list("ring_index", "seat_index")
        .first()
    )
    return seat if seat else (0, 0)


def post_card_for_event(event: BattleEvent) -> ArenaChatMessage | None:
    """Write the hall's card for one battle event, or nothing.

    Returns the row so a caller can assert on it; returns None when the event
    is not one the hall is shown, which is the ordinary case.

    THE CARD IS DECORATION AND THE TRANSITION IS THE TRUTH. This runs inside
    the same call that records a battle moving from one state to the next, so a
    failure here must never be allowed to lose that transition - a hall that
    misses one card is a cosmetic fault, a battle that fails to start is not.
    The exception is logged with the event id rather than swallowed, so a
    broken card is findable rather than invisible.
    """
    kind = CARD_FOR_EVENT.get(event.event_type)
    if kind is None:
        return None
    # A card with no battle has nothing to point a reader at, and every type
    # above belongs to one. A challenge that has not yet become a battle is the
    # one exception and carries its challenge instead.
    if event.battle_id is None and event.challenge_id is None:
        return None
    if not event.is_public:
        return None

    actor = event.actor
    ring, cell = _seat_of(actor)
    try:
        return ArenaChatMessage.objects.create(
            battle=event.battle,
            speaker=actor,
            display_name=(getattr(actor, "name", "") or "The Arena")[:60],
            body=event.message[:300],
            ring_index=ring,
            seat_index=cell,
            kind=kind,
            event=event,
        )
    except Exception:
        logger.exception("arena card failed for BattleEvent %s", event.pk)
        return None


def card_payload(message: ArenaChatMessage) -> dict:
    """What the renderer is given for one card, and nothing more.

    Read off the EVENT rather than off the chat row wherever the event has it,
    so a card shows the battle's own facts. The URL is the point of the card -
    every one of these is an invitation to go and look - and it is built here
    rather than in the browser because the browser has no URL conf.
    """
    if message.combat_round_id is not None:
        return round_card_payload(message)
    event = message.event
    battle = message.battle
    payload = {
        "kind": message.kind,
        "headline": message.body,
        "actor": getattr(message.speaker, "name", "") or "",
        "actor_slug": getattr(message.speaker, "slug", "") or "",
    }
    if battle is not None:
        payload["battle_url"] = battle.get_absolute_url()
        challenger = getattr(battle, "challenger", None)
        opponent = getattr(battle, "opponent", None)
        payload["challenger"] = getattr(challenger, "name", "") or ""
        payload["opponent"] = getattr(opponent, "name", "") or ""
        # THE WINNER IS NAMED ONLY WHEN THE BATTLE HAS ONE. A result card that
        # renders before the score is written would announce a winner the
        # battle has not got, which is exactly the "no fake data" rule.
        winner = getattr(battle, "winner", None)
        if message.kind == ArenaChatMessage.Kind.BATTLE_RESULT and winner is not None:
            payload["winner"] = winner.name
            payload["winner_slug"] = winner.slug
    # AN ARRIVAL HAS NO BATTLE AND NO EVENT. What it has is the chef, and the
    # rank they walked in wearing - which is the only thing about a chef the
    # hall can see from the stands anyway.
    if message.kind == ArenaChatMessage.Kind.CHEF_ENTERED:
        from .models import ChefBattleProfile
        profile = (
            ChefBattleProfile.objects
            .filter(author=message.speaker)
            .only("rank")
            .first()
        )
        if profile is not None:
            payload["rank"] = profile.get_rank_display()
        return payload
    if event is not None and event.payload_json:
        # Only ever a read: the renderer decides what it can use, and an event
        # that carries nothing useful simply gives the card nothing extra.
        #
        # READ AT SERVE TIME, NOT AT WRITE TIME, and the biathlon depends on
        # it: post_card_for_event runs inside create_battle_event, which is
        # BEFORE the shot's payload is attached to the event. The card row is
        # written first and the facts are read fresh on every poll, so the card
        # always shows what the event finally said rather than what it said
        # halfway through being written.
        payload["event"] = event.payload_json
    return payload


def post_arrival_card(author) -> "ArenaChatMessage | None":
    """The hall is told when a CHEF takes a seat in it. P3 item 26.

    A SPECTATOR ARRIVING IS NOT NEWS and does not get a card: the stands fill
    and empty all evening, and a card for every one of them would bury the
    conversation the cards exist to sit beside. A chef arriving is - the people
    in the seats came to watch chefs.

    THERE IS NO EVENT BEHIND THIS ONE, and that is not a hole in the rule. The
    other cards read a BattleEvent because the moments they describe are the
    battle's; this moment is the hall's own, and the fact it states - that this
    chef holds this seat - is a row in ArenaSeat that was written a moment ago
    by the caller. Nothing is invented either way.

    NO DEDUP HERE, because the caller already has one: claim_seat returns an
    existing seat without reaching the create, so this runs on a genuinely new
    seat and only on one. A chef who reloads the arena announces nobody.
    """
    from .models import ChefBattleProfile

    if author is None:
        return None
    profile = (
        ChefBattleProfile.objects
        .filter(author=author, enrolled_at__isnull=False)
        .first()
    )
    if profile is None:
        return None

    ring, cell = _seat_of(author)
    try:
        return ArenaChatMessage.objects.create(
            battle=None,
            speaker=author,
            display_name=(getattr(author, "name", "") or "A chef")[:60],
            body=f"{author.name} has entered the Arena.",
            ring_index=ring,
            seat_index=cell,
            kind=ArenaChatMessage.Kind.CHEF_ENTERED,
        )
    except Exception:
        logger.exception("arrival card failed for author %s", getattr(author, "pk", None))
        return None


# Round one's four outcomes as the hall reads them. BattleRound.Outcome is the
# game's own vocabulary and this is only its plain-English half; the decision of
# WHICH card a round earns is below, and it is made from the outcome rather than
# from who happened to be attacking.
ROUND_OUTCOME_LABEL = {
    "full_hit": "a full hit",
    "partial_hit": "a partial hit",
    "blocked": "blocked",
    "draw": "a clash",
}


def post_round_card(combat_round, challenger_action, opponent_action):
    """The hall's card for one round of combat. P3 items 22 and 23.

    ROUND ONE IS THE ARTIFACT DUEL. Each chef commits Move points and may
    activate an artifact whose power is added to theirs; the higher total takes
    the round, and the attacker's targeted ingredient falls with it. That is a
    different fight from round two's three shots at a menu, and the Owner had to
    say so twice before it was written down here.

    ONE CARD PER ROUND, NOT TWO. A round has one outcome that both chefs are
    inside, so a card each would print the same moment from two angles and cost
    the log twice the space. Which of the Owner's two items it satisfies is
    decided by the outcome: an attack that landed is item 22, an attack a
    defence turned away is item 23.

    NOTHING IS WRITTEN INTO THE BATTLE FOR THIS. No event, no new field on the
    round - the card points at the BattleRound and reads it and the two actions
    beside it. A failure here is logged and swallowed, because it runs inside
    the transaction that resolves the round and a chat row must never be able to
    cost a chef his combat.
    """
    if combat_round is None:
        return None
    outcome = (combat_round.outcome or "").lower()
    if outcome == "draw":
        # A CLASH IS NOT A CARD. Nothing was struck off, nobody's defence was
        # proved, and the hall would be told a thing happened when the state of
        # the fight is exactly what it was.
        return None
    kind = (
        ArenaChatMessage.Kind.ARTIFACT_DEFENCE if outcome == "blocked"
        else ArenaChatMessage.Kind.ARTIFACT_ATTACK
    )
    attacker = combat_round.attacker
    ring, cell = _seat_of(attacker)
    try:
        return ArenaChatMessage.objects.create(
            battle=combat_round.battle,
            speaker=attacker,
            display_name=(getattr(attacker, "name", "") or "A chef")[:60],
            body=combat_round.log_message[:300],
            ring_index=ring,
            seat_index=cell,
            kind=kind,
            combat_round=combat_round,
        )
    except Exception:
        logger.exception("round card failed for BattleRound %s",
                         getattr(combat_round, "pk", None))
        return None


def _artifact_of(action):
    """The artifact a chef actually activated this round, named for the card.

    A chef may fight with Move points alone, so this is often nothing - and the
    card says nothing rather than inventing a bare hand. `artifact_used` is a
    ChefArtifact (the copy this chef owns); the name and rarity live on the
    Artifact it points at.
    """
    owned = getattr(action, "artifact_used", None)
    artifact = getattr(owned, "artifact", None)
    if artifact is None:
        return None
    return {
        "name": artifact.name,
        "rarity": artifact.get_rarity_display(),
        "effect": artifact.effect_type or "",
        "value": artifact.effect_value or 0,
    }


def round_card_payload(message: ArenaChatMessage) -> dict:
    """What a round-one card is given, read off the round at serve time.

    The two actions are found by (battle, round_number, chef) rather than stored
    on the card, so the card cannot hold a stale copy of what a chef played.
    """
    from .models import BattleCombatAction

    combat_round = message.combat_round
    payload = {
        "kind": message.kind,
        "headline": message.body,
        "round": combat_round.round_number,
        "attacker": getattr(combat_round.attacker, "name", "") or "",
        "attacker_slug": getattr(combat_round.attacker, "slug", "") or "",
        "defender": getattr(combat_round.defender, "name", "") or "",
        "outcome": ROUND_OUTCOME_LABEL.get(
            (combat_round.outcome or "").lower(), combat_round.outcome
        ),
        "attack_power": combat_round.attack_power,
        "defence_power": combat_round.defence_power,
        "hits": [combat_round.challenger_hits, combat_round.opponent_hits],
    }
    battle = combat_round.battle
    if battle is not None:
        payload["battle_url"] = battle.get_absolute_url()
    actions = {
        a.chef_id: a for a in BattleCombatAction.objects.filter(
            battle_id=combat_round.battle_id,
            round_number=combat_round.round_number,
        ).select_related("artifact_used__artifact", "target_ingredient")
    }
    attack_action = actions.get(combat_round.attacker_id)
    defend_action = actions.get(combat_round.defender_id)
    if attack_action is not None:
        artifact = _artifact_of(attack_action)
        if artifact:
            payload["attack_artifact"] = artifact
        # THE INGREDIENT IS NAMED ONLY WHEN IT ACTUALLY FELL. A targeted
        # ingredient on a round the attacker lost is still on the menu, and a
        # card that named it would be reporting a casualty that walked away.
        target = getattr(attack_action, "target_ingredient", None)
        if target is not None and target.is_eliminated:
            payload["struck"] = target.name
    if defend_action is not None:
        artifact = _artifact_of(defend_action)
        if artifact:
            payload["defence_artifact"] = artifact
    return payload
