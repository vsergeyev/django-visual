import os
import subprocess
import sys

import pytest

from ide.create_project import copy_project_template

pytestmark = pytest.mark.slow

PAGES = {
    "empty": ["/admin/login/"],
    "blog": ["/", "/admin/login/"],
    "cms": ["/", "/items/", "/admin/login/"],
    "app": ["/", "/admin/login/"],
}

CLIENT_CHECK = """
from django.test import Client
client = Client(HTTP_HOST="localhost")
for url in {urls!r}:
    status = client.get(url).status_code
    assert status == 200, (url, status)
print("pages ok")
"""


def manage(project_dir, *args):
    env = dict(os.environ, DJANGO_SETTINGS_MODULE="smoke.settings")
    return subprocess.run(
        [sys.executable, "-W", "error::DeprecationWarning", "manage.py", *args],
        cwd=project_dir,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )


@pytest.mark.parametrize("template", sorted(PAGES))
def test_generated_project_boots(projects_home, template):
    copy_project_template(template, "smoke")
    project_dir = projects_home / "smoke"

    steps = [
        ["check"],
        ["makemigrations", "--check", "--dry-run"],
        ["migrate", "--noinput"],
        ["shell", "-c", CLIENT_CHECK.format(urls=PAGES[template])],
    ]
    for args in steps:
        result = manage(project_dir, *args)
        assert result.returncode == 0, "{}:\n{}\n{}".format(args, result.stdout, result.stderr)

    assert "pages ok" in result.stdout
