# Defense speech — Smart Home Energy Manager

**Tuleu Tamerlan (A) · Esen Nuradil (B) · about 9 minutes + questions**

Read the English text aloud. The Russian line under each paragraph is only for you — do not read it. **[Brackets]** = what to click.

---

## PART 1 — Problem and objectives · Tamerlan · 2 min

Good afternoon. We are Tuleu Tamerlan and Esen Nuradil, stream one, group three. Our project is the Smart Home Energy Manager. It is topic twelve.

*Добрый день. Мы — Тулеу Тамерлан и Есен Нурадил, поток 1, группа 3. Наш проект — Smart Home Energy Manager, тема 12.*

Here is the problem. Many devices at home work on a fixed schedule. They stay on even when nobody is in the room. This wastes electricity.

*Проблема: многие приборы работают по расписанию и остаются включёнными, даже когда в комнате никого нет. Это лишняя трата электричества.*

A motion sensor can tell us if someone is there. But the sensor is not perfect. It misses a person who sits still, and sometimes it fires in an empty room. And if we turn a device off while a person is there, that person is uncomfortable.

*Датчик движения может подсказать, есть ли кто-то в комнате, но он ошибается: не видит неподвижного человека и иногда срабатывает в пустой комнате. А если выключить прибор при человеке — ему некомфортно.*

So our goal is simple. Every fifteen minutes, the system decides: should this device be on or off? We want to save energy, but not make people uncomfortable.

*Цель: каждые 15 минут система решает, включить прибор или выключить. Экономим энергию, но не в ущерб комфорту.*

We use three methods from the course. They work together. Hill climbing chooses the schedule. Bayesian inference guesses if the room is occupied. And a Markov decision process decides: keep on or turn off.

*Мы используем три метода из курса, и они работают вместе: hill climbing выбирает расписание, байесовский вывод оценивает, занята ли комната, а марковский процесс принятия решений решает — оставить или выключить.*

We describe the system as an agent. The agent sees one motion reading every fifteen minutes. It cannot see if a person is really there — that is hidden. It can switch a device on or off. Its goal is to make the total cost as low as possible: electricity, plus discomfort, plus the cost of starting a device again. The environment is partially observable, random and sequential.

*Систему мы описали как агента. Он видит одно показание датчика раз в 15 минут, но не видит, есть ли человек на самом деле — это скрыто. Он может включить или выключить прибор. Цель — минимальная общая стоимость: электричество + дискомфорт + стоимость повторного включения. Среда частично наблюдаемая, случайная и последовательная.*

One honest point before the demo. We have no real hardware. All devices are virtual. Energy is estimated from the power and the time. The demo data is synthetic, and the app always shows this.

*Честно до демо: настоящего оборудования нет, приборы виртуальные, энергия рассчитывается по мощности и времени, демо-данные искусственные, и сайт всегда это показывает.*

---

## PART 2 — Live demo · 4 min

### Tamerlan · about 2 min

**[My home → Rooms & devices → Add room "Office" → Add device: Fan, 48 W, schedule 18 to 22]**

First, the user adds a room and a device. Every device has a power, a schedule, a comfort value and a start-up cost. The comfort value means: how much one hour without this device is worth, when someone is in the room.

*Сначала пользователь добавляет комнату и прибор. У каждого прибора есть мощность, расписание, «цена комфорта» и стоимость включения. Цена комфорта — сколько стоит час без прибора, когда в комнате кто-то есть.*

**[Readings → 18:00, Motion detected → Save]**

Now I add a sensor reading: motion at six p.m. The AI makes a decision immediately, for every device in this room.

*Теперь добавляю показание датчика: движение в 18:00. ИИ сразу принимает решение для каждого прибора в комнате.*

**[Add 18:15, No motion → Save → AI decisions → click the 18:15 row]**

Here you can see the full explanation. The prior comes from the previous reading. Then the Bayes posterior. Then the probability for the next fifteen minutes. Then the values of the MDP, and the action. Everything is saved in the database.

*Здесь видно полное объяснение: априорная вероятность из прошлого показания, байесовская апостериорная, вероятность на следующие 15 минут, значения MDP и действие. Всё сохраняется в базе.*

**[Readings → Import CSV → readings_with_errors.csv]**

