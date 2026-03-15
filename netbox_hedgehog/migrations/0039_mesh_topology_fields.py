# Generated manually for DIET-309: Mesh topology fields

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0038_plan_server_nic_finalize'),
    ]

    operations = [
        migrations.AddField(
            model_name='planswitchclass',
            name='topology_mode',
            field=models.CharField(
                blank=True,
                choices=[('spine-leaf', 'Spine-Leaf'), ('prefer-mesh', 'Prefer Mesh')],
                default='spine-leaf',
                help_text='Topology mode for this switch class fabric.',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='topologyplan',
            name='mesh_ip_pool',
            field=models.CharField(
                blank=True,
                default='',
                help_text='CIDR prefix for mesh link /31 allocation (e.g. 172.30.128.0/24). Required when any fabric uses prefer-mesh topology.',
                max_length=50,
            ),
        ),
        migrations.CreateModel(
            name='PlanMeshLink',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fabric_name', models.CharField(blank=True, max_length=50)),
                ('subnet', models.CharField(help_text='/31 subnet, e.g. 172.30.128.0/31', max_length=20)),
                ('link_index', models.IntegerField(default=0)),
                ('leaf1_port', models.CharField(blank=True, max_length=50)),
                ('leaf2_port', models.CharField(blank=True, max_length=50)),
                ('plan', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='mesh_links',
                    to='netbox_hedgehog.topologyplan',
                )),
                ('switch_class_a', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='mesh_links_as_a',
                    to='netbox_hedgehog.planswitchclass',
                )),
                ('switch_class_b', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='mesh_links_as_b',
                    to='netbox_hedgehog.planswitchclass',
                )),
            ],
            options={
                'ordering': ['plan', 'fabric_name', 'link_index'],
                'unique_together': {('plan', 'fabric_name', 'link_index')},
            },
        ),
    ]
