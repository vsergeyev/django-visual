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


def test_broken_settings_reports_error(make_project):
    root = make_project("blog")
    with open(root / "sample" / "settings.py", "a") as f:
        f.write("\nFOO = (\n")
    context = project_context("sample", str(root))
    assert "SyntaxError" in context["has_apps_error"]
    assert context["project_apps"] == {}
    assert context["project_databases"] == {}
    assert "/manage.py" in context["project_tree"]["sample"]


def test_directory_without_settings_reports_error(projects_home):
    root = projects_home / "stray"
    root.mkdir(parents=True)
    (root / "notes.txt").write_text("not a project")
    context = project_context("stray", str(root))
    assert "FileNotFoundError" in context["has_apps_error"]
    assert context["project_urls"] == []
    assert "/notes.txt" in context["project_tree"]["stray"]
