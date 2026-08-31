"""
Initial migration for the ``users`` app.

Registers Django's model-state awareness of the existing ``users`` table
(managed=False -- see apps/users/models.py). Because managed=False, this
CreateModel operation is a no-op at the database level: applying it does
NOT create/alter the table, which already exists and is owned by the
separate, not-yet-built Users/RBAC ticket. It exists purely so other
apps' foreign keys into users.User resolve correctly.
"""
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('username', models.CharField(max_length=150, unique=True)),
                ('email', models.EmailField(max_length=255, unique=True)),
                ('password_hash', models.CharField(max_length=255)),
                ('first_name', models.CharField(max_length=100)),
                ('last_name', models.CharField(max_length=100)),
                ('role', models.CharField(max_length=100)),
                ('phone', models.CharField(blank=True, max_length=50, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('last_login', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'User',
                'verbose_name_plural': 'Users',
                'db_table': 'users',
                'managed': False,
            },
        ),
    ]
