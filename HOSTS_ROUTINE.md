# Weekly literature search for FRB host galaxies

This is the procedure for the weekly scheduled Claude task. The goal is to keep
`docs/data/hosts_lit.json` up to date with host galaxy values from papers that are not yet in
the FRBs/FRB repository (which feeds `docs/data/hosts_base.json` every Monday).

The page `docs/hosts.html` merges both files. Literature values never overwrite a value that is
already in hosts_base.json. They fill missing values, or add hosts that are not there at all.

## Steps

1. **Get the repository.** Attach `shotaro-yamasaki/frb-arxiv-daily` with push access and clone it.

2. **Know what is already there.** Read `docs/data/hosts_base.json` and `docs/data/hosts_lit.json`.
   Note `last_search` in hosts_lit.json. Search papers announced since then (or the last 10 days if it is null).

3. **Find candidate papers.**
   - In `docs/data/papers.json`, take papers since `last_search` whose `primary` or `tags` include `host`,
     and any other paper whose title or abstract mentions a localization, a host galaxy, an offset,
     a stellar mass or a star formation rate of an FRB host.
   - Search the web for recent papers, for example: "fast radio burst host galaxy", "FRB localization host",
     "CHIME outriggers host galaxies", "DSA-110 FRB hosts", "MeerKAT FRB localisation", "ASKAP CRAFT host".
     Prefer arXiv. Include journal papers only if they report new host values.
   - Also look for erratum or catalog papers that give host values for many FRBs at once.

4. **Read each candidate paper.** Use the arXiv HTML version (`https://arxiv.org/html/<id>`) or the abstract page.
   Find the table or section that lists host properties. Take only values the paper states explicitly.
   Do not estimate or convert values that need assumptions you cannot check.
   - `z`: redshift (`z_type`: "spec" or "phot")
   - `log_mstar`: log10 of stellar mass in solar masses. `log_mstar_lo` / `log_mstar_up`: errors in dex.
     Set `mstar_kind` to "stellar", or "total formed" if the paper reports the formed mass.
   - `sfr`: star formation rate in Msun/yr, with `sfr_lo` / `sfr_up`. `sfr_kind`: "SED", "Hα/nebular", etc.
     Upper limits: leave `sfr` empty and write the limit in `notes`.
   - `offset_kpc`, `offset_kpc_err`, `offset_arcsec`: projected offset of the FRB from the host centre.
   - `z_gas`: gas metallicity only if given as 12 + log(O/H).
   - `repeater`: true or false if the paper says so. `ra`, `dec`: host position in degrees if given.
   - `morphology`: short words such as "spiral", "elliptical", "dwarf", "merger".
   - `notes`: anything important in one short sentence (limits, a second candidate host, low P(O|x)).
   - `source`: `{"arxiv": "2611.01234", "ref": "Surname2026", "where": "Table 2"}`.
   - `added`: today's date (YYYY-MM-DD). `status`: "auto".

5. **Skip what is not needed.**
   - Skip a host if hosts_base.json already has every value the paper gives.
   - For a host that is in hosts_base.json, add an entry only with the values that are missing there.
   - Do not add the same FRB from the same paper twice (check existing entries).
   - FRB names have no prefix: "20240114A".

6. **Update the file.** Append the new entries to `entries`. Set `updated` and `last_search` to the current
   time in ISO format (UTC). Keep the JSON valid and indented by one space.

7. **Check.** Run `python scripts/check_hosts_lit.py`. Fix every reported problem before committing.

8. **Commit and push to main.** Commit only `docs/data/hosts_lit.json` with the message
   `Add FRB host values from the literature (YYYY-MM-DD)`. If the push is rejected, pull with rebase and push again.
   Pushing to main also publishes the site.

9. **Report.** Send a short summary in Japanese: which papers were checked, which FRBs were added
   with which values, and papers that looked relevant but gave no usable values (with the reason).
   If nothing new was found, say so in one line. Still update `last_search` and push in that case.

## Ground rules

- Correctness matters more than coverage. If a value is ambiguous, leave it out and explain it in `notes`.
- Never change entries with `"status": "checked"`. Those were checked by hand.
- Never edit hosts_base.json, the page, or other files in this routine.
