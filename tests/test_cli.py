from click.testing import CliRunner

from wyndle.cli import main


def test_help_screen_without_subcommand(home):
    result = CliRunner().invoke(main, [])
    assert result.exit_code == 0
    assert "wyndle morning" in result.output


def test_every_command_has_help(home):
    runner = CliRunner()
    for name in main.commands:
        assert runner.invoke(main, [name, "--help"]).exit_code == 0, name


def test_status_before_morning(home):
    result = CliRunner().invoke(main, ["status"])
    assert result.exit_code == 0
    assert "Day not started" in result.output