Readings can also come from a CSV file. If the file has mistakes, nothing is saved, and every mistake is shown with its line number. Now Nuradil will continue.

*Показания можно загрузить из CSV. Если в файле ошибки — ничего не сохраняется, и каждая ошибка показана с номером строки. Дальше продолжит Нурадил.*

### Nuradil · about 2 min

**[Topic 12 walkthrough]**

This page shows topic twelve exactly as the task describes it: one fan, five schedules, two states. At the top are the three results: the best schedule is number four, the probability that the room is occupied is 0.273, and the action is "turn off".

*Эта страница — тема 12 ровно как в задании: один вентилятор, пять расписаний, два состояния. Наверху три результата: лучшее расписание №4, вероятность занятости 0,273, действие — выключить.*

**[Scroll down to "Result: the same evening three ways"]**

Here we tested the same evening in three ways. The fixed schedule uses 48 watt-hours, and the fan runs fifteen minutes in an empty room. The simple one-step rule uses only 24, but a person stays without the fan for fifteen minutes. Our planner uses 36 watt-hours. That is twenty-five percent less than the schedule, and nobody is uncomfortable. It has the lowest total cost.

*Один и тот же вечер тремя способами. Расписание: 48 Вт·ч и 15 минут работы в пустой комнате. Простое правило: 24 Вт·ч, но человек 15 минут без вентилятора. Наш планировщик: 36 Вт·ч — на 25% меньше расписания, и без дискомфорта. Общая стоимость самая низкая.*

**[Demo → Analytics → Compare strategies on the same readings]**

Here is a bigger test: seven days, seven devices, synthetic data. The schedule uses 226.7 kilowatt-hours. Our AI uses 143.7. That is 36.6 percent less. But we show the price too: about 31 hours when someone was in the room and the device was off.

*Большой тест: 7 дней, 7 приборов, синтетические данные. Расписание — 226,7 кВт·ч, наш ИИ — 143,7, это на 36,6% меньше. Но мы показываем и цену: около 31 часа, когда человек был в комнате, а прибор выключен.*

---

## PART 3 — The three AI methods · Nuradil · 2 min

**[Slides 3–5]**

First, hill climbing. This is local search. The state is one schedule. The cost is the energy, plus the chance that someone is there times the discomfort, plus the start-up costs. We start from schedule one. We look at the neighbours and move only if a neighbour is cheaper. One, two, three, four — then no neighbour is cheaper, so we stop. In the full app the schedule has 24 hours, so the search can get stuck. That is why we restart from random schedules and compare with the exact best answer.

*Первый — hill climbing, локальный поиск. Состояние — расписание. Стоимость — энергия + вероятность присутствия × дискомфорт + стоимость включений. Начинаем с расписания 1, смотрим соседей и переходим, только если сосед дешевле: 1, 2, 3, 4 — дальше дешевле нет, стоп. В полном приложении расписание на 24 часа, поиск может застрять, поэтому есть случайные перезапуски и сравнение с точным оптимумом.*

Second, Bayesian inference. Before the reading, the chance that someone is in the room is 0.75. The sensor shows no motion. The chance of "no motion" is 0.10 times 0.75 plus 0.80 times 0.25, which is 0.275. So the new chance is 0.075 divided by 0.275, which is 0.273. It goes down, but not to zero, because the sensor misses a still person ten percent of the time.

*Второй — байесовский вывод. До показания вероятность присутствия 0,75. Датчик: движения нет. Вероятность «нет движения» = 0,10 × 0,75 + 0,80 × 0,25 = 0,275. Новая вероятность = 0,075 / 0,275 = 0,273. Падает, но не до нуля: датчик пропускает неподвижного человека в 10% случаев.*

Third, the Markov decision process. There are two states: occupied or empty. There are two actions: keep on or turn off. Keeping it on costs 0.30. Turning it off costs 0.75, but only if someone is there. If we look only one step ahead, keep on is minus 0.300, turn off is minus 0.228, so we turn off. But our planner looks four steps ahead with value iteration, and it remembers that starting the fan again also costs money. Then keep on is better: minus 0.650 against minus 0.677. That is why the planner kept people comfortable in our result.

