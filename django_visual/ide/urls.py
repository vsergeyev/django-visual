from django.conf.urls import url

from . import views

urlpatterns = [
    url('create_project/', views.create_project, name='create_project'),

    url('open_project/(?P<project_id>\w+)/run_project/', views.run_project, name='run_project'),
    url('open_project/(?P<project_id>\w+)/stop_project/', views.stop_project, name='stop_project'),
    url('open_project/(?P<project_id>\w+)/add_application/', views.add_application, name='add_application'),
    url('open_project/(?P<project_id>\w+)/', views.open_project, name='open_project'),

    url('open_file/', views.open_file, name='open_file'),
    url('save_file/', views.save_file, name='save_file'),

    url('welcome/', views.index, name='index'),
]