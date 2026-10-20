"""A8 — the application writes a real log, so a failure leaves a trace.

Before this, an exception only existed in whatever terminal launched the app.
"""

import logging

from oms_core import logging_setup


def test_setup_writes_into_the_data_directory(tmp_path):
    env = {"OMS_DATA_DIR": str(tmp_path / "datos")}
    path = logging_setup.setup_logging(env=env, console=False)
    assert path == tmp_path / "datos" / "logs" / "oms.log"
    assert path.exists()
    assert path.parent.name == logging_setup.LOG_DIR_NAME


def test_messages_reach_the_file_with_level_and_logger_name(tmp_path):
    path = logging_setup.setup_logging(
        env={"OMS_DATA_DIR": str(tmp_path)}, console=False)
    logging.getLogger("oms_core.test").warning("algo pasó")
    logging.shutdown()
    line = [ln for ln in path.read_text(encoding="utf-8").splitlines() if "algo pasó" in ln]
    assert line, "el mensaje no llegó al archivo"
    assert "WARNING" in line[0]
    assert "oms_core.test" in line[0]


def test_the_level_comes_from_the_environment(tmp_path):
    path = logging_setup.setup_logging(
        env={"OMS_DATA_DIR": str(tmp_path), "OMS_LOG_LEVEL": "DEBUG"}, console=False)
    logging.getLogger("oms_core.test").debug("detalle fino")
    logging.shutdown()
    assert "detalle fino" in path.read_text(encoding="utf-8")
    assert logging.getLogger().level == logging.DEBUG


def test_an_explicit_level_wins_over_the_environment(tmp_path):
    logging_setup.setup_logging(
        level="ERROR",
        env={"OMS_DATA_DIR": str(tmp_path), "OMS_LOG_LEVEL": "DEBUG"},
        console=False)
    assert logging.getLogger().level == logging.ERROR


def test_calling_twice_does_not_stack_handlers(tmp_path):
    env = {"OMS_DATA_DIR": str(tmp_path)}
    logging_setup.setup_logging(env=env, console=False)
    first = len(logging.getLogger().handlers)
    logging_setup.setup_logging(env=env, console=False)
    assert len(logging.getLogger().handlers) == first


def test_it_rotates(tmp_path, monkeypatch):
    monkeypatch.setattr(logging_setup, "MAX_BYTES", 200)
    path = logging_setup.setup_logging(
        env={"OMS_DATA_DIR": str(tmp_path)}, console=False)
    logger = logging.getLogger("oms_core.rotation")
    for index in range(200):
        logger.info("línea %s de relleno para forzar la rotación", index)
    logging.shutdown()
    rotated = path.with_name(path.name + ".1")
    assert rotated.exists(), "no rotó"


def test_uncaught_exceptions_are_logged(tmp_path, monkeypatch):
    path = logging_setup.setup_logging(
        env={"OMS_DATA_DIR": str(tmp_path)}, console=False)
    monkeypatch.setattr(logging_setup.sys, "excepthook", lambda *a: None)
    logging_setup.install_excepthook()
    try:
        raise RuntimeError("boom controlado")
    except RuntimeError:
        logging_setup.sys.excepthook(*logging_setup.sys.exc_info())
    logging.shutdown()
    content = path.read_text(encoding="utf-8")
    assert "boom controlado" in content
    assert "RuntimeError" in content
