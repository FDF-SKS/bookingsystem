from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from Wiki.guides import PAGES, content_for
from Wiki.models import WikiPage


class Command(BaseCommand):
    help = (
        'Opretter wikisiderne med guides til bookingsystemet. '
        'Sider der allerede findes, røres ikke, medmindre --update angives.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--update',
            action='store_true',
            help='Overskriv titel, indhold og placering på sider, der allerede findes.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Vis hvad kommandoen ville gøre, uden at gemme noget.',
        )

    def handle(self, *args, **options):
        update = options['update']
        dry_run = options['dry_run']
        verbosity = options['verbosity']
        created = updated = skipped = 0
        by_slug = {}

        if dry_run and verbosity:
            self.stdout.write(self.style.WARNING('Tør kørsel - der gemmes intet.'))

        with transaction.atomic():
            for entry in PAGES:
                parent = self._parent_for(entry, by_slug, dry_run)
                content = self._content_for(entry)

                page = WikiPage.objects.filter(slug=entry['slug']).first()
                if page is None:
                    created += 1
                    if verbosity:
                        self.stdout.write(f"  + {entry['title']}  (/wiki/{entry['slug']}/)")
                    if not dry_run:
                        page = WikiPage.objects.create(
                            slug=entry['slug'],
                            title=entry['title'],
                            parent=parent,
                            order=entry['order'],
                            content=content,
                        )
                    else:
                        page = WikiPage(
                            slug=entry['slug'],
                            title=entry['title'],
                            parent=parent,
                            order=entry['order'],
                            content=content,
                        )
                else:
                    changes = self._changes(entry, page, parent, content)
                    if not changes:
                        skipped += 1
                    elif update:
                        updated += 1
                        if verbosity:
                            self.stdout.write(f"  ~ {entry['title']}  ({', '.join(changes)})")
                        if not dry_run:
                            for field, value in changes.items():
                                setattr(page, field, value)
                            page.save()
                    else:
                        skipped += 1
                        if verbosity:
                            self.stdout.write(
                                f"  = {entry['title']} findes allerede "
                                f"({', '.join(changes)}) - brug --update for at opdatere"
                            )

                by_slug[entry['slug']] = page

        summary = (
            f'{created} oprettet, {updated} opdateret, '
            f'{skipped} uændret/springet over.'
        )
        if dry_run:
            if verbosity:
                self.stdout.write(self.style.WARNING(f'Tør kørsel: {summary}'))
        else:
            if verbosity:
                self.stdout.write(self.style.SUCCESS(summary))

    def _parent_for(self, entry, by_slug, dry_run):
        parent_slug = entry['parent']
        if not parent_slug:
            return None
        parent = by_slug.get(parent_slug)
        if parent is None and not dry_run:
            raise CommandError(
                f"Kan ikke finde overordnet side '{parent_slug}' for "
                f"'{entry['slug']}'. Er rækkefølgen i Wiki.guides.PAGES ændret?"
            )
        return parent

    def _content_for(self, entry):
        try:
            return content_for(entry)
        except FileNotFoundError as exc:
            raise CommandError(
                f"Mangler indholdsfil for '{entry['slug']}': {exc}"
            ) from exc

    def _changes(self, entry, page, parent, content):
        changes = {}
        if page.title != entry['title']:
            changes['title'] = entry['title']
        if page.order != entry['order']:
            changes['order'] = entry['order']
        # A dry-run placeholder has no pk yet, so it cannot be compared.
        if parent is None or parent.pk is not None:
            target_parent_id = parent.pk if parent is not None else None
            if page.parent_id != target_parent_id:
                changes['parent'] = parent
        if page.content.strip() != content:
            changes['content'] = content
        return changes
