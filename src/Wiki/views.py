import contextlib
import html

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.utils.html import strip_tags
from django.views import generic

from organization.permissions import StaffRequiredMixin

from .forms import WikiPageForm
from .models import WikiPage
from .search import (
    build_filter,
    build_search_results,
    make_snippet,
    page_matches,
    plain_text,
    query_terms,
)


class WikiHomeView(LoginRequiredMixin, generic.TemplateView):
    """Landing page listing the top-level pages in the library."""

    template_name = 'Wiki/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['root_pages'] = (
            WikiPage.objects.filter(parent__isnull=True)
            .annotate(child_count=Count('children'))
            .order_by('order', 'title')
        )
        context['recent_pages'] = WikiPage.objects.order_by('-last_updated')[:6]
        context['total_pages'] = WikiPage.objects.count()
        return context


class WikiPageDetailView(LoginRequiredMixin, generic.DetailView):
    model = WikiPage
    template_name = 'Wiki/page_detail.html'
    context_object_name = 'page'

    def get_queryset(self):
        return WikiPage.objects.select_related('parent', 'created_by')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page = self.object
        context['children'] = page.children.all().order_by('order', 'title')
        # Links created by the cross-reference tool point at /wiki/<slug>/.
        context['backlinks'] = (
            WikiPage.objects.filter(content__icontains=f'/wiki/{page.slug}/')
            .exclude(pk=page.pk)
            .order_by('title')
        )
        return context


class WikiPageCreateView(StaffRequiredMixin, generic.CreateView):
    model = WikiPage
    form_class = WikiPageForm
    template_name = 'Wiki/page_form.html'

    def get_initial(self):
        initial = super().get_initial()
        parent_id = self.request.GET.get('parent')
        if parent_id:
            with contextlib.suppress(TypeError, ValueError):
                initial['parent'] = WikiPage.objects.filter(pk=int(parent_id)).first()
        return initial

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page'] = None
        return context


class WikiPageUpdateView(StaffRequiredMixin, generic.UpdateView):
    model = WikiPage
    form_class = WikiPageForm
    template_name = 'Wiki/page_form.html'
    context_object_name = 'page'


class WikiPageDeleteView(StaffRequiredMixin, generic.DeleteView):
    model = WikiPage
    template_name = 'Wiki/page_confirm_delete.html'
    context_object_name = 'page'

    def get_success_url(self):
        parent = self.object.parent
        if parent is not None:
            return parent.get_absolute_url()
        return reverse_lazy('Wiki_WikiPage_list')


class WikiSearchView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'Wiki/search.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get('q', '').strip()
        context['query'] = query
        context['results'] = build_search_results(query)
        context['result_count'] = len(context['results'])
        return context


@login_required
def wiki_lookup(request):
    """JSON endpoint used by the cross-reference picker in the page editor."""
    query = request.GET.get('q', '').strip()
    condition = build_filter(query)
    pages = WikiPage.objects.all()
    if condition is not None:
        pages = pages.filter(condition)
    pages = pages.order_by('title')[:20]

    terms = query_terms(query)
    results = []
    for page in pages:
        if query and not page_matches(page, terms):
            continue
        body = plain_text(page.content)
        results.append(
            {
                'title': page.title,
                'url': page.get_absolute_url(),
                'path': ' / '.join(ancestor.title for ancestor in page.get_ancestors()),
                'snippet': html.unescape(strip_tags(make_snippet(body, query, radius=90))),
            }
        )
    return JsonResponse({'results': results})
