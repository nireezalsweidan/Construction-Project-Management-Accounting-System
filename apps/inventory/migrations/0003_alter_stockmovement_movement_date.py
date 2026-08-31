"""
Migration for the ``inventory`` app: adds a database index to
StockMovement.movement_date.

An equivalent index (idx_stock_movements_date) already exists on the
live database under a different name, per the canonical
construction_management_supabase.sql -- this migration is applied there
with ``--fake`` to avoid creating a redundant duplicate index. On a
fresh environment it runs normally and creates the index for real.
"""
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0002_warehouse_stockmovement_stock'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stockmovement',
            name='movement_date',
            field=models.DateTimeField(db_index=True, default=django.utils.timezone.now),
        ),
    ]
