# Django 5.2 / 6.1 Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the Visual Django IDE (and the projects it generates) from Python 2.7 / Django 1.11 to Python 3.12+ / Django 5.2 LTS and 6.1, covered by a pytest suite.

**Architecture:** Same Django IDE app (`django_visual/ide`), ported to Python 3. Project introspection moves out of the IDE process into a subprocess (`ide/introspect.py`) that imports the user's project with its own settings and prints JSON. Generated-project templates (`django_visual/conf/`) are rewritten to the modern `startproject` layout.

**Tech Stack:** Python 3.12, Django 5.2 / 6.1, pytest + pytest-django, tox (+ tox-uv), uv for venvs.

**Spec:** `docs/superpowers/specs/2026-10-05-django-5-6-upgrade-design.md`

## Global Constraints

- Branch `feature/django-5-6-upgrade`. **Do not commit.** `git mv` (staging) is allowed for renames; never `git commit`.
- Supported: Django `>=5.2,<6.2` (5.2 LTS and 6.1), Python `>=3.12`. Python 2 support dropped.
- No UI/JS changes except `.iteritems` → `.items` in `ide/templates/open_project.html`.
- URL paths and URL names unchanged (JS uses relative URLs such as `run_project/`, `/ide/open_file/`).
- `ide/*.py` and `conf/**` app code use **tabs** for indentation where the file already does (`views.py`, `open_project.py`, `create_project.py`, template app `views.py`/`models.py`); `run.py`, settings/urls/manage/wsgi templates use 4 spaces. New test files use 4 spaces.
- Generated projects must not need a migration on first run (`makemigrations --check` clean) and must emit no `DeprecationWarning` on 6.1.
- Out of scope: arbitrary-path `open_file`/`save_file`, missing CSRF middleware, `stop_project` not killing the runserver grandchild.
- All commands run from repo root `/Users/odubr/Documents/django-visual` using `.venv/bin/...` unless stated.

## Review Focus

1. Re-opening a project after its `models.py` changed must show the new models (no stale imports in the IDE process) → Task 4 `test_edits_are_reflected_on_reopen`.
2. A broken user project (app missing from disk, `SyntaxError` in `models.py`, an app named like an IDE module e.g. `views`) must still open with the red error banner, not a 500 → Task 4 `test_missing_app_reports_error`, `test_syntax_error_reports_error`, `test_app_named_like_ide_module`.
3. Adding an app that is already installed, or removing one that is not, must leave a valid `INSTALLED_APPS` and return OK → Task 5 `test_add_application_is_idempotent`, `test_remove_application_is_idempotent`.
4. The SQL viewer fetches `db.sqlite3` through `open_file`, and users save non-ASCII source → binary must round-trip byte-exact, text as UTF-8 → Task 5 `test_open_binary_file`, `test_save_and_open_utf8_round_trip`.
5. A settings file whose list is on one line (`INSTALLED_APPS = []`) must actually be rewritten, and Python 3 `__pycache__` dirs must not appear in the project tree → Task 3 `test_edit_installed_apps_single_line`, `test_build_project_tree_skips_compiled_and_pycache`.

---

## File Structure

| Path | Responsibility |
|---|---|
| `requirements.txt` | runtime deps (Django, gunicorn) |
| `requirements-dev.txt` (new) | test deps |
| `runtime.txt` | Heroku Python version |
| `pytest.ini` (new) | pytest-django config, `slow` marker, testpaths |
| `tox.ini` (new) | Django 5.2 / 6.1 matrix |
| `GNUmakefile`, `README.md` | `test` target, requirements/test docs |
| `django_visual/django_visual/settings.py` | IDE settings (+ `RUN_LOG_FILE`, env-overridable `PROJECTS_HOME`) |
| `django_visual/django_visual/urls.py`, `django_visual/ide/urls.py` | `path`/`re_path` routing |
| `django_visual/ide/create_project.py` | render project/app templates via `TemplateCommand` |
| `django_visual/ide/open_project.py` | settings loading, urls parsing, INSTALLED_APPS editing, model adding, tree, `project_context` |
| `django_visual/ide/introspect.py` (new) | standalone subprocess script: project models → JSON |
| `django_visual/ide/run.py` | run makemigrations/migrate/runserver, log output |
| `django_visual/ide/views.py` | HTTP endpoints |
| `django_visual/ide/templates/open_project.html` | `.iteritems` → `.items` only |
| `django_visual/ide/tests/` (new pkg; replaces `ide/tests.py`) | `conftest.py`, `test_urls.py`, `test_create_project.py`, `test_open_project_helpers.py`, `test_introspect.py`, `test_views.py`, `test_run.py`, `test_generated_projects.py` |
| `django_visual/conf/project_template_{empty,blog,cms,app}/…` | generated project templates |
| `django_visual/conf/app_template/…` | "Create application" template |

---

### Task 1: Tooling, test harness, Python 3 import-level port, settings and URLs

**Files:**
- Create: `requirements-dev.txt`, `pytest.ini`, `django_visual/ide/tests/__init__.py`, `django_visual/ide/tests/conftest.py`, `django_visual/ide/tests/test_urls.py`
- Delete: `django_visual/ide/tests.py` (empty stub; conflicts with `tests/` package)
- Modify: `requirements.txt`, `runtime.txt`, `django_visual/django_visual/settings.py` (full rewrite), `django_visual/django_visual/urls.py` (full rewrite), `django_visual/ide/urls.py` (full rewrite), `django_visual/ide/views.py` (imports/except only), `django_visual/ide/run.py` (except only), `django_visual/ide/open_project.py` (imports, `.items()`, `project_settings`, `build_project_tree`), `django_visual/ide/apps.py` (header)

**Interfaces:**
- Produces: fixtures `projects_home` → `pathlib.Path` (not yet existing; `settings.PROJECTS_HOME` and `settings.RUN_LOG_FILE` overridden), `make_project(template="blog", name="sample")` → `pathlib.Path` of generated project. Setting `RUN_LOG_FILE` (str path). `open_project.project_settings(project_id, project_home) -> types.ModuleType` (fresh each call). URL names: `create_project`, `open_project`, `run_project`, `stop_project`, `create_application`, `remove_application`, `add_application`, `add_model`, `open_file`, `save_file`, `index`.

- [ ] **Step 1: Packaging files and venv**

`requirements.txt` (replace whole file):
```
Django>=5.2,<6.2
gunicorn
```

`runtime.txt` (replace whole file):
```
python-3.12
```

`requirements-dev.txt`:
```
-r requirements.txt
pytest
pytest-django
tox
tox-uv
```

`pytest.ini`:
```ini
[pytest]
DJANGO_SETTINGS_MODULE = django_visual.settings
pythonpath = django_visual
testpaths = django_visual/ide/tests
markers =
    slow: generates real projects and runs manage.py in subprocesses
filterwarnings =
    error::DeprecationWarning
```

`testpaths` matters: without it pytest would collect `conf/project_template_*/**/tests.py`, which are templates, not tests.

Run:
```bash
uv venv --python 3.12 .venv
uv pip install --python .venv -r requirements-dev.txt "Django>=6.1,<6.2"
.venv/bin/python -c "import django; print(django.get_version())"
```
Expected: `6.1.x`.

- [ ] **Step 2: Test package, fixtures and failing URL tests**

```bash
rm django_visual/ide/tests.py
mkdir -p django_visual/ide/tests
: > django_visual/ide/tests/__init__.py
```

`django_visual/ide/tests/conftest.py`:
```python
import pytest

from ide.create_project import copy_project_template


@pytest.fixture
def projects_home(tmp_path, settings):
    """
    Points PROJECTS_HOME at a fresh, not yet existing temp dir.
    """
    home = tmp_path / "projects"
    settings.PROJECTS_HOME = str(home)
    settings.RUN_LOG_FILE = str(tmp_path / "project_run.log")
    return home


@pytest.fixture
def make_project(projects_home):
    """
    Generates a project from conf/project_template_<template>, returns its dir.
    """
    def make(template="blog", name="sample"):
        copy_project_template(template, name)
        return projects_home / name
    return make
```

