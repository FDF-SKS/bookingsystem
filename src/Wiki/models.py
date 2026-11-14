from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

# Django's slugify drops Danish characters. Transliterate them first so a title
# like "Sådan gør du" becomes "saadan-goer-du" instead of "sdan-gr-du".
DANISH_SLUG_TRANSLATION = str.maketrans(
    {
        'æ': 'ae',
        'ø': 'oe',
        'å': 'aa',
        'Æ': 'Ae',
        'Ø': 'Oe',
        'Å': 'Aa',
    }
)


def slugify_title(title: str) -> str:
    """Return a URL-safe slug for a wiki title."""
    return slugify(title.translate(DANISH_SLUG_TRANSLATION)) or 'side'


class WikiPage(models.Model):
    """A single page in the wiki, optionally nested under another page."""

    title = models.CharField(max_length=200, verbose_name='Titel')
    slug = models.SlugField(
        max_length=220,
        unique=True,
        blank=True,
        verbose_name='URL-navn',
        help_text='Lad feltet stå tomt for at generere det automatisk ud fra titlen.',
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='children',
        null=True,
        blank=True,
        verbose_name='Overordnet side',
    )
    content = models.TextField(blank=True, verbose_name='Indhold')
    order = models.PositiveIntegerField(
        default=0,
        verbose_name='Rækkefølge',
        help_text='Sider med lavere tal vises først i menuen.',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wiki_pages_created',
        verbose_name='Oprettet af',
    )
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        ordering = ['order', 'title']
        verbose_name = 'Wikiside'
        verbose_name_plural = 'Wikisider'
        indexes = [
            models.Index(fields=['parent', 'order']),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug()
        super().save(*args, **kwargs)

    def _unique_slug(self) -> str:
        base = slugify_title(self.title)
        candidate = base
        suffix = 2
        while WikiPage.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
            candidate = f'{base}-{suffix}'
            suffix += 1
        return candidate

    def clean(self):
        super().clean()
        if not self.parent_id:
            return
        if self.parent_id == self.pk:
            raise ValidationError({'parent': 'En side kan ikke være sin egen overordnede side.'})
        seen = {self.pk}
        ancestor = self.parent
        while ancestor is not None:
            if ancestor.pk in seen:
                raise ValidationError(
                    {'parent': 'Denne placering ville skabe en cirkel i sidestrukturen.'}
                )
            seen.add(ancestor.pk)
            ancestor = ancestor.parent

    def get_absolute_url(self):
        return reverse('Wiki_WikiPage_detail', args=(self.slug,))

    def get_update_url(self):
        return reverse('Wiki_WikiPage_update', args=(self.slug,))

    def get_delete_url(self):
        return reverse('Wiki_WikiPage_delete', args=(self.slug,))

    def get_ancestors(self):
        """Return ancestors from the root down to the direct parent."""
        ancestors = []
        seen = set()
        node = self.parent
        while node is not None and node.pk not in seen:
            ancestors.append(node)
            seen.add(node.pk)
            node = node.parent
        return list(reversed(ancestors))

    def get_descendants(self):
        """Return every page below this one, depth first."""
        descendants = []
        for child in self.children.all().order_by('order', 'title'):
            descendants.append(child)
            descendants.extend(child.get_descendants())
        return descendants

    def get_descendant_ids(self):
        return [page.pk for page in self.get_descendants()]

    @property
    def breadcrumb(self) -> str:
        return ' / '.join([page.title for page in self.get_ancestors()] + [self.title])
