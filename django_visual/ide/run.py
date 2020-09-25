import os
import sys
import subprocess
from multiprocessing import Process

from django.conf import settings


def worker(project_id, project_home):
    """
    Runs manage.py dev. server
    """

    manage_py = os.path.join(project_home, "manage.py")
    log_file = os.path.join(settings.TOP_DIR, 'project_run.log')

    with open(log_file, 'w') as f:
        f.write("Starting development server at http://127.0.0.1:8001/\n")

    try:
        command = "{} {} makemigrations --noinput --settings {}.settings && {} {} migrate --noinput --settings {}.settings && {} {} runserver --settings {}.settings 8001".format(
            sys.executable,  # makemigrations
            manage_py,
            project_id,
            sys.executable,  # migrate
            manage_py,
            project_id,
            sys.executable,  # runserver
            manage_py,
            project_id
        )

        proc = subprocess.Popen(command, shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    except Exception as e:
        with open(log_file, 'a') as f:
            f.write(str(e) + "\n")

    while True:
        line = proc.stdout.readline()
        if not line:
            break

        with open(log_file, 'a') as f:
            f.write(line + "\n")

    with open(log_file, 'a') as f:
        err = proc.stderr.read()
        f.write(err + "\n\n")
        f.write("Development server stoped")


def run_manage(project_id, project_home):
    p = Process(target=worker, args=(project_id, project_home))
    p.start()
    return p.pid
