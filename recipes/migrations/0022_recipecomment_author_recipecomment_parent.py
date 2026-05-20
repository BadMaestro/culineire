from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('recipes', '0021_reciperating_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='recipecomment',
            name='author',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='comment_replies',
                to='recipes.recipeauthor',
            ),
        ),
        migrations.AddField(
            model_name='recipecomment',
            name='parent',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='replies',
                to='recipes.recipecomment',
            ),
        ),
    ]
