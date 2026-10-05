import os

from django.conf import settings
from django.core.management.templates import TemplateCommand
from django.core.management.utils import get_random_secret_key


def template_options(app_or_project, **overrides):
	"""
	Default options of 'django-admin start<app_or_project>', updated with overrides.
	Built from the command's own parser, so options added by newer
	Django versions are always present.
	"""
	parser = TemplateCommand().create_parser(
		'django-admin',
		'start{}'.format(app_or_project)
	)
	options = vars(parser.parse_args(['name']))
	del options['name'], options['directory']
	options.update(overrides)
	return options


def copy_project_template(template_name, project_name):
	"""
	Copies template of new project
	"""
	projects_home = settings.PROJECTS_HOME
	os.makedirs(projects_home, exist_ok=True)

	project_tpl = os.path.join(
		settings.TEMPLATES_HOME,
		'project_template_{}'.format(template_name)
	)

	options = template_options(
		'project',
		verbosity=0,
		template=project_tpl,
		secret_key=get_random_secret_key(),
	)

	TemplateCommand().handle('project', project_name, projects_home, **options)


def copy_application_template(project_home, app_name):
	"""
	Copies template of new application
	"""
	app_tpl = os.path.join(
		settings.TEMPLATES_HOME,
		'app_template'
	)

	options = template_options(
		'app',
		verbosity=0,
		template=app_tpl,
	)

	TemplateCommand().handle('app', app_name, project_home, **options)
