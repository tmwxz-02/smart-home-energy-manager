# Smart Home Energy Manager — Technical Report

**AIF1303 AI Fundamentals · Final Project · Topic 12 "Mini Smart Home Energy Saver"**

**Team:** Tuleu Tamerlan, Esen Nuradil · Stream 1, Group 3 · QAIRU, Astana · November 2026

---

## Abstract

Household devices often run on fixed schedules while nobody is in the room. We built a local web application that controls **virtual** appliances and decides, every 15 minutes, whether each device should run. It integrates three course methods that serve one goal, *save electricity without leaving people uncomfortable*:

1. **Hill climbing** (local search) chooses a device's operating schedule;
2. **Bayesian inference** (HMM filtering) estimates from a noisy motion sensor whether the room is occupied;
3. **A Markov decision process** (value iteration) decides Keep On / Turn Off from that estimate.

The project covers the course brief exactly (one device, 5 schedules, 2 occupancy states; page *Topic 12 walkthrough*) and generalises it to many rooms and devices with 24-hour schedules, SQLite persistence, CSV import, analytics and a strategy replay. On the brief's evening scenario the planner uses **25 % less energy than the fixed schedule with no missed comfort**. On a 7-day seeded synthetic demo (3 rooms, 7 devices) it uses **36.6 % less estimated energy** than the schedule, at a stated comfort cost. **64 automated tests** pass. No hardware is connected; energy is an estimate (rated power × ON time).

---

## 1. Problem and objectives

**Problem.** A fan, light or air conditioner that follows a timetable wastes energy whenever the room is empty. A cheap motion sensor can reveal presence, but it is noisy: it misses people who sit still and sometimes fires in an empty room. Switching a device off while someone *is* present costs comfort. The controller must therefore trade energy against comfort **under uncertainty**, and over time, because restarting a device has its own cost.

**Objectives.**
- O1. Formalise the controller as a rational agent with explicit states, actions, percepts and utility.
- O2. Implement three course algorithms from different topics that work *together* on this goal.
- O3. Build a working, stable application where a user can set up a home, enter sensor data and see every decision explained.
- O4. Evaluate honestly: same inputs for all strategies, energy and comfort side by side, exact optima as a reference.

**Users.** A household member who wants to know how much a smarter schedule could save and why each decision was made; a student or instructor who wants to inspect search, probabilistic inference and sequential decision making on stored data.

## 2. Agent formulation (PEAS)

| Element | Definition |
|---|---|
| **Performance measure** | expected money cost = electricity + discomfort (person present, device off) + start-up wear; lower is better |
| **Environment** | rooms with hidden occupancy that follows a Markov chain; partially observable, stochastic, sequential, single-agent, discrete time (5–60 min intervals, default 15) |
| **Actuators** | ON / OFF command per virtual device per interval (outside its schedule only OFF; a manual override always wins) |
| **Sensors** | one binary motion reading per room per interval |

**Hidden state:** true occupancy. **Utility:** `U = −(P_kW · Δt · tariff) · [ON] − comfort_value · Δt · [OFF ∧ occupied] − startup_cost · [OFF→ON]`.

## 3. System overview

```
Browser (frontend/, display only)              Python standard library (backend/, all calculations)
index.html + js/views/*.js  ── JSON/HTTP ──►   server.py → api.py (validation, 400/404/405)
                                               services.py   rooms, devices, readings, control log
                                               importer.py   CSV validation (all-or-nothing)
                                               engine.py     reading → Bayes → MDP → decision (live and replay)
                                               priors.py     hour-of-day priors from earlier days (no look-ahead)
                                               optimizer.py  hill-climbing service, step-by-step calculator
                                               analytics.py  period summary, CSV report, strategy replay
                                               brief.py      Topic 12 exactly as written (toy inputs)
                                               algorithms/   bayes.py · mdp.py · hill_climbing.py (pure functions)
                                               db.py         SQLite: data/home.db and data/demo.db
```

*One decision engine* makes the live decisions and runs the what-if replay, so both always follow identical rules (a test replays the demo and reproduces the stored totals exactly). *Two databases* keep synthetic demo data and user data apart. Each stored decision keeps a JSON snapshot of the parameters it used.

**How the three methods work together.**

