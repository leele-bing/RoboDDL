#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


ROOT = Path.cwd()
LOCAL_CONFERENCE_DIR = ROOT / "src" / "data" / "conference"
REPORT_DIR = ROOT / "reports"
UPSTREAM_TREE_URL = "https://api.github.com/repos/ccfddl/ccf-deadlines/git/trees/main?recursive=1"
UPSTREAM_RAW_BASE = "https://raw.githubusercontent.com/ccfddl/ccf-deadlines/main/"

TIMEZONE_OFFSETS = {
    "AoE": -12 * 60,
    "PST": -8 * 60,
    "PDT": -7 * 60,
    "EST": -5 * 60,
    "EDT": -4 * 60,
    "UTC": 0,
    "GMT": 0,
}


@dataclass
class YamlLine:
    indent: int
    content: str
    line_number: int


def strip_quotes(value: str) -> str:
    if value.startswith('"') and value.endswith('"'):
        return json.loads(value)
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    return value


def parse_scalar(raw: str) -> Any:
    value = raw.strip()
    if value in {"", "~", "null"}:
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return strip_quotes(value)
    if re.fullmatch(r"-?\d+(\.\d+)?", value):
        return float(value) if "." in value else int(value)
    return value


def split_key_value(content: str, line_number: int) -> tuple[str, str]:
    separator_index = content.find(":")
    if separator_index == -1:
        raise ValueError(f"Invalid YAML at line {line_number}: expected a key/value pair.")

    key = content[:separator_index].strip()
    remainder = content[separator_index + 1 :].strip()
    if not key:
        raise ValueError(f"Invalid YAML at line {line_number}: missing key name.")
    return key, remainder


def parse_block(lines: list[YamlLine], start_index: int, indent: int) -> tuple[Any, int]:
    line = lines[start_index] if start_index < len(lines) else None
    if line is None:
        raise ValueError("Invalid YAML: unexpected end of document.")
    if line.indent != indent:
        raise ValueError(
            f"Invalid YAML at line {line.line_number}: expected indent {indent}, got {line.indent}."
        )
    if line.content.startswith("- "):
        return parse_sequence(lines, start_index, indent)
    return parse_mapping(lines, start_index, indent)


def parse_key_value_line(
    lines: list[YamlLine], line_index: int, base_indent: int, content: str | None = None
) -> tuple[tuple[str, Any], int]:
    line = lines[line_index] if line_index < len(lines) else None
    if line is None:
        raise ValueError("Invalid YAML: missing mapping entry.")
    if content is None:
        content = line.content

    key, remainder = split_key_value(content, line.line_number)
    if remainder:
        return (key, parse_scalar(remainder)), line_index + 1

    next_line = lines[line_index + 1] if line_index + 1 < len(lines) else None
    if next_line is None or next_line.indent <= base_indent:
        return (key, None), line_index + 1

    value, next_index = parse_block(lines, line_index + 1, next_line.indent)
    return (key, value), next_index


def parse_mapping(lines: list[YamlLine], start_index: int, indent: int) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    current_index = start_index

    while current_index < len(lines):
        line = lines[current_index]
        if line.indent < indent:
            break
        if line.indent > indent:
            raise ValueError(
                f"Invalid YAML at line {line.line_number}: unexpected indent {line.indent} in mapping."
            )
        if line.content.startswith("- "):
            raise ValueError(
                f"Invalid YAML at line {line.line_number}: unexpected list item in mapping."
            )

        (key, value), next_index = parse_key_value_line(lines, current_index, indent)
        result[key] = value
        current_index = next_index

    return result, current_index


