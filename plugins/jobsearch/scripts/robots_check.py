#!/usr/bin/env python3
"""Check whether robots.txt allows fetching a URL (stdlib only). Own minimal implementation, written for this
workspace; the idea (check robots.txt before touching a site) comes from MadsLorentzen/ai-job-search (MIT).

  python3 robots_check.py https://example.com/jobs/123 [--agent MyAgent]

Exit 0 = allowed, 1 = disallowed, 2 = robots.txt unreachable (treat as UNKNOWN: ask the user, do not scrape).
This tool never fetches the page itself. Terms of Service are NOT checked here; read them separately.
"""
import argparse, sys, urllib.parse, urllib.request, urllib.robotparser

ap = argparse.ArgumentParser(); ap.add_argument("url"); ap.add_argument("--agent", default="*")
a = ap.parse_args()
u = urllib.parse.urlparse(a.url)
robots = f"{u.scheme}://{u.netloc}/robots.txt"
try:
    req = urllib.request.Request(robots, headers={"User-Agent": "robots-check/1.0"})
    body = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "replace")
except Exception as e:
    print(f"UNKNOWN: cannot read {robots}: {e}"); sys.exit(2)
rp = urllib.robotparser.RobotFileParser(); rp.parse(body.splitlines())
ok = rp.can_fetch(a.agent, a.url)
print(f"{'ALLOWED' if ok else 'DISALLOWED'}: {a.url} for agent '{a.agent}' per {robots}")
sys.exit(0 if ok else 1)
