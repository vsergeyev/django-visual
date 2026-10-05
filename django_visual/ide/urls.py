from django.urls import path, re_path

from . import views

PROJECT = r'^open_project/(?P<project_id>\w+)/'

urlpatterns = [
    path('create_project/', views.create_project, name='create_project'),

    re_path(PROJECT + r'run_project/$', views.run_project, name='run_project'),
    re_path(PROJECT + r'stop_project/$', views.stop_project, name='stop_project'),
    re_path(PROJECT + r'create_application/$', views.create_application, name='create_application'),
    re_path(PROJECT + r'remove_application/$', views.remove_application, name='remove_application'),
    re_path(PROJECT + r'add_application/$', views.add_application, name='add_application'),
    re_path(PROJECT + r'add_model/$', views.add_model, name='add_model'),
    re_path(PROJECT + r'$', views.open_project, name='open_project'),

    path('open_file/', views.open_file, name='open_file'),
    path('save_file/', views.save_file, name='save_file'),

    path('welcome/', views.index, name='index'),
]
