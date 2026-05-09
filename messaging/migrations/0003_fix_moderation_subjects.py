from django.db import migrations


def fix_subjects(apps, _schema_editor):
    message_model = apps.get_model("messaging", "Message")
    author_model = apps.get_model("recipes", "RecipeAuthor")

    try:
        greenbear_user = author_model.objects.get(slug="greenbear").user
    except author_model.DoesNotExist:
        greenbear_user = None

    old_subject = "Message from CulinEire moderation"

    qs = message_model.objects.filter(subject=old_subject)
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
