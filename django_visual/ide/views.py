# -*- coding: utf-8 -*-

import os
import random

from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.core.management.base import CommandError
from django.conf import settings, Settings

from create_project import copy_project_template
from open_project import project_context


PROJECTS_TEMPLATES = [
		"Blog", # Blog project is set of main page <br />with posts flow and blog entry detail page.
		"Content Web Site", # Content web site is a collection of entries, <br />main page and detail page for every item.
		"1-Page Application" # One page web application.
	]

PROJECT_NAMES = ['crazy', 'frog', 'squirrel', 'nut', 'bold',
'hamster', 'blog', 'site', 'red', 'dead', 'last', 'first', 'super']


def index(request):
	"""
	IDE welcome
	Select or Create Project
	"""
	
	projects_home = settings.PROJECTS_HOME
	projects = os.listdir(projects_home)

	templates = PROJECTS_TEMPLATES

	context = {
		"projects": projects,
		"templates": templates
	}
	return render(request, 'index.html', context)

def create_project(request):
	"""
	Create new Django project
	"""

	projects_home = settings.PROJECTS_HOME

	context = {
		"template": request.GET.get("template", "blog"),
		"title": random.choice(PROJECT_NAMES) + "_" + random.choice(PROJECT_NAMES),
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

	return HttpResponse(content)
