# Oral Defense Plan: Smart Home Energy Manager

**AI Fundamentals (AIF1303) · Final Project, Topic 12** · target length about 10 minutes plus questions

## Before the defense

- Run `python -m unittest -v` and check that it reports **64 tests, OK**.
- Double-click `start.bat`. In the header click **Demo** once, so the demo is generated before you present.
- If you want a clean live demo of *My home*, start with an empty data folder: `python app.py --data-dir demo_day`.
- Keep a terminal ready with `python main.py` in case the browser fails.
- Both students rehearse the whole walkthrough, so either can answer any question.

## What changed since the prototype (say this first, about 45 s)

| Prototype | Now |
| --- | --- |
| One 48 W fan, 8 fixed intervals, preset readings | Any number of rooms and devices with their own power, schedule and costs; any number of days |
| Data hard-coded in `config.py` | SQLite: readings from a form or CSV; decisions and settings stored |
| Hill climbing over 5 hand-written schedules | Hill climbing over 2²⁴ daily schedules, with restarts and an exact DP optimum for comparison |
| Bayes with fixed priors | HMM forward filtering, with hour-of-day priors learned from earlier days |
| One-step MDP evaluation | Finite-horizon value iteration with a start-up cost (genuinely sequential), QMDP for the belief; H = 1 reproduces the old rule |
| One invented scenario, result shown as a fact | Results computed from stored history; strategies replayed on identical inputs; comfort only with labels; demo clearly synthetic |
| (the brief itself) | Kept exactly as the course brief states it on the **Topic 12 walkthrough** page and in `python main.py`: 5 schedules, one prior + one reading, Keep On / Turn Off |

## Walkthrough

### Student 1 (Tuleu Tamerlan): problem, setup, data (about 5 minutes)

1. **Problem and agent (45 s).** "Devices run on schedules while rooms are empty. Our agent sees one noisy motion reading per room every 15 minutes. It cannot see true occupancy, and it switches virtual devices ON or OFF. The utility is electricity cost plus the user's cost of discomfort. Everything is virtual: there is no hardware, and energy is rated power times ON time."
2. **Live setup in My home (1.5 min).**
   - *Rooms & devices* → add "Office" → **Add device**: type *Fan*, 48 W, schedule 08–18.
   - Point at the hint: "At 25 KZT/kWh the fan costs 1.20 per hour. The single-interval break-even is P(occupied) ≥ 0.40."
   - Show a validation error: power 0 → clear message.
3. **Readings (1.5 min).**
   - *Readings* → 09:00, motion → the decision appears at once with its explanation.
   - Add 09:15, no motion: "The prior is now the filter's prediction from 09:00, not a fixed number."
   - Try 09:07: "Rejected, because it is not the start of an interval."
4. **CSV import (1 min).**
   - Download **Example with errors** → import → "Nothing was stored, and every bad line is listed with its line number."
   - Then switch to **Demo**: "This workspace is synthetic, 7 days, seed 42. It is a separate database, and the banner always says so."
5. **Hand-over (15 s).** "Now my partner explains the three methods on this data."

### Student 2 (Esen Nuradil): the three methods and the results (about 5 minutes)

1. **Bayes + MDP on one decision (1.5 min).**
   - *How the AI works* → calculator: prior 0.75, **No motion**, Prototype 48 W fan, *Device was ON*.
   - "P(no motion) = 0.10 × 0.75 + 0.80 × 0.25 = 0.275. Posterior = 0.075 / 0.275 = 0.273. The transition step gives 0.305 for the coming interval."
   - "The one-step rule compares −0.300 for ON with −0.228 for OFF and switches OFF. Value iteration over 4 intervals keeps it ON (−0.650 vs −0.677), because switching off would probably mean paying the start-up cost again soon. That is the only reason the problem is multi-step, and we say so in the documentation."
   - Switch to *Device was OFF* → the decision becomes OFF.
2. **Decision history (30 s).** *AI decisions* → filter Heater → click a row: "Time, reading, prior → posterior → prediction, Q-values, action, what the schedule would have done, and the explanation. All of it is stored in SQLite."
3. **Hill climbing (1.5 min).**
   - *Schedule optimizer* → Air conditioner. "The blue bars are occupancy by hour, learned from motion readings only. The dashed line is the break-even."
   - "State: 24 ON/OFF hours. Neighbours: flip one hour. Move only if strictly cheaper. Stop at a local optimum. Restarts are seeded."
   - "We compare with the exact optimum from dynamic programming, so the quality of hill climbing is measured." Show the runs table. If every start reaches the optimum, say so honestly, then show the local-optimum case in `python main.py`, section 3: from a morning-only schedule the search stops 11.10 above the optimum, and random restarts find it.
