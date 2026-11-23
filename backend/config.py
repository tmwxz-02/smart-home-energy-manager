"""Default values and limits. Every number here is an ASSUMPTION, not a measurement.

The user can change the model settings in the Settings page; the values are
stored in SQLite (table ``settings``) per workspace.
"""

APP_NAME = "Smart Home Energy Manager"

# --------------------------------------------------------------------------
# Model settings (editable in the UI). Units in the comments.
# --------------------------------------------------------------------------
DEFAULT_SETTINGS = {
    "currency": "KZT",               # label only
    "tariff_per_kwh": 25.0,          # money per kWh (assumed household tariff)
    "interval_minutes": 15,          # length of one decision interval
    "motion_if_occupied": 0.90,      # sensor hit rate P(motion | occupied)
    "motion_if_empty": 0.20,         # false-alarm rate P(motion | empty)
    "stay_occupied": 0.85,           # P(occupied next interval | occupied now)
    "become_occupied": 0.10,         # P(occupied next interval | empty now)
    "default_prior": 0.5,            # P(occupied) when no history exists
    "horizon": 4,                    # MDP planning horizon (intervals)
    "discount": 1.0,                 # MDP discount factor gamma
    "min_history_readings": 4,       # readings per hour needed to learn a prior
}

# (type, minimum, maximum). Strings have no range.
SETTING_RULES = {
    "currency": ("str", 1, 8),
    "tariff_per_kwh": ("float", 0.0, 10000.0),
    "interval_minutes": ("choice", (5, 10, 15, 20, 30, 60), None),
    "motion_if_occupied": ("float", 0.50, 0.999),
    "motion_if_empty": ("float", 0.001, 0.50),
    "stay_occupied": ("float", 0.0, 1.0),
    "become_occupied": ("float", 0.0, 1.0),
    "default_prior": ("float", 0.01, 0.99),
    "horizon": ("int", 1, 24),
    "discount": ("float", 0.5, 1.0),
    "min_history_readings": ("int", 1, 100),
}

# --------------------------------------------------------------------------
# Device type presets. power_w is a typical rated power; comfort_value_per_hour
# is how much (in money) one hour of missing service is worth to the user when
# someone is in the room; startup_cost is an assumed cost per OFF->ON switch
# (wear, inrush current, warm-up). All editable per device.
# --------------------------------------------------------------------------
DEVICE_TYPES = {
    "fan":     {"label": "Fan",             "power_w": 48,   "comfort_value_per_hour": 3.0,  "startup_cost": 0.3},
    "light":   {"label": "Light",           "power_w": 60,   "comfort_value_per_hour": 4.0,  "startup_cost": 0.0},
    "ac":      {"label": "Air conditioner", "power_w": 1200, "comfort_value_per_hour": 75.0, "startup_cost": 4.0},
    "heater":  {"label": "Heater",          "power_w": 1500, "comfort_value_per_hour": 90.0, "startup_cost": 3.0},
    "tv":      {"label": "TV",              "power_w": 100,  "comfort_value_per_hour": 5.0,  "startup_cost": 0.5},
    "other":   {"label": "Other",           "power_w": 100,  "comfort_value_per_hour": 5.0,  "startup_cost": 0.0},
}

DEVICE_LIMITS = {
    "power_w": (1, 10000),
    "comfort_value_per_hour": (0, 100000),
    "startup_cost": (0, 100000),
}

MAX_CSV_BYTES = 2 * 1024 * 1024
MAX_CSV_ROWS = 50000
MAX_ERRORS_SHOWN = 50

# Demo workspace: synthetic data, reproducible from the seed.
DEMO_DEFAULT_DAYS = 7
DEMO_DEFAULT_SEED = 42
DEMO_START_DATE = "2026-11-02"   # a Monday; fixed so the data is reproducible
