# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml==6.0.3"]
# ///
"""Check that every git-tracked skill has the shape AGENTS.md describes.

    uv run --script .github/scripts/check_skill_structure.py

Checks:
- SKILL.md has YAML frontmatter; `name` matches the directory; `description` is set;
  `runs_on` lists where the skill works (`web`, `local`).
- Vendored skills (frontmatter has `source:`) also set `upstream_ref` and `last_reviewed`.
- agents/openai.yaml exists, parses, and sets interface.display_name,
  short_description, and a default_prompt that mentions `$<name>`.
- Relative markdown links in tracked .md files point at tracked files.
- The `lio` plugin (plugins/lio/, published through .claude-plugin/marketplace.json)
  holds exactly the skills whose `runs_on` includes `web`, each one also reachable
  as a skills/<name> symlink; neither manifest pins a `version`.

Only files git tracks or would commit count, so a local run matches CI:
gitignored skills (aws, twg, generated gitbutler files) are out of scope.
"""

from __future__ import annotations

import json
import os
import posixpath
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

import yaml

ROOT = Path(__file__).resolve().parents[2]
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
LINK = re.compile(r"\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+[\"'][^)]*[\"'])?\s*\)")
INLINE_CODE = re.compile(r"`[^`]*`")
URL_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)
FENCE = re.compile(r"^\s*(```|~~~)")
RUNS_ON = {"web", "local"}
MARKETPLACE = ".claude-plugin/marketplace.json"
MARKETPLACE_NAME = "luther-io"
PLUGIN_NAME = "lio"
PLUGIN_DIR = f"plugins/{PLUGIN_NAME}"
PLUGIN_MANIFEST = f"{PLUGIN_DIR}/.claude-plugin/plugin.json"
SKILL_MD = re.compile(rf"(?:skills|{re.escape(PLUGIN_DIR)}/skills)/[^/]+/SKILL\.md")

errors: list[str] = []


def error(where: str | Path, message: str) -> None:
    errors.append(f"{where}: {message}")


def tracked_files() -> list[str]:
    """Tracked files plus new, not-ignored ones: what a commit would contain."""
    out = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return sorted({p for p in out.split("\0") if p and (ROOT / p).is_file()})


def load_yaml(text: str, where: str) -> object | None:
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        error(where, f"not valid YAML: {exc}")
        return None


