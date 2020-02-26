# -*- coding: utf-8 -*-

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

EXCLUDED_EXTENSIONS = ('.pyc', '.pyo', '.pyd', '.py.class', '.DS_Store')


def project_context(project_id, project_home):
	"""
	Parses Django project
	"""

	pr_settings = project_settings(project_id, project_home)

	old_path = sys.path
	old_app_configs = apps.app_configs

	sys.path.append(project_home)

	apps.ready = False
	apps.app_configs = {}
	apps.populate(installed_apps=pr_settings.INSTALLED_APPS)

	all_models = apps.all_models

	project_apps = collections.OrderedDict()

	for app in pr_settings.INSTALLED_APPS:
		project_apps[app] = []

	for app, models in all_models.iteritems():
		for model_label, model in models.iteritems():
			fields = []
			for field in model._meta.get_fields(include_parents=False):
				fields.append({"name": field.name, "class": field.get_internal_type()})

			if app in project_apps:
				model_path = inspect.getsourcefile(model)
				model_rel_path = model_path.replace(project_home, "")

				project_apps[app].append({
					"name": model.__name__,
					"path": model_path,
					"rel_path": model_rel_path,
					"fields": fields,
				})

	# print all_models
	# print project_apps

	# import pdb; pdb.set_trace()

	# restore original environment
	sys.path = old_path
	apps.app_configs = old_app_configs

	# old_path = sys.path
	# sys.path.append(project_home)
	# Doesn't work for includes()
	# imp.load_source('{}_urls'.join(project_id), os.path.join(
	# 	project_home,
	# 	project_id,
	# 	"urls.py"
	# ))
	# sys.path = old_path

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
		"project_urls": project_urls, # project_urls.urlpatterns
		"project_urls_file": project_urls_file,
		"project_tree": project_tree
	}

	return context


def project_settings(project_id, project_home):
	"""
	Loads and returns project settings module
	"""

	# https://stackoverflow.com/questions/67631/how-to-import-a-module-given-the-full-path
	return imp.load_source('{}_settings'.join(project_id), os.path.join(
		project_home,
		project_id,
		"settings.py"
	))


def parse_urls(source):
	"""
	Parses project/application urls.py
	Extracts url() entries
	"""

	START_MARKER = "urlpatterns = ["
	END_MARKER = "]"

	grep_urls = False
	res = []

	with open(source, 'r') as f:
		for line in f:
			if grep_urls:
				if 'url(' in line:
					res.append(line)

			if START_MARKER in line:
				grep_urls = True

			if END_MARKER in line:
				grep_urls = False

	return res


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

	with open(path, 'r') as f:
		for line in f:
			if START_MARKER in line:
				is_apps = True

			if is_apps and END_MARKER in line:
				is_apps = False

			if is_apps and is_changed:
				pass

			if is_apps and not is_changed:
				new_source.append("{}\n".format(START_MARKER))
				for app in new_installed_apps:
					new_source.append("    '{}',\n".format(app))
				is_changed = True

			if not is_apps:
				new_source.append(line)

	with open(path, 'w') as f:
		f.write("".join(new_source))

	return "ok"


def build_project_tree(project_id, path):
	"""
	Crawl ovel project dir and build dirs/files tree
	"""
	def build_tree(path):
	    res = {}
	    for node in glob.glob(os.path.join(path, "*")):
	        label = node.replace(path, '')
	        if os.path.isdir(node):
	            res[label] = build_tree(node)
	        else:
	        	if not label.lower().endswith(EXCLUDED_EXTENSIONS):
	        		res[label] = node
	    return res

	res = {project_id: {}}
	res[project_id] = build_tree(path)

	return res


def application_add_model(project_id, project_home, data):
	"""
	Adds new model into application from POST data
	"""

	application = data.get("application", "")
	new_model_name = data.get("new_model_name", "")
	fields = zip(
		data.getlist('new_model_field_id'),
		data.getlist('new_model_field_type'),
		data.getlist('new_model_field_options')
	)

	if not application:
		return

	path = os.path.join(project_home, application, "models.py")
	with open(path, "a") as f:
		f.write("\n")
		f.write("\nclass {}(models.Model):".format(new_model_name))
		if data.get("new_model_field_id", ""):
			for field_id, field_type, field_options in fields:
				f.write("\n    {} = models.{}({})".format(field_id, field_type, field_options))
		else: # model with id only
			f.write("\n    pass")
		f.write("\n")

	path_admin = os.path.join(project_home, application, "admin.py")
	with open(path_admin, "a") as f:
		f.write("\n")
		f.write("\nadmin.site.register({})".format(new_model_name))
		f.write("\n")

	# import pdb; pdb.set_trace()


def application_edit_model(project_id, project_home, data):
	"""
	Put changes in model into application from POST data
	"""
