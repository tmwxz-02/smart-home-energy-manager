# Defense script: Smart Home Energy Manager

**Tuleu Tamerlan (Speaker A) · Esen Nuradil (Speaker B) · English · follows the official defense format**

| Part | Time | Who | Slides |
|---|---|---|---|
| 1. Problem statement and project objectives | 2 min | A | 1–2 |
| 2. Live demo | 3–5 min (target 4) | A, then B | app |
| 3. Explanation of the three AI topics | 2 min | B (A adds integration) | 3–5 |
| 4. Questions and answers | up to 3 min | each student answers individually | 6–7 as backup |

The text to say is in normal font. *Italic lines in Russian* explain what each part means; do not read them aloud. **[Brackets]** say what to click.

Before you start: run `python app.py --data-dir demo_day` (clean "My home"), open the app and the slides, and keep the Demo workspace generated (click *Demo* once).

---

## Part 1 · Problem and objectives · Speaker A · 2 minutes · slides 1–2

> Good afternoon. We are Tuleu Tamerlan and Esen Nuradil, stream one, group three. Our project is the Smart Home Energy Manager, topic twelve.
>
> The problem: many devices at home run on a fixed schedule, even when nobody is in the room. This wastes electricity. A motion sensor can tell us whether someone is there, but it is noisy: it misses a person who sits still, and sometimes it fires in an empty room. And if we switch a device off while someone is there, that person is uncomfortable.
>
> So our objective is: decide every fifteen minutes whether each device should run, to save energy without leaving people uncomfortable. We use three methods from the course that work together: hill climbing chooses the schedule, Bayesian inference estimates whether the room is occupied, and a Markov decision process decides Keep On or Turn Off.
>
> We formulated it as an agent. It perceives one motion reading per room per interval. The true occupancy is hidden. Its actions are ON or OFF. Its goal is to minimise electricity cost plus discomfort cost plus start-up cost. The environment is partially observable, stochastic and sequential.
>
> One honest point: there is no real hardware. Devices are virtual and energy is estimated from rated power and time. The demo data is synthetic, and the app always says so.

*Представились. Проблема: приборы работают по расписанию, даже когда никого нет; датчик шумный; выключать при человеке — дискомфорт. Цель: каждые 15 минут решать, включать ли прибор. Три метода работают вместе. Агент: видит датчик, не видит присутствие, действия ON/OFF, цель — минимум затрат. Честно: железа нет, данные демо — синтетика.*

---

## Part 2 · Live demo · 4 minutes

### 2a. Speaker A · setting up and live decisions (about 2 minutes)

**[My home → Rooms & devices → Add room "Office" → Add device: Fan, 48 W, schedule 18 to 22]**

> The user adds rooms and devices. Each device has a rated power, a schedule, a comfort value — how much one hour without it is worth when someone is there — and a start-up cost.

**[Readings → today 18:00, Motion detected → Save]**

> Now a sensor reading. The AI decides immediately, for every device in the room.

**[Add 18:15, No motion → Save → AI decisions → click the 18:15 row]**

> Here is the explanation: the prior came from the previous reading, the Bayes posterior, the probability for the next fifteen minutes, the MDP values, and the action. Every decision is stored in SQLite with these numbers.

**[Readings → Import CSV → choose readings_with_errors.csv]**

> Data can also come from a CSV file. If the file has errors, nothing is saved and every problem is listed by line.

*Комната → прибор → показание → решение с объяснением. CSV с ошибками: ничего не сохраняется, ошибки по строкам.*

### 2b. Speaker B · the brief and the results (about 2 minutes)

**[Topic 12 walkthrough]**

> This page is topic twelve exactly as the brief describes it: one fan, five operating schedules, two occupancy states. On top you see the three expected outputs: best schedule four, occupancy estimate 0.273, action Turn Off.

**[Scroll to "Result: the same evening three ways"]**

> We ran the same evening three ways. The fixed schedule uses 48 watt-hours and runs fifteen minutes in an empty room. The one-step rule uses only 24, but leaves a person without the fan for fifteen minutes. Our planner uses 36 watt-hours, twenty-five percent less than the schedule, with no missed comfort. It has the lowest total cost.

**[Demo → Analytics → Compare strategies on the same readings]**

> On seven days of synthetic data with seven devices: the schedule uses 226.7 kilowatt-hours, our AI 143.7 — 36.6 percent less. The price is about 31 device-hours of missed comfort, which we report next to the saving.

*Страница темы 12: три ожидаемых результата. Один вечер тремя способами: планировщик −25 % энергии без потери комфорта. На демо за 7 дней: −36,6 %, но ~31 час дискомфорта — показываем честно.*

