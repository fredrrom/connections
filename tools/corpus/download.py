#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import urllib.request

DEFAULT_ROOT = Path("benchmarks")
CHUNK_SIZE = 1024 * 1024
PROGRESS_STEP = 64 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ArchiveCorpus:
    name: str
    target_dir: str
    url: str
    archive_name: str
    extracted_dir: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GitCorpus:
    name: str
    target_dir: str
    url: str
    branch: str = "master"
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ArchiveSubdirCorpus:
    name: str
    target_dir: str
    url: str
    archive_name: str
    extracted_dir: str
    source_subdirs: tuple[str, ...]
    aliases: tuple[str, ...] = ()


Corpus = ArchiveCorpus | GitCorpus | ArchiveSubdirCorpus


CORPORA: tuple[Corpus, ...] = (
    ArchiveCorpus(
        name="tptp-v9.2.1",
        aliases=("tptp", "tptp-current", "tptp921"),
        target_dir="TPTP-v9.2.1",
        url="https://tptp.org/TPTP/Distribution/TPTP-v9.2.1.tgz",
        archive_name="TPTP-v9.2.1.tgz",
        extracted_dir="TPTP-v9.2.1",
    ),
    ArchiveCorpus(
        name="tptp-v6.4.0",
        aliases=("tptp6", "tptp640"),
        target_dir="TPTP-v6.4.0",
        url="https://tptp.org/TPTP/Archive/TPTP-v6.4.0.tgz",
        archive_name="TPTP-v6.4.0.tgz",
        extracted_dir="TPTP-v6.4.0",
    ),
    ArchiveCorpus(
        name="iltp",
        aliases=("iltp-firstorder", "iltp-v1.1.2-firstorder"),
        target_dir="ILTP-v1.1.2-firstorder",
        url="https://www.iltp.de/download/ILTP-v1.1.2-firstorder.tar.gz",
        archive_name="ILTP-v1.1.2-firstorder.tar.gz",
        extracted_dir="ILTP-v1.1.2-firstorder",
    ),
    ArchiveCorpus(
        name="qmltp",
        aliases=("qmltp-v1.1",),
        target_dir="QMLTP-v1.1",
        url="https://www.iltp.de/qmltp/download/QMLTP-v1.1.tar.gz",
        archive_name="QMLTP-v1.1.tar.gz",
        extracted_dir="QMLTP-v1.1",
    ),
    GitCorpus(
        name="deepmath",
        target_dir="deepmath",
        url="https://github.com/JUrban/deepmath.git",
    ),
    GitCorpus(
        name="mtptp",
        aliases=("mptp", "mptp2078", "mptp2078b"),
        target_dir="mtptp",
        url="https://github.com/JUrban/MPTP2078.git",
    ),
    ArchiveSubdirCorpus(
        name="m2k",
        aliases=("m2np",),
        target_dir="m2k",
        url="https://codeload.github.com/zsoltzombori/plcop/tar.gz/refs/heads/master",
        archive_name="plcop-master.tar.gz",
        extracted_dir="plcop-master",
        source_subdirs=("theorems/m2np", "theorems/m2k"),
    ),
)


