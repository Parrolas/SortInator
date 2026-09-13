"""Configuration persistence and path safety tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from organizador.config import AppConfig, parse_extensions


def test_parse_extensions_normalises_and_deduplicates() -> None:
    assert parse_extensions("PDF, .docx; ipynb  PDF") == (".docx", ".ipynb", ".pdf")


def test_accepts_final_study_files_but_not_browser_temporaries(app_config: AppConfig) -> None:
    assert app_config.accepts(Path("aula.pdf"))
    assert app_config.accepts(Path("notebook.IPYNB"))
    assert not app_config.accepts(Path("aula.pdf.crdownload"))
    assert not app_config.accepts(Path("programa.exe"))


def test_settings_round_trip_preserves_unicode_paths(app_config: AppConfig) -> None:
    app_config.university_root = app_config.university_root / "Época 1"
    app_config.allowed_extensions = (".pdf", ".md")
    app_config.prompt_timeout_seconds = 61
    app_config.prompt_timeout_enabled = True
    app_config.save()

    loaded = AppConfig.load(app_config.data_dir)

    assert loaded.university_root == app_config.university_root
    assert loaded.allowed_extensions == (".pdf", ".md")
    assert loaded.prompt_timeout_seconds == 61
    assert loaded.prompt_timeout_enabled is True
    assert loaded.initialized


def test_university_folder_cannot_be_inside_downloads(app_config: AppConfig) -> None:
    app_config.university_root = app_config.downloads_dir / "Universidade"

    with pytest.raises(ValueError, match="não podem coincidir"):
        app_config.validate()


def test_downloads_folder_cannot_be_inside_university(app_config: AppConfig) -> None:
    app_config.downloads_dir = app_config.university_root / "Downloads"

    with pytest.raises(ValueError, match="não podem coincidir"):
        app_config.validate()


def test_invalid_popup_timeout_is_rejected(app_config: AppConfig) -> None:
    app_config.prompt_timeout_seconds = 5

    with pytest.raises(ValueError, match="pelo menos 10"):
        app_config.validate()


@pytest.mark.parametrize("field", ["university_root", "downloads_dir"])
@pytest.mark.parametrize("value", [Path(), Path("relative")])
def test_managed_folders_must_be_absolute(app_config: AppConfig, field: str, value: Path) -> None:
    setattr(app_config, field, value)

    with pytest.raises(ValueError, match="caminho absoluto"):
        app_config.validate()


@pytest.mark.parametrize("field", ["university_root", "downloads_dir"])
def test_managed_folders_reject_filesystem_root(app_config: AppConfig, field: str) -> None:
    root = Path(app_config.data_dir.anchor)
    setattr(app_config, field, root)

    with pytest.raises(ValueError, match="raiz"):
        app_config.validate()


@pytest.mark.parametrize("field", ["university_root", "downloads_dir"])
def test_managed_folders_cannot_overlap_application_data(app_config: AppConfig, field: str) -> None:
    setattr(app_config, field, app_config.data_dir / "managed")

    with pytest.raises(ValueError, match="pasta de dados"):
        app_config.validate()


@pytest.mark.parametrize("payload", [None, [], "settings", 3])
def test_load_rejects_non_object_json(tmp_path: Path, payload: object) -> None:
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "settings.json").write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="objeto JSON"):
        AppConfig.load(tmp_path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("university_root", None),
        ("downloads_dir", None),
        ("allowed_extensions", ".pdf"),
        ("allowed_extensions", [".pdf", 1]),
        ("minimum_file_size", None),
        ("minimum_file_size", True),
        ("minimum_file_size", "512"),
        ("watch_enabled", 1),
        ("launch_at_login", "false"),
        ("prompt_timeout_seconds", 45.0),
        ("prompt_timeout_enabled", 1),
        ("initialized", 1),
        ("ocr_enabled", 1),
        ("quiet_intake", 1),
    ],
)
def test_load_rejects_wrong_setting_types(tmp_path: Path, field: str, value: object) -> None:
    payload: dict[str, object] = {
        "university_root": str(tmp_path / "University"),
        "downloads_dir": str(tmp_path / "Downloads"),
        field: value,
    }
    (tmp_path / "settings.json").write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=field):
        AppConfig.load(tmp_path)


def test_load_validates_deserialised_paths(tmp_path: Path) -> None:
    payload = {
        "university_root": str(tmp_path / "AppData" / "Universidade"),
        "downloads_dir": str(tmp_path / "Downloads"),
    }
    data_dir = tmp_path / "AppData"
    data_dir.mkdir()
    (data_dir / "settings.json").write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="pasta de dados"):
        AppConfig.load(data_dir)


def test_load_ignores_persisted_data_dir(app_config: AppConfig, tmp_path: Path) -> None:
    app_config.save()
    payload = json.loads(app_config.settings_path.read_text(encoding="utf-8"))
    payload["data_dir"] = str(tmp_path / "WrongData")
    app_config.settings_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = AppConfig.load(app_config.data_dir)

    assert loaded.data_dir == app_config.data_dir


def test_filename_template_validation_rules(tmp_path: Path) -> None:
    AppConfig(data_dir=tmp_path, filename_template="{disciplina} - {nome_original}").validate()

    for bad in ("{disciplina", "{desconhecido}", "x" * 121, "   "):
        with pytest.raises(ValueError):
            AppConfig(data_dir=tmp_path, filename_template=bad).validate()


def test_settings_round_trip_for_reminder_and_template(tmp_path: Path) -> None:
    config = AppConfig(
        data_dir=tmp_path,
        reminder_lead_days=5,
        filename_template="{codigo}_{tipo}_{nome_original}",
    )
    config.save()

    loaded = AppConfig.load(tmp_path)

    assert loaded.reminder_lead_days == 5
    assert loaded.filename_template == "{codigo}_{tipo}_{nome_original}"


def test_settings_round_trip_for_ocr_toggle(tmp_path: Path) -> None:
    config = AppConfig(data_dir=tmp_path, ocr_enabled=False)
    config.save()

    assert AppConfig.load(tmp_path).ocr_enabled is False
    assert AppConfig(data_dir=tmp_path).ocr_enabled is True


def test_settings_round_trip_for_quiet_intake(tmp_path: Path) -> None:
    config = AppConfig(data_dir=tmp_path, quiet_intake=True)
    config.save()

    assert AppConfig.load(tmp_path).quiet_intake is True
    assert AppConfig(data_dir=tmp_path).quiet_intake is False


def test_load_rejects_wrong_types_for_new_settings(tmp_path: Path) -> None:
    (tmp_path / "settings.json").write_text(
        json.dumps({"reminder_lead_days": "2", "filename_template": 5}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        AppConfig.load(tmp_path)


def test_updates_dir_stays_inside_data_dir(app_config: AppConfig) -> None:
    assert app_config.updates_dir == app_config.data_dir / "updates"


def test_updates_dir_is_derived_and_never_serialized(app_config: AppConfig) -> None:
    app_config.save()

    payload = json.loads(app_config.settings_path.read_text(encoding="utf-8"))

    assert "updates_dir" not in payload
    assert "updates" not in payload
