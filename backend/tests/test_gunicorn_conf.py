import runpy
from pathlib import Path

from gunicorn.config import Config

CONF = Path(__file__).parents[1] / "gunicorn.conf.py"


def test_one_worker_and_no_control_socket():
    # gunicorn 27 opens a control socket under the working directory (/app), where the
    # unprivileged user cannot write: every start logged "Permission denied".
    settings = runpy.run_path(str(CONF))
    config = Config()
    for name, value in settings.items():
        if name in config.settings:
            config.set(name, value)
    assert config.workers == 1
    assert config.settings["control_socket_disable"].get() is True