def parse_sequence(lines: list[YamlLine], start_index: int, indent: int) -> tuple[list[Any], int]:
    items: list[Any] = []
    current_index = start_index

    while current_index < len(lines):
        line = lines[current_index]
        if line.indent < indent:
            break
        if line.indent > indent:
            raise ValueError(
                f"Invalid YAML at line {line.line_number}: unexpected indent {line.indent} in list."
            )
        if not line.content.startswith("- "):
            break

        remainder = line.content[2:].strip()
        if not remainder:
            next_line = lines[current_index + 1] if current_index + 1 < len(lines) else None
            if next_line is None or next_line.indent <= indent:
                items.append(None)
                current_index += 1
                continue

            value, next_index = parse_block(lines, current_index + 1, next_line.indent)
            items.append(value)
            current_index = next_index
            continue

        if re.match(r"^[A-Za-z_][A-Za-z0-9_-]*\s*:", remainder):
            item: dict[str, Any] = {}
            mapping_index = current_index
            entry_content = remainder
            entry_indent = indent

            while True:
                (key, value), next_index = parse_key_value_line(
                    lines, mapping_index, entry_indent, entry_content
                )
                item[key] = value
                current_index = next_index

                continuation_line = lines[current_index] if current_index < len(lines) else None
                if continuation_line is None:
                    break
                if continuation_line.indent < indent + 2:
                    break
                if continuation_line.indent > indent + 2:
                    raise ValueError(
                        f"Invalid YAML at line {continuation_line.line_number}: unexpected indent "
                        f"{continuation_line.indent} in list item."
                    )
                if continuation_line.content.startswith("- "):
                    raise ValueError(
                        "Invalid YAML at line "
                        f"{continuation_line.line_number}: nested list entries must belong to a key."
                    )

                mapping_index = current_index
                entry_content = continuation_line.content
                entry_indent = indent + 2

            items.append(item)
            continue

        items.append(parse_scalar(remainder))
        current_index += 1

    return items, current_index


def parse_yaml_document(raw: str) -> Any:
    lines = []
    for index, line in enumerate(raw.splitlines(), start=1):
        indent = len(line) - len(line.lstrip(" "))
        content = line[indent:]
        trimmed = content.strip()
        if trimmed and not trimmed.startswith("#"):
            lines.append(YamlLine(indent=indent, content=content, line_number=index))

    if not lines:
        raise ValueError("Invalid YAML: document is empty.")

    document, next_index = parse_block(lines, 0, lines[0].indent)
    if next_index != len(lines):
        line = lines[next_index]
        raise ValueError(f"Invalid YAML at line {line.line_number}: trailing content was not parsed.")
    return document


def normalize_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def normalize_dblp(value: Any) -> str:
    return str(value or "").replace("conf/", "").strip().lower()


def timezone_offset_minutes(timezone_name: str) -> int:
    if timezone_name in TIMEZONE_OFFSETS:
        return TIMEZONE_OFFSETS[timezone_name]
    match = re.fullmatch(r"UTC([+-])(\d{1,2})(?::?(\d{2}))?", str(timezone_name))
    if not match:
        raise ValueError(f"Unsupported timezone: {timezone_name}")
    sign = 1 if match.group(1) == "+" else -1
    hours = int(match.group(2))
    minutes = int(match.group(3) or "0")
    return sign * (hours * 60 + minutes)


def parse_local_datetime(date_time: str) -> datetime:
    normalized = str(date_time).replace(" ", "T")
    return datetime.strptime(normalized, "%Y-%m-%dT%H:%M:%S")


def to_utc_ms(date_time: str, timezone_name: str) -> int:
    naive_dt = parse_local_datetime(date_time)
    offset = timedelta(minutes=timezone_offset_minutes(timezone_name))
    aware_dt = naive_dt.replace(tzinfo=timezone(offset))
    return int(aware_dt.astimezone(timezone.utc).timestamp() * 1000)


def format_as_iso_local(date_time: Any) -> str | None:
    if date_time is None:
        return None
    return str(date_time).replace(" ", "T")


def choose_timeline_entry(timeline: Any) -> dict[str, Any] | None:
    if not isinstance(timeline, list):
        return None
    for item in reversed(timeline):
        if isinstance(item, dict) and item.get("deadline") not in {None, "TBD"}:
            return item
    return None


def fetch_json(url: str) -> Any:
    request = Request(
        url,
        headers={
            "User-Agent": "RoboDDL deadline audit",
            "Accept": "application/vnd.github+json",
        },
    )
    with urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "RoboDDL deadline audit"})
    with urlopen(request) as response:
        return response.read().decode("utf-8")


