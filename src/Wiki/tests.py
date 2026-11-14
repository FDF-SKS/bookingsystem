from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django_tiptap_editor.utils.sanitize_html import sanitize_html
from django_tiptap_editor.widgets.tiptap_widget import TipTapWidget

from organization.models import Volunteer

from .guides import PAGES, SLUGS, content_for, content_path
from .models import WikiPage
from .search import plain_text


class WikiPageModelTests(TestCase):
    def test_slug_is_generated_from_title_with_danish_characters(self):
        page = WikiPage.objects.create(title='Sådan gør du i køkkenet')
        self.assertEqual(page.slug, 'saadan-goer-du-i-koekkenet')

    def test_duplicate_titles_get_unique_slugs(self):
        first = WikiPage.objects.create(title='Opvask')
        second = WikiPage.objects.create(title='Opvask')
        self.assertEqual(first.slug, 'opvask')
        self.assertEqual(second.slug, 'opvask-2')

    def test_slug_is_not_regenerated_when_title_changes(self):
        page = WikiPage.objects.create(title='Første titel')
        page.title = 'Ny titel'
        page.save()
        page.refresh_from_db()
        self.assertEqual(page.slug, 'foerste-titel')

    def test_parent_cannot_be_itself(self):
        page = WikiPage.objects.create(title='Side')
        page.parent = page
        with self.assertRaises(ValidationError):
            page.full_clean()

    def test_parent_cycle_is_rejected(self):
        root = WikiPage.objects.create(title='Rod')
        child = WikiPage.objects.create(title='Underside', parent=root)
        root.parent = child
        with self.assertRaises(ValidationError):
            root.full_clean()

    def test_ancestors_descendants_and_breadcrumb(self):
        root = WikiPage.objects.create(title='Rod')
        child = WikiPage.objects.create(title='Barn', parent=root)
        grandchild = WikiPage.objects.create(title='Barnebarn', parent=child)

        self.assertEqual(grandchild.get_ancestors(), [root, child])
        self.assertEqual(root.get_descendants(), [child, grandchild])
        self.assertEqual(root.get_descendant_ids(), [child.pk, grandchild.pk])
        self.assertEqual(grandchild.breadcrumb, 'Rod / Barn / Barnebarn')


