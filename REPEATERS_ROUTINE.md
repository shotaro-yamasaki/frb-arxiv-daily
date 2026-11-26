# Weekly search for repeater activity reports

This is the procedure for the weekly scheduled Claude task. The goal is to keep
`data/repeater_reports.json` up to date with reports of activity (or of no activity) from repeating FRBs
after CHIME/FRB Catalog 2, which ends on 2023-09-15. `docs/repeaters.html` shows the latest report of each
repeater, and the status chips (active within 30 days, within a year, quiet) come from these dates.

## Format of a report

```json
{"frb": "20240114A", "date": "2026-11-20", "type": "detection", "telescope": "FAST",
 "note": "One or two sentences: number of bursts, band, observing dates, burst rate if given.",
 "source": {"arxiv": "2611.01234", "url": "https://arxiv.org/abs/2611.01234"},
 "status": "auto", "added": "2026-11-27"}
```

- `frb`: TNS name without the "FRB" prefix.
- `date`: the date of the last burst or the last observation reported (not the paper date). If the paper only gives
  an observing campaign, use its last day. If no date is given at all, leave the report out.
- `type`: `detection`, `non-detection` (a sensitive campaign that found no bursts), `burst-storm`
  (a period of very high burst rate, say so in `note`), or `atel` (added automatically by `scripts/atel_scan.py`).
- `source`: `arxiv` id, `atel` number and/or `url`. The url must open the paper, telegram or notice.
- `status`: always `"auto"` for new entries. Never change entries marked `"checked"`.

## Steps

1. **Get the repository.** Attach `shotaro-yamasaki/frb-arxiv-daily` with push access and clone it (main branch).
2. **Know what is already there.** Read `data/repeater_reports.json` and note `last_search`. Search reports
   since then (or the last 14 days if it is missing).
3. **Resolve the ATel entries.** For each report with `"type": "atel"`, open the telegram. If it reports bursts,
   change `type` to `detection` (or `burst-storm`), set `date` to the last burst date given, fill `telescope`
   and `note`. If it reports a non-detection, use `non-detection`. If it is not about a repeater's activity
   (for example a localization of a one-off FRB), delete the entry.
4. **Find new reports.**
   - In `docs/data/papers.json`, look at papers since `last_search` that report bursts from a known repeater,
     monitoring campaigns, or new repeaters.
   - Search the web: "ATel FRB repeating", "FRB 20240114A", "FRB 20220912A", "FRB 20201124A", "FRB 20121102A",
     "FRB 20180916B", "FRB 20190520B", "CHIME/FRB repeater new bursts", "FAST repeating FRB active",
     "MeerKAT FRB repeater reactivation". Also check the CHIME/FRB public VOEvent page or recent CHIME/FRB
     repeater announcements if reachable.
   - Prefer the newest information. One report per source per paper or telegram is enough (the latest burst date).
5. **Periodic sources.** If a paper gives a new period, reference epoch or window for FRB 20180916B or
   FRB 20121102A, do not edit `data/repeater_ephemerides.json`. Mention it in the report to the user instead.
6. **Update the file.** Add reports with `"status": "auto"` and `"added"`. Set `last_search` to the current UTC time.
   Keep the JSON valid and indented by one space.
7. **Check.** Run `python scripts/check_repeater_reports.py` and fix every problem. Then run
   `python scripts/repeaters_build.py` to make sure the page data builds.
8. **Commit and push to main.** Commit `data/repeater_reports.json` and `docs/data/repeaters.json` with the
   message `Add repeater activity reports (YYYY-MM-DD)`. If the push is rejected, pull with rebase and push again.
9. **Report.** Send a short summary in Japanese: which repeaters were reported active (date, telescope, source),
   any non-detections, resolved ATels, and any new period or window values. If nothing new was found, say so in
   one line. Still update `last_search` and push in that case.

## Ground rules

- Correctness matters more than coverage. If a date is unclear, leave the report out.
- Never change the page, the scripts or the ephemerides in this routine.