4. **Analytics (1.5 min).**
   - *Analytics*: "AI 143.66 kWh vs schedule 226.73 kWh, 36.6 % less, estimated."
   - Comfort card: "The cost is about 31 device-hours occupied with the device OFF, mostly sensor misses."
   - **Compare strategies**: "Same readings for every strategy. Value iteration has 163 starts vs 198 for the one-step rule. The oracle uses more energy than our AI because it never sacrifices comfort, so part of our saving is paid in comfort."
   - **Export CSV.**
   - "On synthetic data whose sensor matches our model, so this is an optimistic demonstration, not a real-world result."

## Likely instructor questions

1. **Is the MDP really multi-step?**
   Only because of the start-up cost: switching OFF changes the next state (device off), so restarting later costs extra. Without a start-up cost the action cannot change the future, and lookahead gives exactly the one-step decision. The test `test_without_startup_cost_planning_does_not_change_the_decision` checks this.
2. **Occupancy is hidden. Is this a POMDP?**
   Yes. We use the QMDP approximation: solve the fully observed MDP with value iteration and weight the Q-values by the belief. It assumes occupancy becomes known after one step, so it slightly overvalues information. We state this in the README.
3. **Why hill climbing if DP finds the exact optimum?**
   The course topic is local search, and DP only works because our cost couples just neighbouring hours. A richer cost, such as a cap on daily energy or per-room power limits, would break the DP, but hill climbing still works. We keep DP as a measuring stick for hill climbing's solution quality.
4. **How do you avoid cheating with the labels?**
   Labels are never read by the AI. Priors use motion readings only, and only from earlier days. Labels are used only for comfort figures and the oracle.
5. **Where does 36.6 % come from? Is it preset?**
   It is computed from the stored decisions: the sum of the AI's estimated Wh vs the schedule's estimated Wh for the same readings. Change the settings or the schedules and replay to get a different number.
6. **Why does the oracle save less than the AI?**
   The oracle keeps devices ON whenever someone is present. Our AI sometimes switches off when someone is present but still (a sensor miss), which saves energy but costs comfort.
7. **How would this work with real hardware?**
   Replace the virtual control with a relay or smart-plug API, and readings with a real sensor feed. Measure energy with a plug meter. Estimate sensor and transition probabilities from a few labelled days.
8. **Which line chooses the action?**
   `qmdp_decision` in `backend/algorithms/mdp.py`, called from `Engine.decide` in `backend/engine.py`.
9. **Units?**
   Wh = W × minutes / 60. kWh = Wh / 1000. Cost = kWh × tariff. Tests check 1500 W × 30 min = 750 Wh, and 0.75 kWh × 10 = 7.5.

## Known limitations to state openly

Virtual devices only; estimated energy; synthetic demo whose sensor matches the model; QMDP is an approximation; hour-of-day priors ignore the weekday. Details: README §7.

## Team members and contributions

Stream 1, Group 3. Full statement: `docs/TEAM_CONTRIBUTION.md` (check it together before submission). Each student must be able to explain every method, whatever their contribution.

- **Tuleu Tamerlan** (Speaker A): problem statement and agent formulation, rooms/devices/readings and CSV import, user interface; scenario, CSV, API and hosting tests. Verification: ran the tests, walked through the live demo, imported both sample CSV files, checked phone width and persistence after restart.
- **Esen Nuradil** (Speaker B): Bayesian filter, MDP value iteration, hill climbing with the exact DP optimum; algorithm and Topic 12 brief tests. Verification: recomputed the Bayes, break-even, schedule-cost and Q-value numbers by hand; compared hill climbing with the exact optimum.
- Shared: Topic 12 walkthrough, analytics and replay, demo data, report, slides, video.

## AI use declaration (syllabus §8, Appendix)

Generative AI was used substantially in this project and is declared in full in `docs/AI_USAGE_DECLARATION.md`. Summary:

| Field | Details |
| --- | --- |
| Assignment | Final Project, Topic 12, AIF1303, stream 1, group 3, students Tuleu Tamerlan and Esen Nuradil |
| AI tool | Claude (Anthropic), Claude Opus family, in the Claude Code desktop app; 10, 12 and 23 November 2026 |
| Purpose of use | code generation and refactoring, unit tests, checking against the grading criteria, documentation, slides, demo video |
| Key prompts | build the Topic 12 app with hill climbing + Bayes + MDP; turn the prototype into a working application; check the work against all criteria; improve it to meet every requirement |
| AI contribution | most of the code, tests and documents; the students set the topic, scope and decisions and reviewed the results |
| Result verification | 64 automated tests; hand recomputation of the key numbers; manual walkthrough of every page; code reading |
| Student statement | We confirm that we are responsible for the final work and have accurately disclosed AI use. |
