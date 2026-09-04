from pathlib import Path

from mtpdflogo.application.batch import (
    BatchRunner,
    BatchStatus,
    build_jobs,
    discover_pdf_files,
    discover_supported_files,
    load_manifest,
    output_is_inside_input,
    save_manifest,
    validate_jobs,
)


def test_build_jobs_keeps_one_output_per_input(tmp_path: Path) -> None:
    root = tmp_path / "input"
    source = root / "customer" / "a.pdf"
    source.parent.mkdir(parents=True)
    source.touch()

    jobs = build_jobs([source], tmp_path / "output", preserve_subfolders=True, input_root=root)

    assert jobs[0].destination == (
        tmp_path / "output" / "customer" / "a-watermask.pdf"
    ).resolve()


def test_discover_pdf_files_ignores_non_pdf(tmp_path: Path) -> None:
    (tmp_path / "a.pdf").touch()
    (tmp_path / "b.txt").touch()

    assert discover_pdf_files(tmp_path) == [(tmp_path / "a.pdf").resolve()]


def test_discover_supported_files_includes_pdf_and_images(tmp_path: Path) -> None:
    (tmp_path / "a.pdf").touch()
    (tmp_path / "b.png").touch()
    (tmp_path / "c.jpg").touch()
    (tmp_path / "d.txt").touch()

    assert discover_supported_files(tmp_path) == [
        (tmp_path / "a.pdf").resolve(),
        (tmp_path / "b.png").resolve(),
        (tmp_path / "c.jpg").resolve(),
    ]


def test_discover_supported_files_respects_recursive_depth(tmp_path: Path) -> None:
    (tmp_path / "root.pdf").touch()
    level_one = tmp_path / "one"
    level_two = level_one / "two"
    level_two.mkdir(parents=True)
    (level_one / "one.pdf").touch()
    (level_two / "two.pdf").touch()

    assert discover_supported_files(tmp_path, recursive=True, max_depth=0) == [
        (tmp_path / "root.pdf").resolve()
    ]
    assert discover_supported_files(tmp_path, recursive=True, max_depth=1) == [
        (tmp_path / "one" / "one.pdf").resolve(),
        (tmp_path / "root.pdf").resolve(),
    ]
    assert discover_supported_files(tmp_path, recursive=False, max_depth=10) == [
        (tmp_path / "root.pdf").resolve()
    ]


def test_validate_jobs_accepts_supported_images(tmp_path: Path) -> None:
    source = tmp_path / "photo.png"
    source.touch()
    jobs = build_jobs([source], tmp_path / "out")

    assert jobs[0].destination == (tmp_path / "out" / "photo-watermask.png").resolve()
    assert validate_jobs(jobs) == []


def test_batch_runner_isolates_failed_files(tmp_path: Path) -> None:
    good = tmp_path / "good.pdf"
    bad = tmp_path / "bad.pdf"
    good.touch()
    bad.touch()

    def processor(source: Path, destination: Path) -> None:
        if source == bad:
            raise RuntimeError("bad input")
        destination.write_bytes(b"output")

    results = BatchRunner(processor).run(build_jobs([good, bad], tmp_path / "out"))

    assert [result.status for result in results] == [BatchStatus.COMPLETED, BatchStatus.FAILED]


def test_manifest_is_atomic_and_reloadable(tmp_path: Path) -> None:
    path = tmp_path / "status.json"
    expected = {"job": {"status": "completed", "source_size": 10}}

    save_manifest(path, expected)

    assert load_manifest(path) == expected


def test_output_is_inside_input_detects_nested_output(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    output_root = input_root / "out"
    input_root.mkdir()
    output_root.mkdir()

    assert output_is_inside_input(input_root, output_root)
    assert not output_is_inside_input(input_root, tmp_path / "outside")
    assert not output_is_inside_input(None, output_root)
