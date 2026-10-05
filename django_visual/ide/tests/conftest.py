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
