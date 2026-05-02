from pathlib import Path

from cli.main import default_report_save_path


def test_default_report_save_path_uses_results_dir(tmp_path):
    config = {"results_dir": str(tmp_path / "logs")}

    path = default_report_save_path(config, "VG", "20260502_064430")

    assert path == tmp_path / "logs" / "manual_reports" / "VG_20260502_064430"


def test_dockerfile_makes_app_directory_writable_by_appuser():
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert "mkdir -p /home/appuser/app" in dockerfile
    assert "chown -R appuser:appuser /home/appuser/app" in dockerfile
