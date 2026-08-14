from django.db import migrations


SQL = r"""
CREATE OR REPLACE FUNCTION chef_battle_guard_status_transition()
RETURNS trigger AS $$
DECLARE allowed_targets text[];
DECLARE terminal_targets text[] := ARRAY['completed','cancelled','disputed','paused','walkover','void'];
BEGIN
    IF NEW.status = OLD.status THEN RETURN NEW; END IF;
    allowed_targets := CASE OLD.status
      WHEN 'scheduled' THEN ARRAY['waiting','menu_locked'] || terminal_targets
      WHEN 'waiting' THEN ARRAY['menu_locked'] || terminal_targets
      WHEN 'menu_locked' THEN ARRAY['active','voting'] || terminal_targets
      WHEN 'active' THEN ARRAY['ingredient_penalty','voting'] || terminal_targets
      WHEN 'awaiting_submissions' THEN ARRAY['revealed','voting'] || terminal_targets
      WHEN 'revealed' THEN ARRAY['cooking','presentation','voting'] || terminal_targets
      WHEN 'ingredient_penalty' THEN ARRAY['cooking'] || terminal_targets
      WHEN 'cooking' THEN ARRAY['presentation'] || terminal_targets
      WHEN 'presentation' THEN ARRAY['voting'] || terminal_targets
      WHEN 'voting' THEN terminal_targets
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
"""


def broaden_guard(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SQL)


def restore_previous_guard(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        from importlib import import_module
        previous = import_module(
            "chef_battle.migrations.0094_t12_battle_status_transition_guard"
        )
        schema_editor.execute(previous.CREATE_TRIGGER)


class Migration(migrations.Migration):
    dependencies = [("chef_battle", "0094_t12_battle_status_transition_guard")]
    operations = [migrations.RunPython(broaden_guard, restore_previous_guard)]
