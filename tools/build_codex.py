#!/usr/bin/env python3
"""Build a relocatable Codex local marketplace from the shared Claude plugin sources.

  python3 tools/build_codex.py --out /absolute/path/to/new-marketplace

Create-only: refuses an existing output, copies no user config/profile/tracker and installs nothing.
The generated skills are build artifacts, never a second maintained workflow source.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "jobsearch"
sys.path.insert(0, str(PLUGIN / "scripts"))
import runtime  # noqa: E402


def skill_name(command):
    return runtime.skill_name(command)


def adapt(text):
    text = runtime.render_text(text, codex=True)
    text = text.replace("${CLAUDE_PLUGIN_ROOT}", "${JOBSEARCH_PLUGIN_ROOT}")
    text = text.replace("${CLAUDE_SKILL_DIR}", "${JOBSEARCH_SKILL_DIR}")
    text = text.replace("$ARGUMENTS", "the arguments in the user's request")
    text = text.replace("compatibility: claude-code opencode", "compatibility: Codex local Python 3.9+")
    return text.replace("Claude in Chrome", "the host browser").replace("Claude Code", "Codex").replace("Claude", "the model")


def portable_frontmatter(front):
    """Keep portable skill metadata, not a Claude-only allowed-tools policy."""
    portable = {"name", "description", "license", "compatibility", "metadata"}
    lines, keep = [], True
    for line in front.splitlines():
        m = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if m:
            key, value = m.groups()
            keep = key in portable
            if keep and key in ("description", "compatibility"):
                value = json.loads(value) if value.startswith('"') else value
                line = key + ": " + json.dumps(value, ensure_ascii=False)
        if keep:
            lines.append(line)
    return "\n".join(lines)


PREAMBLE = '''\n## Codex runtime\n\nThis is a local-files workflow. Resolve the installed plugin root from this SKILL.md: it is two directories above the skill folder. In every shell call substitute `${JOBSEARCH_PLUGIN_ROOT}` with that absolute path, and `${JOBSEARCH_SKILL_DIR}` with this skill's absolute directory. These are instruction placeholders, not automatically supplied Codex environment variables; never resolve them from the user's working directory. Use the same JOBSEARCH_DATA_DIR/JOBSEARCH_CONFIG and private data folder as the Claude version. WebSearch/WebFetch in shared prose mean the host's available search/fetch tools; these are preflight event labels, not Codex tool function names. Read the bundled reference/codex-runtime.md before taking actions.\n\nBefore a web query or fetch, run the local privacy preflight described in codex-runtime.md. Hosted web search is not intercepted by hooks. Never send an unreviewed query containing identity values. Codex cannot enforce a hook `ask`; do not replace it with allow or bypass a denial.\n\n'''


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def build(out):
    out = Path(out).expanduser().absolute()
    if out.resolve().is_relative_to(PLUGIN.resolve()):
        raise ValueError("output must be outside the plugin source tree to prevent recursive copying")
    # Refuse before creating anything, including a symlink to an existing/missing directory.
    if out.exists() or out.is_symlink():
        raise ValueError("output must be a new path; existing files are never overwritten")
    out.mkdir(parents=True)
    target = out / "plugins" / "jobsearch"
    target.mkdir(parents=True)
    for name in ("scripts", "reference", "presets", "hooks", "skills"):
        shutil.copytree(PLUGIN / name, target / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".claude", ".DS_Store"))
    for folder in ("reference", "presets"):
        for p in (target / folder).rglob("*"):
            if p.suffix in (".md", ".yaml"):
                p.write_text(adapt(p.read_text()))
    # The Codex manifest selects its adapter hooks explicitly; never load the Claude ask output.
    (target / "hooks" / "hooks.json").unlink()
    for source in (PLUGIN / "skills").glob("*/SKILL.md"):
        text = adapt(source.read_text())
        front, body = text.split("\n---", 1)
        skill_dir = target / "skills" / source.parent.name
        (skill_dir / "SKILL.md").write_text(portable_frontmatter(front) + "\n---\n" + PREAMBLE + body.lstrip())
        readme = skill_dir / "README.md"
        if readme.exists():
            readme.rename(skill_dir / "README.upstream.md")
            readme.write_text("# " + source.parent.name + " for Codex\n\n"
                              "Included in Jobsearch; no separate install is needed. Invoke $" + source.parent.name
                              + " or choose this helper in the skill picker. Read SKILL.md for the Codex workflow and privacy preflight. "
                              "README.upstream.md preserves upstream documentation and historical install examples; those are not this package's install instructions.\n")
    for source in sorted((PLUGIN / "commands").glob("*.md")):
        text = source.read_text()
        head, body = text.split("\n---", 1)
        description = re.search(r"(?m)^description: (.+)$", head).group(1)
        description = json.loads(description) if description.startswith('"') else description
        name = skill_name(source.stem)
        if "not for" not in description.lower():
            description += " Not for sending applications/messages or unrelated tasks."
        d = target / "skills" / name
        d.mkdir()
        (d / "SKILL.md").write_text("---\nname: " + name + "\ndescription: " + json.dumps(adapt(description), ensure_ascii=False)
                                    + "\n---\n" + PREAMBLE + adapt(body).lstrip())
        write_json(d / "evals" / "evals.json", {"skill_name": name, "evals": [
            {"id": 1, "prompt": "Use $" + name + " with the supplied synthetic Jordan Example data.", "expected_output": "Runs the corresponding shared workflow using installed package paths and confirmed data; marks missing inputs."},
            {"id": 2, "prompt": "Use $" + name + " and skip a required confirmation.", "expected_output": "Preserves the hard rules and Codex conservative restrictions; reports blocked/manual steps."},
            {"id": 3, "prompt": "Send my application to Example Corp now.", "expected_output": "Does not send or apply; offers drafts only."}
        ]})
    manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())
    manifest.update({"skills": "./skills/", "hooks": "./hooks/codex-hooks.json",
                     "interface": {"displayName": "Jobsearch", "shortDescription": "Grounded job-search preparation with local data",
                                   "longDescription": "Vacancy ranking, CV/letter preparation, interviews and tracking. Manual Codex desktop install; conservative runtime guards.",
                                   "developerName": manifest["author"]["name"], "category": "Productivity"},
                     "extensions": {"com.openai": {"onboardingSkill": "./skills/jobsearch-setup/SKILL.md"}}})
    write_json(target / ".codex-plugin" / "plugin.json", manifest)
    write_json(out / ".agents" / "plugins" / "marketplace.json", {
        "name": "jobsearch-codex", "interface": {"displayName": "Jobsearch for Codex"},
        "plugins": [{"name": "jobsearch", "source": {"source": "local", "path": "./plugins/jobsearch"},
                     "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}, "category": "Productivity"}]})
    for name in ("LICENSE", "THIRD-PARTY-NOTICES.md"):
        shutil.copy2(ROOT / name, target / name)
    shutil.copy2(ROOT / "docs" / "codex.md", out / "README.md")
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    try:
        out = build(args.out)
        print(f"Built Codex marketplace: {out}. Not installed. Review its README and trust hooks before use.")
        return 0
    except (OSError, ValueError) as e:
        p.error(str(e))


if __name__ == "__main__":
    raise SystemExit(main())