```
stored readings ─► hour-of-day priors ─► (1) HILL CLIMBING ─► operating schedule of each device
new reading ─────► (2) BAYES (HMM filter) ─► P(occupied during the interval)
                ─► (3) MDP value iteration ─► Keep On / Turn Off inside the schedule ─► history ─► analytics
```

Hill climbing decides *when the device may run*; Bayes decides *how likely someone is there now*; the MDP decides *whether to run now*, given that belief and the schedule constraint. Remove any one of them and the controller either runs blindly (no Bayes), cannot weigh energy against comfort over time (no MDP), or has no schedule to work inside (no search).

## 4. Method 1 — Hill climbing (local search)

**Why this method.** The schedule space is combinatorial (2²⁴ ≈ 16.8 million daily schedules) and the objective is cheap to evaluate, which suits local search; the course brief asks for choosing the lowest-cost operating schedule.

**Brief version (5 candidates).** Candidates are ordered narrow → broad (intervals {4}, {3,4}, {3,4,5}, {3–6}, {2–6} of an 18:00–20:00 evening, 15-min intervals). Neighbours are adjacent candidates (one interval added or removed).

```
cost(s) = Σ_ON energy  +  Σ_OFF P(occupied_k) · discomfort  +  startup · #starts
energy = 0.048 kW × 0.25 h × 25 KZT/kWh = 0.300 KZT     discomfort = 3 KZT/h × 0.25 h = 0.750 KZT
```

| Schedule | 1 | 2 | 3 | **4** | 5 |
|---|---:|---:|---:|---:|---:|
| Expected cost, KZT | 2.7750 | 2.5125 | 2.2500 | **2.1375** | 2.2875 |

From schedule 1 the search moves 1 → 2 → 3 → 4 and stops (no strictly cheaper neighbour) after 8 cost evaluations. Exhaustive checking of all candidates confirms schedule 4 (18:30–19:30) is the global optimum here. A test also builds an occupancy profile where the search **stops in a local optimum** (schedule 1 while schedule 5 is cheaper) and a restart escapes it.

**Application version (24 hours).** State: 24 hourly ON/OFF slots. Neighbours: the 24 schedules differing in one hour. Steepest ascent, strictly-better moves, stop at a local optimum or 200 iterations, plus seeded random restarts. `P(occupied at hour h)` is learned from the room's motion rates by the method of moments, `p = (rate − P(m|empty)) / (P(m|occ) − P(m|empty))`, Laplace-smoothed and clipped to [0.02, 0.98]; occupancy labels are never used. The start-up cost couples neighbouring hours and creates local optima, so the app also computes the **exact optimum by dynamic programming** (fix hour 23, then a 2-state DP over the day) and reports the gap: started from a morning-only schedule, plain hill climbing stops **11.10** above the optimum; with 10 restarts the gap is **0.00**.

## 5. Method 2 — Bayesian inference (probabilistic reasoning, HMM filtering)

**Why this method.** Occupancy is hidden and the sensor is unreliable; Bayes' rule turns a prior belief plus one noisy observation into a calibrated probability, which is exactly what a cost-based decision needs.

```
P(occ | reading) = P(reading | occ) · P(occ) / P(reading)
P(reading)       = P(reading | occ) · P(occ) + P(reading | empty) · P(empty)
prediction       P(occ next) = P(occ) · 0.85 + (1 − P(occ)) · 0.10
Sensor model: P(motion | occ) = 0.90, P(motion | empty) = 0.20
```

**Worked example (brief, interval 5, prior 0.75, no motion).** `P(reading) = 0.10 × 0.75 + 0.80 × 0.25 = 0.275`; `P(occ | no motion) = 0.075 / 0.275 = 0.273`; one transition step gives `0.305` for the coming interval. With motion the posterior is `0.675 / 0.725 = 0.931`. "No motion" lowers the belief but does not make it zero, because the sensor misses a still person 10 % of the time.

**In the application** consecutive readings are chained by the HMM **forward algorithm** (predict → update): if the room has a reading exactly one interval earlier, its prediction is the next prior; otherwise the hour-of-day prior learned from *earlier days only* is used (tested: no look-ahead).

## 6. Method 3 — Markov decision process (sequential decision making)

**Why this method.** The choice is a trade-off between an immediate certain cost (electricity) and an uncertain one (discomfort), and today's action changes tomorrow's state (a device that was switched off must pay a start-up cost to run again). An MDP models exactly that.

