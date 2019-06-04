from django.conf.urls import url

from . import views

urlpatterns = [
    url('create_project/', views.create_project, name='create_project'),
    url('open_project/(?P<project_id>\w+)/', views.open_project, name='open_project'),
    url('welcome/', views.index, name='index'),
]