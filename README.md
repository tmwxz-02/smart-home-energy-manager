# Smart Home Energy Manager

**AI Fundamentals (AIF1303) · Final Project, Topic 12 · local web app, Python standard library only**

**Team:** Tuleu Tamerlan, Esen Nuradil · Stream 1, Group 3

A local application for managing **virtual** home devices, estimating their energy use and inspecting the decisions of an AI controller. The user sets up rooms and devices, adds motion-sensor readings by hand or from CSV, and the system decides for every device whether to run it. It then compares the stored decisions with a plain schedule.

> **Honesty notes.** No hardware is connected: every device is virtual and every ON/OFF command only changes simulated state. Energy is **estimated** as rated power × ON time, not measured. The demo workspace contains **synthetic** data, kept in a separate database and labelled in the UI. Savings are computed from stored history, never preset. This project is an improved version of the earlier prototype; the [requirements table](#8-requirements-coverage) shows what is covered and what is not.

## Deliverables (final-project checklist)

| Required deliverable | Where |
| --- | --- |
| Working application and live/local demo | `python app.py` or `start.bat`; page **Topic 12 walkthrough** shows the brief exactly; `python main.py` console version |
| GitHub repository | this repository (source, tests, docs) |
| Technical report | [`docs/REPORT.md`](docs/REPORT.md) · [`docs/Technical_Report.pdf`](docs/Technical_Report.pdf) |
| 5–7 slide presentation | [`docs/Presentation.pptx`](docs/Presentation.pptx) (7 slides, speaker notes) · [`docs/Presentation.pdf`](docs/Presentation.pdf) |
| 2–3 minute demo video | [`docs/demo_video.mp4`](docs/demo_video.mp4) (2 min 40 s, captioned) |
| AI usage declaration | [`docs/AI_USAGE_DECLARATION.md`](docs/AI_USAGE_DECLARATION.md) |
| Team contribution statement | [`docs/TEAM_CONTRIBUTION.md`](docs/TEAM_CONTRIBUTION.md) |
| Notebook with all numbers (syllabus: Jupyter/Colab) | [`notebooks/topic12_walkthrough.ipynb`](notebooks/topic12_walkthrough.ipynb) |
| Defense script (official timing) and Q&A | [`DEFENSE_SCRIPT.md`](DEFENSE_SCRIPT.md), [`DEFENSE.md`](DEFENSE.md) |

**Topic 12 brief → expected output** (`python main.py`, first block): best schedule **4 (18:30–19:30)**, occupancy estimate **0.273**, action **Turn Off** (one-step MDP); the app's planner (value iteration, H = 4, start-up cost) chooses **Keep On** and, on the same evening, uses 25 % less energy than the schedule with no missed comfort.

---

## 1. Problem and users

**Problem.** Devices in a home often run on fixed schedules while nobody is in the room. A controller that infers occupancy from a cheap, noisy motion sensor can skip those runs. Skipping a run while someone *is* present costs comfort, so the system must trade energy against comfort under uncertainty.

**Users.**
- A household member who wants to see how much a smarter schedule could save, and why each decision was made.
- A student or instructor who wants to inspect search, probabilistic inference and sequential decision making on realistic, stored data.

**Agent formulation (RO1).**

| Element | In this project |
| --- | --- |
| Agent | Controller of the virtual devices in each room |
| Percepts | One motion reading per room per interval (5–60 min, default 15) |
| Hidden state | True occupancy of the room |
| Actions | ON / OFF per device per interval; outside its schedule only OFF |
| Utility | −(electricity cost) − (user-defined cost of discomfort) − (start-up cost) |
| Constraints | Daily schedule per device; manual override always wins |
| Environment | Partially observable, stochastic, sequential, single agent |

---

## 2. Features

| # | Feature | Where |
| --- | --- | --- |
| 1 | Rooms and devices: add, rename/edit, rated power, comfort value, start-up cost, 24-hour schedule editor, archive and restore (history is kept) | *Rooms & devices* |
| 2 | Manual and automatic control: each device is in **Auto (AI)** or **Manual ON/OFF** mode; every command is logged; the UI always says the device is **virtual** | *Dashboard* |
| 3 | Persistent storage in SQLite: settings, rooms, devices, readings, decisions, control log, optimizer runs | `data/home.db` |
| 4 | Readings from a form or CSV import, with downloadable example files and line-by-line error messages; imports are all-or-nothing | *Readings* |
| 5 | Separate demo workspace: reproducible synthetic data (seed 42, 7 days, 3 rooms, 7 devices) in `data/demo.db`, shown with a banner | header switch *Demo* |
| 6 | Decision history: time, device, reading, prior → posterior → predicted occupancy, Q-values, action, schedule action, explanation | *AI decisions* |
| 7 | Analytics for a chosen period: estimated kWh, cost at a configurable tariff, AI vs schedule, saving or overspend, per device/day/hour, comfort (only with labels), strategy replay on identical readings, CSV export | *Analytics* |
| 8 | Responsive interface (phone to desktop), navigation, forms with validation, SVG charts, loading, empty and error states | all pages |
| + | Hill-climbing schedule optimizer with exact optimum for comparison; interactive Bayes + MDP calculator; console fallback | *Schedule optimizer*, *How the AI works*, `python main.py` |
| + | **Topic 12 walkthrough**: the brief's exact setup (one fan, 5 schedules, 2 states), input → calculation → output → explanation for each method, editable inputs, three-strategy result | *Topic 12 walkthrough*, `backend/brief.py`, notebook |

---

## 3. Running the project (Windows)

Requirements: **Python 3.10 or newer**. No packages, no internet, no paid services.

1. Double-click **`start.bat`**. It finds Python, starts the server and opens `http://127.0.0.1:8000/`.
2. Keep the black window open while using the app. Close it (or press Ctrl+C) to stop.

From a terminal in the project folder:

```bash
python app.py
```

Options: `--port 8001` (if 8000 is busy), `--network` (other devices on the same Wi-Fi can connect; `start_network.bat` does the same), `--no-browser`, `--data-dir <folder>` (use another data folder).

If `python` is not found, install Python from python.org and tick **"Add python.exe to PATH"**. In VS Code: run `open_in_vscode.bat`, then press **F5**.

**Putting it online** so others can open it at any time: see **DEPLOY.md** (free PythonAnywhere hosting, optional read-only mode and password).

**Tests**

```bash
python -m unittest -v
```

**Console fallback** (worked examples and a demo summary; uses a temporary folder):

```bash
python main.py
```

**First steps in the app**

1. *My home* starts empty. To explore immediately, click **Demo** in the header; the demo is generated on first open.
2. In *My home*: **Rooms & devices** → add a room → **Add device** (choose type, power, schedule).
3. **Readings** → enter a reading. The AI decision for each device in that room appears straight away. Or import `samples/readings_example.csv` (create rooms "Living room" and "Bedroom" first).
4. **AI decisions** → click a row for the full explanation.
5. **Analytics** → choose a period and tariff → **Compare strategies** → **Export CSV**.
6. **Schedule optimizer** → run hill climbing for a device → **Apply** if you want the new schedule.

### CSV format

```text
timestamp,room,motion,occupied
2026-11-10 08:00,Living room,1,1
2026-11-10 08:15,Living room,0,
```

- `timestamp`: local time `YYYY-MM-DD HH:MM` at the start of an interval (minutes must be a multiple of the interval length).
- `room`: an existing, non-archived room (case-insensitive).
- `motion`: `1/0`, `true/false` or `yes/no`.
- `occupied` (optional): the true occupancy if known, or empty. It is used **only** to evaluate comfort, never by the AI.
- Comma or semicolon separated; UTF-8 with or without BOM; at most 2 MB.

`samples/readings_with_errors.csv` shows every kind of error message.

---

## 4. Architecture

```text
Browser (frontend/, display only)                 Python (backend/, all calculations)
---------------------------------                 ------------------------------------
index.html, css/styles.css
js/app.js      router, workspace switch            server.py     HTTP: static files + /api/*, JSON, CSV downloads
js/api.js      fetch + X-Workspace header  ──────► api.py        routes, query validation, error -> HTTP 400/404/405
js/views/*.js  one file per page                   services.py   rooms, devices, settings, readings, control, history
js/charts.js   SVG charts                          importer.py   CSV parsing + validation (all-or-nothing)
js/ui.js       DOM helpers, states                 engine.py     reading -> Bayes -> MDP -> decision (live + replay)
                                                   priors.py     hour-of-day priors from earlier days (no look-ahead)
                                                   optimizer.py  hill-climbing service, Bayes/MDP calculator
                                                   analytics.py  period summary, CSV report, strategy replay
                                                   demo.py       reproducible synthetic data
                                                   algorithms/   bayes.py · mdp.py · hill_climbing.py (pure functions)
                                                   db.py         SQLite schema; data/home.db and data/demo.db
```

- **Two databases.** "My home" and "Demo" are separate SQLite files, chosen per request by the `X-Workspace` header. Synthetic and user data cannot mix.
- **One decision engine.** `engine.Engine` makes the live decisions and also runs the *what-if* replay, so both always follow identical rules. A test checks that replaying the demo reproduces the stored totals exactly.
- **Snapshot of parameters.** Each stored decision keeps a JSON snapshot of the model parameters it used. Changing the settings affects only new decisions.

Main tables: `rooms`, `devices`, `readings` (with prior/posterior/predicted), `decisions` (action, schedule action, Q-values, estimated Wh for both strategies, explanation), `control_log`, `optimizations`, `imports`, `settings`.

### API (summary)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/dashboard`, `/api/meta`, `/api/health` | overview, workspace info |
| GET/PUT | `/api/settings` | model settings (validated) |
| GET/POST, PUT | `/api/rooms`, `/api/rooms/{id}`; POST `/archive`, `/restore` | rooms |
| GET/POST, GET/PUT | `/api/devices`, `/api/devices/{id}`; POST `/archive`, `/restore`, `/control`; PUT `/schedule` | devices, virtual control |
| GET/POST | `/api/readings`; POST `/api/readings/import`; GET `/api/readings/sample.csv` | readings |
| GET | `/api/decisions?room&device&from&to&action&limit&offset` | history |
| GET | `/api/analytics`, `/api/analytics/report.csv`, `/api/analytics/compare` (`from,to,room,device,tariff`) | analytics |
| POST | `/api/optimize`, `/api/explain`, `/api/demo/reset` | AI tools |

Errors return `{"error": "...", "details": [...]}` with HTTP 400 (invalid input), 404 or 405.

---

## 5. The three AI methods

Each method solves a separate problem inside the app. Default values below are editable in *Settings*.

### 5.1 Hill climbing: a device's daily schedule (local search, RO2)

- **State:** 24 hourly slots, each ON or OFF (2²⁴ ≈ 16.8 million schedules).
- **Objective** (minimise expected daily cost, in money):

  ```text
  cost(s) = Σ_h [ s_h · P_kW · 1 h · tariff  +  (1 − s_h) · P(occupied at hour h) · comfort_value ]
            + startup_cost · (number of OFF→ON switches, cyclic day)
  ```

  `P(occupied at hour h)` is learned from the room's motion readings by the method of moments: `p = (rate − P(m|empty)) / (P(m|occ) − P(m|empty))`, with Laplace smoothing, clipped to [0.02, 0.98]. Hours with too few readings use the default prior. Occupancy labels are **not** used.
- **Neighbours:** the 24 schedules that differ in exactly one hour.
- **Move rule:** steepest ascent. Evaluate all neighbours and move to the cheapest one only if it is **strictly** cheaper.
- **Stop:** no neighbour is cheaper (local optimum), or 200 iterations.
- **Restarts:** the search runs from the current schedule and from N seeded random schedules, and the best result wins. The same seed always gives the same result.
- **Quality check:** without the start-up cost every hour is independent and the greedy result is exact. The start-up cost couples neighbouring hours and creates local optima. The app therefore also computes the **exact optimum by dynamic programming** (fix the state of hour 23, then a 2-state DP over the day) and shows the gap. In `test_restarts_can_escape_a_poor_local_optimum`, the search from a morning-only schedule stops 11.10 above the optimum, and random restarts find it.

### 5.2 Bayesian inference: is anyone in the room? (HMM filtering, RO3)

```text
P(occ | reading) = P(reading | occ) · P(occ) / P(reading)
P(reading)       = P(reading | occ) · P(occ) + P(reading | empty) · P(empty)
prediction       P(occ next) = P(occ) · stay_occupied + (1 − P(occ)) · become_occupied
```

Defaults: P(motion | occ) = 0.90, P(motion | empty) = 0.20, stay = 0.85, become = 0.10 per interval.

**Prior for each reading:**
1. If the room has a reading exactly one interval earlier, the prior is the prediction from that reading's posterior. This is the HMM **forward algorithm** (predict → update).
2. Otherwise the prior is the hour-of-day prior learned from **earlier days only**, so there is no look-ahead (tested).
3. With too little history, the default prior is used.

"No motion" lowers the belief but does not make it zero, because the sensor misses people who sit still. For example, prior 0.75 with no motion gives posterior 0.273.

### 5.3 Markov decision process: ON or OFF? (value iteration, RO3)

| Element | Definition |
| --- | --- |
| States | (occupancy during the interval ∈ {occupied, empty}, device state in the previous interval ∈ {on, off}) |
| Actions | {ON, OFF} inside the schedule; {OFF} outside it (auto mode never starts a device outside its schedule) |
| Transitions | occupancy follows the Markov chain above, independent of the action; device state ← action |
| Rewards (money) | ON: −P_kW·Δt·tariff, and −start-up cost if the device was off; OFF and occupied: −comfort_value·Δt; OFF and empty: 0 |
| Solution | finite-horizon **value iteration** (backward induction), horizon H = 4 intervals, γ = 1 |

```text
V_H(s) = 0
Q_k(s,a) = r(s,a) + γ Σ_s' T(s'|s,a) V_{k+1}(s'),   V_k(s) = max_a Q_k(s,a)
Q(b,a)   = b · Q_0(occ, d, a) + (1 − b) · Q_0(empty, d, a)          (QMDP)
```

**What this is, and what it is not:**
- The plan is genuinely multi-step **only because of the start-up cost**: switching OFF now changes the next state (the device is off), so restarting later costs extra. Without a start-up cost the action cannot influence the future, and lookahead gives exactly the one-step decision (tested).
- Occupancy is hidden, so the decision uses the **QMDP approximation**, which assumes occupancy becomes known after the current step. It is an approximation of the POMDP, not an exact solution.
- With **H = 1** the rule is exactly the prototype's one-step rule: choose ON if P(occ) ≥ energy cost ÷ comfort value. Ties go to ON (tested).
- Costs scale with each device's power and with the interval length. Nothing is tied to the old 48 W fan.

**Example** (48 W fan, 25 KZT/kWh, comfort 3 KZT/h, start-up 0.3 KZT, prior 0.75, no motion): posterior 0.273 → P(occ during interval) 0.305 < break-even 0.40.
- One-step rule: Q(ON) −0.300 vs Q(OFF) −0.228 → **OFF**.
- Value iteration, H = 4, fan currently ON: Q(ON) −0.650 vs Q(OFF) −0.677 → **ON**, because switching off would probably mean paying the start-up cost again soon.

Reproduce it on *How the AI works* or with `python main.py`.

---

## 6. Verification results

Verified on 2026-11-12, Windows 11, Python 3.12.8.

**Automated tests:** `python -m unittest -v` runs **64 tests, OK** (re-verified 2026-11-23).
- `tests/test_algorithms.py` (23 tests):
  - the prototype's Bayes and MDP numbers are preserved (0.931, 0.273, −6.00, −11.38, −5.45);
  - H = 1 equals the one-step rule, and start-up cost 0 makes lookahead irrelevant;
  - the start-up cost changes the decision;
  - value iteration equals brute-force expectimax;
  - the DP optimum equals brute force over 2¹⁰ schedules;
  - hill climbing ends in a true local optimum, restarts escape a poor one, and the same seed gives the same result.
- `tests/test_scenario.py` (19 tests):
  - the full scenario (room → device → reading → decision → history → analytics → CSV report);
  - data survives reconnecting;
  - units (1500 W × 30 min = 750 Wh; 0.75 kWh × 10 = 7.5);
  - validation of readings, devices and settings; the interval length is locked once readings exist;
  - manual mode and archiving; auto mode never starts a device outside its schedule;
  - the filter uses the previous interval; priors do not look ahead;
  - comfort is not reported without labels;
  - CSV import: example file, error file (every line reported, nothing stored), header problems, semicolon/BOM, duplicates;
  - the demo is reproducible and separate from home; the replay reproduces the stored decisions.
- `tests/test_wsgi.py` (4 tests): the hosting entry point `wsgi.py`: static files, no path traversal, the API flow, read-only mode, password.
- `tests/test_brief.py` (13 tests): the Topic 12 brief: interval costs, all 5 schedule costs by hand, path 1→2→3→4, a local-optimum trap and its escape, Bayes 0.2727 / 0.931, MDP Turn Off vs planner Keep On, ties go to Keep On, the true occupancy never changes a decision, `/api/brief` with validation and read-only mode.
- `tests/test_api.py` (5 tests): real HTTP server. Static files and content types, 400/404/405, the full flow over HTTP, CSV download headers, workspace separation.

**Manual UI check** (separate test data folder, `--data-dir`):
- Added a room and an AC (1200 W, 18–23). An invalid power showed a clear error.
- Entered 18:00 motion (→ ON) and 18:15 no motion. The prior 0.71 came from the filter → OFF.
- An off-grid time (18:07) and a duplicate reading were rejected.
- The error CSV was rejected with 6 line-numbered problems. The example CSV was rejected while "Bedroom" was missing, then imported 192 rows.
- History, analytics, strategy replay and CSV export showed consistent numbers.
- Manual ON and back to Auto were logged.
- After a **server restart** all rooms, readings and decisions were still there.
- At **375 px width** no page scrolls horizontally (tables scroll inside their own box). This check found and fixed an overflow on *How the AI works*.

**Demo results.** Synthetic data, seed 42, 7 days, 3 rooms, 7 devices, 2016 readings. These numbers come from invented occupancy, not from measurements. They show how the methods behave, not real-world savings.

| Strategy (same readings, same schedules) | Estimated energy | OFF→ON starts | Occupied but OFF* | ON while empty* |
| --- | ---: | ---: | ---: | ---: |
| Schedule only | 226.73 kWh | 57 | 0 min | 11 460 min |
| AI, one-step rule | 145.57 kWh | 198 | 1 785 min | 1 425 min |
| **AI, value iteration H = 4** (stored decisions) | **143.66 kWh (−36.6 %)** | **163** | 1 845 min | 1 440 min |
| Oracle (knows true occupancy) | 156.55 kWh | 83 | 0 min | 0 min |

\* device-minutes in scheduled hours, from the synthetic labels.

**Interpretation:**
- The AI removes most of the energy wasted on empty rooms.
- The price is about 31 device-hours of missed service in a week, mostly sensor misses: the sensor misses a still person 10 % of the time.
- Planning ahead (H = 4) cuts device starts by 18 % compared with the one-step rule, at similar energy.
- The oracle uses *more* energy than the AI because it never sacrifices comfort. The AI's extra "saving" is partly paid in comfort.
- Energy saved and comfort lost are reported side by side. The exchange rate between them is each device's comfort value, which the user sets.

---

## 7. Limitations

- **No hardware.** Devices are virtual and there is no integration with plugs, relays or meters. Energy is rated power × time. Real consumption varies (standby, thermostats, compressor cycles).
- **Synthetic demo.** The demo sensor follows exactly the model the controller assumes, which flatters the AI. Real sensors differ, and the sensor and transition probabilities should be estimated from labelled real data.
- **Model simplifications.**
  - One motion sensor per room, read once per interval.
  - A time-homogeneous 2-state occupancy chain.
  - The fan or heater does not affect occupancy.
  - QMDP is an approximation of the partially observable problem.
  - Hour-of-day priors ignore weekday/weekend differences.
- **Comfort** is only measurable when the user supplies occupancy labels. Comfort values and start-up costs are user assumptions.
- **Hill climbing** optimises the *expected* daily cost under the learned priors. A schedule that is good in expectation can still be poor on a given day.
- **Decision history** is a log of what was decided at the time. Readings inserted later for an earlier time do not re-run decisions that were already made.
- Single shared database and no user accounts. An online copy can be protected only with one shared password (`SHEM_PASSWORD`) and/or read-only mode (`SHEM_READ_ONLY`); see DEPLOY.md.

---

## 8. Requirements coverage

| Requirement | Status | Evidence |
| --- | --- | --- |
| Rooms and devices: add/edit, power, schedule, archive | Done | *Rooms & devices*; `test_device_validation_and_room_names`, `test_manual_mode_and_archive` |
| Manual + automatic control, clearly virtual | Done | *Dashboard*; banner on every page; `control_log` |
| SQLite persistence of settings, readings, decisions | Done | `data/*.db`; `test_data_survives_reconnect`; restart check |
| Readings via form + CSV, example file, clear errors | Done | *Readings*; `samples/`; `CsvImportTests` |
| Separate reproducible demo mode, not mixed | Done | `data/demo.db`, banner; `test_demo_is_reproducible_and_separate` |
| Decision history with time, device, reading, probability, action, explanation | Done | *AI decisions* |
| Analytics: kWh, tariff, vs schedule, saving/overspend, CSV export | Done | *Analytics*; `report.csv` |
| Responsive UI, navigation, forms, charts, loading/empty/error states | Done | checked at 375 px and desktop |
| Hill climbing explained (objective, neighbours, stop) | Done | §5.1, *Schedule optimizer* |
| Bayesian inference of presence | Done | §5.2 |
| MDP with states/actions/transitions/rewards; honest about scope | Done | §5.3: value iteration + QMDP, approximation stated |
| No preset savings; same inputs for all strategies; comfort only with labels | Done | analytics + replay; `test_comfort_needs_labels` |
| Real hardware / measured energy | **Not done** | out of scope; see limitations |
| Real labelled field data | **Not done** | only synthetic demo + user input |
| Topic 12 brief exactly (one device, 5 schedules, 2 states; best schedule, occupancy estimate, action) | Done | *Topic 12 walkthrough*; `backend/brief.py`; `tests/test_brief.py` |
| Jupyter notebook (syllabus lists Jupyter/Colab as the environment) | Done | `notebooks/topic12_walkthrough.ipynb`, executed outputs |
| Report, slides, demo video, AI declaration, team contribution | Done | `docs/` |

Syllabus outcomes addressed: **RO1** (agent formulation, §1), **RO2** (hill climbing compared with the exact optimum and restarts), **RO3** (Bayesian filtering, MDP value iteration with interpretation). RO4 (ML / neural networks / generative AI) is **not** part of this topic's implementation.

---

## 9. Folder structure

```text
fai/
├── app.py · main.py · wsgi.py (hosting) · make_zip.py · start.bat · start_network.bat · open_in_vscode.bat
├── backend/      (see Architecture)
├── frontend/     index.html · css/styles.css · js/{app,api,ui,charts}.js · js/views/*.js
├── samples/      readings_example.csv · readings_with_errors.csv
├── tests/        test_algorithms.py · test_brief.py · test_scenario.py · test_api.py · test_wsgi.py
├── notebooks/    topic12_walkthrough.ipynb (all numbers, executed)
├── docs/         REPORT.md · Technical_Report.pdf · Presentation.pptx/.pdf · demo_video.mp4 · AI_USAGE_DECLARATION.md · TEAM_CONTRIBUTION.md · screenshots/
├── data/         home.db · demo.db (created on first run; not part of the source)
├── DEPLOY.md     how to put the app online
├── DEFENSE_SCRIPT.md  speaking script for two presenters, Q&A, checklist
└── DEFENSE.md    defense plan, demo script, likely questions, AI-use declaration
```

The earlier prototype zips are kept locally for reference and are not part of the repository.
