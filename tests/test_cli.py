import json

from typer.testing import CliRunner

from syllabus_expert.cli import app

runner = CliRunner()


def test_cli_extract_json(sample_pdf, tmp_path):
    output = tmp_path / "out.json"
    result = runner.invoke(
        app, ["extract", str(sample_pdf), "-o", str(output), "-m", "heuristic"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text())
    assert len(payload["mcqs"]) == 3
    assert "Extracted 3 MCQ" in result.output


def test_cli_extract_csv(sample_pdf, tmp_path):
    output = tmp_path / "out.csv"
    result = runner.invoke(
        app, ["extract", str(sample_pdf), "-o", str(output), "-m", "heuristic"]
    )
    assert result.exit_code == 0, result.output
    text = output.read_text()
    assert "option_A" in text
    assert "Newton" in text


def test_cli_from_text(tmp_path, sample_text):
    text_file = tmp_path / "paper.txt"
    text_file.write_text(sample_text)
    output = tmp_path / "out.json"
    result = runner.invoke(app, ["from-text", str(text_file), "-o", str(output)])
    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text())
    assert len(payload["mcqs"]) == 3


def test_cli_review_help():
    result = runner.invoke(app, ["review", "--help"])
    assert result.exit_code == 0, result.output
    assert "website" in result.output.lower() or "review" in result.output.lower()


def test_cli_serve_help():
    result = runner.invoke(app, ["serve", "--help"])
    assert result.exit_code == 0, result.output
    assert "website" in result.output.lower()
