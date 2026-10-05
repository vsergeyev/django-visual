import re

import pytest
from django.core.management.base import CommandError

from ide.create_project import (
    copy_application_template,
    copy_project_template,
    template_options,
)

TEMPLATES = ["empty", "blog", "cms", "app"]
TEMPLATE_APPS = {"empty": None, "blog": "blog", "cms": "cms", "app": "app"}
PY2_LEFTOVERS = ["unicode_literals", "coding: utf-8", "django.conf.urls", "USE_L10N", "{{", "{%"]


def python_sources(root):
    return [p for p in root.rglob("*.py")]


def test_template_options_has_command_defaults():
    options = template_options("project", verbosity=0, template="/tpl")
    assert options["verbosity"] == 0
    assert options["template"] == "/tpl"
    assert options["extensions"] == ["py"]
    assert options["files"] == []
    assert "name" not in options and "directory" not in options


@pytest.mark.parametrize("template", TEMPLATES)
def test_project_template_renders(projects_home, template):
    copy_project_template(template, "sample")
    root = projects_home / "sample"

    assert (root / "manage.py").is_file()
    assert not (root / "project_name").exists()
    assert not list(root.rglob("*-tpl"))

    settings_py = (root / "sample" / "settings.py").read_text()
    assert "ROOT_URLCONF = 'sample.urls'" in settings_py
    assert "WSGI_APPLICATION = 'sample.wsgi.application'" in settings_py
    assert re.search(r"^SECRET_KEY = '.{50}'$", settings_py, re.M)
    assert "DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'" in settings_py
    app = TEMPLATE_APPS[template]
    if app:
        assert "    '{}',\n".format(app) in settings_py

    assert "'sample.settings'" in (root / "manage.py").read_text()
    assert "'sample.settings'" in (root / "sample" / "wsgi.py").read_text()

    for source in python_sources(root):
        text = source.read_text()
        for leftover in PY2_LEFTOVERS:
            assert leftover not in text, "{} in {}".format(leftover, source)
        compile(text, str(source), "exec")


def test_cms_template_configures_sites(projects_home):
    copy_project_template("cms", "sample")
    settings_py = (projects_home / "sample" / "sample" / "settings.py").read_text()
    assert "SITE_ID = 1" in settings_py
    assert "'django.contrib.flatpages.middleware.FlatpageFallbackMiddleware'," in settings_py


@pytest.mark.parametrize("template, app", [("blog", "blog"), ("cms", "cms")])
def test_shipped_migrations_keep_auto_field(projects_home, template, app):
    copy_project_template(template, "sample")
    apps_py = (projects_home / "sample" / app / "apps.py").read_text()
    assert "default_auto_field = 'django.db.models.AutoField'" in apps_py


def test_app_template_has_migrations_package(projects_home):
    copy_project_template("app", "sample")
    assert (projects_home / "sample" / "app" / "migrations" / "__init__.py").is_file()


def test_blog_template_keeps_bundled_database(projects_home):
    copy_project_template("blog", "sample")
    assert (projects_home / "sample" / "db.sqlite3").stat().st_size > 0


def test_creates_projects_home_if_missing(projects_home):
    assert not projects_home.exists()
    copy_project_template("empty", "sample")
    assert projects_home.is_dir()


@pytest.mark.parametrize("name", ["bad-name", "1abc", "os"])
def test_invalid_project_name(projects_home, name):
    with pytest.raises(CommandError):
        copy_project_template("blog", name)


def test_unknown_template(projects_home):
    with pytest.raises(CommandError, match="couldn't handle"):
        copy_project_template("nope", "sample")


def test_existing_project_is_not_overwritten(make_project):
    root = make_project("blog")
    settings_py = root / "sample" / "settings.py"
    original = settings_py.read_text()
    with pytest.raises(CommandError, match="already exists"):
        copy_project_template("blog", "sample")
    assert settings_py.read_text() == original


def test_copy_application_template(make_project):
    root = make_project("empty")
    copy_application_template(str(root), "shop")
    app = root / "shop"
    for name in ["__init__.py", "admin.py", "apps.py", "models.py", "tests.py",
                 "views.py", "migrations/__init__.py"]:
        assert (app / name).is_file(), name
    apps_py = (app / "apps.py").read_text()
    assert "class ShopConfig(AppConfig):" in apps_py
    assert "name = 'shop'" in apps_py
    assert "from .models import *" in (app / "admin.py").read_text()
    for source in python_sources(app):
        assert "{{" not in source.read_text()


def test_copy_application_template_invalid_name(make_project):
    root = make_project("empty")
    with pytest.raises(CommandError):
        copy_application_template(str(root), "bad-name")
