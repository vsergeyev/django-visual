import os
from os.path import join, isdir
import random
import signal

from django.shortcuts import render, redirect
from django.http import Http404, HttpResponse
from django.core.management.base import CommandError
from django.conf import settings

from .create_project import (
	copy_project_template,
	copy_application_template
)

from .open_project import (
	project_context,
	project_settings,
	edit_installed_apps,
	application_add_model,
)

from .run import run_manage


def installed_apps(project_id, project_home):
	"""
	Current INSTALLED_APPS of project as a list
	"""
	return list(project_settings(project_id, project_home).INSTALLED_APPS)


def index(request):
	"""
	IDE welcome
	Open or Create Project
	"""

	projects_home = settings.PROJECTS_HOME
	# Projects dir may not exist, let create it
	os.makedirs(projects_home, exist_ok=True)

	projects = sorted(
		node for node in os.listdir(projects_home)
		if isdir(join(projects_home, node))
	)

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
		except CommandError as e:
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

	if not isdir(project_home):
		raise Http404("Project '{}' not found".format(project_id))

	context = project_context(project_id, project_home)

	context["project_id"] = project_id

	return render(request, 'open_project.html', context)


def create_application(request, project_id):
	"""
	Creates new application for given project
	"""
	project_home = join(settings.PROJECTS_HOME, project_id)

	if request.method == "POST":
		app_name = request.POST.get("app_name")

		try:
			copy_application_template(project_home, app_name)
		except CommandError as e:
			return HttpResponse(str(e), status=400)

		try:
			apps = installed_apps(project_id, project_home)
		except Exception as e:
			return HttpResponse("{}: {}".format(type(e).__name__, e), status=400)
		if app_name not in apps:
			apps.append(app_name)
			edit_installed_apps(project_id, project_home, apps)

		return HttpResponse("OK")
	else:
		return HttpResponse("POST 'app_name' of new application to create")


def add_application(request, project_id):
	"""
	Add existing application to INSTALLED_APPS
	"""
	project_home = join(settings.PROJECTS_HOME, project_id)

	if request.method == "POST":
		app_name = request.POST.get("app_name")
		try:
			apps = installed_apps(project_id, project_home)
		except Exception as e:
			return HttpResponse("{}: {}".format(type(e).__name__, e), status=400)

		if app_name and app_name not in apps:
			apps.append(app_name)
			edit_installed_apps(project_id, project_home, apps)

		return HttpResponse("OK")
	else:
		return HttpResponse("POST 'app_name' of new application to add")


def remove_application(request, project_id):
	"""
	Remove existing application from INSTALLED_APPS
	"""
	project_home = join(settings.PROJECTS_HOME, project_id)

	if request.method == "POST":
		app_name = request.POST.get("app_name")
		try:
			apps = installed_apps(project_id, project_home)
		except Exception as e:
			return HttpResponse("{}: {}".format(type(e).__name__, e), status=400)

		if app_name in apps:
			apps.remove(app_name)
			edit_installed_apps(project_id, project_home, apps)

		return HttpResponse("OK")
	else:
		return HttpResponse("POST 'app_name' of new application to remove")


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
	Read as bytes: SQL viewer loads db.sqlite3 through here.
	"""

	path = request.GET.get("path", "")

	if not path:
		return HttpResponse("")

	with open(path, 'rb') as f:
		content = f.read()

	return HttpResponse(content, content_type='application/octet-stream')


def save_file(request):
	"""
	Saves file in IDE editor.
	"""

	if request.method == "POST":
		path = request.POST.get("path", "")
		content = request.POST.get("content", "")

		with open(path, 'w', encoding='utf-8', newline='') as f:
			f.write(content)

		return HttpResponse("File saved")

	return HttpResponse("POST 'path' and 'content' of file to save")


def run_project(request, project_id):
	"""
	Run given project manage.py runserver 8001
	"""
	project_home = join(settings.PROJECTS_HOME, project_id)

	if request.method == "POST":
		pid = run_manage(project_id, project_home)
		return HttpResponse(pid)

	if request.GET.get("pid", ""):
		try:
			with open(settings.RUN_LOG_FILE, 'r', encoding='utf-8', errors='replace') as f:
				return HttpResponse(f.read())
		except FileNotFoundError:
			pass

	return HttpResponse("")


def stop_project(request, project_id):
	"""
	Kills running python with manage.py inside for project
	"""

	if request.method == "POST":
		pid = request.POST.get("pid", "")
		if pid:
			try:
				pid = int(pid)
				# 0 and 1 would hit the IDE's own group or every user process
				if pid <= 1:
					return HttpResponse("")
				try:
					# pid leads the project's process group, see run.serve
					os.killpg(pid, signal.SIGKILL)
				except ProcessLookupError:
					# worker not yet past setsid, its group doesn't exist yet
					os.kill(pid, signal.SIGKILL)
				return HttpResponse("OK")
			except (OSError, ValueError) as e:
				return HttpResponse(str(e))

	return HttpResponse("")
