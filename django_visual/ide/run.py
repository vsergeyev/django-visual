import os
import signal
import subprocess
import sys
import threading
import time
from multiprocessing import Process

from django.conf import settings

DEV_SERVER_PORT = "8001"


def worker(project_id, project_home, log_file):
    """
    Runs manage.py makemigrations, migrate and dev. server,
    writing their output into log_file
    """

    manage_py = os.path.join(project_home, "manage.py")
    settings_option = ["--settings", "{}.settings".format(project_id)]
    commands = [
        [sys.executable, manage_py, "makemigrations", "--noinput"] + settings_option,
        [sys.executable, manage_py, "migrate", "--noinput"] + settings_option,
        [sys.executable, manage_py, "runserver"] + settings_option + [DEV_SERVER_PORT],
    ]
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    # inherited from the IDE's own runserver; would make the project's
    # runserver exit on first code change instead of reloading
    env.pop("RUN_MAIN", None)

    with open(log_file, "w", encoding="utf-8") as log:
        log.write("Starting development server at http://127.0.0.1:{}/\n".format(DEV_SERVER_PORT))
        log.flush()

        for command in commands:
            try:
                proc = subprocess.Popen(
                    command,
                    cwd=project_home,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )
            except OSError as e:
                log.write(str(e) + "\n")
                break

            for line in proc.stdout:
                log.write(line)
                log.flush()

            if proc.wait() != 0:
                break

        log.write("\nDevelopment server stopped\n")


def watch_parent(parent_pid, interval=0.5):
    """
    Kills the worker's process group once the IDE is gone: setsid keeps
    terminal Ctrl+C from reaching the project's server, so it would
    otherwise outlive the IDE and keep its port
    """
    while os.getppid() == parent_pid:
        time.sleep(interval)
    os.killpg(0, signal.SIGKILL)


def serve(project_id, project_home, log_file):
    """
    Worker process entry: leads its own process group, so Stop
    kills manage.py and its autoreloader child along with it
    """
    parent_pid = os.getppid()
    os.setsid()
    threading.Thread(target=watch_parent, args=(parent_pid,), daemon=True).start()
    worker(project_id, project_home, log_file)


def run_manage(project_id, project_home):
    p = Process(target=serve, args=(project_id, project_home, settings.RUN_LOG_FILE))
    p.start()
    return p.pid