**Brief version (2 states × 2 actions).** States: occupied / empty. Actions: Keep On / Turn Off. Rewards (KZT): Keep On −0.300 in either state; Turn Off −0.750 if occupied, 0 if empty. Transitions: occupied→occupied 0.85, empty→occupied 0.10 (independent of the action). One-step expected reward:

```
Q(Keep On)  = −0.300
Q(Turn Off) = 0.305 × (−0.750) = −0.228   →  Turn Off      (break-even P(occ) = 0.300 / 0.750 = 0.40)
```

**Application version (value iteration).** State = (occupancy during the interval, device state in the previous interval), 4 states; actions {ON, OFF} inside the schedule, {OFF} outside; reward adds the start-up cost when switching OFF→ON. Finite-horizon **value iteration** (backward induction), H = 4 intervals, γ = 1:

```
V_H(s) = 0,   Q_k(s,a) = r(s,a) + γ Σ_s' T(s'|s,a) V_{k+1}(s'),   V_k(s) = max_a Q_k(s,a)
Belief (occupancy hidden), QMDP:  Q(b,a) = b · Q_0(occ,d,a) + (1 − b) · Q_0(empty,d,a)
```

In the same example, with the fan already ON and start-up cost 0.3 KZT, value iteration gives `Q(ON) = −0.650` vs `Q(OFF) = −0.677` → **Keep On**: switching off now would probably mean paying the start-up cost again soon. With H = 1 (or start-up cost 0) the planner reduces exactly to the one-step rule; value iteration equals brute-force expectimax. All three facts are unit-tested. *Scope:* QMDP assumes occupancy becomes known after the current step; it is an approximation of the POMDP and is labelled as such.

## 7. Testing and results

### 7.1 Automated tests — `python -m unittest -v` → **64 tests, OK**

| File | Tests | What is checked |
|---|---:|---|
| `test_algorithms.py` | 23 | prototype numbers preserved (0.931, 0.273, …); H = 1 equals the one-step rule; start-up cost changes the decision; value iteration = brute-force expectimax; DP optimum = brute force over 2¹⁰; hill climbing ends in a true local optimum; restarts escape a poor one; same seed → same result |
| `test_brief.py` | 13 | Topic 12 brief: interval costs, all 5 candidate costs by hand, path 1→2→3→4, local-optimum trap and escape, Bayes 0.2727/0.931, MDP Turn Off vs planner Keep On, tie → Keep On, truth never affects decisions, `/api/brief` incl. validation and read-only mode |
| `test_scenario.py` | 19 | full flow room → device → reading → decision → history → analytics → CSV; persistence across reconnects; unit conversions; validation; manual mode, archive; auto never starts outside the schedule; priors do not look ahead; comfort only with labels; CSV import error reporting; demo reproducible and separate; replay reproduces stored decisions |
| `test_api.py` | 5 | real HTTP server: static files, 400/404/405, full flow, CSV headers, workspace separation |
| `test_wsgi.py` | 4 | hosting entry point: static files, no path traversal, read-only mode, password |

### 7.2 Topic 12 brief — the same evening three ways

Same readings (motion at 18:30 and 18:45 only), same chosen schedule 4; the true occupancy (18:30–19:15) is used only for scoring.

| Strategy | Energy | Starts | Occupied but OFF | ON while empty | Total cost |
|---|---:|---:|---:|---:|---:|
| Schedule only | 48 Wh | 1 | 0 min | 15 min | 1.500 KZT |
| AI, one-step MDP | 24 Wh | 1 | 15 min | 0 min | 1.650 KZT |
| **AI, value iteration H = 4** | **36 Wh** | 1 | **0 min** | **0 min** | **1.200 KZT** |

*Interpretation.* The one-step rule switches off at 19:00 after one silent reading and leaves a present person without the fan; the planner keeps the fan on through that interval (re-starting would cost more) and switches off at 19:15 when the room is really empty. Result: 25 % less energy than the schedule and no missed comfort.

### 7.3 Full application — 7-day synthetic demo (seed 42, 3 rooms, 7 devices, 2016 readings)

| Strategy (same readings and schedules) | Est. energy | OFF→ON starts | Occupied but OFF* | ON while empty* |
|---|---:|---:|---:|---:|
| Schedule only | 226.73 kWh | 57 | 0 min | 11 460 min |
| AI, one-step rule | 145.57 kWh | 198 | 1 785 min | 1 425 min |
| **AI, value iteration H = 4** | **143.66 kWh (−36.6 %)** | **163** | 1 845 min | 1 440 min |
| Oracle (knows true occupancy) | 156.55 kWh | 83 | 0 min | 0 min |

