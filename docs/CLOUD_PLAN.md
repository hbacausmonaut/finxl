# CLOUD_PLAN.md: cloud run of v1 work (approved 2026-11-04)

*Written by the planning chat. Read it together with `CHAT_HANDOFF.md` (items 3.4, 3.5, 4, 5 and 6).*

**Why:** Harsh has Claude Code on the web credits that expire on **2026-11-05**. They're used before his normal limits. The goal is to run the approved v1 work in **three parallel cloud sessions** today and tomorrow, while he studies.

**Harsh's instruction:** do the whole setup yourself, including GitHub and browser logins via **Claude in Chrome**. Ping him only when he's genuinely required (see below). He approves this plan once, in the local Claude Code, and that approval covers Part 1, Part 2 and the three sessions' work.

---

## Part 0: Rules for this run

### Ping Harsh only if
1. **A password, 2FA code, CAPTCHA or "confirm it's you" prompt** needs him (e.g. GitHub or claude.ai isn't already signed in, in Chrome). Never type or guess passwords yourself.
2. **Something would cost money**: a paid plan, an upgrade or a billing prompt. **Never accept these.**
3. **Something can't be undone and isn't covered by this plan.**
4. **All three sessions are blocked**, e.g. credits are exhausted, or Screener/BSE block downloads and the fallback below also fails.

**How to ping:** use a push notification if you have one; otherwise write it at the top of **Questions for chat** in `CHAT_HANDOFF.md`. Keep it to one line saying what you need from him, then carry on with anything that isn't blocked.

### Never
- make the repo public
- commit secrets (the Gemini key, tokens, `.env`)
- force-push or rewrite history
- delete files on Harsh's laptop
- edit files owned by another session (see the table in Part 2)

---

## Part 1: Setup (local Claude Code, on Harsh's laptop)

### 1.1 Pre-flight
- `git status`: commit pending changes, including `CLOUD_PLAN.md` and `CHAT_HANDOFF.md`.
- **Secret scan** of the working tree **and git history**: search for the Gemini key value, `AIza`-style keys, and `GEMINI_API_KEY=` assignments. If a secret is in history, stop and ping Harsh (rule 3); don't push.
- Confirm `.gitignore` still excludes PDFs, Excels, XML, `.claude/` and `tests/results/run_*.json`. The PDF cache lives outside the repo (`~/DocFetcherData`), so cloud sessions will download what they need.
- Check the repo size; it should be well under 100 MB.

### 1.2 Private GitHub repo
- Check `gh` (`gh auth status`). If it's missing, install it (`winget install GitHub.cli`).
- If it isn't signed in, run `gh auth login --web` and complete the device-code page **in Chrome via Claude in Chrome**. GitHub is probably already signed in there; if not, ping Harsh (rule 1).
- `gh repo create docfetcher --private --source . --remote origin --push`. If the name is taken, use `docfetcher-v1`.
- Verify on github.com (in Chrome) that the repo is **Private**.

### 1.3 Connect Claude to the repo
- In Chrome, open https://github.com/apps/claude and install the Claude GitHub App on **only this repository**.
- At https://claude.ai/code, confirm the repo appears in the repository picker.

### 1.4 Cloud environment (at claude.ai/code, in Chrome)
Create an environment named **`docfetcher`**:
- **Network access: Custom.** Allowed domains:
  ```
  screener.in
  *.screener.in
  bseindia.com
  *.bseindia.com
  nseindia.com
  *.nseindia.com
  generativelanguage.googleapis.com
  ```
  Tick **"Also include default list of common package managers"**.
- **Environment variables:**
  ```
  GEMINI_API_KEY=<value of the GEMINI_API_KEY environment variable on this laptop>
  BASH_DEFAULT_TIMEOUT_MS=600000
  DOCFETCHER_CACHE=/root/DocFetcherData
  ```
  This is Harsh's personal free key in his private environment, so a plain variable is acceptable. `llm_extract.py` reads the key and sends it as a header.
- **Setup script:** `pip install -r requirements.txt`
- Save. Don't pick any paid option.

### 1.5 Record
Under **Done** in `CHAT_HANDOFF.md`: the repo URL, the environment name, and anything that deviated from this plan. Commit and push.

---

## Part 2: Launch three cloud sessions

Start each one in the **`docfetcher`** environment, on its own branch, with the prompt below, using `claude --cloud "<prompt>"` from the repo folder (choose the `docfetcher` environment) or from claude.ai/code in Chrome. Record the three session links under **Done**.

| Session | Branch | Work | Owns these files (no one else edits them) |
|---|---|---|---|
| **A: Parser** | `cloud/a-parser` | Items 3.4 A+B, then 3.5 | `ar_extract.py`, `finxl.py`, `quality.py`, `label_words.txt`, `fetchdocs.py`, `tests/regression.py`, `tests/companies.json`, `tests/baseline.json`, `tests/summary.py`, **all logs** (`RUN_LOG.md`, `ERROR_LOG.md`, `TEST_LOG.md`, `PROJECT_PLAN.md`) |
| **B: Screens** | `cloud/b-screens` | Item 4 (audit screen) + the gold-set **review** screen from 3.4 C | new files only (e.g. `audit.py`, `review_ui.py`, `tests/audit/`), plus adding a page or tab in `app.py` |
| **C: Checks** | `cloud/c-checks` | The 3.4 C gold-set **builder** (Claude as second reader), 5c (NSE-first cross-check), then the **silver expansion** with the leftover credits | `accuracy_check.py`, `llm_extract.py`, new `gold.py`, `tests/gold/` |

Only session A writes to the logs. B and C report in their pull request descriptions, and A copies their summaries into the logs when merging.

### Prompt for session A (Parser)
```
You are session A (Parser) of three parallel cloud sessions on DocFetcher. Read CLAUDE.md, CHAT_HANDOFF.md and CLOUD_PLAN.md first. Harsh has already approved this work; don't wait for approval, and only ping him per CLOUD_PLAN.md Part 0.
Branch: cloud/a-parser. You own the files listed for session A in CLOUD_PLAN.md Part 2, and only those.
Step 0 (first 15 minutes): download ONE annual report (SBIN, latest year) via fetchdocs.py to test whether Screener/BSE allow downloads from this cloud machine. If blocked, write that under Questions for chat, push, and continue with parts of 3.4 A+B that can be tested on the companies whose reports you can reach; the 100-company download will then run on Harsh's laptop later.
Then do CHAT_HANDOFF item 3.4 parts A and B (the SBI-found bug patterns, EPS sanity check, junk-row check) on all 63 test companies, with the regression suite after every fix and no regressions. Report how many companies had the EPS unit bug.
Then do item 3.5 (37 new companies, fix recurring patterns, stop rule as written).
Also, after each of your fix rounds, git fetch the cloud/c-checks branch and read tests/gold/silver_findings.md (Claude-vs-parser mismatches grouped by pattern); fix patterns affecting 2+ companies under the same regression rules.
Commit and push after every verified fix, and at least every hour, so nothing is lost if credits run out or the VM expires. Log every run in RUN_LOG and every fix in ERROR_LOG as usual. When finished, open a pull request to the default branch with a summary of results.
```

### Prompt for session B (Screens)
```
You are session B (Screens) of three parallel cloud sessions on DocFetcher. Read CLAUDE.md, CHAT_HANDOFF.md and CLOUD_PLAN.md first. Harsh has already approved this work; don't wait for approval, and only ping him per CLOUD_PLAN.md Part 0.
Branch: cloud/b-screens. Only create new files and add a page or tab to app.py. Do NOT edit parser files, accuracy_check.py, tests/regression.py or any log files; session A and C own those.
Build CHAT_HANDOFF item 4 (sampling-audit screen) exactly as specified: 100-figure stratified sample with fixed seed, PDF page with highlighted value, buttons and reasons, progress saved after every click, report with per-group accuracy and 95% range.
Also build the gold-set REVIEW screen from item 3.4 C: it reads a disagreements file produced by session C (tests/gold/disagreements_*.json; agree a simple JSON format and document it in your PR) and shows each disagreement next to the PDF page, so Harsh can pick parser / Gemini / neither-and-type-the-value. Save his answers to tests/gold/.
Generate a few Excels yourself (e.g. 3 companies) to test the screens end to end; download reports as needed.
Do NOT do the audit or the review yourself; Harsh does those later. Commit and push often. When finished, open a pull request with screenshots or a description of how to launch each screen.
```

### Prompt for session C (Checks)
```
You are session C (Checks) of three parallel cloud sessions on DocFetcher. Read CLAUDE.md, CHAT_HANDOFF.md and CLOUD_PLAN.md (especially "Gold and silver sets") first. Harsh has already approved this work; don't wait for approval, and only ping him per CLOUD_PLAN.md Part 0.
Branch: cloud/c-checks. You own accuracy_check.py, llm_extract.py, a new gold.py and tests/gold/. Do NOT edit parser files, app.py, tests/regression.py or log files.
1) GOLD core (item 3.4 C): about 5 companies x 1 year x 3 consolidated statements (SBI, an NBFC, an IT company, a manufacturer, a small cap). For each statement, YOU are the second reader: render the PDF pages as images and read every row yourself (label, value per year, order), independently of the parser output, then compare row by row with the parser. Use Gemini (GEMINI_API_KEY is set) only as an optional third reader to break ties. Write tests/gold/disagreements_<company>_<fy>_<statement>.json in the format agreed with session B (if none is visible yet, define one and document it in your PR). These 15 statements become GOLD after Harsh resolves the disagreements.
2) NSE-first cross-check (item 5c): NSE XBRL as the main figure, Screener only where NSE has no figure (reported separately), Yahoo dropped or info-only, and NSE compared with the as-originally-reported figure for that year.
3) SILVER expansion (use the remaining credits): repeat the same Claude-vs-parser comparison on more statements, in batches of 10 companies (latest year, 3 consolidated statements each), across the 63 test companies first, then the new ones from session A's list. Use subagents to read pages in parallel. After each batch: commit, push, and append to tests/gold/silver_findings.md the mismatches grouped by PATTERN (e.g. "EPS unit-converted", "wrapped label split", "value in wrong year column") with example rows, so session A can fix the parser. Keep going until the credits are low (a usage warning), the credits expire on 2026-11-05, or the batches run out.
Write a gold-check function that compares any future output with the gold and silver copies (gold = hard failure, silver = warning); session A will wire it into the regression suite after merge.
Note: the parser may change on session A's branch; build against the current default branch and keep your code independent of parser internals where possible.
Commit and push often. When finished, open a pull request summarising: gold disagreements per statement, silver statements and rows compared, and the top mismatch patterns.
```

### Launch amendments (approved by Harsh, 2026-11-04; these override the prompts above)
**All sessions:**
- Your full prompt is the block for your session above, plus these amendments.
- Harsh does not want his normal or weekly limits used. The $100 cloud credit expires at **13:29 IST on 2026-11-05** (07:59 UTC), and after that cloud sessions use his regular limits. **Hard stop: check the clock (`date -u`) regularly. By 07:30 UTC on 2026-11-05, push your work and end the session, finished or not.** Stop earlier at any usage or credit warning.
- Yahoo is deliberately not available (yfinance isn't installed and yahoo.com isn't allowed).
- `GEMINI_API_KEY` is not set in this environment. Claude is the second reader, so skip the optional Gemini tie-breaker.
- Commands time out at 10 minutes, so run long jobs in the background and check on them.

**Session A:**
- **Batched testing:** after each fix, test only the affected companies. Run the full regression suite once after each batch of fixes, and always before the final pull request.
- Yahoo-only verified figures will drop in the cloud. At the start, run the suite once and use that result as your cloud starting point for regression comparisons. Don't chase those drops.

**Session B:** in the review screen, the choices are parser / second reader / neither-and-type-the-value (not "Gemini").

### Gold and silver sets (added 2026-11-04)
Harsh wants the spare credits used for a bigger answer key, read by Claude instead of Gemini Flash.
- **Second reader = Claude (in the cloud session), not Gemini.** Claude reads the page images. Gemini is optional, as a tie-breaker only.
- **GOLD** (about 15 statements): every disagreement is resolved by Harsh in session B's review screen. These are human-verified. The regression check treats any difference as a **failure**.
- **SILVER** (as many statements as the credits allow): rows where Claude and the parser agree, plus Claude's reading where they disagree. It's AI-verified, not human-verified, so the regression check treats differences as **warnings**, never as automatic truth.
- **The main value of silver is finding parser bugs at scale.** Every Claude-vs-parser mismatch is either a parser bug or a Claude misread. `tests/gold/silver_findings.md` groups them by pattern for session A.
- **Harsh's review load stays small:** the gold disagreements, plus an optional random sample of about 30 silver rows to measure how often Claude itself is wrong. He is **not** asked to review all silver mismatches.
- **Session A:** check `silver_findings.md` on the `cloud/c-checks` branch (git fetch) after each of your own fix rounds, and fix the patterns that affect 2+ companies, under the same regression rules.

---

## Part 3: After the sessions finish (local Claude Code, when Harsh is back)
1. Merge in this order: **C → B → A**, resolving conflicts. Session A's branch wins on parser files.
2. Wire the gold check into `tests/regression.py`, then run the full regression suite once on the laptop.
3. Pull everything into Harsh's local folder.
4. Update `CHAT_HANDOFF.md` **Done** and the logs.
5. Tell Harsh what's waiting for him: the gold-set review (30–60 min), the optional silver sample (about 30 rows), and the audit (about 25 min).

**Credits:** they're used before Harsh's normal limits and expire 2026-11-05. If they run out, the sessions would start using his normal weekly limits. If a session reports a usage or credit warning, push your work and pause.
