from django.db import migrations


def create_email_addresses(apps, schema_editor):
    Volunteer = apps.get_model('organization', 'Volunteer')
    EmailAddress = apps.get_model('account', 'EmailAddress')
    for volunteer in Volunteer.objects.exclude(email='').iterator():
        EmailAddress.objects.get_or_create(
            user=volunteer,
            email=volunteer.email.lower(),
            defaults={'verified': True, 'primary': True},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0020_historicalteam_discord_topic_thread_id_and_more'),
        ('account', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_email_addresses, migrations.RunPython.noop),
    ]
