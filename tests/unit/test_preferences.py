from pathlib import Path

from mtpdflogo.config.preferences import UserPreferences, load_preferences, save_preferences


def test_preferences_round_trip_as_toml(tmp_path: Path) -> None:
    path = tmp_path / "preferences.toml"
    original = UserPreferences(
        pdf_folder=tmp_path / "pdfs",
        output_folder=tmp_path / "outputs",
        settings_folder=tmp_path / "settings",
        default_settings_file=tmp_path / "settings" / "default.toml",
        recent_settings_files=[
            tmp_path / "settings" / "one.toml",
            tmp_path / "settings" / "two.toml",
        ],
        open_output_folder_on_finish=True,
    )

    save_preferences(original, path)
    loaded = load_preferences(path)

    assert loaded.pdf_folder == original.pdf_folder
    assert loaded.output_folder == original.output_folder
    assert loaded.settings_folder == original.settings_folder
    assert loaded.default_settings_file == original.default_settings_file
    assert loaded.recent_settings_files == original.recent_settings_files
    assert loaded.open_output_folder_on_finish == original.open_output_folder_on_finish


def test_preferences_default_open_output_folder_is_off() -> None:
    assert UserPreferences().open_output_folder_on_finish is False


def test_remember_settings_file_keeps_recent_unique_and_limited(tmp_path: Path) -> None:
    preferences = UserPreferences()
    files = [tmp_path / f"preset-{index}.toml" for index in range(7)]

    for path in files:
        preferences.remember_settings_file(path)
    preferences.remember_settings_file(files[3])

    assert preferences.settings_folder == files[3].resolve().parent
    assert preferences.recent_settings_files[0] == files[3].resolve()
    assert len(preferences.recent_settings_files) == 5
    assert len(set(preferences.recent_settings_files)) == 5
