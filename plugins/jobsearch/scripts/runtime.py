"""Runtime-specific command names from the installed package, never the current project."""
import os
import re

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODEX = os.path.isfile(os.path.join(PLUGIN_ROOT, ".codex-plugin", "plugin.json"))


def command(name):
    if CODEX:
        return "$jobsearch-setup" if name == "jobsearch-setup" else "$jobsearch-" + name
    return "/jobsearch:" + name


NAMES = "apply followup funnel help interview jobsearch-setup outcome rank scan upskill".split()


def skill_name(name):
    return "jobsearch-setup" if name == "jobsearch-setup" else "jobsearch-" + name


def render_text(text, codex=None):
    """Display commands for this host without editing the user's stored files."""
    codex = CODEX if codex is None else codex
    for name in sorted(NAMES, key=len, reverse=True):
        skill = skill_name(name)
        if codex:
            text = text.replace("/jobsearch:" + name, "$" + skill)
            text = re.sub(r"(?<![\w/:])/" + re.escape(name) + r"(?![\w/-])", lambda m: "$" + skill, text)
        else:
            text = re.sub(r"\$" + re.escape(skill) + r"(?![\w-])", lambda m: "/jobsearch:" + name, text)
    return text
