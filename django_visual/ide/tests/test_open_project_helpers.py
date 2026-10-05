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


def test_parse_urls_brackets_inside_patterns(tmp_path):
    source = tmp_path / "urls.py"
    source.write_text(
        "urlpatterns = [\n"
        "    re_path(r'^item/[0-9]+/$', views.item),\n"
        "    path('tags/', views.tags, kwargs={'x': [1]}),  # ] in comment\n"
        "    path('last/', views.last),\n"
        "]\n"
    )
    lines = [l.strip() for l in parse_urls(str(source))]
    assert [l.split(",")[0] for l in lines] == [
        "re_path(r'^item/[0-9]+/$'",
        "path('tags/'",
        "path('last/'",
    ]


def test_parse_urls_single_line_list(tmp_path):
    source = tmp_path / "urls.py"
    source.write_text(
        "urlpatterns = []\n"
        "extra = path('d/', views.d)\n"
    )
    assert parse_urls(str(source)) == []


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


def test_edit_installed_apps_ignores_brackets_in_comments(tmp_path):
    home = write_settings(tmp_path, (
        "INSTALLED_APPS = [\n"
        "    'a',\n"
        "    # 'debug_toolbar',  [disabled]\n"
        "    'b',\n"
        "]\n"
        "TAIL = 1\n"
    ))
    edit_installed_apps("proj", home, ["a", "b", "c"])
    module = project_settings("proj", home)
    assert module.INSTALLED_APPS == ["a", "b", "c"]
    assert module.TAIL == 1
