from django.urls import path

from . import views

urlpatterns = [
    path('', views.WikiHomeView.as_view(), name='Wiki_WikiPage_list'),
    path('search/', views.WikiSearchView.as_view(), name='Wiki_Search'),
    path('lookup/', views.wiki_lookup, name='Wiki_Lookup'),
    path('create/', views.WikiPageCreateView.as_view(), name='Wiki_WikiPage_create'),
    path('<slug:slug>/', views.WikiPageDetailView.as_view(), name='Wiki_WikiPage_detail'),
    path('<slug:slug>/edit/', views.WikiPageUpdateView.as_view(), name='Wiki_WikiPage_update'),
    path('<slug:slug>/delete/', views.WikiPageDeleteView.as_view(), name='Wiki_WikiPage_delete'),
]
