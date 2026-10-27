from click.testing import CliRunner

from wyndle.cli import main
from wyndle.lib import notifier


def test_notification_test_reports_failure(monkeypatch):
    monkeypatch.setattr(notifier, "notify", lambda *args, **kwargs: False)
    result = CliRunner().invoke(main, ["daemon", "test"])
    assert result.exit_code != 0
    assert "Test notification failed" in result.output
    assert "accepted" not in result.output


def test_notification_test_distinguishes_acceptance_from_visibility(monkeypatch):
    monkeypatch.setattr(notifier, "notify", lambda *args, **kwargs: True)
    result = CliRunner().invoke(main, ["daemon", "test"])
    assert result.exit_code == 0
    assert "macOS accepted" in result.output
    assert "System Settings" in result.output
