from pathlib import Path

from mtpdflogo.config.preferences import UserPreferences, load_preferences, save_preferences


def test_preferences_round_trip_as_toml(tmp_path: Path) -> None:
    path = tmp_path / "preferences.toml"
    original = UserPreferences(
        pdf_folder=tmp_path / "pdfs",
        output_folder=tmp_path / "outputs",
        settings_folder=tmp_path / "settings",
        open_output_folder_on_finish=True,
    )

    save_preferences(original, path)
    loaded = load_preferences(path)

    assert loaded.pdf_folder == original.pdf_folder
    assert loaded.output_folder == original.output_folder
    assert loaded.settings_folder == original.settings_folder
    assert loaded.open_output_folder_on_finish == original.open_output_folder_on_finish


def test_preferences_default_open_output_folder_is_off() -> None:
    assert UserPreferences().open_output_folder_on_finish is False
