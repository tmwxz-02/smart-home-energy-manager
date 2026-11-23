"""Hour-of-day occupancy priors learned from a room's stored motion readings.

Only motion readings are used, never the optional occupancy labels: labels
are reserved for evaluating the controller, so using them here would leak
the answer into the decisions.

For hour h with n readings and m motion detections the observed motion rate
is r = (m + 1) / (n + 2) (Laplace smoothing). Because
    P(motion) = P(m | occ) p + P(m | empty) (1 - p),
the occupancy probability is recovered as
    p = (r - P(m | empty)) / (P(m | occ) - P(m | empty)),
clipped to [0.02, 0.98] (method of moments). Hours with fewer than
``min_history_readings`` readings use the default prior.

``before`` restricts the history to readings strictly earlier than a time
stamp, so a decision never uses data from its own day or the future.
"""

HOURS = 24
CLIP_LOW, CLIP_HIGH = 0.02, 0.98


def prior_from_counts(readings, motions, settings):
    if readings < settings["min_history_readings"]:
        return settings["default_prior"], "default"
    rate = (motions + 1) / (readings + 2)
    hit, false_alarm = settings["motion_if_occupied"], settings["motion_if_empty"]
    estimate = (rate - false_alarm) / (hit - false_alarm)
    return min(CLIP_HIGH, max(CLIP_LOW, estimate)), "learned"


def hourly_priors(conn, room_id, settings, before=None):
    """Return 24 dicts {hour, prior, source, readings, motion_rate}."""
    query = ("SELECT CAST(substr(ts, 12, 2) AS INTEGER) AS hour, COUNT(*) AS n, "
             "SUM(motion) AS m FROM readings WHERE room_id = ?")
    params = [room_id]
    if before:
        query += " AND ts < ?"
        params.append(before)
    query += " GROUP BY hour"
    counts = {row["hour"]: (row["n"], row["m"] or 0) for row in conn.execute(query, params)}
    result = []
    for hour in range(HOURS):
        n, m = counts.get(hour, (0, 0))
        prior, source = prior_from_counts(n, m, settings)
        result.append({"hour": hour, "prior": prior, "source": source, "readings": n,
                       "motion_rate": (m / n) if n else None})
    return result


class PriorCache:
    """Caches hour-of-day priors per (room, day), using only earlier days."""

    def __init__(self, conn, settings):
        self.conn = conn
        self.settings = settings
        self.cache = {}

    def get(self, room_id, ts):
        day = ts[:10]
        key = (room_id, day)
        if key not in self.cache:
            self.cache[key] = hourly_priors(self.conn, room_id, self.settings, before=f"{day}T00:00")
        entry = self.cache[key][int(ts[11:13])]
        return entry["prior"], ("hourly" if entry["source"] == "learned" else "default")