*Третий — MDP. Два состояния: занято или пусто. Два действия: оставить или выключить. Оставить стоит 0,30, выключить — 0,75, но только если человек есть. Если смотреть на шаг вперёд: оставить −0,300, выключить −0,228 — выключаем. Но наш планировщик с value iteration смотрит на 4 шага вперёд и учитывает, что повторное включение тоже стоит денег. Тогда лучше оставить: −0,650 против −0,677. Поэтому планировщик сохранил комфорт.*

**Tamerlan (closing, 15 sec):**

So, the three methods have one goal. Search decides when a device may run. Bayes estimates if someone is there. The MDP decides if it should run now. Thank you. We are ready for your questions.

*Итак, у трёх методов одна цель: поиск решает, когда прибору можно работать, Байес — есть ли кто-то, MDP — включать ли сейчас. Спасибо, готовы к вопросам.*

---

## Likely questions — short answers

**Why hill climbing for only five schedules?**
In the task, yes, we could just check all five, and we do check them — it confirms schedule four. Hill climbing is needed in the full app, where there are about seventeen million daily schedules.
*На пяти можно перебрать, и мы перебираем для проверки. Hill climbing нужен для 24-часового расписания — там ~17 млн вариантов.*

**Is your MDP really multi-step?**
Only because of the start-up cost. Turning off changes the next state, so starting again costs extra. Without that cost, the answer is the same as one step. We have a test for this.
*Многошаговость только из-за стоимости включения. Без неё ответ как у одношагового правила. Есть тест.*

**Occupancy is hidden. Is this a POMDP?**
Yes. We use an approximation called QMDP. It is not the exact solution, and we say this in the report.
*Да. Используем приближение QMDP — не точное решение, и мы это пишем в отчёте.*

**Is the 36.6 percent saving fixed in the code?**
No. It is calculated from the saved decisions. If you change the settings, the number changes.
*Нет, считается из сохранённых решений. Меняются настройки — меняется число.*

**Why does the oracle use more energy than your AI?**
The oracle never turns a device off when someone is there. Our AI sometimes makes a mistake when the sensor misses a person. That saves energy but costs comfort.
*Оракул никогда не выключает при человеке, а наш ИИ иногда ошибается, когда датчик не видит человека — экономия за счёт комфорта.*

**How would it work with real devices?**
We would use smart plugs, a real sensor and an energy meter, and learn the probabilities from real data.
*Умные розетки, настоящий датчик, счётчик энергии и обучение вероятностей на реальных данных.*

**Which code chooses the action?**
The function `qmdp_decision` in `backend/algorithms/mdp.py`. It is called from `Engine.decide` in `backend/engine.py`.
*Функция qmdp_decision в mdp.py, её вызывает Engine.decide в engine.py.*

**Who did what? Did you use AI tools?**
Tamerlan led the problem, the data part and the interface. Nuradil led the three algorithms and their tests. Yes, we used Claude in Claude Code for most of the code and documents. We decided the scope, checked the numbers by hand and with 64 tests, and we can explain every part.
*Тамерлан — задача, данные и интерфейс; Нурадил — три алгоритма и их тесты. Да, использовали Claude для большей части кода и документов; мы задавали рамки, проверяли числа вручную и 64 тестами и можем объяснить любую часть.* (Скажите так, как было на самом деле.)

**If you do not know the answer:**
"That is a good question. We did not test this, but we think … because …"
*Если не знаете: «Хороший вопрос. Мы это не проверяли, но думаем… потому что…». Числа не выдумывать.*

---

## Numbers to remember

| | |
|---|---|
| Interval | 15 min · fan 48 W · 25 KZT per kWh |
| Bayes | 0.75 → no motion → **0.273** (with motion **0.931**) |
| Break-even | 0.300 ÷ 0.750 = **0.40** |
| Best schedule | **#4, 18:30–19:30**, cost **2.1375** |
| One step | keep on −0.300, turn off −0.228 → **turn off** |
| Planner (4 steps) | −0.650 vs −0.677 → **keep on** |
| Evening result | planner **36 Wh, −25 %**, no discomfort |
| 7-day demo | **226.7 → 143.7 kWh, −36.6 %**, about 31 h discomfort |
| Tests | **64, all pass** |
