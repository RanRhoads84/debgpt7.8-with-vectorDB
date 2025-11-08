#!/usr/bin/env python3
"""
Interactive helper for generating the vector service .env file.
"""
from __future__ import annotations

import getpass
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

SENSITIVE_SUFFIXES: Tuple[str, ...] = (
    "_KEY", "_TOKEN", "_SECRET", "_PASSWORD")


def parse_env(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        values[key] = value
    return values


def read_example(path: Path) -> Tuple[List[str], List[str], Dict[str, str]]:
    lines = path.read_text().splitlines()
    order: List[str] = []
    defaults: Dict[str, str] = {}
    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        order.append(key)
        defaults[key] = value
    return lines, order, defaults


def is_secret(key: str) -> bool:
    upper_key = key.upper()
    return any(upper_key.endswith(suffix) for suffix in SENSITIVE_SUFFIXES)


def prompt_value(key: str, current: str, secret: bool) -> str:
    if secret:
        masked = "(hidden)" if current else "(empty)"
        print(f"{key} {masked}")
        entered = getpass.getpass(
            "Enter new value (leave blank to keep current): ")
        return entered if entered else current
    default_hint = current
    prompt = f"{key} [{default_hint}]: " if default_hint else f"{key}: "
    entered = input(prompt).strip()
    return entered if entered else current


def build_output(example_lines: Sequence[str], values: Dict[str, str], extras: Dict[str, str]) -> str:
    result_lines: List[str] = []
    for raw_line in example_lines:
        stripped = raw_line.strip()
        if stripped and not stripped.startswith("#") and "=" in raw_line:
            key = raw_line.split("=", 1)[0]
            result_lines.append(f"{key}={values.get(key, '')}")
        else:
            result_lines.append(raw_line)
    remaining = {k: v for k, v in extras.items() if k not in values}
    if remaining:
        if result_lines and result_lines[-1] != "":
            result_lines.append("")
        result_lines.append("# Custom entries preserved from existing .env")
        for key in sorted(remaining):
            result_lines.append(f"{key}={remaining[key]}")
    result_lines.append("")
    return "\n".join(result_lines)


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    example_path = script_dir / ".env.example"
    target_path = script_dir / ".env"

    if not example_path.exists():
        print("Could not locate .env.example next to this script.", file=sys.stderr)
        return 1

    example_lines, order, defaults = read_example(example_path)
    existing = parse_env(target_path)

    print("Interactive configuration for vector service environment file\n")
    values: Dict[str, str] = {}
    for key in order:
        baseline = existing.get(key, defaults.get(key, ""))
        value = prompt_value(key, baseline, is_secret(key))
        values[key] = value

    output = build_output(example_lines, values, existing)
    target_path.write_text(output)

    print(
        f"\nWrote {target_path}. You can rerun this script to update values later.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
