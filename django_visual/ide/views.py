# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import random

from django.shortcuts import render, redirect
from django.http import HttpResponse

from django.conf import settings

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
		"template": request.GET.get("template", ""),
		"title": random.choice(PROJECT_NAMES) + "_" + random.choice(PROJECT_NAMES),
		"projects_home": projects_home
	}

	if request.method == "POST":
		template = request.POST.get("template")
		return HttpResponse(template)
	
	return render(request, 'create_project.html', context)

def open_project(request):
	"""
	Load project structure into IDE.
	"""
