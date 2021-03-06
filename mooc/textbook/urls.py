# -*- coding: utf-8 -*-
from django.conf.urls import patterns, include, url
from django.views.generic.base import TemplateView

from textbook import views

# Textbook URL pattern.
urlpatterns = patterns('',
    url(r'^$', views.view_page, name='textbook'),
    url(r'^(?P<page>[^/]+)/$', views.view_page, name='textbook_page'),
    url(r'^search/(?P<query>[^/]+)$', views.find_pages, name='textbook_search'),
)

