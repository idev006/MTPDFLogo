from pathlib import Path

from mtpdflogo.config.preferences import UserPreferences, load_preferences, save_preferences


def test_preferences_round_trip_as_toml(tmp_path: Path) -> None:
    path = tmp_path / "preferences.toml"
    original = UserPreferences(
        pdf_folder=tmp_path / "pdfs",
        output_folder=tmp_path / "outputs",
    )

    save_preferences(original, path)
    loaded = load_preferences(path)

    assert loaded.pdf_folder == original.pdf_folder
    assert loaded.output_folder == original.output_folder