\* device-minutes in scheduled hours, from synthetic labels.

*Interpretation.* The AI removes most energy wasted on empty rooms (191 h → 24 h of ON-while-empty). The price is about 31 device-hours of missed service per week, mostly sensor misses. Planning ahead cuts device starts by 18 % versus the one-step rule at similar energy. The oracle uses *more* energy than the AI because it never sacrifices comfort, so part of the AI's extra saving is paid in comfort; we report both, and the exchange rate is each device's user-set comfort value. Because the synthetic sensor follows the controller's own model, these numbers flatter the AI and are **not** real-world savings.

### 7.4 Manual checks

Invalid power, off-grid times (18:07), duplicate readings and the error CSV (6 line-numbered problems) are rejected with clear messages; the example CSV imports 192 rows; manual ON and return to Auto are logged; all data survives a server restart; at 375 px width no page scrolls horizontally, including the new *Topic 12 walkthrough* page; the browser console shows no errors.

## 8. User interface and user experience

Responsive single-page app (phone to desktop), sidebar navigation, a workspace switch (*My home* / *Demo*) with a banner on synthetic data, and a permanent "virtual devices" notice. Forms validate input and show line-by-line errors; every list has loading, empty and error states. Charts are SVG and animate in. The soft-graphite monochrome theme has a moving background: a dot grid, soft blobs and a particle network shift opposite to the mouse (parallax). Page changes fade and slide, the active menu item and the workspace switch slide to their new place, and buttons fill smoothly on hover; all motion is disabled when the OS asks for reduced motion. Every decision row expands into a plain-English explanation (prior → posterior → belief → Q-values → action). *Topic 12 walkthrough* lets the examiner change the start schedule, the interval and the sensor reading and watch all three steps recompute. *How the AI works* contains the formal models and a live calculator. Screenshots: `docs/screenshots/`.

## 9. Limitations, risks and responsible use

- **No hardware**: devices are virtual; energy = rated power × time (real consumption varies with standby and thermostats).
- **Data**: the demo is synthetic and its sensor matches the model; probabilities should be re-estimated from labelled real data.
- **Model**: one sensor per room, a time-homogeneous 2-state chain, hour-of-day priors that ignore weekdays, QMDP approximation.
- **Comfort** is measurable only with occupancy labels; comfort values and start-up costs are user assumptions.
- **Privacy**: occupancy history reveals when people are at home. All data stays in a local SQLite file; nothing is sent to external services; an online copy can be password-protected or read-only.
- **Human control**: a manual override always wins and every command is logged; the AI never starts a device outside its schedule.

## 10. Future development

Real smart plugs (MQTT/Zigbee) and measured energy; learning the sensor and transition probabilities from labelled data (EM / Baum–Welch); several sensors per room; an exact POMDP solver for small cases; weekday-aware priors; time-of-use tariffs and Q-learning when the model is unknown. The architecture (pure algorithm functions behind one engine) allows these without rewriting the UI.

## 11. Reproducibility

Python 3.10+, standard library only. `python app.py` (web app at http://127.0.0.1:8000), `python main.py` (console: Topic 12 brief and worked examples), `python -m unittest -v` (tests), `notebooks/topic12_walkthrough.ipynb` (all numbers with outputs). The demo is regenerated from seed 42. Verified on Windows 11, Python 3.12.

## References

1. Russell, S. J., Norvig, P. *Artificial Intelligence: A Modern Approach*, 4th ed. Pearson — chapters on local search, probabilistic reasoning over time (HMM filtering), and sequential decisions (MDPs, value iteration).
2. Littman, M. L., Cassandra, A. R., Kaelbling, L. P. (1995). Learning policies for partially observable environments: scaling up. *ICML* — the QMDP approximation.
3. QAIRU AIF1303 lecture notes: Local Search (week 3), MDP and Reinforcement Learning (week 5), Probability and Bayesian Networks (week 6), Hidden Markov Models (week 7).

## Appendix A — AI usage declaration

See `docs/AI_USAGE_DECLARATION.md` (also reproduced in `DEFENSE.md`).

## Appendix B — Team contribution statement

See `docs/TEAM_CONTRIBUTION.md`.
