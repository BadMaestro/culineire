from django.db import migrations


def fix_subjects(apps, schema_editor):
    Message = apps.get_model("messaging", "Message")
    RecipeAuthor = apps.get_model("recipes", "RecipeAuthor")

    try:
        greenbear_user = RecipeAuthor.objects.get(slug="greenbear").user
    except RecipeAuthor.DoesNotExist:
        greenbear_user = None

    old_subject = "Message from CulinEire moderation"

    qs = Message.objects.filter(subject=old_subject)
    for msg in qs:
        if greenbear_user and msg.sender_id == greenbear_user.pk:
            msg.subject = "Message from CulinEire Kitchen Head Chef"
        else:
            msg.subject = "Message from CulinEire Kitchen Sous Chef"
        msg.save(update_fields=["subject"])


class Migration(migrations.Migration):

    dependencies = [
        ("messaging", "0002_message_archive"),
        ("recipes", "0010_recipeauthor_user"),
    ]

    operations = [
        migrations.RunPython(fix_subjects, migrations.RunPython.noop),
    ]
