from __future__ import annotations

from pathlib import Path
import tarfile

import pytest

from tools.corpus import download


def test_corpus_lookup_supports_aliases_and_normalization() -> None:
    lookup = download.corpus_lookup()

    assert lookup["tptp"].name == "tptp-v9.2.1"
    assert lookup["tptp-current"].name == "tptp-v9.2.1"
    assert lookup["m2np"].name == "m2k"
    assert lookup["mptp2078b"].name == "mtptp"
    assert download.normalize_name("TPTP_CURRENT") == "tptp-current"


def test_select_corpora_deduplicates_aliases() -> None:
    selected = download.select_corpora(
        ("tptp", "tptp-current", "m2k"),
        all_corpora=False,
        lookup=download.corpus_lookup(),
    )

    assert [spec.name for spec in selected] == ["tptp-v9.2.1", "m2k"]


def test_select_corpora_requires_explicit_selection() -> None:
    with pytest.raises(SystemExit, match="select at least one corpus"):
        download.select_corpora(
            (),
            all_corpora=False,
            lookup=download.corpus_lookup(),
        )


def test_should_skip_only_skips_nonempty_existing_targets(tmp_path: Path) -> None:
    target = tmp_path / "m2k"
    target.mkdir()

    assert not download.should_skip("m2k", target, force=False)

    (target / "problem.p").write_text("", encoding="utf-8")

    assert download.should_skip("m2k", target, force=False)
    assert not download.should_skip("m2k", target, force=True)


def test_remove_path_refuses_paths_outside_corpus_root(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="outside corpus root"):
        download.remove_path(
            tmp_path.parent / "outside",
            root=tmp_path / "benchmarks",
        )


def test_install_archive_subdir_extracts_selected_subdir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = tmp_path / "plcop-master.tar.gz"
    source_root = tmp_path / "source" / "plcop-master"
    theorem_dir = source_root / "theorems" / "m2np"
    theorem_dir.mkdir(parents=True)
    (theorem_dir / "tiny.p").write_text("fof(tiny,conjecture,p).\n", encoding="utf-8")
    with tarfile.open(archive, "w:gz") as handle:
        handle.add(source_root, arcname="plcop-master")

    def fake_download_url(*args: object, **kwargs: object) -> Path:
        return archive

    monkeypatch.setattr(download, "download_url", fake_download_url)
    spec = download.corpus_lookup()["m2k"]
    assert isinstance(spec, download.ArchiveSubdirCorpus)

    archive_path = download.install_archive_subdir(
        spec,
        root=tmp_path / "benchmarks",
        archive_dir=tmp_path / ".downloads",
        force=False,
    )

    assert archive_path == archive
    assert (tmp_path / "benchmarks" / "m2k" / "tiny.p").exists()
    assert not (tmp_path / "benchmarks" / ".m2k.extracting").exists()