`django_visual/ide/tests/test_urls.py`:
```python
import importlib

import pytest
from django.urls import Resolver404, resolve, reverse

IDE_MODULES = [
    "django_visual.urls",
    "ide.urls",
    "ide.views",
    "ide.run",
    "ide.open_project",
    "ide.create_project",
]

PROJECT_ROUTES = [
    "run_project",
    "stop_project",
    "create_application",
    "remove_application",
    "add_application",
    "add_model",
]


@pytest.mark.parametrize("module", IDE_MODULES)
def test_module_imports(module):
    importlib.import_module(module)


@pytest.mark.parametrize("name, kwargs, path", [
    ("create_project", {}, "/ide/create_project/"),
    ("open_project", {"project_id": "demo"}, "/ide/open_project/demo/"),
    ("open_file", {}, "/ide/open_file/"),
    ("save_file", {}, "/ide/save_file/"),
] + [
    (name, {"project_id": "demo"}, "/ide/open_project/demo/{}/".format(name))
    for name in PROJECT_ROUTES
])
def test_reverse_and_resolve(name, kwargs, path):
    assert reverse(name, kwargs=kwargs) == path
    match = resolve(path)
    assert match.url_name == name
    assert match.kwargs == kwargs


@pytest.mark.parametrize("path", ["/", "/ide/welcome/"])
def test_welcome_page_routes(path):
    assert resolve(path).func.__name__ == "index"


@pytest.mark.parametrize("path", [
    "/ide/foo/create_project/",
    "/ide/open_project/demo/extra/",
    "/ide/open_project/../etc/",
])
def test_unanchored_paths_do_not_match(path):
    with pytest.raises(Resolver404):
        resolve(path)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest django_visual/ide/tests/test_urls.py -q`
Expected: FAIL/ERROR — `ImportError: cannot import name 'url' from 'django.conf.urls'` (and `SyntaxError` for `except CommandError, e` in `ide.views`).

- [ ] **Step 4: Strip Python 2 headers from `ide/*.py`**

```bash
python3 - django_visual/ide <<'EOF'
import pathlib, sys
DROP = {"# -*- coding: utf-8 -*-", "from __future__ import unicode_literals"}
for root in sys.argv[1:]:
    root = pathlib.Path(root)
    for p in [*root.rglob("*.py"), *root.rglob("*.py-tpl")]:
        text = p.read_text(encoding="utf-8")
        lines = [l for l in text.splitlines(keepends=True) if l.rstrip("\r\n") not in DROP]
        new = "".join(lines).lstrip("\n")
        if new != text:
            p.write_text(new, encoding="utf-8")
            print("stripped", p)
EOF
```
Expected: prints `stripped …` for `admin.py`, `apps.py`, `create_project.py`, `models.py`, `open_project.py`, `views.py` (`run.py`, `urls.py`, `__init__.py` have no header and are untouched).

- [ ] **Step 5: IDE settings (replace whole `django_visual/django_visual/settings.py`)**

```python
"""
Django settings for django_visual project.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.2/ref/settings/
"""

import os

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOP_DIR = os.path.abspath(os.path.join(BASE_DIR, os.pardir))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 't@-^$$tlw0gav=lp38^l_8g-(xo88&td-(f4*_uc=_6c#pcsa='

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]']

# Application definition

INSTALLED_APPS = [
    'django.contrib.staticfiles',
    'ide',
]

MIDDLEWARE = [
]

ROOT_URLCONF = 'django_visual.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
            ],
        },
    },
]

WSGI_APPLICATION = 'django_visual.wsgi.application'


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_PASSWORD_VALIDATORS = [
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = '/static/'

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
]

PROJECTS_HOME = os.environ.get(
    'DJANGO_VISUAL_PROJECTS_HOME',
    os.path.join(TOP_DIR, 'projects')
)
TEMPLATES_HOME = os.path.join(BASE_DIR, 'conf')

# Output of the project started with "Run" button
RUN_LOG_FILE = os.path.join(TOP_DIR, 'project_run.log')

PROJECTS_TEMPLATES = [
    ("empty", "Empty Project", "New Django project with default configuration. <br />Same as running 'django-admin startproject' from terminal."),
    ("blog", "Blog", "Blog project starts with main page and blog posts list on it. <br />Admin panel included to edit blog entries."),
    ("cms", "Web Site", "Starting point for content site. Includes main page, <br />items list and item detail page. Preconfigured with <br />'Contact Us' and 'About' pages as well as admin panel."),
    ("app", "1-Page Application", "One page web application project. <br />Preconfigured index page template based on Bootstrap 4.")
]

PROJECT_NAMES = ['shiny', 'crazy', 'frog', 'squirrel', 'nut', 'bold',
    'hamster', 'blog', 'site', 'red', 'dead', 'last', 'first', 'super', 'cool',
    'brilliant', 'py', 'web', 'app', 'hello'
]
```

- [ ] **Step 6: URLs**

`django_visual/django_visual/urls.py` (replace whole file):
```python
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
```

`django_visual/ide/urls.py` (replace whole file):
```python
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
```

- [ ] **Step 7: Import-level Python 3 port**

`django_visual/ide/views.py` — replace:
```python
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.core.management.base import CommandError
from django.conf import settings, Settings

from create_project import (
	copy_project_template,
	copy_application_template
)

from open_project import (
```
with:
```python
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.core.management.base import CommandError
from django.conf import settings

from .create_project import (
	copy_project_template,
	copy_application_template
)

from .open_project import (
```
and replace `from run import run_manage` with `from .run import run_manage`, `except CommandError, e:` with `except CommandError as e:`, `except OSError, e:` with `except OSError as e:`.

`django_visual/ide/run.py` — replace `    except Exception, e:` with `    except Exception as e:`.

`django_visual/ide/open_project.py` — replace the import block:
```python
import os
import glob
import sys
import inspect
import imp
from importlib import import_module
import collections

# from django.conf import settings
from django.apps.registry import Apps

from django.apps import apps
```
with:
```python
import collections
import glob
import inspect
import os
import sys
import types

from django.apps import apps
```
replace `for app, models in all_models.iteritems():` with `for app, models in all_models.items():` and `for model_label, model in models.iteritems():` with `for model_label, model in models.items():`.

Replace the whole `project_settings` function with:
```python
def project_settings(project_id, project_home):
	"""
	Loads and returns project settings module.
	settings.py is executed on every call, so edits are always visible.
	"""

	path = os.path.join(project_home, project_id, "settings.py")

	module = types.ModuleType("{}_settings".format(project_id))
	module.__file__ = path

	with open(path, 'r', encoding='utf-8') as f:
		source = f.read()

	exec(compile(source, path, "exec"), module.__dict__)

	return module
```