def load_local_venues() -> list[dict[str, Any]]:
    venues = []
    for file_path in sorted(LOCAL_CONFERENCE_DIR.glob("*.yaml")):
        raw = file_path.read_text(encoding="utf-8")
        document = parse_yaml_document(raw)
        document["fileName"] = file_path.name
        document["filePath"] = str(file_path)
        venues.append(document)
    return venues


def build_candidate_keys(local_venue: dict[str, Any]) -> list[str]:
    keys = {
        str(local_venue.get("slug") or "").lower(),
        normalize_dblp(local_venue.get("dblp")),
        normalize_name(local_venue.get("title")),
    }
    title_aliases = {
        "neurips": ["nips"],
        "roman": ["roman", "ro-man"],
    }
    for alias in title_aliases.get(local_venue.get("slug"), []):
        keys.add(alias.lower())
        keys.add(normalize_name(alias))
    return [key for key in keys if key]


def load_upstream_candidate_documents(
    local_venues: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    tree = fetch_json(UPSTREAM_TREE_URL)
    conference_files = [
        entry["path"]
        for entry in tree["tree"]
        if re.fullmatch(r"conference/.+\.yml", entry["path"])
    ]

    by_base_name: dict[str, list[str]] = {}
    for relative_path in conference_files:
        base_name = Path(relative_path).stem.lower()
        by_base_name.setdefault(base_name, []).append(relative_path)

    candidate_paths: set[str] = set()
    for local_venue in local_venues:
        for key in build_candidate_keys(local_venue):
            for candidate in by_base_name.get(key, []):
                candidate_paths.add(candidate)

    documents = []
    for relative_path in sorted(candidate_paths):
        raw = fetch_text(f"{UPSTREAM_RAW_BASE}{relative_path}")
        document = parse_yaml_document(raw)
        items = document if isinstance(document, list) else [document]
        for item in items:
            item["relativePath"] = relative_path
            documents.append(item)

    return documents, sorted(candidate_paths)


def match_upstream_venue(
    local_venue: dict[str, Any], upstream_documents: list[dict[str, Any]]
) -> dict[str, Any] | None:
    local_title = normalize_name(local_venue.get("title"))
    local_dblp = normalize_dblp(local_venue.get("dblp"))
    local_keys = {normalize_name(key) for key in build_candidate_keys(local_venue)}

    best_document = None
    best_score = 0
    for document in upstream_documents:
        upstream_title = normalize_name(document.get("title"))
        upstream_dblp = normalize_dblp(document.get("dblp"))
        base_name = normalize_name(Path(document["relativePath"]).stem)
        score = 0

        if local_dblp and upstream_dblp and local_dblp == upstream_dblp:
            score += 5
        if local_title and upstream_title and local_title == upstream_title:
            score += 4
        if base_name in local_keys:
            score += 3
        if upstream_dblp in local_keys or upstream_title in local_keys:
            score += 2

        if score > best_score:
            best_document = document
            best_score = score

    return best_document


def detect_local_suspicion(local_venue: dict[str, Any]) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = []
    known_editions = local_venue.get("knownEditions") or []
    abstract_map: dict[str, list[int]] = {}
    paper_map: dict[str, list[int]] = {}

    for edition in known_editions:
        abstract_deadline = edition.get("abstractDeadline")
        if abstract_deadline:
            abstract_map.setdefault(str(abstract_deadline), []).append(edition["year"])

        paper_key = f'{edition.get("paperDeadline")}|{edition.get("timezone")}'
        paper_map.setdefault(paper_key, []).append(edition["year"])

        if edition.get("conferenceDates") == "TBA" or edition.get("location") == "TBA":
            reasons.append(
                {
                    "type": "tba_metadata",
                    "year": edition["year"],
                    "message": "conferenceDates 或 location 仍为 TBA",
                }
            )

    for deadline, years in abstract_map.items():
        if len(years) > 1:
            reasons.append(
                {
                    "type": "reused_abstract_deadline",
                    "years": years,
                    "message": f"abstractDeadline {deadline} 被重复用于多个年份",
                }
            )

    for deadline, years in paper_map.items():
        if len(years) > 1:
            reasons.append(
                {
                    "type": "reused_paper_deadline",
                    "years": years,
                    "message": f"paperDeadline {deadline} 被重复用于多个年份",
                }
            )

    return reasons


def compare_venue(
    local_venue: dict[str, Any], upstream_venue: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[int]]:
    upstream_confs = upstream_venue.get("confs") or []
    upstream_by_year = {conf["year"]: conf for conf in upstream_confs}
    local_editions = local_venue.get("knownEditions") or []
    matches = []
    mismatches = []
    missing_upstream_years = []

    for edition in local_editions:
        upstream_conf = upstream_by_year.get(edition["year"])
        if upstream_conf is None:
            missing_upstream_years.append(edition["year"])
            continue

        timeline_entry = choose_timeline_entry(upstream_conf.get("timeline"))
        if timeline_entry is None:
            missing_upstream_years.append(edition["year"])
            continue

        local_paper_iso = format_as_iso_local(edition.get("paperDeadline"))
        upstream_paper_iso = format_as_iso_local(timeline_entry.get("deadline"))
        local_paper_utc_ms = to_utc_ms(local_paper_iso, edition["timezone"])
        upstream_paper_utc_ms = to_utc_ms(upstream_paper_iso, upstream_conf["timezone"])

        local_abstract_iso = format_as_iso_local(edition.get("abstractDeadline"))
        upstream_abstract_iso = format_as_iso_local(timeline_entry.get("abstract_deadline"))
        local_abstract_utc_ms = (
            to_utc_ms(local_abstract_iso, edition["timezone"]) if local_abstract_iso else None
        )
        upstream_abstract_utc_ms = (
            to_utc_ms(upstream_abstract_iso, upstream_conf["timezone"]) if upstream_abstract_iso else None
        )

        differing_fields = []
        if local_paper_utc_ms != upstream_paper_utc_ms:
            differing_fields.append("paperDeadline")
        if local_abstract_utc_ms != upstream_abstract_utc_ms:
            if not (local_abstract_utc_ms is None and upstream_abstract_utc_ms is None):
                differing_fields.append("abstractDeadline")

        record = {
            "year": edition["year"],
            "local": {
                "title": local_venue["title"],
                "fileName": local_venue["fileName"],
                "paperDeadline": local_paper_iso,
                "abstractDeadline": local_abstract_iso,
                "timezone": edition["timezone"],
                "link": edition.get("link"),
            },
            "upstream": {
                "title": upstream_venue["title"],
                "path": upstream_venue["relativePath"],
                "paperDeadline": upstream_paper_iso,
                "abstractDeadline": upstream_abstract_iso,
                "timezone": upstream_conf["timezone"],
                "link": upstream_conf.get("link"),
            },
            "sameAbsolutePaperDeadline": local_paper_utc_ms == upstream_paper_utc_ms,
            "sameAbsoluteAbstractDeadline": local_abstract_utc_ms == upstream_abstract_utc_ms,
            "paperDifferenceHours": (local_paper_utc_ms - upstream_paper_utc_ms) / 3600000,
            "abstractDifferenceHours": (
                (local_abstract_utc_ms - upstream_abstract_utc_ms) / 3600000
                if local_abstract_utc_ms is not None and upstream_abstract_utc_ms is not None
                else None
            ),
            "differingFields": differing_fields,
        }

        if differing_fields:
            mismatches.append(record)
        else:
            matches.append(record)

    return matches, mismatches, missing_upstream_years


def build_markdown_report(results: dict[str, Any]) -> str:
    lines = [
        "# CCFDDL Deadline Audit",
        "",
        f'- Audit time: {datetime.now(timezone.utc).isoformat()}',
        f'- Local conference files: {results["summary"]["localConferenceCount"]}',
        f'- Matched upstream venues: {results["summary"]["matchedVenueCount"]}',
        f'- Unmatched local venues: {results["summary"]["unmatchedVenueCount"]}',
        f'- Matching editions: {results["summary"]["matchingEditionCount"]}',
        f'- Mismatching editions: {results["summary"]["mismatchingEditionCount"]}',
        "",
        "## Unmatched Local Venues",
        "",
    ]

    if not results["unmatchedLocalVenues"]:
        lines.append("- None")
    else:
        for venue in results["unmatchedLocalVenues"]:
            lines.append(f'- {venue["title"]} ({venue["fileName"]})')

    lines.extend(["", "## Mismatching Editions", ""])
    if not results["mismatches"]:
        lines.append("- None")
    else:
        for mismatch in results["mismatches"]:
            lines.append(
                f'- {mismatch["local"]["title"]} {mismatch["year"]}: local '
                f'{mismatch["local"]["paperDeadline"]} {mismatch["local"]["timezone"]}, upstream '
                f'{mismatch["upstream"]["paperDeadline"]} {mismatch["upstream"]["timezone"]}; '
                f'differingFields={", ".join(mismatch["differingFields"])}'
            )

    lines.extend(["", "## Suspicious Local Entries", ""])
    if not results["suspiciousLocalVenues"]:
        lines.append("- None")
    else:
        for venue in results["suspiciousLocalVenues"]:
            details = "; ".join(reason["message"] for reason in venue["reasons"])
            lines.append(f'- {venue["title"]} ({venue["fileName"]}): {details}')

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    local_venues = load_local_venues()
    upstream_documents, candidate_paths = load_upstream_candidate_documents(local_venues)

    matched_venues = []
    unmatched_local_venues = []
    mismatches = []
    matches = []
    suspicious_local_venues = []

    for local_venue in local_venues:
        suspicion = detect_local_suspicion(local_venue)
        if suspicion:
            suspicious_local_venues.append(
                {
                    "title": local_venue["title"],
                    "fileName": local_venue["fileName"],
                    "reasons": suspicion,
                }
            )

        upstream_venue = match_upstream_venue(local_venue, upstream_documents)
        if upstream_venue is None:
            unmatched_local_venues.append(
                {
                    "title": local_venue["title"],
                    "fileName": local_venue["fileName"],
                    "slug": local_venue.get("slug"),
                    "dblp": local_venue.get("dblp"),
                }
            )
            continue

        venue_matches, venue_mismatches, missing_upstream_years = compare_venue(
            local_venue, upstream_venue
        )
        matched_venues.append(
            {
                "local": {
                    "title": local_venue["title"],
                    "fileName": local_venue["fileName"],
                },
                "upstream": {
                    "title": upstream_venue["title"],
                    "path": upstream_venue["relativePath"],
                },
                "missingUpstreamYears": missing_upstream_years,
                "matchCount": len(venue_matches),
                "mismatchCount": len(venue_mismatches),
            }
        )
        matches.extend(venue_matches)
        mismatches.extend(venue_mismatches)

    results = {
        "summary": {
            "localConferenceCount": len(local_venues),
            "matchedVenueCount": len(matched_venues),
            "unmatchedVenueCount": len(unmatched_local_venues),
            "matchingEditionCount": len(matches),
            "mismatchingEditionCount": len(mismatches),
            "fetchedUpstreamCandidateFiles": len(candidate_paths),
        },
        "matchedVenues": matched_venues,
        "unmatchedLocalVenues": unmatched_local_venues,
        "matches": matches,
        "mismatches": mismatches,
        "suspiciousLocalVenues": suspicious_local_venues,
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_DIR / "ccfddl-deadline-audit.json"
    md_path = REPORT_DIR / "ccfddl-deadline-audit.md"
    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(build_markdown_report(results), encoding="utf-8")

    print(f"Wrote {json_path.relative_to(ROOT)}")
    print(f"Wrote {md_path.relative_to(ROOT)}")
    print(
        json.dumps(
            {
                "summary": results["summary"],
                "unmatchedLocalVenues": [venue["title"] for venue in unmatched_local_venues],
                "mismatches": [
                    {
                        "title": mismatch["local"]["title"],
                        "year": mismatch["year"],
                        "differingFields": mismatch["differingFields"],
                    }
                    for mismatch in mismatches
                ],
            },
            indent=2,
            ensure_ascii=False,
        )
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
