from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-installer-smoke",
        action="store_true",
        default=False,
        help="run slow clean-machine source zip installer smoke tests",
    )
    parser.addoption(
        "--installer-zip",
        action="store",
        default="dist/MTPDFLogo-installer.zip",
        help="path to source installer zip for smoke tests",
    )
    parser.addoption(
        "--installer-smoke-cache-dir",
        action="store",
        default="",
        help="optional cache folder for extracted installer smoke environments",
    )
    parser.addoption(
        "--force-installer-reinstall",
        action="store_true",
        default=False,
        help="force installer smoke tests to recreate the cached environment",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "installer_smoke: slow tests that install and verify the source zip package",
    )