---

## Part 3 · The three AI topics · Speaker B · 2 minutes · slides 3–5

> **Hill climbing — local search.** The state is one schedule. The cost is energy, plus the probability that someone is there times the discomfort when the device is off, plus start-up costs. From schedule one we look at the neighbours, move only if a neighbour is strictly cheaper, and stop when none is: one, two, three, four, stop. In the full app the schedule is 24 hours; hill climbing can get stuck, so we use random restarts and compare with the exact optimum from dynamic programming.
>
> **Bayesian inference.** Prior 0.75, no motion. The probability of no motion is 0.10 times 0.75 plus 0.80 times 0.25, that is 0.275. The posterior is 0.075 divided by 0.275: 0.273. It drops, but not to zero, because the sensor misses a still person ten percent of the time. In the app each reading's prediction becomes the next prior — the forward algorithm of a hidden Markov model.
>
> **MDP.** Two states, occupied or empty; two actions, Keep On or Turn Off. Keep On costs 0.30; Turn Off costs 0.75 only if someone is there. With probability 0.305, Keep On gives minus 0.300 and Turn Off minus 0.228, so one step ahead we turn off. But our planner uses value iteration four intervals ahead with a start-up cost, and then Keep On wins, minus 0.650 against minus 0.677, because switching off would mean paying to start again soon. That is why it kept comfort in the result.

**Speaker A (10 s):**

> So the three methods serve one goal: search decides when a device may run, Bayes estimates whether someone is there, and the MDP decides whether to run now. Thank you, we are ready for your questions.

*Hill climbing: состояние, стоимость, соседи, остановка; 1→2→3→4. Байес: 0,75 → 0,273. MDP: одношаговое правило — выключить; value iteration с учётом стоимости включения — оставить. Три метода — одна цель.*

---

## Cheat sheet: numbers to know

| What | Number |
| --- | --- |
| Interval | 15 minutes; fan 48 W; tariff 25 KZT/kWh |
| Energy per ON interval | 0.048 kW × 0.25 h × 25 = **0.300 KZT** |
| Discomfort per OFF interval if occupied | 3 KZT/h × 0.25 h = **0.750 KZT** |
| Break-even | 0.300 ÷ 0.750 = **0.40** |
| Sensor | P(motion \| occupied) = 0.90, P(motion \| empty) = 0.20 |
| Bayes example | prior 0.75, no motion → P(reading) 0.275 → posterior **0.273** → next interval **0.305**; with motion **0.931** |
| Brief schedule costs | 2.7750 · 2.5125 · 2.2500 · **2.1375** · 2.2875 → best **schedule 4 (18:30–19:30)**, path 1→2→3→4 |
| One-step rule | Keep On −0.300, Turn Off −0.228 → **Turn Off** |
| Value iteration H = 4 | ON −0.650, OFF −0.677 → **Keep On** (device was on, start-up 0.3) |
| Brief evening result | schedule 48 Wh / 1.500 KZT · one-step 24 Wh, 15 min missed / 1.650 · planner **36 Wh, 0 missed / 1.200** |
| Demo, schedule only | **226.73 kWh** |
| Demo, AI | **143.66 kWh, −36.6 %**; about **31 device-hours** occupied but off |
| Device starts | AI 163 vs one-step 198 (−18 %) |
| Oracle | 156.55 kWh, 0 discomfort |
| Hill climbing, 24 h | stuck 11.10 above the optimum; 10 restarts → gap 0.00 |
| Tests | **64 tests, all pass** |

---

## Questions and short answers

Both speakers should know all answers. *Russian line = what the answer means.*

**1. Is your MDP really multi-step?**
> Only because of the start-up cost. Switching off changes the next state, so restarting costs extra. Without a start-up cost, planning gives the same answer as one step. We have a test for this.
*Многошаговость только из-за стоимости включения; без неё результат = одношаговому. Есть тест.*

**2. Occupancy is hidden. Is this a POMDP?**
> Yes. We use the QMDP approximation: we solve the normal MDP and weight the values by our belief. It assumes we will know the state after one step, so it is optimistic.
*Да, это POMDP. Используем приближение QMDP, оно немного оптимистично.*

**3. Why hill climbing for only five schedules? That is just a maximum.**
> In the brief, yes, five candidates could be checked directly, and we do check them: exhaustive search confirms schedule four. Hill climbing matters in the full app, where there are 2 to the 24 schedules. There it can get stuck, so we use restarts and measure the gap to the exact optimum.
*На 5 вариантах можно перебрать — мы и перебираем для проверки. Hill climbing нужен для 24-часового расписания (16,8 млн вариантов).*

