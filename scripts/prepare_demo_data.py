#!/usr/bin/env python3
"""Create a small demo dataset from the full compressed datasets.

The full IoT-Zoo repository stores device datasets inside the corresponding
`devices/<profile>/` folders, usually compressed as `.csv.xz`. This utility
extracts only a small number of rows from the Urban Observatory datasets needed
by `demo_experiment.py` and writes them to `sample_data/urban_observatory/`.

It does not modify the original datasets.
"""

from __future__ import annotations

import argparse
import csv
import fnmatch
import lzma
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
URBAN_ROOT = PROJECT_ROOT / "devices" / "urban_observatory"
OUTPUT_ROOT = PROJECT_ROOT / "sample_data" / "urban_observatory"


@dataclass(frozen=True)
class DemoSource:
    label: str
    variable: str
    output_subdir: str
    preferred_patterns: Sequence[str]
    fallback_patterns: Sequence[str] = ()


DEMO_SOURCES: tuple[DemoSource, ...] = (
    DemoSource(
        label="CO air-quality telemetry",
        variable="CO",
        output_subdir="air_quality",
        preferred_patterns=("2025-CO.csv.xz", "2025-CO.csv", "*-CO.csv.xz", "*-CO.csv"),
    ),
    DemoSource(
        label="NO2 air-quality telemetry",
        variable="NO2",
        output_subdir="air_quality",
        preferred_patterns=("2025-NO2.csv.xz", "2025-NO2.csv", "*NO2*.csv.xz", "*NO2*.csv"),
    ),
    DemoSource(
        label="Internal Temperature building telemetry",
        variable="Internal Temperature",
        output_subdir="building",
        preferred_patterns=(
            "*Internal*Temperature*.csv.xz",
            "*Internal*Temperature*.csv",
            "*InternalTemperature*.csv.xz",
            "*InternalTemperature*.csv",
        ),
        fallback_patterns=("*Temperature*.csv.xz", "*Temperature*.csv", "*Temp*.csv.xz", "*Temp*.csv"),
    ),
)


def iter_data_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        [p for p in root.rglob("*") if p.is_file() and (p.name.endswith(".csv") or p.name.endswith(".csv.xz"))]
    )


def score_candidate(path: Path, source: DemoSource, patterns: Sequence[str]) -> int | None:
    rel = str(path.relative_to(URBAN_ROOT)).lower()
    name = path.name.lower()
    for idx, pattern in enumerate(patterns):
        pattern_l = pattern.lower()
        if fnmatch.fnmatch(name, pattern_l) or fnmatch.fnmatch(rel, pattern_l):
            # Lower is better. Prefer files located in a matching domain folder.
            domain_bonus = 0
            if source.output_subdir.lower() in rel:
                domain_bonus = -10
            # Avoid CO accidentally matching NO/NO2/NOx files in fallback mode.
            if source.variable == "CO" and any(token in name for token in ("no2", "nox", "no.csv", "count")):
                domain_bonus += 50
            return idx + domain_bonus
    return None


def find_source_file(files: Sequence[Path], source: DemoSource) -> Path | None:
    for pattern_group in (source.preferred_patterns, source.fallback_patterns):
        if not pattern_group:
            continue
        scored: list[tuple[int, Path]] = []
        for path in files:
            score = score_candidate(path, source, pattern_group)
            if score is not None:
                scored.append((score, path))
        if scored:
            return sorted(scored, key=lambda item: (item[0], len(str(item[1])), str(item[1])))[0][1]
    return None


def open_text(path: Path):
    if path.name.endswith(".xz"):
        return lzma.open(path, mode="rt", encoding="utf-8", errors="replace", newline="")
    return path.open(mode="r", encoding="utf-8", errors="replace", newline="")


def output_name(src: Path) -> str:
    name = src.name
    if name.endswith(".xz"):
        name = name[:-3]
    return name


