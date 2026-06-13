from __future__ import annotations

import argparse
import csv
import hashlib
import re
from dataclasses import asdict, dataclass
from pathlib import Path


SUPPORTED_EXTS = {".pdf", ".docx"}
EXCLUDED_DIRS = {".git", ".agents", ".codex", "rename_work"}

TAG_TRANSLATION_RESULT = "（翻译结果）"
TAG_TRANSLATED = "（译文）"
TAG_BILINGUAL = "（双语）"
TAG_CHINESE = "（中文版）"

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None

try:
    from docx import Document
except Exception:  # pragma: no cover
    Document = None


@dataclass
class PlanRow:
    index: int
    original_name: str
    final_name: str
    needs_review: bool
    title_source: str
    reason: str
    extension: str
    size_bytes: int
    sha1: str
    original_path: str
    final_path: str


def one_line(value: str | None) -> str:
    if not value:
        return ""
    value = value.replace("\x00", " ").replace("\xa0", " ").replace("\ufeff", "")
    return re.sub(r"\s+", " ", value).strip(" .\t\r\n")


def keyify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"\(翻译结果\)", "", value)
    value = re.sub(r"(_|-)?translated$", "", value)
    value = re.sub(r"(_|-)?billingual$", "", value)
    value = re.sub(r"(_|-)?bilingual$", "", value)
    value = re.sub(r"(_|-)?compress$", "", value)
    value = re.sub(r"(_|-)?main$", "", value)
    value = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def strip_variant(stem: str) -> str:
    value = re.sub(r"\(翻译结果\)", "", stem)
    value = re.sub(r"(_|-)?translated$", "", value, flags=re.I)
    value = re.sub(r"(_|-)?billingual$", "", value, flags=re.I)
    value = re.sub(r"(_|-)?bilingual$", "", value, flags=re.I)
    value = re.sub(r"(_|-)?compress$", "", value, flags=re.I)
    value = re.sub(r"(_|-)?main$", "", value, flags=re.I)
    return value


def detect_variant(path: Path) -> str:
    stem = path.stem
    lower = stem.lower()
    tags: list[str] = []
    if "翻译结果" in stem:
        tags.append(TAG_TRANSLATION_RESULT)
    elif "translated" in lower:
        tags.append(TAG_TRANSLATED)
    if "billingual" in lower or "bilingual" in lower:
        tags.append(TAG_BILINGUAL)
    if "中文版" in stem:
        tags.append(TAG_CHINESE)
    return "".join(tags)


def is_identifierish(stem: str) -> bool:
    key = keyify(stem)
    patterns = [
        r"^ssrn(?: id)? \d+",
        r"^\d+[\d a-z.-]*$",
        r"^10 \d+",
        r"^1 s2 0 ",
        r"^s\d{5}",
        r"^[a-z]{2,}\d{2,}",
        r"^jgad\d+",
        r"^pone \d+",
    ]
    weak = {"re", "precedent", "precednet", "originalism", "unleashed"}
    return key in weak or any(re.search(pattern, key) for pattern in patterns)


def clean_filename_title(path: Path) -> str:
    stem = strip_variant(path.stem).replace("_", " ")
    stem = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    if stem.islower():
        small = {"and", "or", "of", "the", "in", "on", "at", "to", "for", "with", "as", "by", "from"}
        words = []
        for i, word in enumerate(stem.split()):
            words.append(word if i and word in small else word[:1].upper() + word[1:])
        stem = " ".join(words)
    return stem


def sanitize_stem(value: str) -> str:
    value = value.replace("：", " - ").replace("？", "")
    value = value.replace("“", "").replace("”", "")
    value = value.replace("‘", "").replace("’", "'")
    value = re.sub(r"[<>:\"/\\|?*]", " - ", value)
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"\s+-\s+", " - ", value)
    value = value.strip(" .-")
    return (value[:170].rstrip(" .-") if len(value) > 170 else value) or "untitled"


def looks_boilerplate(value: str) -> bool:
    lower = value.lower()
    markers = [
        "electronic copy available",
        "content downloaded",
        "heinonline",
        "license agreement",
        "search text of this pdf",
        "qr code",
        "abstract",
        "keywords",
        "available online",
        "doi:",
        "ssrn.com",
        "journal of",
        "volume",
    ]
    return any(marker in lower for marker in markers)


