import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """DIET-607 rack-aware placement: opt-in PlanServerClass fields + the
    durable PlanLocalityRange report model. Additive and reversible; disabled
    state (place_in_racks=False, the default) leaves behavior unchanged.

    Scoped to ONLY the rack-placement changes; pre-existing framework field
    drift detected by makemigrations is intentionally excluded.
    """

    dependencies = [
        ('dcim', '0216_latitude_longitude_validators'),
        ('extras', '0133_make_cf_minmax_decimal'),
        ('netbox_hedgehog', '0054_seed_sfp_plus_10gbase_t'),
    ]

    operations = [
        migrations.AddField(
            model_name='planserverclass',
            name='place_in_racks',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='planserverclass',
            name='servers_per_rack',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='planserverclass',
            name='membership_only',
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name='PlanLocalityRange',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('rack_index', models.PositiveIntegerField()),
                ('distribution', models.CharField(max_length=32)),
                ('alloc_seq_start', models.PositiveIntegerField()),
                ('alloc_seq_end', models.PositiveIntegerField()),
                ('server_ordinal_start', models.PositiveIntegerField()),
                ('server_ordinal_end', models.PositiveIntegerField()),
                ('logical_name_first', models.CharField(max_length=64)),
                ('logical_name_last', models.CharField(max_length=64)),
                ('logical_sequence', models.JSONField(default=list)),
                ('physical_sequence', models.JSONField(default=list)),
                ('physical_ports_distinct', models.JSONField(default=list)),
                ('port_count', models.PositiveIntegerField()),
                ('spans_boundary', models.BooleanField(default=False)),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='locality_ranges', to='netbox_hedgehog.topologyplan')),
                ('rack', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='dcim.rack')),
                ('server_class', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='locality_ranges', to='netbox_hedgehog.planserverclass')),
                ('switch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='dcim.device')),
                ('zone', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='locality_ranges', to='netbox_hedgehog.switchportzone')),
            ],
            options={
                'verbose_name': 'Locality Range',
                'verbose_name_plural': 'Locality Ranges',
                'ordering': ['plan', 'server_class', 'rack_index', 'switch__name', 'zone__priority', 'zone__zone_name', 'alloc_seq_start'],
                'unique_together': {('plan', 'server_class', 'rack', 'switch', 'zone')},
            },
        ),
    ]
