from django.db import migrations


CREATE_TRIGGER = r"""
CREATE OR REPLACE FUNCTION chef_battle_guard_status_transition()
RETURNS trigger AS $$
DECLARE allowed_targets text[];
BEGIN
    IF NEW.status = OLD.status THEN RETURN NEW; END IF;
    allowed_targets := CASE OLD.status
      WHEN 'scheduled' THEN ARRAY['waiting','menu_locked','cancelled','paused']
      WHEN 'waiting' THEN ARRAY['menu_locked','walkover','void','cancelled','paused']
      WHEN 'menu_locked' THEN ARRAY['active','voting','cancelled','paused']
      WHEN 'active' THEN ARRAY['ingredient_penalty','voting','completed','walkover','void','cancelled','paused']
      WHEN 'awaiting_submissions' THEN ARRAY['revealed','voting','cancelled','paused']
      WHEN 'revealed' THEN ARRAY['cooking','presentation','voting','cancelled','paused']
      WHEN 'ingredient_penalty' THEN ARRAY['cooking','cancelled','paused']
      WHEN 'cooking' THEN ARRAY['presentation','cancelled','paused']
      WHEN 'presentation' THEN ARRAY['voting','cancelled','paused']
      WHEN 'voting' THEN ARRAY['completed','disputed','cancelled','paused']
      WHEN 'disputed' THEN ARRAY['voting','cancelled']
      WHEN 'paused' THEN ARRAY['scheduled','waiting','menu_locked','active','awaiting_submissions','revealed','ingredient_penalty','cooking','presentation','voting','cancelled']
      ELSE ARRAY[]::text[]
    END;
    IF NOT NEW.status = ANY(allowed_targets) THEN
      RAISE EXCEPTION 'illegal Battle.status transition: % -> %', OLD.status, NEW.status
        USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS chef_battle_status_transition_guard ON chef_battle_battle;
CREATE TRIGGER chef_battle_status_transition_guard
BEFORE UPDATE OF status ON chef_battle_battle
FOR EACH ROW EXECUTE FUNCTION chef_battle_guard_status_transition();
"""

DROP_TRIGGER = r"""
DROP TRIGGER IF EXISTS chef_battle_status_transition_guard ON chef_battle_battle;
DROP FUNCTION IF EXISTS chef_battle_guard_status_transition();
"""


def create_guard(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(CREATE_TRIGGER)


def drop_guard(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(DROP_TRIGGER)


class Migration(migrations.Migration):
    dependencies = [("chef_battle", "0093_t08_t09_token_lots_and_partial_refunds")]
    operations = [migrations.RunPython(create_guard, drop_guard)]