def build_parser() -> argparse.ArgumentParser:
    names = ", ".join(spec.name for spec in CORPORA)
    parser = argparse.ArgumentParser(
        description="Download benchmark corpora used by connections diagnostics.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "corpora",
        nargs="*",
        metavar="NAME",
        help=f"Corpora to download. Known names: {names}",
    )
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=None,
        help="Directory for downloaded archives. Defaults to ROOT/.downloads.",
    )
    parser.add_argument("--all", action="store_true", help="Download every corpus.")
    parser.add_argument("--list", action="store_true", help="List corpora and exit.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace existing target directories and cached archives.",
    )
    parser.add_argument(
        "--keep-archives",
        action="store_true",
        help="Keep downloaded archives after extraction.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    lookup = corpus_lookup()

    if args.list:
        print_corpora()
        return 0

    selected = select_corpora(args.corpora, all_corpora=args.all, lookup=lookup)
    root = args.root.expanduser().resolve()
    archive_dir = (
        args.archive_dir.expanduser().resolve()
        if args.archive_dir is not None
        else root / ".downloads"
    )
    root.mkdir(parents=True, exist_ok=True)

    for spec in selected:
        install_corpus(
            spec,
            root=root,
            archive_dir=archive_dir,
            force=args.force,
            keep_archives=args.keep_archives,
        )
    return 0


def corpus_lookup() -> dict[str, Corpus]:
    lookup: dict[str, Corpus] = {}
    for spec in CORPORA:
        for key in (spec.name, *spec.aliases):
            normalized = normalize_name(key)
            if normalized in lookup:
                raise RuntimeError(f"duplicate corpus key: {key}")
            lookup[normalized] = spec
    return lookup


def normalize_name(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def print_corpora() -> None:
    for spec in CORPORA:
        aliases = f" (aliases: {', '.join(spec.aliases)})" if spec.aliases else ""
        print(f"{spec.name}: {spec.target_dir}{aliases}")


def select_corpora(
    names: Sequence[str],
    *,
    all_corpora: bool,
    lookup: dict[str, Corpus],
) -> tuple[Corpus, ...]:
    if all_corpora:
        return CORPORA
    if not names:
        raise SystemExit("select at least one corpus, or pass --all")

    selected: list[Corpus] = []
    seen: set[str] = set()
    for name in names:
        key = normalize_name(name)
        if key not in lookup:
            known = ", ".join(sorted(lookup))
            raise SystemExit(f"unknown corpus {name!r}; known names: {known}")
        spec = lookup[key]
        if spec.name in seen:
            continue
        selected.append(spec)
        seen.add(spec.name)
    return tuple(selected)


def install_corpus(
    spec: Corpus,
    *,
    root: Path,
    archive_dir: Path,
    force: bool,
    keep_archives: bool,
) -> None:
    if isinstance(spec, ArchiveCorpus):
        archive_path = install_archive(
            spec,
            root=root,
            archive_dir=archive_dir,
            force=force,
        )
        if archive_path is not None:
            cleanup_archive(archive_path, keep=keep_archives)
        return
    if isinstance(spec, GitCorpus):
        install_git(spec, root=root, force=force)
        return
    archive_path = install_archive_subdir(
        spec,
        root=root,
        archive_dir=archive_dir,
        force=force,
    )
    if archive_path is not None:
        cleanup_archive(archive_path, keep=keep_archives)


def install_archive(
    spec: ArchiveCorpus,
    *,
    root: Path,
    archive_dir: Path,
    force: bool,
) -> Path | None:
    target = root / spec.target_dir
    if should_skip(spec.name, target, force=force):
        return None

    archive_path = download_url(
        spec.url,
        archive_dir / spec.archive_name,
        force=force,
        label=spec.name,
    )
    staging, extracted = extract_to_staging(
        archive_path,
        root=root,
        label=spec.name,
        expected_dir=spec.extracted_dir,
    )
    try:
        replace_with_extracted(extracted, target, root=root)
        print(f"{spec.name}: installed {target}")
    finally:
        remove_path(staging, root=root)
    return archive_path


def install_archive_subdir(
    spec: ArchiveSubdirCorpus,
    *,
    root: Path,
    archive_dir: Path,
    force: bool,
) -> Path | None:
    target = root / spec.target_dir
    if should_skip(spec.name, target, force=force):
        return None

    archive_path = download_url(
        spec.url,
        archive_dir / spec.archive_name,
        force=force,
        label=spec.name,
    )
    staging, extracted = extract_to_staging(
        archive_path,
        root=root,
        label=spec.name,
        expected_dir=spec.extracted_dir,
    )
    try:
        source = first_existing_subdir(extracted, spec.source_subdirs)
        if target.exists():
            remove_path(target, root=root)
        shutil.copytree(source, target)
        print(f"{spec.name}: installed {target} from {source.relative_to(extracted)}")
    finally:
        remove_path(staging, root=root)
    return archive_path


def install_git(spec: GitCorpus, *, root: Path, force: bool) -> None:
    target = root / spec.target_dir
    if should_skip(spec.name, target, force=force):
        return
    if shutil.which("git") is None:
        raise SystemExit(f"{spec.name}: git is required to clone {spec.url}")
    if target.exists():
        remove_path(target, root=root)

    print(f"{spec.name}: cloning {spec.url} into {target}")
    run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            spec.branch,
            spec.url,
            str(target),
        ]
    )
    print(f"{spec.name}: installed {target}")


