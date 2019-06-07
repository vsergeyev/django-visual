# -*- coding: utf-8 -*-

import os
import glob
import sys
# Python 2
import imp

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
		"project_apps": project_settings.INSTALLED_APPS,
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
