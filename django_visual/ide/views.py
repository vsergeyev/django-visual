# -*- coding: utf-8 -*-

import os
import random

from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.core.management.base import CommandError
from django.conf import settings, Settings

from create_project import copy_project_template
from open_project import project_context


def index(request):
	"""
	IDE welcome
	Open or Create Project
	"""
	
	projects_home = settings.PROJECTS_HOME
	projects = os.listdir(projects_home)

	context = {
		"projects": projects,
		"templates": settings.PROJECTS_TEMPLATES
	}
	return render(request, 'index.html', context)


def create_project(request):
	"""
	Create new Django project
	"""

	names = settings.PROJECT_NAMES
	projects_home = settings.PROJECTS_HOME

	context = {
		"template": request.GET.get("template", "blog"),
		"title": random.choice(names) + "_" + random.choice(names),
		"projects_home": projects_home,
		'error': ''
	}

	if request.method == "POST":
		template = request.POST.get("template")
		title = request.POST.get("title")

		try:
			copy_project_template(template, title)
		except CommandError, e:
			context['title'] = title
			context['error'] = str(e)
			return render(request, 'create_project.html', context)

		return redirect('open_project', project_id=title)
	
	return render(request, 'create_project.html', context)


def open_project(request, project_id):
	"""
	Load project structure into IDE.
	"""
	project_home = os.path.join(settings.PROJECTS_HOME, project_id)

	context = project_context(project_id, project_home)

	context["project_id"] = project_id

	return render(request, 'open_project.html', context)


def open_file(request):
	"""
	Retrieves file content into IDE to edit.
	"""

	path = request.GET.get("path", "")

	if not path:
		return HttpResponse("")

	with open(path, 'r') as f:
		content = f.read()

	return HttpResponse(content, content_type='application/octet-stream')
