# Django 5.2 / 6.1 upgrade + test suite — design

Date: 2026-10-05
Branch: `feature/django-5-6-upgrade` (changes left uncommitted)

## Goal

Visual Django IDE runs on modern Python/Django, the projects it generates
work on that same Django, and a test suite proves both.

- Supported: Django 5.2 LTS and 6.1 (latest), Python 3.12+.
- Python 2 support is dropped.
- Out of scope: UI/JS changes; hardening `open_file`/`save_file` arbitrary
  paths and missing CSRF middleware (local-only tool — noted, not fixed).

## 1. Runtime, packaging, IDE app

### Packaging
- `requirements.txt`: `Django>=5.2,<6.2`, `gunicorn` (drop `django-heroku`).
- `runtime.txt`: `python-3.12`.
- `requirements-dev.txt`: `pytest`, `pytest-django`, `tox`.
- `pytest.ini`: `DJANGO_SETTINGS_MODULE = django_visual.settings`,
  `pythonpath = django_visual`, `slow` marker registered.
- `tox.ini`: envs `django52` (`Django>=5.2,<5.3`) and `django61`
  (`Django>=6.1,<6.2`).
- `README.md`: Requirements + Running tests section; `GNUmakefile`: `test`
  target.

### IDE settings / URLs
- `settings.py`: remove `USE_L10N`, `TEMPLATE_LOADERS`,
  `TEMPLATE_CONTEXT_PROCESSORS`; add `DEFAULT_AUTO_FIELD`;
  `ALLOWED_HOSTS = ['localhost', '127.0.0.1']`; `PROJECTS_HOME` overridable
  via `DJANGO_VISUAL_PROJECTS_HOME` env var.
- `urls.py`, `ide/urls.py`: `url()` → `path()`/`re_path()`. Patterns
  anchored (`^...$`); URL names and path strings preserved so the JS keeps
  working. (`testserver` needn't be in `ALLOWED_HOSTS`: Django's
  `setup_test_environment`, which pytest-django calls, adds it.)

### IDE modules
- Python 3 syntax, explicit relative imports, `.items()`.
- `open_project.project_settings()`: reads `settings.py` and executes it into a
  fresh `types.ModuleType` on every call (replaces `imp.load_source`; no
  `sys.modules` entry, no stale `.pyc`).
- `open_project.project_context()`: calls new `ide/introspect.py` in a
  subprocess (`sys.executable -P`, so the IDE's `ide/` dir is not on the
  project's `sys.path`; `cwd=project_home`, `PYTHONPATH=project_home`,
  `DJANGO_SETTINGS_MODULE=<project_id>.settings`). The script runs
  `django.setup()` and prints JSON
  `{"apps": {<INSTALLED_APPS entry>: [{name, path, rel_path, fields: [{name, class}]}]}, "error": ""}`.
  Entries are paired with app configs by registration order; only apps
  located inside `project_home` report models (contrib apps get `[]`, as
  today). Any exception → `error` (`"<Type>: <message>"`) → `has_apps_error`;
  apps still listed with empty model lists. Unparseable output → stderr's last
  line.
- `open_project.parse_urls()`: matches `path(`, `re_path(` and `url(` lines.
- `create_project.py`: options built from
  `TemplateCommand().create_parser('django-admin', 'startproject')` defaults,
  then overridden (`template`, `extensions=['py']`, `secret_key`, `verbosity`),
  so newer required keys (`exclude`, …) are present.
- `run.py`: Python 3 fixes, text-mode subprocess output (stderr merged into
  stdout), argument lists instead of a shell `&&` string (three sequential
  calls, stop on first failure). Log path becomes setting `RUN_LOG_FILE`
  (default `TOP_DIR/project_run.log`) and is passed to the worker.
  The worker (`run.serve`) calls `setsid()` so Stop can `killpg` it together
  with runserver and its autoreloader; a watchdog thread kills that group
  when the IDE process exits (Ctrl+C no longer reaches it after `setsid`).
