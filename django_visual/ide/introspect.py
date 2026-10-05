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