class WikiViewTests(TestCase):
    def setUp(self):
        self.user = Volunteer.objects.create_user(
            username='wiki-reader',
            email='reader@example.com',
            password='test-password',
            first_name='Læs',
            last_name='Bruger',
        )
        self.staff = Volunteer.objects.create_user(
            username='wiki-admin',
            email='admin@example.com',
            password='test-password',
            first_name='Wiki',
            last_name='Admin',
            is_staff=True,
        )
        self.root = WikiPage.objects.create(
            title='Rodside',
            content='<p>Introduktion til wikien.</p>',
        )
        self.child = WikiPage.objects.create(
            title='Underside',
            parent=self.root,
            content='<p>Her står der noget om opvask og en blå svamp.</p>',
        )

    def test_home_requires_login(self):
        response = self.client.get(reverse('Wiki_WikiPage_list'))
        self.assertEqual(response.status_code, 302)

    def test_authenticated_user_can_view_page(self):
        self.client.force_login(self.user)
        response = self.client.get(self.root.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rodside')
        self.assertContains(response, 'Introduktion til wikien.')

    def test_home_lists_root_pages(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('Wiki_WikiPage_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hovedemner')
        self.assertContains(response, self.root.title)

    def test_staff_can_open_delete_confirmation(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('Wiki_WikiPage_delete', args=[self.child.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.child.title)

    def test_sidebar_lists_subpages(self):
        self.client.force_login(self.user)
        response = self.client.get(self.root.get_absolute_url())
        self.assertContains(response, self.child.title)
        self.assertContains(response, 'wiki-nav-list')

    def test_non_staff_cannot_create_page(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('Wiki_WikiPage_create'))
        self.assertEqual(response.status_code, 403)

    def test_staff_can_create_page_and_is_recorded_as_author(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('Wiki_WikiPage_create'),
            {
                'title': 'Ny side',
                'parent': self.root.pk,
                'order': '0',
                'content': '<h2>Overskrift</h2><p>Indhold.</p>',
            },
        )
        self.assertEqual(response.status_code, 302)
        page = WikiPage.objects.get(title='Ny side')
        self.assertEqual(page.parent, self.root)
        self.assertEqual(page.created_by, self.staff)
        self.assertIn('<h2>Overskrift</h2>', page.content)

    def test_create_form_uses_tiptap_widget(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('Wiki_WikiPage_create'))
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.context['form'].fields['content'].widget, TipTapWidget)
        self.assertContains(response, 'data-tiptap-config')
        self.assertContains(response, 'id="wikiReferenceModal"')
        self.assertContains(response, 'data-lookup-url="/wiki/lookup/"')

    def test_script_tags_are_stripped_on_save(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('Wiki_WikiPage_create'),
            {
                'title': 'Ren side',
                'parent': '',
                'order': '0',
                'content': '<script>alert("xss")</script><p>Hej</p>',
            },
        )
        self.assertEqual(response.status_code, 302)
        page = WikiPage.objects.get(title='Ren side')
        self.assertNotIn('<script', page.content)
        self.assertIn('<p>Hej</p>', page.content)

    def test_cross_reference_links_are_preserved(self):
        self.client.force_login(self.staff)
        link = f'<p>Se <a href="{self.child.get_absolute_url()}">undersiden</a>.</p>'
        response = self.client.post(
            reverse('Wiki_WikiPage_create'),
            {'title': 'Linkende side', 'parent': '', 'order': '0', 'content': link},
        )
        self.assertEqual(response.status_code, 302)
        page = WikiPage.objects.get(title='Linkende side')
        self.assertIn(self.child.get_absolute_url(), page.content)

    def test_update_rejects_parent_cycle(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('Wiki_WikiPage_update', args=[self.root.slug]),
            {
                'title': self.root.title,
                'parent': self.child.pk,
                'order': '0',
                'content': self.root.content,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('parent', response.context['form'].errors)

    def test_staff_can_delete_page(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse('Wiki_WikiPage_delete', args=[self.child.slug]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(WikiPage.objects.filter(pk=self.child.pk).exists())

    def test_backlinks_are_listed(self):
        self.child.content = f'<p>Se <a href="{self.root.get_absolute_url()}">rodsiden</a>.</p>'
        self.child.save()
        self.client.force_login(self.user)

        response = self.client.get(self.root.get_absolute_url())
        self.assertIn(self.child, response.context['backlinks'])


class WikiGuideContentTests(TestCase):
    """The bundled guides are deployable as-is: valid markup and real assets."""

    def test_every_page_has_a_content_file(self):
        for page in PAGES:
            self.assertTrue(
                content_path(page['slug']).exists(),
                f"Missing content for {page['slug']}",
            )
            self.assertTrue(content_for(page), page['slug'])

    def test_parents_are_defined_before_their_children(self):
        seen = set()
        for page in PAGES:
            if page['parent']:
                self.assertIn(page['parent'], seen, page['slug'])
            seen.add(page['slug'])

    def test_slugs_are_unique(self):
        self.assertEqual(len(SLUGS), len(set(SLUGS)))

    def test_content_survives_the_editor_sanitizer_unchanged(self):
        """A page opened and saved in the editor must not change."""
        for page in PAGES:
            content = content_for(page)
            self.assertEqual(str(sanitize_html(content)), content, page['slug'])

    def test_images_point_at_existing_static_files(self):
        import re

        from django.conf import settings

        pattern = re.compile(r'<img[^>]+src="([^"]+)"')
        for page in PAGES:
            for src in pattern.findall(content_for(page)):
                self.assertTrue(src.startswith('/static/'), f"{page['slug']}: {src}")
                asset = settings.BASE_DIR / 'static' / src.removeprefix('/static/')
                self.assertTrue(asset.exists(), f"{page['slug']}: {src} is missing")

    def test_internal_wiki_links_point_at_known_pages(self):
        import re

        pattern = re.compile(r'href="/wiki/([a-z0-9-]+)/"')
        reserved = {'search', 'lookup', 'create'}
        for page in PAGES:
            for slug in pattern.findall(content_for(page)):
                if slug in reserved:
                    continue
                self.assertIn(slug, SLUGS, f"{page['slug']} links to {slug}")


class SeedWikiGuidesCommandTests(TestCase):
    def test_command_creates_the_whole_tree(self):
        call_command('seed_wiki_guides', verbosity=0)

        self.assertEqual(WikiPage.objects.count(), len(PAGES))
        for page in PAGES:
            wiki_page = WikiPage.objects.get(slug=page['slug'])
            self.assertEqual(wiki_page.title, page['title'])
            expected_parent = WikiPage.objects.get(slug=page['parent']) if page['parent'] else None
            self.assertEqual(wiki_page.parent, expected_parent)

    def test_running_twice_does_not_duplicate_or_overwrite(self):
        call_command('seed_wiki_guides', verbosity=0)
        page = WikiPage.objects.get(slug=PAGES[0]['slug'])
        page.content = '<p>Rettet i editoren.</p>'
        page.save()

        call_command('seed_wiki_guides', verbosity=0)

        self.assertEqual(WikiPage.objects.count(), len(PAGES))
        page.refresh_from_db()
        self.assertEqual(page.content, '<p>Rettet i editoren.</p>')

    def test_update_flag_restores_the_bundled_content(self):
        call_command('seed_wiki_guides', verbosity=0)
        page = WikiPage.objects.get(slug=PAGES[0]['slug'])
        page.content = '<p>Rettet i editoren.</p>'
        page.save()

        call_command('seed_wiki_guides', '--update', verbosity=0)

        page.refresh_from_db()
        self.assertEqual(page.content, content_for(PAGES[0]))

    def test_dry_run_writes_nothing(self):
        call_command('seed_wiki_guides', '--dry-run', verbosity=0)
        self.assertFalse(WikiPage.objects.exists())


class WikiSearchTests(TestCase):
    def setUp(self):
        self.user = Volunteer.objects.create_user(
            username='wiki-searcher',
            email='searcher@example.com',
            password='test-password',
        )
        self.client.force_login(self.user)
        self.page = WikiPage.objects.create(
            title='Rengøring af køkken',
            content='<p>' + ('fyld ' * 80) + 'Brug den blå svamp til tallerkenerne. ' + ('fyld ' * 80) + '</p>',
        )

    def test_search_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('Wiki_Search'), {'q': 'svamp'})
        self.assertEqual(response.status_code, 302)

    def test_search_finds_title_match_and_highlights_it(self):
        response = self.client.get(reverse('Wiki_Search'), {'q': 'rengøring'})
        self.assertEqual(response.context['result_count'], 1)
        self.assertContains(response, '<mark>Rengøring</mark>')

    def test_search_finds_content_and_builds_contextual_preview(self):
        response = self.client.get(reverse('Wiki_Search'), {'q': 'svamp'})
        self.assertEqual(response.context['result_count'], 1)
        result = response.context['results'][0]
        self.assertIn('svamp', str(result['snippet']))
        self.assertIn('…', str(result['snippet']))
        self.assertContains(response, '<mark>svamp</mark>')

    def test_search_matches_all_terms_across_title_and_content(self):
        response = self.client.get(reverse('Wiki_Search'), {'q': 'rengøring svamp'})
        self.assertEqual(response.context['result_count'], 1)

    def test_empty_query_returns_no_results(self):
        response = self.client.get(reverse('Wiki_Search'))
        self.assertEqual(response.context['result_count'], 0)

    def test_lookup_returns_json_and_requires_login(self):
        response = self.client.get(reverse('Wiki_Lookup'), {'q': 'svamp'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['title'], self.page.title)
        self.assertEqual(data['results'][0]['url'], self.page.get_absolute_url())

        self.client.logout()
        response = self.client.get(reverse('Wiki_Lookup'), {'q': 'svamp'})
        self.assertEqual(response.status_code, 302)

    def test_plain_text_removes_markup_and_entities(self):
        self.assertEqual(plain_text('<p>Hej &amp; velkommen</p>'), 'Hej & velkommen')