- `build_project_tree()`: fix mixed tabs/spaces (TabError on Py3), skip
  `__pycache__` dirs, sorted output.
- `views.py`: `open_project` → 404 for unknown project; `add_application` /
  `remove_application` idempotent (no duplicate entry, no 500 for absent
  app); `create_application` → 400 with message on `CommandError`;
  `open_file` reads bytes (SQL viewer opens `db.sqlite3`), `save_file`
  writes UTF-8; `run_project` GET without pid / before log exists → empty
  200; `index` sorted project list.
- `templates/open_project.html`: `.iteritems` → `.items` (Py3 dicts; loops
  rendered nothing otherwise). No other UI/JS change.

## 2. Generated project templates

All four (`empty`, `blog`, `cms`, `app`):
- `urls.py-tpl` / app `urls.py`: `path()`/`re_path()`, imports from
  `django.urls`, `path('admin/', admin.site.urls)`.
- `settings.py-tpl`: `pathlib.Path` `BASE_DIR`, no `USE_L10N`,
  `DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'`.
- `manage.py-tpl`, `wsgi.py-tpl`: modern `startproject` shape (`main()`).
- No `from __future__` / coding headers.
- `blog`/`cms` apps keep `AutoField` for their shipped `0001_initial.py`
  via `default_auto_field = 'django.db.models.AutoField'` in `apps.py`
  (no phantom migration).

`cms`: rename plain `manage.py`, `settings.py`, `urls.py`, `wsgi.py`,
`__init__.py` to `.py-tpl` (`git mv`, uncommitted) with `{{ project_name }}` /
`{{ secret_key }}` placeholders.

`cms`: add `SITE_ID = 1` (flatpages fallback middleware needs it).

`blog`: keep bundled `db.sqlite3` (holds the readme's admin/superuser login);
`migrate` upgrades it — smoke test proves this on 5.2 and 6.1.

`app` (1-Page Application): add empty `app/migrations/__init__.py` so models
added through the IDE get migrations on Run.

`app_template`: drop `{{ unicode_literals }}`; `apps.py-tpl` gets
`default_auto_field`.

## 3. Tests

Location `django_visual/ide/tests/`, pytest-django, run via tox on both envs.
`conftest.py` provides `projects_home` fixture (`settings.PROJECTS_HOME` →
`tmp_path`).

- `test_open_project_helpers.py`: `parse_urls`; `edit_installed_apps`
  round-trip keeps rest of file; `application_add_model` (with/without
  fields) writes `models.py` + `admin.py`; `build_project_tree` exclusions;
  `project_settings` reflects edits on reload.
- `test_create_project.py`: each template renders, no leftover `{{ }}`,
  secret key filled; invalid name → `CommandError`;
  `copy_application_template` creates app files.
- `test_introspect.py`: JSON shape for blog template; broken
  `INSTALLED_APPS` → error string, no exception.
- `test_views.py` (test client): `index` (lists, creates missing home);
  `create_project` GET / valid POST redirect / invalid name error;
  `open_project` 200 + context; `create_application` / `add_application` /
  `remove_application` GET + POST effects on `INSTALLED_APPS`; `add_model`
  redirect; `open_file`/`save_file` round-trip; `stop_project` kills a dummy
  `sleep`; `run_project` with `run_manage` mocked.
- `test_generated_projects.py` (`@pytest.mark.slow`): per template generate,
  then subprocess (`-W error::DeprecationWarning`, `DJANGO_SETTINGS_MODULE`
  forced to the generated project) `manage.py check`,
  `makemigrations --check --dry-run`, `migrate`, then GET the template's pages
  (`/admin/login/` for all; `/` for blog/cms/app; `/items/` for cms) via
  `manage.py shell -c` with the test `Client`.
- `test_run.py`: worker command order/stop-on-failure/log with `Popen`
  faked; `run_manage` with `Process` faked.

## Verification

- `tox -e django52,django61` green.
- `python -W error::DeprecationWarning -m pytest` clean on 6.1.
