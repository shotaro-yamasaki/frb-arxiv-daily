# Weekly literature search for the transient phase space

This is the procedure for the weekly scheduled Claude task. The goal is to keep
`scripts/phase_manual.json` up to date with newly reported objects, and to rebuild
`docs/data/phase.json`, which `docs/phase.html` draws.

## What goes in phase_manual.json

- `lpt`: long-period radio transients (periods of minutes to hours). One entry per source:
  `name`, `S_min`, `S_max` (peak flux density in Jy), `W_min`, `W_max` (pulse width in s),
  `nu_GHz` (frequency of those flux densities), `D_kpc` (distance), `detail` (one or two sentences with
  the period, the telescope and band, and how the distance was obtained), `ref`
  ("Surname et al. YEAR, Journal (arXiv:XXXX.XXXXX)"), `status`, `added`.
- `he`: classes on the luminosity–duration plane. Each class has a box (`t` in s, `L` in erg/s) and an
  optional list of individual objects in `points`: `x` (duration in s), `y` (peak luminosity in erg/s),
  `label`, `detail`, `ref`, `status`, `added`.
  Add new objects to the matching class (for example a new QPE source, a new LFBOT, a new extragalactic
  magnetar giant flare, a new Einstein Probe fast X-ray transient, a new kilonova). Do not change the class boxes.
- Top-level `last_search`: ISO time of the last run.

## Steps

1. **Get the repository.** Attach `shotaro-yamasaki/frb-arxiv-daily` with push access and clone it (main branch).

2. **Know what is already there.** Read `scripts/phase_manual.json`. Note `last_search`. Search papers
   announced since then (or the last 10 days if it is missing).

3. **Find candidate papers.**
   - In `docs/data/papers.json`, look at papers since `last_search` that mention long-period transients,
     magnetar radio bursts, or compare FRBs with other transients.
   - Search the web for new discoveries since `last_search`, for example: "long-period radio transient discovery",
     "ultra-long period radio source", "quasi-periodic eruptions new source", "luminous fast blue optical transient",
     "magnetar giant flare extragalactic", "Einstein Probe fast X-ray transient luminosity", "kilonova candidate".
     Prefer arXiv and journal papers. Skip conference abstracts, press releases without numbers, and preprints
     that only re-analyse known objects without new values.

4. **Read each candidate paper** (arXiv HTML `https://arxiv.org/html/<id>` or the abstract page) and take only
   values the paper states explicitly.
   - Long-period transients: peak flux densities, pulse widths, the observing frequency of those values, and the
     distance with its method. If only a fluence is given, do not invent a width. Leave the source out and mention it
     in the report.
   - High-energy/optical objects: peak luminosity in erg/s (say which band in `detail`) and a characteristic
     duration in s (single-eruption duration, rise time, T90, or time above half maximum; say which in `detail`).
   - If the paper gives a range, use the range for LPTs and the typical or peak value for single points.

5. **Skip what is not needed.** Skip objects already in the file (check names and aliases such as
   ASKAP/DART). If a newer paper gives clearly better values for an object marked `"status": "auto"`, update it and
   say so in the report. Never change entries marked `"status": "checked"`.

6. **Update the file.** Add entries with `"status": "auto"` and `"added": "YYYY-MM-DD"`. Set `last_search` to the
   current UTC time. Keep the JSON valid and indented by one space.

7. **Check.** Run `python scripts/check_phase_manual.py` and fix every reported problem before committing.
   Do not rebuild `docs/data/phase.json` yourself: the daily workflow rebuilds it automatically after your push
   (it uses the CHIME/FRB Catalog 2 copy in `data/chimefrbcat2.csv`).

8. **Commit and push to main.** Commit only `scripts/phase_manual.json` with the message
   `Add transients to the phase space from the literature (YYYY-MM-DD)`. If the push is rejected, pull with rebase
   and push again. Pushing to main starts the workflow that rebuilds the data and publishes the site.

9. **Report.** Send a short summary in Japanese: papers checked, objects added with their values and source,
   and relevant papers that gave no usable values (with the reason). If nothing new was found, say so in one line.
   Still update `last_search` and push in that case.

## Ground rules

- Correctness matters more than coverage. If a value is ambiguous or needs an assumption, leave it out.
- Never change class boxes, the page, the build script or other files in this routine.
