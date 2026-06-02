import re
from pathlib import Path

from parser import iter_assets

GUID_RE = re.compile(r"^guid:\s+([a-f0-9]{32})", re.MULTILINE)


def build_guid_map(project_root: str) -> dict[str, str]:
    """Return {guid: relative_asset_path} for every .meta file found under Assets/."""
    root = Path(project_root)
    guid_map: dict[str, str] = {}

    for meta_file in iter_assets(project_root, ".meta"):
        try:
            text = meta_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        match = GUID_RE.search(text)
        if not match:
            continue

        guid = match.group(1)
        # The asset path is the .meta path without the .meta suffix
        asset_path = meta_file.with_suffix("")
        guid_map[guid] = str(asset_path.relative_to(root))

    return guid_map
