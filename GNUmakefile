default: gunicorn

migrate:
	python3 ./django_visual/manage.py makemigrations && python3 ./django_visual/manage.py migrate

gunicorn: migrate
	gunicorn --pythonpath="$(PWD)/django_visual" django_visual.wsgi

runserver: migrate
	python3 ./django_visual/manage.py runserver

