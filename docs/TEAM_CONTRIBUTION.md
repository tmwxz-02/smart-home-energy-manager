# Team Contribution Statement

**Project:** Smart Home Energy Manager (AIF1303 Final Project, Topic 12) · **Stream 1, Group 3** · **Team size:** 2

Both members worked on the project together, reviewed each other's parts and can explain all three algorithms and every part of the code (the brief requires that each member answers questions individually). AI assistance is declared separately in `AI_USAGE_DECLARATION.md`.

| Area | Tuleu Tamerlan | Esen Nuradil |
|---|:---:|:---:|
| Topic choice, problem statement, agent (PEAS) formulation | **lead** | review |
| Rooms & devices, virtual control, settings (services, UI pages) | **lead** | review |
| Readings: manual form and CSV import with validation, sample files | **lead** | review |
| Bayesian inference / HMM filter (`algorithms/bayes.py`, `engine.py`) | review | **lead** |
| MDP and value iteration (`algorithms/mdp.py`) | review | **lead** |
| Hill climbing and exact DP optimum (`algorithms/hill_climbing.py`, optimizer page) | review | **lead** |
| Topic 12 walkthrough (`brief.py`, page, notebook) | shared | shared |
| Analytics, strategy replay, demo data generator | shared | shared |
| Automated tests | scenario, CSV, API, hosting tests | algorithm and brief tests |
| User interface and UX checks (desktop and phone) | **lead** | review |
| Technical report, slides, demo video, README | shared | shared |
| Defense | Part 1: problem, agent, live demo (setup, readings) | Part 2: Bayes, MDP, hill climbing, results |

**Approximate share of work:** Tuleu Tamerlan 50 %, Esen Nuradil 50 %.

### Individual verification performed

- **Tuleu Tamerlan:** ran the full test suite; walked through the live-demo scenario (add room and device, enter readings 18:00 motion / 18:15 no motion, import `readings_example.csv` and `readings_with_errors.csv`); checked the interface at phone width; restarted the server and confirmed the data persisted.
- **Esen Nuradil:** recomputed by hand the Bayes posterior (0.273, 0.931), the break-even probability (0.40), the five schedule costs of the Topic 12 brief (2.7750 … 2.1375) and the one-step Q-values (−0.300 vs −0.228); compared hill climbing with the exact optimum on the Optimizer page.

**Signatures:** Tuleu Tamerlan ______________   Esen Nuradil ______________

> This split was drafted from the defense roles. Before submitting, both members must check it and correct any line that does not match who actually did what.
