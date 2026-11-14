from django import forms
from django.conf import settings
from django_tiptap_editor.forms.fields import TipTapFormField
from django_tiptap_editor.widgets.tiptap_widget import TipTapWidget

from .models import WikiPage

# Reuse the project's TipTap toolbar and image settings, with room for a long
# article. Keeping this derived from settings means the wiki editor follows the
# rest of the site when the default toolbar changes.
WIKI_TIPTAP_CONFIG = {
    **dict(getattr(settings, 'TIPTAP_DEFAULT_CONFIG', {})),
    'height': '520px',
}


class WikiPageForm(forms.ModelForm):
    content = TipTapFormField(
        label='Indhold',
        required=False,
        widget=TipTapWidget(
            config=WIKI_TIPTAP_CONFIG,
            attrs={'class': 'form-control', 'rows': 20},
        ),
    )

    class Meta:
        model = WikiPage
        fields = ['title', 'parent', 'order', 'content']
        labels = {
            'title': 'Titel',
            'parent': 'Overordnet side',
            'order': 'Rækkefølge',
        }
        widgets = {
            'title': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'F.eks. Sådan booker du et løb',
                }
            ),
            'parent': forms.Select(attrs={'class': 'form-select'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['parent'].required = False
        self.fields['parent'].empty_label = 'Ingen overordnet side (rod)'

        queryset = WikiPage.objects.all().order_by('title')
        if self.instance.pk:
            excluded_ids = [self.instance.pk, *self.instance.get_descendant_ids()]
            queryset = queryset.exclude(pk__in=excluded_ids)
        self.fields['parent'].queryset = queryset
