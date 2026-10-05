import sys

from ide import run


class FakePopen:
    """
    Records commands; each call returns next (output lines, exit code)
    """
    def __init__(self, results):
        self.results = iter(results)
        self.calls = []

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        lines, code = next(self.results)
        proc = type("Proc", (), {})()
        proc.stdout = iter(lines)
        proc.wait = lambda: code
        return proc


def test_worker_runs_commands_in_order(monkeypatch, tmp_path):
    monkeypatch.setenv("RUN_MAIN", "true")  # set when the IDE itself runs under runserver
    fake = FakePopen([(["No changes detected\n"], 0), (["Applied\n"], 0), (["Quit with CONTROL-C\n"], 0)])
    monkeypatch.setattr(run.subprocess, "Popen", fake)
    log = tmp_path / "run.log"

    run.worker("sample", "/projects/sample", str(log))

    commands = [command for command, _ in fake.calls]
    assert [c[2] for c in commands] == ["makemigrations", "migrate", "runserver"]
    for command, kwargs in fake.calls:
        assert command[:2] == [sys.executable, "/projects/sample/manage.py"]
        assert command[command.index("--settings") + 1] == "sample.settings"
        assert kwargs["cwd"] == "/projects/sample"
        assert kwargs["stderr"] is run.subprocess.STDOUT
        assert kwargs["text"] is True
        assert "RUN_MAIN" not in kwargs["env"]
    assert commands[2][-1] == "8001"

    text = log.read_text()
    assert text.startswith("Starting development server at http://127.0.0.1:8001/\n")
    assert "No changes detected\nApplied\nQuit with CONTROL-C\n" in text
    assert text.rstrip().endswith("Development server stopped")


def test_worker_stops_after_failed_step(monkeypatch, tmp_path):
    fake = FakePopen([(["SystemCheckError: boom\n"], 1)])
    monkeypatch.setattr(run.subprocess, "Popen", fake)
    log = tmp_path / "run.log"

    run.worker("sample", "/projects/sample", str(log))

    assert len(fake.calls) == 1
    assert "SystemCheckError: boom" in log.read_text()


def test_worker_logs_start_failure(monkeypatch, tmp_path):
    def broken_popen(command, **kwargs):
        raise OSError("no python")
    monkeypatch.setattr(run.subprocess, "Popen", broken_popen)
    log = tmp_path / "run.log"

    run.worker("sample", "/projects/sample", str(log))

    assert "no python" in log.read_text()


def test_run_manage_starts_worker_process(monkeypatch, settings, tmp_path):
    settings.RUN_LOG_FILE = str(tmp_path / "run.log")
    started = {}

    class FakeProcess:
        pid = 777

        def __init__(self, target, args):
            started.update(target=target, args=args)

        def start(self):
            started["started"] = True

    monkeypatch.setattr(run, "Process", FakeProcess)

    assert run.run_manage("sample", "/p/sample") == 777
    assert started == {
        "target": run.serve,
        "args": ("sample", "/p/sample", settings.RUN_LOG_FILE),
        "started": True,
    }


def test_watch_parent_kills_group_when_parent_exits(monkeypatch):
    ppids = iter([100, 100, 1])
    killed = []
    monkeypatch.setattr(run.os, "getppid", lambda: next(ppids))
    monkeypatch.setattr(run.os, "killpg", lambda pgid, sig: killed.append((pgid, sig)))

    run.watch_parent(100, interval=0)

    assert killed == [(0, run.signal.SIGKILL)]
