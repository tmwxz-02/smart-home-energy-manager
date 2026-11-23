"""Method 3 (sequential decision making): device control as a finite-horizon MDP.

Formal model (one device in one room, decision epochs = start of every interval)

* State      s_k = (o_k, d_k)
             o_k in {occupied, empty}: occupancy during interval k
             d_k in {on, off}: device state in the PREVIOUS interval (k-1)
* Actions    A_k = {ON, OFF} if interval k is inside the device schedule,
             A_k = {OFF} otherwise (auto mode never starts a device outside
             its schedule).
* Transition o_{k+1} follows the occupancy Markov chain
                 P(occ | occ) = stay_occupied, P(occ | empty) = become_occupied
             and is independent of the action (a fan does not make people
             come or go). The device part is deterministic: d_{k+1} = a_k.
* Reward     r(s_k, a_k) = - energy_cost          if a_k = ON
                           - comfort_cost         if a_k = OFF and o_k = occupied
                           - startup_cost         if a_k = ON  and d_k = off
             energy_cost  = power [kW] x interval [h] x tariff
             comfort_cost = value of service [money/h] x interval [h]
* Objective  maximise the expected sum of rewards over the next H intervals
             (finite horizon, optional discount gamma).

Because of the start-up cost the action now changes the next state (d), so
the problem is genuinely sequential: switching OFF for one interval and ON
again can cost more than staying ON. It is solved exactly by backward
induction (finite-horizon value iteration) over the 4 states.

Occupancy is NOT observed directly; the controller only has the Bayesian
belief b = P(o_0 = occupied). We act with the QMDP approximation
(Littman et al., 1995):  Q(b, a) = b Q_0(occ, d, a) + (1 - b) Q_0(empty, d, a).
QMDP assumes occupancy becomes known after the current step, so it slightly
overvalues future information. It is an approximation of the POMDP, and the
project documentation says so.

With H = 1 and no start-up cost this reduces EXACTLY to the one-step rule of
the original prototype (``one_step_decision``); a unit test checks this.
"""

OCC, EMPTY = 1, 0
ON, OFF = "ON", "OFF"


def interval_costs(power_w, interval_minutes, tariff, comfort_value_per_hour, startup_cost=0.0):
    """Money-valued costs of one interval for one device."""
    hours = interval_minutes / 60.0
    return {
        "energy_kwh": power_w / 1000.0 * hours,
        "energy": power_w / 1000.0 * hours * tariff,
        "comfort": comfort_value_per_hour * hours,
        "startup": float(startup_cost),
    }


def reward(occupied, was_on, action, costs):
    """Immediate reward (negative cost) of one interval."""
    if action == ON:
        return -costs["energy"] - (0.0 if was_on else costs["startup"])
    return -costs["comfort"] if occupied else 0.0


def value_iteration(allowed, costs, stay_occupied, become_occupied, gamma=1.0):
    """Finite-horizon backward induction.

    ``allowed`` is a list with one entry per future interval (length = H);
    each entry is the tuple of actions allowed in that interval.
    Returns (q0, values): q0[(o, d)][a] for the first interval and the list of
    value tables V_k[(o, d)] for k = 0..H (V_H = 0).
    """
    horizon = len(allowed)
    if horizon < 1:
        raise ValueError("horizon must be at least 1")
    states = [(o, d) for o in (OCC, EMPTY) for d in (True, False)]
    values = [None] * (horizon + 1)
    values[horizon] = {state: 0.0 for state in states}
    q_tables = [None] * horizon
    for k in range(horizon - 1, -1, -1):
        q_k = {}
        for occupied, was_on in states:
            p_next_occ = stay_occupied if occupied else become_occupied
            q_k[(occupied, was_on)] = {}
            for action in allowed[k]:
                device_next = action == ON
                future = (p_next_occ * values[k + 1][(OCC, device_next)]
                          + (1 - p_next_occ) * values[k + 1][(EMPTY, device_next)])
                q_k[(occupied, was_on)][action] = (reward(occupied, was_on, action, costs)
                                                   + gamma * future)
        q_tables[k] = q_k
        values[k] = {state: max(q_k[state].values()) for state in states}
    return q_tables[0], values


def qmdp_decision(belief_occupied, was_on, allowed, costs, stay_occupied, become_occupied,
                  gamma=1.0):
    """Choose an action for the current interval from the occupancy belief.

    Returns a dict with the belief-level Q values, the chosen action and the
    state-level Q table. Ties are broken towards ON (comfort first).
    """
    q0, _ = value_iteration(allowed, costs, stay_occupied, become_occupied, gamma)
    q = {}
    for action in allowed[0]:
        q[action] = (belief_occupied * q0[(OCC, was_on)][action]
                     + (1 - belief_occupied) * q0[(EMPTY, was_on)][action])
    if ON in q and (OFF not in q or q[ON] >= q[OFF] - 1e-12):
        action = ON
    else:
        action = OFF
    table = {f"{'occupied' if o else 'empty'}|{'on' if d else 'off'}": acts
             for (o, d), acts in q0.items()}
    return {"q": q, "action": action, "state_q": table, "horizon": len(allowed)}


def one_step_decision(belief_occupied, costs):
    """The prototype's rule: compare expected reward of ON and OFF for one interval.

    Expected reward(ON) = -energy, Expected reward(OFF) = -b x comfort.
    ON wins (or ties) when b >= energy / comfort (the break-even probability).
    Start-up cost is ignored here, exactly as in the prototype.
    """
    q = {ON: -costs["energy"], OFF: -belief_occupied * costs["comfort"]}
    action = ON if q[ON] >= q[OFF] - 1e-12 else OFF
    return {"q": q, "action": action, "horizon": 1}


def break_even_probability(costs):
    """Occupancy probability above which ON beats OFF in a single interval."""
    if costs["comfort"] <= 0:
        return None
    return costs["energy"] / costs["comfort"]
