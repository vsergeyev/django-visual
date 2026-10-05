"""django_visual URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path

from ide import views


urlpatterns = [
    path('ide/', include('ide.urls')),
    path('', views.index, name='index'),
]

urlpatterns += staticfiles_urlpatterns()
