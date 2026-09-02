from pathlib import Path


def resolve_library_root(value: str) -> Path:
    root = Path(value).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"library path is not an existing directory: {root}")
    return root


def normalize_local_path(library_root: Path, value: str | None) -> str:
    if value is None or not value.strip():
        return ""

    supplied = Path(value).expanduser()
    target = supplied.resolve() if supplied.is_absolute() else (library_root / supplied).resolve()
    try:
        relative = target.relative_to(library_root)
    except ValueError as error:
        raise ValueError("local_path must be inside the selected library") from error
    if not target.exists():
        raise ValueError(f"local_path does not exist: {target}")
    return relative.as_posix()


def absolute_local_path(library_root: Path, value: str | None) -> str:
    if not value:
        return ""
    return str((library_root / Path(value)).resolve())
