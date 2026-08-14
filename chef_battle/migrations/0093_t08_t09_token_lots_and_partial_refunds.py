from django.db import migrations, models
import django.db.models.deletion


def create_legacy_lots(apps, schema_editor):
    TokenWallet = apps.get_model("chef_battle", "TokenWallet")
    TokenLot = apps.get_model("chef_battle", "TokenLot")
    for wallet in TokenWallet.objects.filter(balance__gt=0).iterator():
        TokenLot.objects.create(
            wallet_id=wallet.pk,
            source_type="legacy",
            original_amount=wallet.balance,
            remaining_amount=wallet.balance,
            origin_ambiguous=True,
        )


class Migration(migrations.Migration):

    dependencies = [("chef_battle", "0092_t07_payout_paid_disputed")]

    operations = [
        migrations.AlterField(
            model_name="tokenorder", name="status",
            field=models.CharField(choices=[("pending", "Pending"), ("completed", "Completed"), ("expired", "Expired"), ("cancelled", "Cancelled"), ("partial_refund", "Partially Refunded"), ("refunded", "Refunded"), ("disputed", "Under Dispute")], db_index=True, default="pending", max_length=16),
        ),
        migrations.AddField(model_name="tokenorder", name="refunded_amount_cents", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="tokenorder", name="clawed_tokens", field=models.PositiveIntegerField(default=0)),
        migrations.CreateModel(
            name="TokenLot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_type", models.CharField(choices=[("purchase", "Purchase"), ("reward", "Reward / Grant"), ("legacy", "Legacy balance — origin ambiguous")], max_length=16)),
                ("original_amount", models.PositiveIntegerField()),
                ("remaining_amount", models.PositiveIntegerField()),
                ("origin_ambiguous", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("source_order", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="token_lot", to="chef_battle.tokenorder")),
                ("source_transaction", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="created_lots", to="chef_battle.tokentransaction")),
                ("wallet", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="token_lots", to="chef_battle.tokenwallet")),
            ],
            options={"ordering": ["created_at", "pk"]},
        ),
        migrations.CreateModel(
            name="TokenSpendAllocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.PositiveIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("lot", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="spend_allocations", to="chef_battle.tokenlot")),
                ("transaction", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="spend_allocations", to="chef_battle.tokentransaction")),
            ],
        ),
        migrations.AddConstraint(model_name="tokenspendallocation", constraint=models.UniqueConstraint(fields=("transaction", "lot"), name="unique_token_spend_lot")),
        migrations.AddField(model_name="appreciationgift", name="token_transaction", field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="appreciation_gift", to="chef_battle.tokentransaction")),
        migrations.AddField(model_name="viewerbattlegift", name="token_transaction", field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="viewer_battle_gift", to="chef_battle.tokentransaction")),
        migrations.RunPython(create_legacy_lots, migrations.RunPython.noop),
    ]