def sample_csv(src: Path, dst: Path, rows: int) -> int:
    dst.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with open_text(src) as fin, dst.open("w", encoding="utf-8", newline="") as fout:
        reader = csv.reader(fin)
        writer = csv.writer(fout)
        try:
            header = next(reader)
        except StopIteration:
            raise RuntimeError(f"Source file is empty: {src}")
        writer.writerow(header)
        for row in reader:
            writer.writerow(row)
            written += 1
            if written >= rows:
                break
    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate minimal IoT-Zoo demo data from full .csv.xz datasets.")
    parser.add_argument("--duration", type=int, default=120, help="Intended demo duration in seconds. Default: 120.")
    parser.add_argument("--margin", type=int, default=60, help="Extra seconds used to size the sample. Default: 60.")
    parser.add_argument("--rows-per-second", type=int, default=5, help="Approximate sample density. Default: 5.")
    parser.add_argument("--min-rows", type=int, default=500, help="Minimum rows copied per source file. Default: 500.")
    parser.add_argument("--max-rows", type=int, default=2000, help="Maximum rows copied per source file. Default: 2000.")
    parser.add_argument("--clean", action="store_true", help="Remove the existing generated sample_data/urban_observatory folder first.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = max(args.min_rows, (args.duration + args.margin) * args.rows_per_second)
    rows = min(rows, args.max_rows)

    print("IoT-Zoo demo data preparation")
    print(f"Full dataset root: {URBAN_ROOT}")
    print(f"Output folder:      {OUTPUT_ROOT}")
    print(f"Rows per source:   {rows}")

    if args.clean and OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)

    files = iter_data_files(URBAN_ROOT)
    if not files:
        print("\nERROR: no Urban Observatory .csv or .csv.xz files were found.", file=sys.stderr)
        print("Expected files under devices/urban_observatory/, for example:", file=sys.stderr)
        print("  devices/urban_observatory/air_quality/2025-CO.csv.xz", file=sys.stderr)
        print("  devices/urban_observatory/air_quality/2025-NO2.csv.xz", file=sys.stderr)
        print("  devices/urban_observatory/building/<internal-temperature-file>.csv.xz", file=sys.stderr)
        return 1

    manifest_lines = ["# Generated demo dataset manifest", "", f"Rows requested per source: {rows}", ""]
    missing: list[DemoSource] = []

    for source in DEMO_SOURCES:
        src = find_source_file(files, source)
        if src is None:
            missing.append(source)
            continue
        # Use canonical output names expected by demo_experiment.py and
        # urban_sensor.py filename-based filtering.
        canonical_names = {
            "CO": "2025-CO.csv",
            "NO2": "2025-NO2.csv",
            "Internal Temperature": "2025-InternalTemperature.csv",
        }
        dst = OUTPUT_ROOT / source.output_subdir / canonical_names.get(source.variable, output_name(src))
        try:
            written = sample_csv(src, dst, rows)
        except Exception as exc:  # noqa: BLE001 - CLI diagnostics
            print(f"ERROR: failed to sample {src}: {exc}", file=sys.stderr)
            return 1
        rel_src = src.relative_to(PROJECT_ROOT)
        rel_dst = dst.relative_to(PROJECT_ROOT)
        print(f"[OK] {source.label}: {rel_src} -> {rel_dst} ({written} rows)")
        manifest_lines.extend(
            [
                f"## {source.label}",
                f"Variable: {source.variable}",
                f"Source: `{rel_src}`",
                f"Output: `{rel_dst}`",
                f"Rows written: {written}",
                "",
            ]
        )

    if missing:
        print("\nERROR: required demo source files were not found:", file=sys.stderr)
        for source in missing:
            print(f"  - {source.label} ({source.variable})", file=sys.stderr)
        print("\nThe full topology may still work, but the minimal demo needs these sources.", file=sys.stderr)
        return 1

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    (OUTPUT_ROOT / "MANIFEST.md").write_text("\n".join(manifest_lines), encoding="utf-8")
    (OUTPUT_ROOT / ".gitignore").write_text("*.csv\nMANIFEST.md\n", encoding="utf-8")

    print("\nDemo data ready.")
    print("Next steps:")
    print("  ./scripts/build_images.sh --demo")
    print("  ./scripts/run_demo.sh --time 120 --output /tmp/iot_zoo_demo.pcap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