def should_skip(name: str, target: Path, *, force: bool) -> bool:
    if target.exists() and is_nonempty_dir(target) and not force:
        print(f"{name}: already present at {target}")
        return True
    return False


def is_nonempty_dir(path: Path) -> bool:
    return path.is_dir() and any(path.iterdir())


def download_url(url: str, target: Path, *, force: bool, label: str) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size > 0 and not force:
        print(f"{label}: using cached archive {target}")
        return target

    partial = target.with_name(f"{target.name}.part")
    if partial.exists():
        partial.unlink()

    print(f"{label}: downloading {url}")
    with urllib.request.urlopen(url) as response, partial.open("wb") as handle:
        expected = int(response.headers.get("Content-Length") or 0)
        copied = 0
        next_report = PROGRESS_STEP
        while True:
            chunk = response.read(CHUNK_SIZE)
            if not chunk:
                break
            handle.write(chunk)
            copied += len(chunk)
            if copied >= next_report:
                print_progress(label, copied, expected)
                next_report += PROGRESS_STEP

    partial.replace(target)
    print(f"{label}: wrote {target} ({format_bytes(target.stat().st_size)})")
    return target


def print_progress(label: str, copied: int, expected: int) -> None:
    if expected:
        print(f"{label}: downloaded {format_bytes(copied)} / {format_bytes(expected)}")
    else:
        print(f"{label}: downloaded {format_bytes(copied)}")


def extract_to_staging(
    archive_path: Path,
    *,
    root: Path,
    label: str,
    expected_dir: str,
) -> tuple[Path, Path]:
    staging = root / f".{label}.extracting"
    if staging.exists():
        remove_path(staging, root=root)
    staging.mkdir(parents=True)

    print(f"{label}: extracting {archive_path}")
    with tarfile.open(archive_path) as archive:
        safe_extract(archive, staging)

    extracted = staging / expected_dir
    if extracted.exists():
        return staging, extracted

    top_level_dirs = [path for path in staging.iterdir() if path.is_dir()]
    if len(top_level_dirs) == 1:
        return staging, top_level_dirs[0]

    found = ", ".join(path.name for path in staging.iterdir())
    raise RuntimeError(
        f"{label}: expected extracted directory {expected_dir!r}; found: {found}"
    )


def safe_extract(archive: tarfile.TarFile, destination: Path) -> None:
    try:
        archive.extractall(destination, filter="data")
    except TypeError:
        safe_extract_legacy(archive, destination)


def safe_extract_legacy(archive: tarfile.TarFile, destination: Path) -> None:
    destination = destination.resolve()
    for member in archive.getmembers():
        member_path = (destination / member.name).resolve()
        if not is_relative_to(member_path, destination):
            raise RuntimeError(f"refusing to extract unsafe path: {member.name}")
        if member.isdev():
            raise RuntimeError(f"refusing to extract device file: {member.name}")
        if member.issym() or member.islnk():
            link_target = Path(member.linkname)
            if link_target.is_absolute():
                raise RuntimeError(f"refusing to extract absolute link: {member.name}")
            resolved_target = (member_path.parent / link_target).resolve()
            if not is_relative_to(resolved_target, destination):
                raise RuntimeError(f"refusing to extract unsafe link: {member.name}")
    archive.extractall(destination)


def replace_with_extracted(extracted: Path, target: Path, *, root: Path) -> None:
    if target.exists():
        remove_path(target, root=root)
    shutil.move(str(extracted), str(target))


def first_existing_subdir(root: Path, candidates: Iterable[str]) -> Path:
    for candidate in candidates:
        path = root / candidate
        if path.is_dir():
            return path
    tried = ", ".join(candidates)
    raise RuntimeError(f"none of the expected source directories exist: {tried}")


def cleanup_archive(archive_path: Path, *, keep: bool) -> None:
    if keep or not archive_path.exists():
        return
    archive_path.unlink()


def remove_path(path: Path, *, root: Path) -> None:
    resolved = path.resolve()
    if not is_relative_to(resolved, root.resolve()):
        raise RuntimeError(f"refusing to remove path outside corpus root: {path}")
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def run(args: Sequence[str]) -> None:
    subprocess.run(args, check=True)


def format_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.1f} {unit}"
        value /= 1024
    raise AssertionError("unreachable")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        raise SystemExit(130)
