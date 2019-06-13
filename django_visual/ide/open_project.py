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

	# https://stackoverflow.com/questions/67631/how-to-import-a-module-given-the-full-path
	project_settings = imp.load_source('{}_settings'.join(project_id), os.path.join(
		project_home,
		project_id,
		"settings.py"
	))

	old_path = sys.path
	old_app_configs = apps.app_configs
	
	sys.path.append(project_home)

	apps.ready = False
	apps.app_configs = {}
	apps.populate(installed_apps=project_settings.INSTALLED_APPS)

	all_models = apps.all_models

	project_apps = collections.OrderedDict()

	for app in project_settings.INSTALLED_APPS:
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

	project_urls = parse_urls(os.path.join(
		project_home,
		project_id,
		"urls.py"
	))

	project_tree = build_project_tree(project_id, project_home)

	context = {
		"project_id": project_id,
		"project_home": project_home,
		"project_apps": project_apps,
		"project_databases": project_settings.DATABASES,
		"project_urls": project_urls, # project_urls.urlpatterns
		"project_tree": project_tree
	}

	return context

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
