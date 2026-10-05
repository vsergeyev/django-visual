from django.apps import AppConfig


class BlogConfig(AppConfig):
    # shipped migrations/0001_initial.py uses AutoField
    default_auto_field = 'django.db.models.AutoField'
    name = 'blog'
