from django.db import migrations


def remove_fake_entries(apps, schema_editor):
    CoworkingAgent = apps.get_model("coworking", "CoworkingAgent")
    CoworkingLogEntry = apps.get_model("coworking", "CoworkingLogEntry")

    # Remove fake log entries on Bolt from fake Jam-Oliver and fake GreenBear handoffs
    CoworkingLogEntry.objects.filter(
        agent__agent_id="bolt",
        action__icontains="Received handoff from Jam-Oliver",
    ).delete()

    CoworkingLogEntry.objects.filter(
        agent__agent_id="bolt",
        action__icontains="Received handoff from GreenBear",
        note__icontains="HOW TO PLAY CHEF BATTLE",
    ).delete()

    # Remove fake log entries on GreenBear (claude-d) that were submitted fraudulently
    CoworkingLogEntry.objects.filter(
        agent__agent_id="claude-d",
        action__icontains="Handed off to Bolt",
        note__icontains="HOW TO PLAY CHEF BATTLE",
    ).delete()

    # Remove the Jam-Oliver agent and all its log entries
    CoworkingAgent.objects.filter(agent_id="jam-oliver").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("coworking", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(remove_fake_entries, migrations.RunPython.noop),
    ]