def load_json(path: str) -> dict | None:
    try:
        data = json.loads((ROOT / path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        error(path, "missing")
        return None
    except json.JSONDecodeError as exc:
        error(path, f"not valid JSON: {exc}")
        return None
    if not isinstance(data, dict):
        error(path, "must be a JSON object")
        return None
    return data


def check_plugin(skills: list[str], runs_on: dict[str, list[str]], tracked: set[str]) -> None:
    """The lio plugin is what claude.ai installs: web skills in, local-only skills out."""
    marketplace = load_json(MARKETPLACE)
    if marketplace is not None:
        if marketplace.get("name") != MARKETPLACE_NAME:
            error(MARKETPLACE, f"name must be {MARKETPLACE_NAME!r}")
        entries = marketplace.get("plugins")
        entry = entries[0] if isinstance(entries, list) and len(entries) == 1 else None
        if not isinstance(entry, dict) or entry.get("name") != PLUGIN_NAME:
            error(MARKETPLACE, f"plugins must hold exactly one entry, named {PLUGIN_NAME!r}")
        else:
            if entry.get("source") != f"./{PLUGIN_DIR}":
                error(MARKETPLACE, f"the {PLUGIN_NAME} entry's source must be './{PLUGIN_DIR}'")
            if "version" in entry:
                error(MARKETPLACE, "no version on the entry: it would pin users to that version")

    manifest = load_json(PLUGIN_MANIFEST)
    if manifest is not None:
        if manifest.get("name") != PLUGIN_NAME:
            error(PLUGIN_MANIFEST, f"name must be {PLUGIN_NAME!r}")
        if "version" in manifest:
            error(PLUGIN_MANIFEST, "no version: it would pin users to that version")

    if any(p.startswith(f"{PLUGIN_DIR}/bin/") for p in tracked):
        error(f"{PLUGIN_DIR}/bin", "claude.ai refuses to install a plugin with a top-level bin/ directory")

    for skill_md in skills:
        skill_dir = posixpath.dirname(skill_md)
        name = posixpath.basename(skill_dir)
        web = "web" in runs_on.get(skill_md, [])
        if skill_dir.startswith(f"{PLUGIN_DIR}/"):
            if not web:
                error(skill_md, f"is in the {PLUGIN_NAME} plugin but runs_on lacks 'web'; move it to skills/{name}/")
            link = ROOT / "skills" / name
            want = f"../{skill_dir}"
            if not link.is_symlink() or os.readlink(link) != want:
                error(f"skills/{name}", f"must be a symlink to {want}, so local agents still find the skill")
        elif web:
            error(
                skill_md,
                f"runs_on includes 'web', so the skill belongs in {PLUGIN_DIR}/skills/{name}/ "
                f"with skills/{name} a symlink to it",
            )


def check_skill(skill_md: str, tracked: set[str]) -> list[str]:
    """Check one skill; return its runs_on values (empty when unreadable)."""
    skill_dir = posixpath.dirname(skill_md)
    dir_name = posixpath.basename(skill_dir)
    text = (ROOT / skill_md).read_text(encoding="utf-8")

    match = FRONTMATTER.match(text)
    if not match:
        error(skill_md, "no YAML frontmatter (a --- block at the top of the file)")
        return []
    meta = load_yaml(match.group(1), f"{skill_md} frontmatter")
    if meta is None:
        return []
    if not isinstance(meta, dict):
        error(skill_md, "frontmatter must be a mapping")
        return []

    name = meta.get("name")
    if name != dir_name:
        error(skill_md, f"name {name!r} must match the directory name {dir_name!r}")
    description = meta.get("description")
    if not isinstance(description, str) or not description.strip():
        error(skill_md, "description is missing or empty")
    runs_on = meta.get("runs_on")
    if (
        not isinstance(runs_on, list)
        or not runs_on
        or not all(isinstance(v, str) for v in runs_on)
        or not set(runs_on) <= RUNS_ON
    ):
        error(skill_md, f"runs_on must be a non-empty list drawn from {sorted(RUNS_ON)}, got {runs_on!r}")
    if "source" in meta:
        for field in ("upstream_ref", "last_reviewed"):
            if not meta.get(field):
                error(skill_md, f"vendored skill (has source:) is missing {field}:")

    declared = [v for v in runs_on if isinstance(v, str)] if isinstance(runs_on, list) else []

    openai_yaml = f"{skill_dir}/agents/openai.yaml"
    if openai_yaml not in tracked:
        error(openai_yaml, "missing; every skill needs agents/openai.yaml")
        return declared
    data = load_yaml((ROOT / openai_yaml).read_text(encoding="utf-8"), openai_yaml)
    if data is None:
        return declared
    interface = data.get("interface") if isinstance(data, dict) else None
    if not isinstance(interface, dict):
        error(openai_yaml, "needs an interface: mapping")
        return declared
    for key in ("display_name", "short_description", "default_prompt"):
        value = interface.get(key)
        if not isinstance(value, str) or not value.strip():
            error(openai_yaml, f"interface.{key} is missing or empty")
    prompt = interface.get("default_prompt")
    if isinstance(prompt, str) and f"${dir_name}" not in prompt:
        error(openai_yaml, f"interface.default_prompt should mention ${dir_name}")
    return declared


def check_links(md_file: str, tracked: set[str], tracked_dirs: set[str]) -> None:
    in_fence = False
    lines = (ROOT / md_file).read_text(encoding="utf-8").splitlines()
    for lineno, line in enumerate(lines, 1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for target in LINK.findall(INLINE_CODE.sub("", line)):
            if URL_SCHEME.match(target) or target.startswith(("#", "/")):
                continue
            path = unquote(target.split("#", 1)[0].split("?", 1)[0])
            if not path:
                continue
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(md_file), path))
            if resolved.startswith("../"):
                error(f"{md_file}:{lineno}", f"link points outside the repo: {target}")
            elif resolved not in tracked and resolved not in tracked_dirs:
                # skills/<name> may be a symlink into the lio plugin; follow it.
                real = Path(os.path.realpath(ROOT / resolved))
                physical = real.relative_to(ROOT).as_posix() if real.is_relative_to(ROOT) else None
                if physical not in tracked and physical not in tracked_dirs:
                    error(f"{md_file}:{lineno}", f"link target is not a tracked file: {target}")


def main() -> int:
    files = tracked_files()
    tracked = set(files)
    tracked_dirs = {posixpath.dirname(p) for p in files}
    for p in list(tracked_dirs):
        while p:
            p = posixpath.dirname(p)
            tracked_dirs.add(p)

    skills = sorted(p for p in files if SKILL_MD.fullmatch(p))
    runs_on = {skill_md: check_skill(skill_md, tracked) for skill_md in skills}
    check_plugin(skills, runs_on, tracked)

    for p in files:
        if re.fullmatch(r"skills/[^/]+/agents/openai\.yaml", p) and not p.startswith(
            tuple(posixpath.dirname(s) + "/" for s in skills)
        ):
            # Skills whose SKILL.md is generated and gitignored (gitbutler): YAML must still parse.
            load_yaml((ROOT / p).read_text(encoding="utf-8"), p)

    markdown = [p for p in files if p.endswith(".md")]
    for md_file in markdown:
        check_links(md_file, tracked, tracked_dirs)

    if errors:
        print(f"{len(errors)} problem(s):")
        for line in errors:
            print(f"  {line}")
        return 1
    print(f"OK: {len(skills)} skills, {len(markdown)} markdown files checked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
