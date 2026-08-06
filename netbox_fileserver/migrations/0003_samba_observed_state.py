import django.db.models.deletion
import django.utils.timezone
import netbox.models.deletion
import taggit.managers
import utilities.json
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_fileserver", "0002_fileserverenrollmenttoken"),
    ]

    operations = [
        migrations.CreateModel(
            name="SambaConfigFile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                (
                    "custom_field_data",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        encoder=utilities.json.CustomFieldJSONEncoder,
                    ),
                ),
                ("path", models.CharField(max_length=255)),
                ("content", models.TextField(blank=True)),
                ("sha256", models.CharField(max_length=64)),
                ("size", models.PositiveBigIntegerField()),
                ("mtime", models.DateTimeField()),
                ("is_primary", models.BooleanField(default=False)),
                ("fetched_at", models.DateTimeField()),
                (
                    "domain",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="config_files",
                        to="netbox_fileserver.sambadomain",
                    ),
                ),
                (
                    "tags",
                    taggit.managers.TaggableManager(
                        through="extras.TaggedItem", to="extras.Tag"
                    ),
                ),
            ],
            options={
                "verbose_name": "Samba Config File",
                "ordering": ("domain", "path"),
                "unique_together": {("domain", "path")},
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.CreateModel(
            name="SambaConfigSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                (
                    "custom_field_data",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        encoder=utilities.json.CustomFieldJSONEncoder,
                    ),
                ),
                ("snapshot_id", models.CharField(max_length=128)),
                ("content", models.JSONField(default=dict)),
                (
                    "domain",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="config_snapshots",
                        to="netbox_fileserver.sambadomain",
                    ),
                ),
                (
                    "tags",
                    taggit.managers.TaggableManager(
                        through="extras.TaggedItem", to="extras.Tag"
                    ),
                ),
            ],
            options={
                "verbose_name": "Samba Config Snapshot",
                "ordering": ("domain", "-created"),
                "unique_together": {("domain", "snapshot_id")},
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.CreateModel(
            name="SambaObservedGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                (
                    "custom_field_data",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        encoder=utilities.json.CustomFieldJSONEncoder,
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("sid", models.CharField(blank=True, max_length=255)),
                ("members", models.JSONField(blank=True, default=list)),
                (
                    "domain",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="observed_groups",
                        to="netbox_fileserver.sambadomain",
                    ),
                ),
                (
                    "tags",
                    taggit.managers.TaggableManager(
                        through="extras.TaggedItem", to="extras.Tag"
                    ),
                ),
            ],
            options={
                "verbose_name": "Samba Observed Group",
                "ordering": ("domain", "name"),
                "unique_together": {("domain", "name")},
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.CreateModel(
            name="SambaObservedShare",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                (
                    "custom_field_data",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        encoder=utilities.json.CustomFieldJSONEncoder,
                    ),
                ),
                ("name", models.CharField(max_length=80)),
                ("path", models.CharField(blank=True, max_length=255)),
                ("raw_params", models.JSONField(blank=True, default=dict)),
                ("browseable", models.BooleanField(default=True)),
                ("read_only", models.BooleanField(default=True)),
                ("guest_ok", models.BooleanField(default=False)),
                ("drift_state", models.CharField(default="unmanaged", max_length=30)),
                (
                    "domain",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="observed_shares",
                        to="netbox_fileserver.sambadomain",
                    ),
                ),
                (
                    "tags",
                    taggit.managers.TaggableManager(
                        through="extras.TaggedItem", to="extras.Tag"
                    ),
                ),
            ],
            options={
                "verbose_name": "Samba Observed Share",
                "ordering": ("domain", "name"),
                "unique_together": {("domain", "name")},
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.CreateModel(
            name="SambaObservedUser",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                (
                    "custom_field_data",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        encoder=utilities.json.CustomFieldJSONEncoder,
                    ),
                ),
                ("username", models.CharField(max_length=255)),
                ("sid", models.CharField(blank=True, max_length=255)),
                ("enabled", models.BooleanField(default=True)),
                ("last_logon", models.DateTimeField(blank=True, null=True)),
                (
                    "domain",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="observed_users",
                        to="netbox_fileserver.sambadomain",
                    ),
                ),
                (
                    "tags",
                    taggit.managers.TaggableManager(
                        through="extras.TaggedItem", to="extras.Tag"
                    ),
                ),
            ],
            options={
                "verbose_name": "Samba Observed User",
                "ordering": ("domain", "username"),
                "unique_together": {("domain", "username")},
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.CreateModel(
            name="SambaServerState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                (
                    "custom_field_data",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        encoder=utilities.json.CustomFieldJSONEncoder,
                    ),
                ),
                ("version", models.CharField(blank=True, max_length=100)),
                ("smbd_active_state", models.CharField(blank=True, max_length=30)),
                ("smbd_sub_state", models.CharField(blank=True, max_length=30)),
                ("smbd_unit_file_state", models.CharField(blank=True, max_length=30)),
                ("nmbd_active_state", models.CharField(blank=True, max_length=30)),
                ("nmbd_sub_state", models.CharField(blank=True, max_length=30)),
                ("nmbd_unit_file_state", models.CharField(blank=True, max_length=30)),
                ("winbind_active_state", models.CharField(blank=True, max_length=30)),
                ("winbind_sub_state", models.CharField(blank=True, max_length=30)),
                ("winbind_unit_file_state", models.CharField(blank=True, max_length=30)),
                (
                    "samba_ad_dc_active_state",
                    models.CharField(blank=True, max_length=30),
                ),
                ("samba_ad_dc_sub_state", models.CharField(blank=True, max_length=30)),
                (
                    "samba_ad_dc_unit_file_state",
                    models.CharField(blank=True, max_length=30),
                ),
                ("config_sha256", models.CharField(blank=True, max_length=64)),
                ("testparm_ok", models.BooleanField(default=False)),
                ("observed_at", models.DateTimeField()),
                (
                    "domain",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="server_state",
                        to="netbox_fileserver.sambadomain",
                    ),
                ),
                (
                    "tags",
                    taggit.managers.TaggableManager(
                        through="extras.TaggedItem", to="extras.Tag"
                    ),
                ),
            ],
            options={
                "verbose_name": "Samba Server State",
                "ordering": ("domain",),
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.CreateModel(
            name="SambaSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                (
                    "custom_field_data",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        encoder=utilities.json.CustomFieldJSONEncoder,
                    ),
                ),
                ("username", models.CharField(blank=True, max_length=255)),
                ("machine", models.CharField(blank=True, max_length=255)),
                ("remote_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("share", models.CharField(blank=True, max_length=80)),
                ("pid", models.PositiveBigIntegerField()),
                ("opened_at", models.DateTimeField(blank=True, null=True)),
                (
                    "domain",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sessions",
                        to="netbox_fileserver.sambadomain",
                    ),
                ),
                (
                    "tags",
                    taggit.managers.TaggableManager(
                        through="extras.TaggedItem", to="extras.Tag"
                    ),
                ),
            ],
            options={
                "verbose_name": "Samba Session",
                "ordering": ("domain", "username", "machine", "share", "pid"),
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.CreateModel(
            name="SambaSyncRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                (
                    "custom_field_data",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        encoder=utilities.json.CustomFieldJSONEncoder,
                    ),
                ),
                ("started", models.DateTimeField(default=django.utils.timezone.now)),
                ("finished", models.DateTimeField(blank=True, null=True)),
                ("status", models.CharField(default="running", max_length=30)),
                ("rpc_execution_ids", models.JSONField(blank=True, default=list)),
                ("error_message", models.TextField(blank=True)),
                (
                    "domain",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sync_runs",
                        to="netbox_fileserver.sambadomain",
                    ),
                ),
                (
                    "tags",
                    taggit.managers.TaggableManager(
                        through="extras.TaggedItem", to="extras.Tag"
                    ),
                ),
            ],
            options={
                "verbose_name": "Samba Sync Run",
                "ordering": ("-started",),
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
    ]