**4. Why hill climbing if dynamic programming finds the exact answer?**
> DP works here only because the cost depends on neighbouring hours. With more complex rules, for example a daily energy limit, DP would not work, but hill climbing would. We use DP to check the quality.
*DP работает только из-за простой формы стоимости; hill climbing универсальнее. DP — для проверки качества.*

**5. Where do the priors come from?**
> From motion readings of earlier days only. We never use future data, and we never use the occupancy labels for decisions.
*Только из прошлых дней и только из датчика. Метки присутствия AI не видит.*

**6. Is the 36.6 % saving preset?**
> No. It is computed from the stored decisions. If you change the settings or the schedule and replay, you get a different number.
*Нет, считается из сохранённых решений.*

**7. Why does the oracle save less than the AI?**
> The oracle keeps devices on whenever someone is there. Our AI sometimes switches off when a person sits still and the sensor misses them. That saves energy but costs comfort.
*Оракул не жертвует комфортом, а AI иногда ошибается и выключает прибор при человеке.*

**8. Why is "no motion" not "empty"?**
> Because the sensor misses a still person ten percent of the time. With a high prior, some probability stays on "occupied".
*Датчик пропускает неподвижного человека в 10 % случаев.*

**9. How would this work with real devices?**
> We would replace the virtual control with smart plugs or relays, read a real sensor, measure energy with a plug meter, and learn the probabilities from a few labelled days.
*Умные розетки или реле, настоящий датчик, счётчик, обучение вероятностей на реальных данных.*

**10. How do you compare strategies fairly?**
> All strategies get exactly the same readings, devices and settings. The app replays the stored readings through each strategy. The true occupancy is used only to score, never to decide; a test flips it and checks that no decision changes.
*Одинаковые входные данные; истина только для оценки — есть тест.*

**11. Which line of code chooses the action?**
> The function `qmdp_decision` in `backend/algorithms/mdp.py`. It is called from `Engine.decide` in `backend/engine.py`. For the brief, `mdp_step` in `backend/brief.py`.

**12. How do you calculate energy?**
> Watt-hours equal watts times minutes divided by sixty. Kilowatt-hours are watt-hours divided by a thousand. Cost is kilowatt-hours times the tariff.
*Вт·ч = Вт × мин / 60; кВт·ч = Вт·ч / 1000; стоимость = кВт·ч × тариф.*

**13. What would you improve?**
> Real sensor data, weekday and weekend priors, learning the probabilities with Baum–Welch, and a full POMDP solution instead of QMDP.
*Реальные данные, разные вероятности для будней и выходных, обучение вероятностей, точный POMDP.*

**14. Who did what? Did you use AI tools?**
> Answer as in `docs/TEAM_CONTRIBUTION.md` and `docs/AI_USAGE_DECLARATION.md`: yes, we used Claude in Claude Code for most of the code and documents; we set the scope, made the decisions, verified the numbers by hand and with 64 tests, and we can explain every part.
*Отвечать так же, как в декларации и в распределении вклада. Каждый должен уметь объяснить любой метод.*

**If you do not know an answer:** "That is a good question. We did not test this, but we think ... because ..." Never invent numbers.
*Если не знаете ответа: честно скажите, что не проверяли, и порассуждайте. Цифры не выдумывайте.*

---

## Preparation checklist

**Before submission**
- [ ] Both read and, if needed, correct `docs/TEAM_CONTRIBUTION.md` and `docs/AI_USAGE_DECLARATION.md`.
- [ ] Each speaker reads `docs/REPORT.md` §4–6 (the three methods) once.

**Rehearsal (at least twice)**
- [ ] Rehearsal 1: read the script aloud with the app open; time it (parts 1–3 ≤ 9 minutes).
- [ ] Rehearsal 2: swap roles. Each person must be able to present every part and answer every question alone.
- [ ] Recalculate on paper: Bayes 0.75 → 0.273; break-even 0.40; schedule 4 cost 2.1375.

**The day before**
- [ ] Laptop: `python -m unittest` (64 OK) and `start.bat`.
- [ ] Online copy (if used): PythonAnywhere → Web → "Run until 1 month from today"; Demo → Settings → Regenerate demo data.

**At the defense**
- [ ] Open the app and the slides **before** you start. Keep `docs/demo_video.mp4` ready as a backup.
- [ ] If the browser fails: `python main.py` prints the Topic 12 brief and the worked examples in the terminal.
- [ ] For the live part use a clean data folder: `python app.py --data-dir demo_day`.
