import glob
import json
import os
import subprocess
import sys
import types

EXCLUDED_EXTENSIONS = ('.pyc', '.pyo', '.pyd', '.py.class', '.DS_Store')
EXCLUDED_DIRS = ('__pycache__',)
URL_FUNCTIONS = ('path(', 'url(')  # 'path(' also matches re_path(

INTROSPECT_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "introspect.py")
INTROSPECT_TIMEOUT = 60


def project_context(project_id, project_home):
	"""
	Parses Django project
	"""

	# broken settings.py must not lock the project out of the IDE editor
	try:
		pr_settings = project_settings(project_id, project_home)
	except Exception as e:
		pr_settings = None
		has_apps_error = "{}: {}".format(type(e).__name__, e)
		models_by_app = {}
	else:
		models_by_app, has_apps_error = introspect_project(project_id, project_home)

	installed_apps = pr_settings.INSTALLED_APPS if pr_settings else []
	project_apps = {
		app: models_by_app.get(app, [])
		for app in installed_apps
	}

	project_settings_file = os.path.join(project_home, project_id, "settings.py")
	project_urls_file = os.path.join(project_home, project_id, "urls.py")
	project_urls = parse_urls(project_urls_file) if os.path.isfile(project_urls_file) else []

	project_tree = build_project_tree(project_id, project_home)

	context = {
		"project_id": project_id,
		"project_home": project_home,
		"project_apps": project_apps,
		"project_databases": pr_settings.DATABASES if pr_settings else {},
		"project_settings_file": project_settings_file,
		"project_urls": project_urls,
		"project_urls_file": project_urls_file,
		"project_tree": project_tree,
		"has_apps_error": has_apps_error
	}

	return context


def introspect_project(project_id, project_home):
	"""
	Lists project models by INSTALLED_APPS entry.
	Runs introspect.py in a subprocess with project's own settings,
	so project code never gets imported into the IDE process.
	Returns (models_by_app, error) tuple.
	"""

	env = dict(os.environ)
	env["DJANGO_SETTINGS_MODULE"] = "{}.settings".format(project_id)
	env["PYTHONPATH"] = os.pathsep.join(
		p for p in (project_home, env.get("PYTHONPATH")) if p
	)

	# -P: keep the IDE's own ide/ dir off project's sys.path
	command = [sys.executable, "-P", INTROSPECT_SCRIPT, project_home]

	try:
		proc = subprocess.run(
			command,
			cwd=project_home,
			env=env,
			capture_output=True,
			text=True,
			timeout=INTROSPECT_TIMEOUT
		)
	except subprocess.TimeoutExpired:
		return {}, "Project introspection timed out after {} seconds".format(INTROSPECT_TIMEOUT)

	# project code may print to stdout too, result is the last line
	lines = proc.stdout.strip().splitlines()
	try:
		data = json.loads(lines[-1])
	except (IndexError, ValueError):
		errors = proc.stderr.strip().splitlines()
		if errors:
			return {}, errors[-1]
		return {}, "Project introspection failed with exit code {}".format(proc.returncode)

	return data["apps"], data["error"]


def project_settings(project_id, project_home):
	"""
	Loads and returns project settings module.
	settings.py is executed on every call, so edits are always visible.
	"""

	path = os.path.join(project_home, project_id, "settings.py")

	module = types.ModuleType("{}_settings".format(project_id))
	module.__file__ = path

	with open(path, 'r', encoding='utf-8') as f:
		source = f.read()

	exec(compile(source, path, "exec"), module.__dict__)

	return module


def parse_urls(source):
	"""
	Parses project/application urls.py
	Extracts path() / re_path() / url() entries
	"""

	START_MARKER = "urlpatterns = ["
	END_MARKER = "]"

	grep_urls = False
	res = []

	with open(source, 'r', encoding='utf-8') as f:
		for line in f:
			if grep_urls:
				if any(func in line for func in URL_FUNCTIONS):
					res.append(line)

			code = strip_comment(line).strip()

			if START_MARKER in line:
				# list may be closed on the same line: urlpatterns = []
				grep_urls = not code.endswith(END_MARKER)

			# ']' closing urlpatterns, not one inside a regex or comment
			elif code.startswith(END_MARKER):
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

	with open(path, 'r', encoding='utf-8') as f:
		for line in f:
			if not is_changed and START_MARKER in line:
				new_source.append("{}\n".format(START_MARKER))
				for app in new_installed_apps:
					new_source.append("    '{}',\n".format(app))
				new_source.append("{}\n".format(END_MARKER))
				is_changed = True
				# list may be closed on the same line: INSTALLED_APPS = []
				is_apps = END_MARKER not in strip_comment(line.split(START_MARKER, 1)[1])
				continue

			if is_apps:
				if END_MARKER in strip_comment(line):
					is_apps = False
				continue

			new_source.append(line)

	with open(path, 'w', encoding='utf-8') as f:
		f.write("".join(new_source))

	return "ok"


def strip_comment(line):
	"""
	Code part of settings.py line, without '# ...' comment
	"""
	return line.split("#", 1)[0]


def build_project_tree(project_id, path):
	"""
	Crawl over project dir and build dirs/files tree
	"""
	def build_tree(path):
		res = {}
		for node in sorted(glob.glob(os.path.join(path, "*"))):
			label = node.replace(path, '')
			if os.path.isdir(node):
				if os.path.basename(node) not in EXCLUDED_DIRS:
					res[label] = build_tree(node)
			elif not label.lower().endswith(EXCLUDED_EXTENSIONS):
				res[label] = node
		return res

	return {project_id: build_tree(path)}


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
	with open(path, "a", encoding="utf-8") as f:
		f.write("\n")
		f.write("\nclass {}(models.Model):".format(new_model_name))
		if data.get("new_model_field_id", ""):
			for field_id, field_type, field_options in fields:
				f.write("\n    {} = models.{}({})".format(field_id, field_type, field_options))
		else: # model with id only
			f.write("\n    pass")
		f.write("\n")

	path_admin = os.path.join(project_home, application, "admin.py")
	with open(path_admin, "a", encoding="utf-8") as f:
		f.write("\n")
		f.write("\nadmin.site.register({})".format(new_model_name))
		f.write("\n")


def application_edit_model(project_id, project_home, data):
	"""
	Put changes in model into application from POST data
	"""
