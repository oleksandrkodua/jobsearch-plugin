# Third-party notices

## humanizer skill (MIT)

`plugins/jobsearch/skills/humanizer/` is based on the humanizer skill by Siqi Chen, MIT licence. The licence text, kept unchanged in `plugins/jobsearch/skills/humanizer/LICENSE`, is:

```
MIT License

Copyright (c) 2025 Siqi Chen

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## MadsLorentzen/ai-job-search (MIT)

The interview, upskill, grounding-audit and robots-check features use ideas from the MadsLorentzen/ai-job-search project (MIT licence). No code is copied; the implementations here are written separately.

## career-ops (MIT)

Some features use ideas from the career-ops project (MIT licence): data-folder precedence, the funnel and patterns report, posting legitimacy checks, the STAR+R story bank, the interview debrief and red-flag checks. Its name is not used for any plugin, command or feature here, in line with its trademark policy. No code is copied.

## Minicharts (MIT)

`docs/img/vacancy-path.svg` and `docs/img/vacancy-path.html` are drawn with Minicharts by April Zhu, MIT licence, Copyright (c) 2026 April Zhu. The HTML page embeds the Minicharts engine, its example drawings and its page unchanged; the SVG is their output. `tools/build_vacancy_path.py` copies the short colour-softening function from Minicharts `assets/build.py`. The MIT permission notice and warranty disclaimer are the same text as quoted in the humanizer section above. The page loads its fonts (Young Serif, Gaegu, DM Sans, SIL Open Font License) from Google Fonts when opened; they are not bundled. Minicharts is not a dependency of the plugin.

## ATS screening rubric

`plugins/jobsearch/skills/ats-screening/scripts/ats_technical_score.py` follows the published rubric of the cv.shykov.dev project idea for its weights, thresholds and layout method. Credited here as a rubric and idea source only; the code and the word lists in the script are written separately.
