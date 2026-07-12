from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('chef_battle', '0065_battle_gift_artifact'),
        ('recipes', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='BattleIngredient',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150)),
                ('is_key', models.BooleanField(default=False, help_text='Hidden combat lock — protects this ingredient from elimination')),
                ('is_eliminated', models.BooleanField(db_index=True, default=False)),
                ('eliminated_at', models.DateTimeField(blank=True, null=True)),
                ('position', models.PositiveSmallIntegerField(default=0, help_text="Display order within this chef's list")),
                ('battle', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='battle_ingredients', to='chef_battle.battle')),
                ('chef', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='battle_ingredients', to='recipes.recipeauthor')),
                ('eliminated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ingredients_eliminated', to='recipes.recipeauthor')),
            ],
            options={
                'ordering': ['battle', 'chef', 'position'],
            },
        ),
        migrations.AddConstraint(
            model_name='battleingredient',
            constraint=models.UniqueConstraint(fields=['battle', 'chef', 'position'], name='unique_ingredient_position_per_chef'),
        ),
    ]
