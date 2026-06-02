import re
from dataclasses import dataclass, field
from pathlib import Path

USING_RE = re.compile(r"^\s*using\s+([\w.]+)\s*;", re.MULTILINE)

# Matches: class Foo : BaseClass, IInterface { ... }
CLASS_RE = re.compile(
    r"\bclass\s+(\w+)"
    r"(?:\s*:\s*([\w<>.\[\],\s]+?))?(?=\s*(?:\{|where\b))",
    re.MULTILINE,
)

# Matches [SerializeField] on same line or line(s) above the field declaration.
# Handles blank lines and // comments between attribute and field.
SERIALIZE_FIELD_RE = re.compile(
    r"\[(?:[^\]]*,\s*)?SerializeField(?:\s*,[^\]]*)?\]"
    r"(?:[ \t]*(?://[^\n]*)?\n)*[ \t]*"  # skip blank/comment lines + leading whitespace
    r"(?:(?:private|public|protected|internal|readonly|static|override|virtual|new)\s+)*"
    r"([\w<>\[\]., \t]+?)\s+"  # type: horizontal whitespace only (handles generics)
    r"(\w+)\s*(?:;|=|\{)",
)


@dataclass
class ScriptInfo:
    file_path: str
    class_name: str | None
    base_class: str | None
    interfaces: list[str] = field(default_factory=list)
    usings: list[str] = field(default_factory=list)
    serialize_fields: list[dict] = field(default_factory=list)


def _split_top_level(s: str) -> list[str]:
    """Split on commas that are not inside angle brackets (handles generic types)."""
    parts, depth, current = [], 0, []
    for ch in s:
        if ch == "<":
            depth += 1
            current.append(ch)
        elif ch == ">":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current).strip())
    return [p for p in parts if p]


def _parse_inheritance(raw: str | None) -> tuple[str | None, list[str]]:
    if not raw:
        return None, []
    parts = _split_top_level(raw)
    if not parts:
        return None, []
    return parts[0], parts[1:]


def parse_script(file_path: str, source: str) -> ScriptInfo:
    usings = USING_RE.findall(source)

    class_match = CLASS_RE.search(source)
    class_name = class_match.group(1) if class_match else None
    base_class, interfaces = _parse_inheritance(
        class_match.group(2) if class_match else None
    )

    serialize_fields = [
        {"type": m.group(1).strip(), "name": m.group(2)}
        for m in SERIALIZE_FIELD_RE.finditer(source)
    ]

    return ScriptInfo(
        file_path=file_path,
        class_name=class_name,
        base_class=base_class,
        interfaces=interfaces,
        usings=usings,
        serialize_fields=serialize_fields,
    )


def parse_scripts(project_root: str) -> list[ScriptInfo]:
    root = Path(project_root)
    results = []
    for cs_file in root.rglob("*.cs"):
        try:
            source = cs_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel_path = str(cs_file.relative_to(root))
        results.append(parse_script(rel_path, source))
    return results
