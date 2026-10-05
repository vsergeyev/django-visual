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