Replace the whole `build_project_tree` function (mixed tabs/spaces raise `TabError` on Python 3) with:
```python
def build_project_tree(project_id, path):
	"""
	Crawl over project dir and build dirs/files tree
	"""
	def build_tree(path):
		res = {}
		for node in glob.glob(os.path.join(path, "*")):
			label = node.replace(path, '')
			if os.path.isdir(node):
				res[label] = build_tree(node)
			elif not label.lower().endswith(EXCLUDED_EXTENSIONS):
				res[label] = node
		return res

	return {project_id: build_tree(path)}
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `.venv/bin/pytest django_visual/ide/tests/test_urls.py -q`
Expected: all PASS.

Run: `.venv/bin/python -m compileall -q django_visual/ide django_visual/django_visual`
Expected: no output (no syntax/tab errors).

- [ ] **Step 9: Checkpoint (no commit)**

Run: `git status --short` — expect the files above modified/added and `D django_visual/ide/tests.py`. Do **not** commit.

---

### Task 2: Modern project/app templates and `create_project.py`

**Files:**
- Rename (`git mv`): `conf/project_template_cms/project_name/manage.py` → `manage.py-tpl`; `conf/project_template_cms/project_name/project_name/{__init__,settings,urls,wsgi}.py` → `*.py-tpl`
- Modify (all under `django_visual/conf/`): `project_template_{empty,blog,cms,app}/project_name/manage.py-tpl`, `…/project_name/{settings,urls,wsgi}.py-tpl`, `project_template_blog/project_name/blog/{urls,apps}.py`, `project_template_cms/project_name/cms/{urls,apps}.py`, `project_template_app/project_name/app/urls.py`, `app_template/app_name/*.py-tpl`, every `*.py` under `conf/` (header strip)
- Create: `conf/project_template_app/project_name/app/migrations/__init__.py` (empty)
- Modify: `django_visual/ide/create_project.py` (full rewrite)
- Test: `django_visual/ide/tests/test_create_project.py`

**Interfaces:**
- Consumes: `projects_home`, `make_project` fixtures (Task 1).
- Produces: `create_project.template_options(app_or_project: str, **overrides) -> dict`; `copy_project_template(template_name: str, project_name: str) -> None` (creates `PROJECTS_HOME` if missing; raises `CommandError` on invalid/duplicate name or unknown template); `copy_application_template(project_home: str, app_name: str) -> None` (raises `CommandError`). Generated project layout: `<home>/<name>/manage.py`, `<home>/<name>/<name>/settings.py`, etc.

- [ ] **Step 1: Write the failing tests**

`django_visual/ide/tests/test_create_project.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest django_visual/ide/tests/test_create_project.py -q`
Expected: ERROR at import — `ImportError: cannot import name 'template_options'`.

- [ ] **Step 3: Rewrite `django_visual/ide/create_project.py`** (whole file, tabs)

```python
import os

from django.conf import settings
from django.core.management.templates import TemplateCommand
from django.core.management.utils import get_random_secret_key


def template_options(app_or_project, **overrides):
	"""
	Default options of 'django-admin start<app_or_project>', updated with overrides.
	Built from the command's own parser, so options added by newer
	Django versions are always present.
	"""
	parser = TemplateCommand().create_parser(
		'django-admin',
		'start{}'.format(app_or_project)
	)
	options = vars(parser.parse_args(['name']))
	del options['name'], options['directory']
	options.update(overrides)
	return options


def copy_project_template(template_name, project_name):
	"""
	Copies template of new project
	"""
	projects_home = settings.PROJECTS_HOME
	os.makedirs(projects_home, exist_ok=True)

	project_tpl = os.path.join(
		settings.TEMPLATES_HOME,
		'project_template_{}'.format(template_name)
	)

	options = template_options(
		'project',
		verbosity=0,
		template=project_tpl,
		secret_key=get_random_secret_key(),
	)

	TemplateCommand().handle('project', project_name, projects_home, **options)


def copy_application_template(project_home, app_name):
	"""
	Copies template of new application
	"""
	app_tpl = os.path.join(
		settings.TEMPLATES_HOME,
		'app_template'
	)

	options = template_options(
		'app',
		verbosity=0,
		template=app_tpl,
	)

	TemplateCommand().handle('app', app_name, project_home, **options)
```

(`TemplateCommand.handle` validates the name itself; the old explicit `validate_name()` call crashes on Django ≥ 4 because `app_or_project` is only set inside `handle`.)

- [ ] **Step 4: Rename cms project files to `-tpl`**

```bash
cd django_visual/conf/project_template_cms/project_name
git mv manage.py manage.py-tpl
for f in __init__ settings urls wsgi; do git mv project_name/$f.py project_name/$f.py-tpl; done
cd /Users/odubr/Documents/django-visual
```

- [ ] **Step 5: Write `empty` template files**

`django_visual/conf/project_template_empty/project_name/manage.py-tpl`:
```python
#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', '{{ project_name }}.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
```

`django_visual/conf/project_template_empty/project_name/project_name/wsgi.py-tpl`:
```python
"""
WSGI config for {{ project_name }} project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/{{ docs_version }}/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', '{{ project_name }}.settings')

application = get_wsgi_application()
```

`django_visual/conf/project_template_empty/project_name/project_name/settings.py-tpl`:
```python
"""
Django settings for {{ project_name }} project.

Generated by 'django-admin startproject' using Django {{ django_version }}.

For more information on this file, see
https://docs.djangoproject.com/en/{{ docs_version }}/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/{{ docs_version }}/ref/settings/
"""

from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/{{ docs_version }}/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '{{ secret_key }}'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = '{{ project_name }}.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = '{{ project_name }}.wsgi.application'


# Database
# https://docs.djangoproject.com/en/{{ docs_version }}/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/{{ docs_version }}/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/{{ docs_version }}/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/{{ docs_version }}/howto/static-files/

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/{{ docs_version }}/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
```

`django_visual/conf/project_template_empty/project_name/project_name/urls.py-tpl`:
```python
"""
URL configuration for {{ project_name }} project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/{{ docs_version }}/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

urlpatterns = [
    path('admin/', admin.site.urls),
]
```

- [ ] **Step 6: Derive `blog`, `app`, `cms` project files from `empty`**

```bash
python3 - <<'EOF'
from pathlib import Path
conf = Path("django_visual/conf")
empty = conf / "project_template_empty/project_name"
anchor = "    'django.contrib.staticfiles',\n"
settings = (empty / "project_name/settings.py-tpl").read_text()
urls = (empty / "project_name/urls.py-tpl").read_text()

for template in ["blog", "app", "cms"]:
    dest = conf / f"project_template_{template}/project_name"
    for rel in ["manage.py-tpl", "project_name/wsgi.py-tpl"]:
        (dest / rel).write_text((empty / rel).read_text())
    (dest / "project_name/__init__.py-tpl").write_text("")

for template, app in [("blog", "blog"), ("app", "app")]:
    dest = conf / f"project_template_{template}/project_name/project_name"
    (dest / "settings.py-tpl").write_text(settings.replace(anchor, anchor + f"    '{app}',\n", 1))
    (dest / "urls.py-tpl").write_text(urls.replace(
        "from django.urls import path\n\nurlpatterns = [\n    path('admin/', admin.site.urls),\n]\n",
        "from django.urls import include, path\n\nurlpatterns = [\n"
        "    path('admin/', admin.site.urls),\n"
        f"    path('', include('{app}.urls')),\n]\n",
    ))

cms = conf / "project_template_cms/project_name/project_name"
cms_settings = settings.replace(
    anchor,
    anchor + "    'django.contrib.sites',\n    'django.contrib.flatpages',\n    'cms',\n",
    1,
).replace(
    "    'django.middleware.clickjacking.XFrameOptionsMiddleware',\n",
    "    'django.middleware.clickjacking.XFrameOptionsMiddleware',\n"
    "    'django.contrib.flatpages.middleware.FlatpageFallbackMiddleware',\n",
    1,
).replace(
    "ROOT_URLCONF = ",
    "SITE_ID = 1\n\nROOT_URLCONF = ",
    1,
)
(cms / "settings.py-tpl").write_text(cms_settings)
(cms / "urls.py-tpl").write_text(urls.replace(
    "from django.urls import path\n\nurlpatterns = [\n    path('admin/', admin.site.urls),\n]\n",
    "from django.urls import include, path\n\nurlpatterns = [\n"
    "    path('admin/', admin.site.urls),\n"
    "    path('pages/', include('django.contrib.flatpages.urls')),\n"
    "    path('', include('cms.urls')),\n]\n",
))
EOF
grep -L "path('', include" django_visual/conf/project_template_{blog,app,cms}/project_name/project_name/urls.py-tpl
grep -L "'blog',\|'app',\|'cms'," django_visual/conf/project_template_{blog,app,cms}/project_name/project_name/settings.py-tpl
```
Expected: both greps print **nothing** (every urls/settings template got its app line).

- [ ] **Step 7: App-level urls and apps**

`django_visual/conf/project_template_blog/project_name/blog/urls.py` and `django_visual/conf/project_template_app/project_name/app/urls.py` (same content in both):
```python
from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
]
```

`django_visual/conf/project_template_cms/project_name/cms/urls.py`:
```python
from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('item/<int:item_id>/', views.item_detail, name='item_detail'),
    path('items/', views.item_list, name='item_list'),
]
```

`django_visual/conf/project_template_blog/project_name/blog/apps.py`:
```python
from django.apps import AppConfig


class BlogConfig(AppConfig):
    # shipped migrations/0001_initial.py uses AutoField
    default_auto_field = 'django.db.models.AutoField'
    name = 'blog'
```

`django_visual/conf/project_template_cms/project_name/cms/apps.py`:
```python
from django.apps import AppConfig


class CmsConfig(AppConfig):
    # shipped migrations/0001_initial.py uses AutoField
    default_auto_field = 'django.db.models.AutoField'
    name = 'cms'
```

```bash
mkdir -p django_visual/conf/project_template_app/project_name/app/migrations
: > django_visual/conf/project_template_app/project_name/app/migrations/__init__.py
```

- [ ] **Step 8: App template (`conf/app_template/app_name/`)**

```bash
sed -i '' 's/^{{ unicode_literals }}//' django_visual/conf/app_template/app_name/*.py-tpl
```

`django_visual/conf/app_template/app_name/apps.py-tpl`:
```python
from django.apps import AppConfig


class {{ camel_case_app_name }}Config(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = '{{ app_name }}'
```

Run: `grep -rn "unicode_literals" django_visual/conf/app_template` → expect no output.

- [ ] **Step 9: Strip Python 2 headers from `conf/`**

```bash
python3 - django_visual/conf <<'EOF'
import pathlib, sys
DROP = {"# -*- coding: utf-8 -*-", "from __future__ import unicode_literals"}
for root in sys.argv[1:]:
    root = pathlib.Path(root)
    for p in [*root.rglob("*.py"), *root.rglob("*.py-tpl")]:
        text = p.read_text(encoding="utf-8")
        lines = [l for l in text.splitlines(keepends=True) if l.rstrip("\r\n") not in DROP]
        new = "".join(lines).lstrip("\n")
        if new != text:
            p.write_text(new, encoding="utf-8")
            print("stripped", p)
EOF
grep -rln "unicode_literals\|coding: utf-8\|django.conf.urls\|USE_L10N" django_visual/conf
```
Expected: last grep prints nothing.

- [ ] **Step 10: Run tests to verify they pass**

Run: `.venv/bin/pytest django_visual/ide/tests/test_create_project.py -q`
Expected: all PASS.

- [ ] **Step 11: Checkpoint (no commit)** — `git status --short` shows cms renames as `R`, others `M`/`??`. Do not commit.

---

### Task 3: `open_project` helpers (settings, urls, INSTALLED_APPS, models, tree)

**Files:**
- Modify: `django_visual/ide/open_project.py` (`EXCLUDED_*` constants, `parse_urls`, `edit_installed_apps`, `application_add_model`, `build_project_tree`)
- Test: `django_visual/ide/tests/test_open_project_helpers.py`

**Interfaces:**
- Consumes: `make_project`, `projects_home` (Task 1), `project_settings` (Task 1).
- Produces: `parse_urls(source: str) -> list[str]` (raw lines incl. newline, from inside `urlpatterns = [ … ]`, containing `path(`/`re_path(`/`url(`); `edit_installed_apps(project_id, project_home, new_installed_apps: list[str]) -> "ok"`; `application_add_model(project_id, project_home, data: QueryDict) -> None`; `build_project_tree(project_id, path) -> {project_id: {"/<name>": path | {...}}}`; `EXCLUDED_DIRS = ('__pycache__',)`.

- [ ] **Step 1: Write the failing tests**

`django_visual/ide/tests/test_open_project_helpers.py`:
```python
import sys

from django.http import QueryDict

from ide.open_project import (
    application_add_model,
    build_project_tree,
    edit_installed_apps,
    parse_urls,
    project_settings,
)


def write_settings(tmp_path, text):
    """
    Minimal project 'proj' with given settings.py, returns project_home
    """
    package = tmp_path / "proj" / "proj"
    package.mkdir(parents=True)
    (package / "settings.py").write_text(text)
    return str(tmp_path / "proj")


def model_form(**fields):
    data = QueryDict(mutable=True)
    for key, value in fields.items():
        data.setlist(key, value if isinstance(value, list) else [value])
    return data


# project_settings

def test_project_settings_reflects_edits(tmp_path):
    home = write_settings(tmp_path, "DEBUG = True\nAPPS = ['a']\n")
    assert project_settings("proj", home).DEBUG is True
    (tmp_path / "proj" / "proj" / "settings.py").write_text("DEBUG = False\nAPPS = ['a']\n")
    assert project_settings("proj", home).DEBUG is False
    assert "proj_settings" not in sys.modules


def test_project_settings_sets_file(make_project):
    root = make_project("blog")
    module = project_settings("sample", str(root))
    assert str(module.BASE_DIR) == str(root)
    assert "blog" in module.INSTALLED_APPS


# parse_urls

def test_parse_urls_generated_project(make_project):
    root = make_project("blog")
    lines = [l.strip() for l in parse_urls(str(root / "sample" / "urls.py"))]
    assert lines == [
        "path('admin/', admin.site.urls),",
        "path('', include('blog.urls')),",
    ]


def test_parse_urls_all_styles_only_inside_urlpatterns(tmp_path):
    source = tmp_path / "urls.py"
    source.write_text(
        '"""\n    path(\'docs/\', views.docs)\n"""\n'
        "urlpatterns = [\n"
        "    path('a/', views.a),\n"
        "    re_path(r'^b/$', views.b),\n"
        "    url(r'^c/$', views.c),\n"
        "    # comment\n"
        "]\n"
        "extra = path('d/', views.d)\n"
    )
    lines = [l.strip() for l in parse_urls(str(source))]
    assert lines == [
        "path('a/', views.a),",
        "re_path(r'^b/$', views.b),",
        "url(r'^c/$', views.c),",
    ]


# edit_installed_apps

def test_edit_installed_apps_round_trip(make_project):
    root = make_project("blog")
    path = root / "sample" / "settings.py"
    original = path.read_text()
    apps = list(project_settings("sample", str(root)).INSTALLED_APPS) + ["shop"]

    assert edit_installed_apps("sample", str(root), apps) == "ok"

    assert list(project_settings("sample", str(root)).INSTALLED_APPS) == apps
    edited = path.read_text()
    assert edited[:edited.index("INSTALLED_APPS")] == original[:original.index("INSTALLED_APPS")]
    assert edited[edited.index("MIDDLEWARE"):] == original[original.index("MIDDLEWARE"):]


def test_edit_installed_apps_single_line(tmp_path):
    home = write_settings(tmp_path, "DEBUG = True\nINSTALLED_APPS = []\nTAIL = 1\n")
    edit_installed_apps("proj", home, ["a", "b"])
    module = project_settings("proj", home)
    assert module.INSTALLED_APPS == ["a", "b"]
    assert module.DEBUG is True and module.TAIL == 1


def test_edit_installed_apps_single_line_with_items(tmp_path):
    home = write_settings(tmp_path, "INSTALLED_APPS = ['x', 'y']\nTAIL = 1\n")
    edit_installed_apps("proj", home, ["x"])
    module = project_settings("proj", home)
    assert module.INSTALLED_APPS == ["x"]
    assert module.TAIL == 1


# application_add_model

def test_application_add_model_with_fields(make_project):
    root = make_project("blog")
    application_add_model("sample", str(root), model_form(
        application="blog",
        new_model_name="Comment",
        new_model_field_id=["body", "post"],
        new_model_field_type=["TextField", "ForeignKey"],
        new_model_field_options=["", "BlogPost, on_delete=models.CASCADE"],
    ))
    models_py = (root / "blog" / "models.py").read_text()
    assert "\nclass Comment(models.Model):" in models_py
    assert "\n    body = models.TextField()" in models_py
    assert "\n    post = models.ForeignKey(BlogPost, on_delete=models.CASCADE)" in models_py
    compile(models_py, "models.py", "exec")
    assert "admin.site.register(Comment)" in (root / "blog" / "admin.py").read_text()


def test_application_add_model_without_fields(make_project):
    root = make_project("blog")
    application_add_model("sample", str(root), model_form(application="blog", new_model_name="Tag"))
    assert "class Tag(models.Model):\n    pass\n" in (root / "blog" / "models.py").read_text()


def test_application_add_model_requires_application(make_project):
    root = make_project("blog")
    before = (root / "blog" / "models.py").read_text()
    application_add_model("sample", str(root), model_form(new_model_name="Tag"))
    assert (root / "blog" / "models.py").read_text() == before


# build_project_tree

def test_build_project_tree_skips_compiled_and_pycache(tmp_path):
    (tmp_path / "pkg" / "__pycache__").mkdir(parents=True)
    (tmp_path / "pkg" / "__pycache__" / "mod.cpython-312.pyc").write_text("")
    (tmp_path / "pkg" / "mod.py").write_text("")
    (tmp_path / "manage.py").write_text("")
    (tmp_path / "old.pyc").write_text("")

    tree = build_project_tree("sample", str(tmp_path))

    assert tree == {"sample": {
        "/manage.py": str(tmp_path / "manage.py"),
        "/pkg": {"/mod.py": str(tmp_path / "pkg" / "mod.py")},
    }}
    assert list(tree["sample"]) == ["/manage.py", "/pkg"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest django_visual/ide/tests/test_open_project_helpers.py -q`
Expected: FAIL — `test_parse_urls_*` (returns `[]` for `path(` lines), `test_edit_installed_apps_single_line*` (list unchanged), `test_build_project_tree_skips_compiled_and_pycache` (`/__pycache__` present). Others may already pass.

- [ ] **Step 3: Implement**

In `django_visual/ide/open_project.py` replace:
```python
EXCLUDED_EXTENSIONS = ('.pyc', '.pyo', '.pyd', '.py.class', '.DS_Store')
```
with:
```python
EXCLUDED_EXTENSIONS = ('.pyc', '.pyo', '.pyd', '.py.class', '.DS_Store')
EXCLUDED_DIRS = ('__pycache__',)
URL_FUNCTIONS = ('path(', 'url(')  # 'path(' also matches re_path(
```

Replace the whole `parse_urls` function with:
```python
def parse_urls(source):
	"""
	Parses project/application urls.py
	Extracts path() / re_path() / url() entries
	"""

	START_MARKER = "urlpatterns = ["
	END_MARKER = "]"

	grep_urls = False
	res = []

	with open(source, 'r', encoding='utf-8') as f:
		for line in f:
			if grep_urls:
				if any(func in line for func in URL_FUNCTIONS):
					res.append(line)

			if START_MARKER in line:
				grep_urls = True

			if END_MARKER in line:
				grep_urls = False

	return res
```

Replace the whole `edit_installed_apps` function with:
```python
def edit_installed_apps(project_id, project_home, new_installed_apps):
	"""
	Replaces INSTALLED_APPS in project settings.py with new list
	"""

	# TODO: implement it with ast / nodes transforms

	START_MARKER = "INSTALLED_APPS = ["
	END_MARKER = "]"

	path = os.path.join(
		project_home,
		project_id,
		"settings.py"
	)

	is_apps = False
	is_changed = False
	new_source = []

	with open(path, 'r', encoding='utf-8') as f:
		for line in f:
			if not is_changed and START_MARKER in line:
				new_source.append("{}\n".format(START_MARKER))
				for app in new_installed_apps:
					new_source.append("    '{}',\n".format(app))
				new_source.append("{}\n".format(END_MARKER))
				is_changed = True
				# list may be closed on the same line: INSTALLED_APPS = []
				is_apps = END_MARKER not in line.split(START_MARKER, 1)[1]
				continue

			if is_apps:
				if END_MARKER in line:
					is_apps = False
				continue

			new_source.append(line)

	with open(path, 'w', encoding='utf-8') as f:
		f.write("".join(new_source))

	return "ok"
```

In `application_add_model`: change `with open(path, "a") as f:` to `with open(path, "a", encoding="utf-8") as f:` and `with open(path_admin, "a") as f:` to `with open(path_admin, "a", encoding="utf-8") as f:`; delete the trailing `	# import pdb; pdb.set_trace()` line.

Replace the whole `build_project_tree` function with:
```python
def build_project_tree(project_id, path):
	"""
	Crawl over project dir and build dirs/files tree
	"""
	def build_tree(path):
		res = {}
		for node in sorted(glob.glob(os.path.join(path, "*"))):
			label = node.replace(path, '')
			if os.path.isdir(node):
				if os.path.basename(node) not in EXCLUDED_DIRS:
					res[label] = build_tree(node)
			elif not label.lower().endswith(EXCLUDED_EXTENSIONS):
				res[label] = node
		return res

	return {project_id: build_tree(path)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest django_visual/ide/tests/test_open_project_helpers.py -q`
Expected: all PASS.

- [ ] **Step 5: Checkpoint (no commit)** — `git status --short`.

---

### Task 4: Subprocess introspection (`introspect.py`, `project_context`)

**Files:**
- Create: `django_visual/ide/introspect.py`
- Modify: `django_visual/ide/open_project.py` (imports, new `introspect_project`, rewrite `project_context`)
- Test: `django_visual/ide/tests/test_introspect.py`

**Interfaces:**
- Consumes: `make_project`, `project_settings`, `edit_installed_apps`, `application_add_model` (Tasks 1–3), `copy_application_template` (Task 2).
- Produces: `introspect_project(project_id: str, project_home: str) -> tuple[dict[str, list[dict]], str]` — `({<INSTALLED_APPS entry>: [{"name", "path", "rel_path", "fields": [{"name", "class"}]}]}, error_str)`; `project_context(project_id, project_home) -> dict` with keys `project_id, project_home, project_apps (dict entry -> list), project_databases, project_settings_file, project_urls, project_urls_file, project_tree, has_apps_error`.

- [ ] **Step 1: Write the failing tests**

`django_visual/ide/tests/test_introspect.py`:
```python
import os

from django.apps import apps as ide_apps
from django.http import QueryDict

from ide.create_project import copy_application_template
from ide.open_project import (
    application_add_model,
    edit_installed_apps,
    introspect_project,
    project_context,
    project_settings,
)


def add_model(root, application, name):
    data = QueryDict(mutable=True)
    data["application"] = application
    data["new_model_name"] = name
    application_add_model("sample", str(root), data)


def install(root, app):
    apps = list(project_settings("sample", str(root)).INSTALLED_APPS) + [app]
    edit_installed_apps("sample", str(root), apps)


def model_names(context, app):
    return sorted(m["name"] for m in context["project_apps"][app])


def test_blog_project_context(make_project):
    root = make_project("blog")
    context = project_context("sample", str(root))

    assert context["has_apps_error"] == ""
    assert list(context["project_apps"]) == list(project_settings("sample", str(root)).INSTALLED_APPS)
    assert context["project_apps"]["django.contrib.auth"] == []

    [model] = context["project_apps"]["blog"]
    assert model["name"] == "BlogPost"
    assert model["path"] == str(root / "blog" / "models.py")
    assert model["rel_path"] == os.sep + os.path.join("blog", "models.py")
    assert {"name": "id", "class": "AutoField"} in model["fields"]
    assert {"name": "title", "class": "CharField"} in model["fields"]
    assert {"name": "text", "class": "TextField"} in model["fields"]

    assert context["project_id"] == "sample"
    assert context["project_home"] == str(root)
    assert context["project_settings_file"] == str(root / "sample" / "settings.py")
    assert context["project_urls_file"] == str(root / "sample" / "urls.py")
    assert len(context["project_urls"]) == 2
    assert context["project_databases"]["default"]["ENGINE"] == "django.db.backends.sqlite3"
    assert "/manage.py" in context["project_tree"]["sample"]


def test_introspect_project_shape(make_project):
    root = make_project("cms")
    models_by_app, error = introspect_project("sample", str(root))
    assert error == ""
    assert [m["name"] for m in models_by_app["cms"]] == ["Item"]
    assert models_by_app["django.contrib.flatpages"] == []


def test_edits_are_reflected_on_reopen(make_project):
    root = make_project("blog")
    assert model_names(project_context("sample", str(root)), "blog") == ["BlogPost"]
    add_model(root, "blog", "Tag")
    assert model_names(project_context("sample", str(root)), "blog") == ["BlogPost", "Tag"]


def test_missing_app_reports_error(make_project):
    root = make_project("blog")
    install(root, "missing_app")
    context = project_context("sample", str(root))
    assert "missing_app" in context["has_apps_error"]
    assert context["project_apps"]["missing_app"] == []
    assert context["project_apps"]["blog"] == []


def test_syntax_error_reports_error(make_project):
    root = make_project("blog")
    with open(root / "blog" / "models.py", "a") as f:
        f.write("\ndef broken(:\n")
    context = project_context("sample", str(root))
    assert context["has_apps_error"].startswith("SyntaxError")


def test_app_named_like_ide_module(make_project):
    root = make_project("empty")
    copy_application_template(str(root), "views")
    install(root, "views")
    add_model(root, "views", "Page")
    context = project_context("sample", str(root))
    assert context["has_apps_error"] == ""
    assert model_names(context, "views") == ["Page"]


def test_ide_app_registry_untouched(make_project):
    root = make_project("blog")
    before = [c.label for c in ide_apps.get_app_configs()]
    project_context("sample", str(root))
    assert [c.label for c in ide_apps.get_app_configs()] == before
    assert not ide_apps.is_installed("blog")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest django_visual/ide/tests/test_introspect.py -q`
Expected: ERROR at import — `ImportError: cannot import name 'introspect_project'`.

- [ ] **Step 3: Create `django_visual/ide/introspect.py`** (tabs)

```python
"""
Lists models of a Django project as JSON on stdout.

Runs in a subprocess (see open_project.introspect_project), so the project is
imported with its own settings, isolated from the IDE process:

    DJANGO_SETTINGS_MODULE=<project_id>.settings python -P introspect.py <project_home>

Output: {"apps": {<INSTALLED_APPS entry>: [<model>, ...]}, "error": ""}
Only apps located inside <project_home> report their models.
"""

import inspect
import json
import os
import sys


def describe_field(field):
	get_type = getattr(field, "get_internal_type", None)
	return {
		"name": field.name,
		"class": get_type() if get_type else type(field).__name__,
	}


def describe_model(model, project_home):
	path = inspect.getsourcefile(model) or ""
	return {
		"name": model.__name__,
		"path": path,
		"rel_path": path.replace(project_home, ""),
		"fields": [describe_field(f) for f in model._meta.get_fields(include_parents=False)],
	}


def is_project_app(app_config, real_home):
	app_path = os.path.realpath(app_config.path)
	return os.path.commonpath([app_path, real_home]) == real_home


def main(project_home):
	real_home = os.path.realpath(project_home)
	result = {"apps": {}, "error": ""}

	try:
		import django
		from django.apps import apps
		from django.conf import settings

		django.setup()

		# app configs are registered in INSTALLED_APPS order, one per entry
		for entry, app_config in zip(settings.INSTALLED_APPS, apps.get_app_configs()):
			models = []
			if is_project_app(app_config, real_home):
				models = [describe_model(m, project_home) for m in app_config.get_models()]
			result["apps"][entry] = models
	except Exception as e:
		result["error"] = "{}: {}".format(type(e).__name__, e)

	print(json.dumps(result))


if __name__ == "__main__":
	main(sys.argv[1])
```

- [ ] **Step 4: Wire it into `open_project.py`**

Replace the import block:
```python
import collections
import glob
import inspect
import os
import sys
import types

from django.apps import apps
```
with:
```python
import glob
import json
import os
import subprocess
import sys
import types
```

After the `URL_FUNCTIONS` line add:
```python

INTROSPECT_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "introspect.py")
INTROSPECT_TIMEOUT = 60
```

Replace the whole `project_context` function (from `def project_context` through its `return context`) with:
```python
def project_context(project_id, project_home):
	"""
	Parses Django project
	"""

	pr_settings = project_settings(project_id, project_home)
	models_by_app, has_apps_error = introspect_project(project_id, project_home)

	project_apps = {
		app: models_by_app.get(app, [])
		for app in pr_settings.INSTALLED_APPS
	}

	project_settings_file = os.path.join(project_home, project_id, "settings.py")
	project_urls_file = os.path.join(project_home, project_id, "urls.py")
	project_urls = parse_urls(project_urls_file)

	project_tree = build_project_tree(project_id, project_home)

	context = {
		"project_id": project_id,
		"project_home": project_home,
		"project_apps": project_apps,
		"project_databases": pr_settings.DATABASES,
		"project_settings_file": project_settings_file,
		"project_urls": project_urls,
		"project_urls_file": project_urls_file,
		"project_tree": project_tree,
		"has_apps_error": has_apps_error
	}

	return context


def introspect_project(project_id, project_home):
	"""
	Lists project models by INSTALLED_APPS entry.
	Runs introspect.py in a subprocess with project's own settings,
	so project code never gets imported into the IDE process.
	Returns (models_by_app, error) tuple.
	"""

	env = dict(os.environ)
	env["DJANGO_SETTINGS_MODULE"] = "{}.settings".format(project_id)
	env["PYTHONPATH"] = os.pathsep.join(
		p for p in (project_home, env.get("PYTHONPATH")) if p
	)

	# -P: keep the IDE's own ide/ dir off project's sys.path
	command = [sys.executable, "-P", INTROSPECT_SCRIPT, project_home]

	try:
		proc = subprocess.run(
			command,
			cwd=project_home,
			env=env,
			capture_output=True,
			text=True,
			timeout=INTROSPECT_TIMEOUT
		)
	except subprocess.TimeoutExpired:
		return {}, "Project introspection timed out after {} seconds".format(INTROSPECT_TIMEOUT)

	# project code may print to stdout too, result is the last line
	lines = proc.stdout.strip().splitlines()
	try:
		data = json.loads(lines[-1])
	except (IndexError, ValueError):
		errors = proc.stderr.strip().splitlines()
		if errors:
			return {}, errors[-1]
		return {}, "Project introspection failed with exit code {}".format(proc.returncode)

	return data["apps"], data["error"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest django_visual/ide/tests/test_introspect.py django_visual/ide/tests/test_open_project_helpers.py -q`
Expected: all PASS.

- [ ] **Step 6: Checkpoint (no commit)** — `git status --short`.

---

### Task 5: Views, run worker, `open_project.html`

**Files:**
- Modify: `django_visual/ide/views.py` (full rewrite), `django_visual/ide/run.py` (full rewrite), `django_visual/ide/templates/open_project.html` (`.iteritems` → `.items`)
- Test: `django_visual/ide/tests/test_views.py`, `django_visual/ide/tests/test_run.py`

**Interfaces:**
- Consumes: everything from Tasks 1–4; setting `RUN_LOG_FILE`.
- Produces: `run.worker(project_id: str, project_home: str, log_file: str) -> None`; `run.run_manage(project_id, project_home) -> int` (pid); `views.installed_apps(project_id, project_home) -> list[str]`.

- [ ] **Step 1: Write the failing tests**

`django_visual/ide/tests/test_views.py`:
```python
import subprocess
import sys

import pytest

from ide import views
from ide.open_project import project_settings

PROJECT_URL = "/ide/open_project/sample/"


@pytest.fixture
def blog(make_project):
    return make_project("blog")


def installed(root):
    return list(project_settings("sample", str(root)).INSTALLED_APPS)


# welcome

def test_index_creates_home_and_lists_projects(client, projects_home):
    response = client.get("/")
    assert response.status_code == 200
    assert projects_home.is_dir()
    assert response.context["projects"] == []

    (projects_home / "beta").mkdir()
    (projects_home / "alpha").mkdir()
    (projects_home / "notes.txt").write_text("not a project")
    response = client.get("/ide/welcome/")
    assert response.context["projects"] == ["alpha", "beta"]


# create_project

def test_create_project_get(client, projects_home):
    response = client.get("/ide/create_project/", {"template": "cms"})
    assert response.status_code == 200
    assert response.context["template"] == "cms"
    assert response.context["error"] == ""
    assert "_" in response.context["title"]


def test_create_project_post_redirects(client, projects_home):
    response = client.post("/ide/create_project/", {"template": "blog", "title": "my_blog"})
    assert response.status_code == 302
    assert response["Location"] == "/ide/open_project/my_blog/"
    assert (projects_home / "my_blog" / "manage.py").is_file()


@pytest.mark.parametrize("data, message", [
    ({"template": "blog", "title": "bad-name"}, "not a valid"),
    ({"template": "nope", "title": "fine_name"}, "couldn't handle"),
])
def test_create_project_errors(client, projects_home, data, message):
    response = client.post("/ide/create_project/", data)
    assert response.status_code == 200
    assert message in response.context["error"]
    assert response.context["title"] == data["title"]


def test_create_project_existing_name(client, blog):
    settings_py = blog / "sample" / "settings.py"
    original = settings_py.read_text()
    response = client.post("/ide/create_project/", {"template": "blog", "title": "sample"})
    assert response.status_code == 200
    assert "already exists" in response.context["error"]
    assert settings_py.read_text() == original


# open_project

def test_open_project(client, blog):
    response = client.get(PROJECT_URL)
    assert response.status_code == 200
    assert response.context["project_id"] == "sample"
    assert [m["name"] for m in response.context["project_apps"]["blog"]] == ["BlogPost"]
    content = response.content.decode()
    assert "BlogPost" in content
    assert "[sample]<>->[blog]" in content  # apps loop rendered (.items, not .iteritems)
    assert "var project_apps = [" in content and "'blog', " in content


def test_open_project_shows_apps_error(client, blog):
    (blog / "blog" / "models.py").write_text("def broken(:\n")
    response = client.get(PROJECT_URL)
    assert response.status_code == 200
    assert "Error in INSTALLED_APPS" in response.content.decode()


def test_open_missing_project_404(client, projects_home):
    assert client.get("/ide/open_project/ghost/").status_code == 404


# applications

@pytest.mark.parametrize("endpoint", ["create_application", "add_application", "remove_application"])
def test_application_endpoints_get_help(client, blog, endpoint):
    response = client.get(PROJECT_URL + endpoint + "/")
    assert response.status_code == 200
    assert b"POST 'app_name'" in response.content


def test_create_application(client, blog):
    response = client.post(PROJECT_URL + "create_application/", {"app_name": "shop"})
    assert response.content == b"OK"
    assert (blog / "shop" / "apps.py").is_file()
    assert installed(blog)[-1] == "shop"


@pytest.mark.parametrize("data", [{"app_name": "bad-name"}, {}])
def test_create_application_invalid_name(client, blog, data):
    before = installed(blog)
    response = client.post(PROJECT_URL + "create_application/", data)
    assert response.status_code == 400
    assert installed(blog) == before


def test_add_application_is_idempotent(client, blog):
    assert client.post(PROJECT_URL + "add_application/", {"app_name": "blog"}).content == b"OK"
    assert installed(blog).count("blog") == 1

    assert client.post(PROJECT_URL + "add_application/", {"app_name": "django.contrib.sites"}).content == b"OK"
    assert installed(blog)[-1] == "django.contrib.sites"

    before = installed(blog)
    assert client.post(PROJECT_URL + "add_application/", {}).content == b"OK"
    assert installed(blog) == before


def test_remove_application_is_idempotent(client, blog):
    assert client.post(PROJECT_URL + "remove_application/", {"app_name": "blog"}).content == b"OK"
    assert "blog" not in installed(blog)
    response = client.post(PROJECT_URL + "remove_application/", {"app_name": "blog"})
    assert response.status_code == 200
    assert response.content == b"OK"


def test_add_model_redirects(client, blog):
    response = client.post(PROJECT_URL + "add_model/", {"application": "blog", "new_model_name": "Tag"})
    assert response.status_code == 302
    assert response["Location"] == PROJECT_URL
    assert "class Tag(models.Model):" in (blog / "blog" / "models.py").read_text()


# files

def test_save_and_open_utf8_round_trip(client, tmp_path):
    target = tmp_path / "notes.py"
    text = "# café ✓\nprint('ok')\n"
    response = client.post("/ide/save_file/", {"path": str(target), "content": text})
    assert response.content == b"File saved"
    assert target.read_bytes() == text.encode("utf-8")

    response = client.get("/ide/open_file/", {"path": str(target)})
    assert response.content.decode("utf-8") == text


def test_open_binary_file(client, blog):
    database = blog / "db.sqlite3"
    response = client.get("/ide/open_file/", {"path": str(database)})
    assert response.status_code == 200
    assert response.content == database.read_bytes()


def test_open_file_without_path(client):
    assert client.get("/ide/open_file/").content == b""


def test_save_file_get(client):
    assert b"POST 'path'" in client.get("/ide/save_file/").content


# run / stop

def test_run_project_post_starts_worker(client, blog, monkeypatch):
    calls = []
    monkeypatch.setattr(views, "run_manage", lambda *args: calls.append(args) or 4321)
    response = client.post(PROJECT_URL + "run_project/")
    assert response.content == b"4321"
    assert calls == [("sample", str(blog))]


def test_run_project_get_returns_log(client, blog, settings, tmp_path):
    assert client.get(PROJECT_URL + "run_project/").content == b""
    assert client.get(PROJECT_URL + "run_project/", {"pid": "1"}).content == b""

    (tmp_path / "project_run.log").write_text("Starting…\n", encoding="utf-8")
    assert settings.RUN_LOG_FILE == str(tmp_path / "project_run.log")
    response = client.get(PROJECT_URL + "run_project/", {"pid": "1"})
    assert response.content.decode("utf-8") == "Starting…\n"


def test_stop_project_kills_process(client, blog):
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    response = client.post(PROJECT_URL + "stop_project/", {"pid": str(proc.pid)})
    assert response.content == b"OK"
    assert proc.wait(timeout=5) == -9


def test_stop_project_unknown_pid(client, blog):
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    response = client.post(PROJECT_URL + "stop_project/", {"pid": str(proc.pid)})
    assert b"No such process" in response.content


def test_stop_project_without_pid(client, blog):
    assert client.post(PROJECT_URL + "stop_project/").content == b""
```

`django_visual/ide/tests/test_run.py`:
```python
import sys

from ide import run


class FakePopen:
    """
    Records commands; each call returns next (output lines, exit code)
    """
    def __init__(self, results):
        self.results = iter(results)
        self.calls = []

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        lines, code = next(self.results)
        proc = type("Proc", (), {})()
        proc.stdout = iter(lines)
        proc.wait = lambda: code
        return proc


def test_worker_runs_commands_in_order(monkeypatch, tmp_path):
    fake = FakePopen([(["No changes detected\n"], 0), (["Applied\n"], 0), (["Quit with CONTROL-C\n"], 0)])
    monkeypatch.setattr(run.subprocess, "Popen", fake)
    log = tmp_path / "run.log"

    run.worker("sample", "/projects/sample", str(log))

    commands = [command for command, _ in fake.calls]
    assert [c[2] for c in commands] == ["makemigrations", "migrate", "runserver"]
    for command, kwargs in fake.calls:
        assert command[:2] == [sys.executable, "/projects/sample/manage.py"]
        assert command[command.index("--settings") + 1] == "sample.settings"
        assert kwargs["cwd"] == "/projects/sample"
        assert kwargs["stderr"] is run.subprocess.STDOUT
        assert kwargs["text"] is True
    assert commands[2][-1] == "8001"

    text = log.read_text()
    assert text.startswith("Starting development server at http://127.0.0.1:8001/\n")
    assert "No changes detected\nApplied\nQuit with CONTROL-C\n" in text
    assert text.rstrip().endswith("Development server stopped")


def test_worker_stops_after_failed_step(monkeypatch, tmp_path):
    fake = FakePopen([(["SystemCheckError: boom\n"], 1)])
    monkeypatch.setattr(run.subprocess, "Popen", fake)
    log = tmp_path / "run.log"

    run.worker("sample", "/projects/sample", str(log))

    assert len(fake.calls) == 1
    assert "SystemCheckError: boom" in log.read_text()


def test_worker_logs_start_failure(monkeypatch, tmp_path):
    def broken_popen(command, **kwargs):
        raise OSError("no python")
    monkeypatch.setattr(run.subprocess, "Popen", broken_popen)
    log = tmp_path / "run.log"

    run.worker("sample", "/projects/sample", str(log))

    assert "no python" in log.read_text()


def test_run_manage_starts_worker_process(monkeypatch, settings, tmp_path):
    settings.RUN_LOG_FILE = str(tmp_path / "run.log")
    started = {}

    class FakeProcess:
        pid = 777

        def __init__(self, target, args):
            started.update(target=target, args=args)

        def start(self):
            started["started"] = True

    monkeypatch.setattr(run, "Process", FakeProcess)

    assert run.run_manage("sample", "/p/sample") == 777
    assert started == {
        "target": run.worker,
        "args": ("sample", "/p/sample", settings.RUN_LOG_FILE),
        "started": True,
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest django_visual/ide/tests/test_views.py django_visual/ide/tests/test_run.py -q`
Expected: FAIL — e.g. `test_open_project` (`[sample]<>->[blog]` missing), `test_open_missing_project_404` (500/FileNotFoundError), `test_add_application_is_idempotent` (duplicate), `test_remove_application_is_idempotent` (ValueError), `test_open_binary_file` (UnicodeDecodeError), `test_run_project_get_returns_log` (view returned None), all `test_run.py` (worker signature).

- [ ] **Step 3: Template fix**

```bash
sed -i '' 's/\.iteritems/.items/g' django_visual/ide/templates/open_project.html
grep -c "iteritems" django_visual/ide/templates/open_project.html
```
Expected: `0`.

- [ ] **Step 4: Rewrite `django_visual/ide/views.py`** (whole file, tabs)

```python
import os
from os.path import join, isdir
import random

from django.shortcuts import render, redirect
from django.http import Http404, HttpResponse
from django.core.management.base import CommandError
from django.conf import settings

from .create_project import (
	copy_project_template,
	copy_application_template
)

from .open_project import (
	project_context,
	project_settings,
	edit_installed_apps,
	application_add_model,
)

from .run import run_manage


def installed_apps(project_id, project_home):
	"""
	Current INSTALLED_APPS of project as a list
	"""
	return list(project_settings(project_id, project_home).INSTALLED_APPS)


def index(request):
	"""
	IDE welcome
	Open or Create Project
	"""

	projects_home = settings.PROJECTS_HOME
	# Projects dir may not exist, let create it
	os.makedirs(projects_home, exist_ok=True)

	projects = sorted(
		node for node in os.listdir(projects_home)
		if isdir(join(projects_home, node))
	)

	context = {
		"projects": projects,
		"templates": settings.PROJECTS_TEMPLATES
	}
	return render(request, 'index.html', context)


def create_project(request):
	"""
	Create new Django project
	"""

	names = settings.PROJECT_NAMES
	projects_home = settings.PROJECTS_HOME

	context = {
		"template": request.GET.get("template", "blog"),
		"title": random.choice(names) + "_" + random.choice(names),
		"projects_home": projects_home,
		'error': ''
	}

	if request.method == "POST":
		template = request.POST.get("template")
		title = request.POST.get("title")

		try:
			copy_project_template(template, title)
		except CommandError as e:
			context['title'] = title
			context['error'] = str(e)
			return render(request, 'create_project.html', context)

		return redirect('open_project', project_id=title)

	return render(request, 'create_project.html', context)


def open_project(request, project_id):
	"""
	Load project structure into IDE.
	"""
	project_home = join(settings.PROJECTS_HOME, project_id)

	if not isdir(project_home):
		raise Http404("Project '{}' not found".format(project_id))

	context = project_context(project_id, project_home)

	context["project_id"] = project_id

	return render(request, 'open_project.html', context)


def create_application(request, project_id):
	"""
	Creates new application for given project
	"""
	project_home = join(settings.PROJECTS_HOME, project_id)

	if request.method == "POST":
		app_name = request.POST.get("app_name")

		try:
			copy_application_template(project_home, app_name)
		except CommandError as e:
			return HttpResponse(str(e), status=400)

		apps = installed_apps(project_id, project_home)
		if app_name not in apps:
			apps.append(app_name)
			edit_installed_apps(project_id, project_home, apps)

		return HttpResponse("OK")
	else:
		return HttpResponse("POST 'app_name' of new application to create")


def add_application(request, project_id):
	"""
	Add existing application to INSTALLED_APPS
	"""
	project_home = join(settings.PROJECTS_HOME, project_id)

	if request.method == "POST":
		app_name = request.POST.get("app_name")
		apps = installed_apps(project_id, project_home)

		if app_name and app_name not in apps:
			apps.append(app_name)
			edit_installed_apps(project_id, project_home, apps)

		return HttpResponse("OK")
	else:
		return HttpResponse("POST 'app_name' of new application to add")


def remove_application(request, project_id):
	"""
	Remove existing application from INSTALLED_APPS
	"""
	project_home = join(settings.PROJECTS_HOME, project_id)

	if request.method == "POST":
		app_name = request.POST.get("app_name")
		apps = installed_apps(project_id, project_home)

		if app_name in apps:
			apps.remove(app_name)
			edit_installed_apps(project_id, project_home, apps)

		return HttpResponse("OK")
	else:
		return HttpResponse("POST 'app_name' of new application to remove")


def add_model(request, project_id):
	"""
	Creates new model in application specified in POST data
	"""
	project_home = join(settings.PROJECTS_HOME, project_id)

	if request.method == "POST":
		application_add_model(project_id, project_home, request.POST)

	return redirect("open_project", project_id=project_id)


def open_file(request):
	"""
	Retrieves file content into IDE to edit.
	Read as bytes: SQL viewer loads db.sqlite3 through here.
	"""

	path = request.GET.get("path", "")

	if not path:
		return HttpResponse("")

	with open(path, 'rb') as f:
		content = f.read()

	return HttpResponse(content, content_type='application/octet-stream')


def save_file(request):
	"""
	Saves file in IDE editor.
	"""

	if request.method == "POST":
		path = request.POST.get("path", "")
		content = request.POST.get("content", "")

		with open(path, 'w', encoding='utf-8', newline='') as f:
			f.write(content)

		return HttpResponse("File saved")

	return HttpResponse("POST 'path' and 'content' of file to save")


def run_project(request, project_id):
	"""
	Run given project manage.py runserver 8001
	"""
	project_home = join(settings.PROJECTS_HOME, project_id)

	if request.method == "POST":
		pid = run_manage(project_id, project_home)
		return HttpResponse(pid)

	if request.GET.get("pid", ""):
		try:
			with open(settings.RUN_LOG_FILE, 'r', encoding='utf-8', errors='replace') as f:
				return HttpResponse(f.read())
		except FileNotFoundError:
			pass

	return HttpResponse("")


def stop_project(request, project_id):
	"""
	Kills running python with manage.py inside for project
	"""

	if request.method == "POST":
		pid = request.POST.get("pid", "")
		if pid:
			try:
				os.kill(int(pid), 9)
				return HttpResponse("OK")
			except OSError as e:
				return HttpResponse(str(e))

	return HttpResponse("")
```

- [ ] **Step 5: Rewrite `django_visual/ide/run.py`** (whole file, 4 spaces)

```python
import os
import subprocess
import sys
from multiprocessing import Process

from django.conf import settings

DEV_SERVER_PORT = "8001"


def worker(project_id, project_home, log_file):
    """
    Runs manage.py makemigrations, migrate and dev. server,
    writing their output into log_file
    """

    manage_py = os.path.join(project_home, "manage.py")
    settings_option = ["--settings", "{}.settings".format(project_id)]
    commands = [
        [sys.executable, manage_py, "makemigrations", "--noinput"] + settings_option,
        [sys.executable, manage_py, "migrate", "--noinput"] + settings_option,
        [sys.executable, manage_py, "runserver"] + settings_option + [DEV_SERVER_PORT],
    ]
    env = dict(os.environ, PYTHONUNBUFFERED="1")

    with open(log_file, "w", encoding="utf-8") as log:
        log.write("Starting development server at http://127.0.0.1:{}/\n".format(DEV_SERVER_PORT))
        log.flush()

        for command in commands:
            try:
                proc = subprocess.Popen(
                    command,
                    cwd=project_home,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )
            except OSError as e:
                log.write(str(e) + "\n")
                break

            for line in proc.stdout:
                log.write(line)
                log.flush()

            if proc.wait() != 0:
                break

        log.write("\nDevelopment server stopped\n")


def run_manage(project_id, project_home):
    p = Process(target=worker, args=(project_id, project_home, settings.RUN_LOG_FILE))
    p.start()
    return p.pid
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/pytest -q`
Expected: all PASS (whole suite so far).

- [ ] **Step 7: Checkpoint (no commit)** — `git status --short`.

---

### Task 6: Generated-project smoke tests, tox matrix, docs

**Files:**
- Create: `django_visual/ide/tests/test_generated_projects.py`, `tox.ini`
- Modify: `GNUmakefile`, `README.md`

**Interfaces:**
- Consumes: `projects_home` fixture, `copy_project_template` (Task 2).

- [ ] **Step 1: Write the smoke test**

`django_visual/ide/tests/test_generated_projects.py`:
```python
import os
import subprocess
import sys

import pytest

from ide.create_project import copy_project_template

pytestmark = pytest.mark.slow

PAGES = {
    "empty": ["/admin/login/"],
    "blog": ["/", "/admin/login/"],
    "cms": ["/", "/items/", "/admin/login/"],
    "app": ["/", "/admin/login/"],
}

CLIENT_CHECK = """
from django.test import Client
client = Client(HTTP_HOST="localhost")
for url in {urls!r}:
    status = client.get(url).status_code
    assert status == 200, (url, status)
print("pages ok")
"""


def manage(project_dir, *args):
    env = dict(os.environ, DJANGO_SETTINGS_MODULE="smoke.settings")
    return subprocess.run(
        [sys.executable, "-W", "error::DeprecationWarning", "manage.py", *args],
        cwd=project_dir,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )


@pytest.mark.parametrize("template", sorted(PAGES))
def test_generated_project_boots(projects_home, template):
    copy_project_template(template, "smoke")
    project_dir = projects_home / "smoke"

    steps = [
        ["check"],
        ["makemigrations", "--check", "--dry-run"],
        ["migrate", "--noinput"],
        ["shell", "-c", CLIENT_CHECK.format(urls=PAGES[template])],
    ]
    for args in steps:
        result = manage(project_dir, *args)
        assert result.returncode == 0, "{}:\n{}\n{}".format(args, result.stdout, result.stderr)

    assert "pages ok" in result.stdout
```

(`DJANGO_SETTINGS_MODULE` must be forced: pytest-django exports the IDE's own settings module, and generated `manage.py` only uses `setdefault`.)

- [ ] **Step 2: Run it**

Run: `.venv/bin/pytest -m slow -q`
Expected: 4 PASS. If a step fails, the assertion message shows the `manage.py` output — fix the template (Task 2 files), not the test. If a `DeprecationWarning` originates outside this repo (Django/Python internals), stop and report it rather than suppressing it.

- [ ] **Step 3: tox matrix**

`tox.ini`:
```ini
[tox]
envlist = django52, django61
skipsdist = true

[testenv]
basepython = python3.12
skip_install = true
deps =
    pytest
    pytest-django
    django52: Django>=5.2,<5.3
    django61: Django>=6.1,<6.2
commands = pytest {posargs}
```

Run: `.venv/bin/tox -e django52,django61`
Expected: both envs `OK`, each showing the full suite passed (including `slow`).

- [ ] **Step 4: Makefile and README**

`GNUmakefile` — append:
```make

test:
	python3 -m pytest
```

`README.md` — insert before `## Hints`:
```markdown
## Requirements

Python 3.12+ and Django 5.2 LTS or 6.1.

    pip install -r requirements.txt
    make runserver

## Running tests

    pip install -r requirements-dev.txt
    pytest                  # full suite
    pytest -m "not slow"    # skip generated-project smoke tests
    tox                     # Django 5.2 and 6.1

```

- [ ] **Step 5: Final verification**

```bash
.venv/bin/pytest -q
.venv/bin/tox -e django52,django61
.venv/bin/python django_visual/manage.py check
grep -rn "iteritems\|except [A-Za-z]*, \|import imp$\|django.conf.urls" django_visual --include='*.py' --include='*.html' --include='*-tpl'
git status --short
```
Expected: suites green on both Django versions; `check` → `System check identified no issues`; grep prints nothing; status shows only uncommitted changes on `feature/django-5-6-upgrade`. Do **not** commit.
