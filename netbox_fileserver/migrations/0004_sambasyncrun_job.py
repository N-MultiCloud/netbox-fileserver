import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_fileserver", "0003_samba_observed_state"),
        ("core", "0011_move_objectchange"),
    ]

    operations = [
        migrations.AddField(
            model_name="sambasyncrun",
            name="job",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="core.job",
            ),
        ),
    ]
