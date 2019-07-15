# -*- coding: utf-8 -*-

import os
from os.path import join, isdir
import random
import sys
import subprocess
from sys import stdout, stdin, stderr

from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.core.management.base import CommandError
from django.conf import settings, Settings

from create_project import (
	copy_project_template,
	copy_application_template
)

from open_project import (
	project_context,
	project_settings,
	edit_installed_apps,
	application_add_model,
	application_edit_model
)

from run import run_manage


def index(request):
	"""
	IDE welcome
	Open or Create Project
	"""

	projects_home = settings.PROJECTS_HOME
	projects = []
	for node in os.listdir(projects_home):
		if isdir(join(projects_home, node)):
			projects.append(node)

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
	project_home = join(settings.PROJECTS_HOME, project_id)

	context = project_context(project_id, project_home)

	context["project_id"] = project_id

	return render(request, 'open_project.html', context)


def add_application(request, project_id):
	"""
	Creates new application for given project
	"""
	project_home = join(settings.PROJECTS_HOME, project_id)

	if request.method == "POST":
		app_name = request.POST.get("app_name")
		copy_application_template(project_home, app_name)

		pr_settings = project_settings(project_id, project_home)
		apps = pr_settings.INSTALLED_APPS
		apps.append(app_name)

		edit_installed_apps(project_id, project_home, apps)

		return HttpResponse("OK")
	else:
		return HttpResponse("POST 'app_name' of new application to create")


def add_model(request, project_id):
	"""
	Creates new model in application specified in POST data
	"""
	project_home = join(settings.PROJECTS_HOME, project_id)

	if request.method == "POST":
		application_add_model(project_id, project_home, request.POST)

	return redirect("open_project", project_id=project_id)

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


def save_file(request):
	"""
	Saves file in IDE editor.
	"""

	if request.method == "POST":
		path = request.POST.get("path", "")
		content = request.POST.get("content", "")

		with open(path, 'w') as f:
			f.write(content)

		return HttpResponse("File saved")

	return HttpResponse("POST 'path' and 'content' of file to save")


def run_project(request, project_id):
	"""
	Run given project manage.py runserver 8001
	"""
	project_home = join(settings.PROJECTS_HOME, project_id)
	# TODO: makemigrations && migrate
	if request.method == "POST":
		pid = run_manage(project_id, project_home)
		return HttpResponse(pid)

	pid = request.GET.get("pid", "")
	if pid:
		fh = open(join(settings.TOP_DIR, 'project_run.log'), 'r')
		data = fh.read()
		return HttpResponse(data)


def stop_project(request, project_id):
	"""
	Kills running python with manage.py inside for project
	"""

	if request.method == "POST":
		pid = request.POST.get("pid", "")
		if pid:
			try:
				os.kill(int(pid), 9)
				return HttpResponse("OK")
			except OSError, e:
				return HttpResponse(str(e))

	return HttpResponse("")
