# -*- coding: utf-8 -*-

import os

from django.core.management.templates import TemplateCommand
from django.core.management.utils import get_random_secret_key
from django.conf import settings


def copy_project_template(template_name, project_name):
	"""
	Copies template of new projexct
	"""
	projects_home = settings.PROJECTS_HOME

	if not os.path.isdir(projects_home):
		# let create it first
		os.mkdir(projects_home)

	project_tpl = os.path.join(
		settings.TEMPLATES_HOME,
		'project_template_{}'.format(template_name)
	)

	options = {
		'verbosity': 0,
		'extensions': ['py'],
		'files': [],
		'secret_key': get_random_secret_key(),
		'template': project_tpl,
	}

	cmd = TemplateCommand()

	cmd.validate_name(project_name, "project")

	cmd.handle('project', project_name, projects_home, **options)


def copy_application_template(project_home, app_name):
	"""
	Copies template of new application
	"""

	app_tpl = os.path.join(
		settings.TEMPLATES_HOME,
		'app_template'
	)

	options = {
		'verbosity': 2,
		'extensions': ['py'],
		'files': [],
		'template': app_tpl,
	}

	cmd = TemplateCommand()

	cmd.validate_name(app_name, "app")

	cmd.handle('app', app_name, project_home, **options)