def metadata_title(path: Path) -> tuple[str, str]:
    try:
        if path.suffix.lower() == ".pdf" and PdfReader is not None:
            reader = PdfReader(str(path))
            metadata = reader.metadata or {}
            title = one_line(getattr(metadata, "title", "") or metadata.get("/Title", ""))
        elif path.suffix.lower() == ".docx" and Document is not None:
            doc = Document(str(path))
            title = one_line(doc.core_properties.title)
        else:
            title = ""
    except Exception:
        title = ""
    lower = title.lower()
    if not title or looks_boilerplate(title) or "microsoft word" in lower or ".doc" in lower or ".wpd" in lower:
        return "", ""
    if ".." in title or re.fullmatch(r"[A-Z]{2,}\d+[A-Z0-9 ._-]*", title):
        return "", ""
    if re.fullmatch(r"[A-Za-z0-9_. -]{4,24}", title) and re.search(r"\d", title):
        return "", ""
    if len(title) < 8 or len(title) > 180:
        return "", ""
    return title, "metadata"


def load_overrides(path: Path | None) -> tuple[dict[str, str], dict[str, str]]:
    by_name: dict[str, str] = {}
    by_key: dict[str, str] = {}
    if not path or not path.exists():
        return by_name, by_key
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            final_name = one_line(row.get("final_name"))
            title = one_line(row.get("title"))
            value = final_name or title
            if not value:
                continue
            if row.get("original_name"):
                by_name[row["original_name"].lower()] = value
            if row.get("key"):
                by_key[keyify(row["key"])] = value
    return by_name, by_key


def iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in EXCLUDED_DIRS for part in rel.parts):
            continue
        if path.suffix.lower() in SUPPORTED_EXTS:
            files.append(path)
    return sorted(files, key=lambda p: str(p).lower())


def sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def unique_name(proposed: str, used: set[str]) -> str:
    stem = Path(proposed).stem
    suffix = Path(proposed).suffix
    candidate = proposed
    counter = 2
    while candidate.lower() in used:
        candidate = f"{stem} ({counter}){suffix}"
        counter += 1
    used.add(candidate.lower())
    return candidate


def choose_title(path: Path, by_name: dict[str, str], by_key: dict[str, str]) -> tuple[str, str, bool, str]:
    key = keyify(strip_variant(path.stem))
    override = by_name.get(path.name.lower()) or by_key.get(key)
    if override:
        return override, "override", False, ""
    meta, source = metadata_title(path)
    if meta and is_identifierish(path.stem):
        return meta, source, False, ""
    if is_identifierish(path.stem):
        return clean_filename_title(path), "filename", True, "cryptic filename needs title confirmation"
    return clean_filename_title(path), "filename", False, ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Folder containing literature files.")
    parser.add_argument("--out-dir", default=None, help="Output folder. Defaults to <root>/rename_work.")
    parser.add_argument("--overrides", default=None, help="Optional CSV with original_name/key/title/final_name columns.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    out_dir = Path(args.out_dir).resolve() if args.out_dir else root / "rename_work"
    out_dir.mkdir(parents=True, exist_ok=True)
    by_name, by_key = load_overrides(Path(args.overrides).resolve() if args.overrides else None)

    rows: list[PlanRow] = []
    used_by_parent: dict[Path, set[str]] = {}
    for index, path in enumerate(iter_files(root), start=1):
        title, source, needs_review, reason = choose_title(path, by_name, by_key)
        variant = detect_variant(path)
        if Path(title).suffix.lower() in SUPPORTED_EXTS:
            final_name = sanitize_stem(Path(title).stem) + Path(title).suffix.lower()
        else:
            final_name = sanitize_stem(f"{title}{variant}") + path.suffix.lower()
        used = used_by_parent.setdefault(path.parent.resolve(), set())
        final_name = unique_name(final_name, used)
        rows.append(
            PlanRow(
                index=index,
                original_name=path.name,
                final_name=final_name,
                needs_review=needs_review,
                title_source=source,
                reason=reason,
                extension=path.suffix.lower(),
                size_bytes=path.stat().st_size,
                sha1=sha1_file(path),
                original_path=str(path),
                final_path=str(path.with_name(final_name)),
            )
        )

    csv_path = out_dir / "literature_rename_plan.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(rows[0]).keys()) if rows else [])
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

    review_path = out_dir / "literature_rename_review.csv"
    with review_path.open("w", encoding="utf-8-sig", newline="") as handle:
        review_rows = [row for row in rows if row.needs_review]
        writer = csv.DictWriter(handle, fieldnames=list(asdict(rows[0]).keys()) if rows else [])
        writer.writeheader()
        for row in review_rows:
            writer.writerow(asdict(row))

    print(f"total={len(rows)}")
    print(f"needs_review={sum(1 for row in rows if row.needs_review)}")
    print(f"plan={csv_path}")
    print(f"review={review_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
