from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0019_alter_tjanse_description'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalteam',
            name='discord_topic_thread_id',
            field=models.CharField(blank=True, help_text='ID på Discord-tråden i forumkanalen. Oprettes automatisk.', max_length=64, null=True),
        ),
        migrations.AddField(
            model_name='team',
            name='discord_topic_thread_id',
            field=models.CharField(blank=True, help_text='ID på Discord-tråden i forumkanalen. Oprettes automatisk.', max_length=64, null=True),
        ),
    ]
