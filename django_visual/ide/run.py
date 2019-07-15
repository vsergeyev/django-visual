import os
import sys
import subprocess
from multiprocessing import Process

from django.conf import settings


def worker(project_id, project_home):
    """
    Runs manage.py dev. server
    """
    command = "{} {} runserver --settings {}.settings 8001".format(
        sys.executable,
        os.path.join(project_home, "manage.py"),
        project_id
    )

    proc = subprocess.Popen(command, shell=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    while True:
        line = proc.stdout.readline()
        if not line:
            break

        with open(os.path.join(settings.TOP_DIR, 'project_run.log'), 'a') as f:
            f.write(line + "\n")


def run_manage(project_id, project_home):
    p = Process(target=worker, args=(project_id, project_home))
    p.start()
    return p.pid
