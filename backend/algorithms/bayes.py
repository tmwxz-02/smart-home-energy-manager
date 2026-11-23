"""Method 2 (probabilistic reasoning): Bayesian occupancy estimation.

Two pieces, both standard HMM ("hidden Markov model") operations:

* ``bayes_details`` - the Bayes-rule update of P(occupied) from ONE motion
  reading (the "update" step of a filter).
* ``predict_occupancy`` - the transition step: given P(occupied) now, the
  probability that the room is occupied one interval later.

Doing predict -> update for every reading in time order is the HMM forward
algorithm (filtering). ``filter_sequence`` runs it over a list of readings.
"""


def bayes_details(prior, motion_detected, motion_if_occupied, motion_if_empty):
    """Return every number of P(Occupied | Reading).

    P(Occupied | Reading) = P(Reading | Occupied) x P(Occupied) / P(Reading)
    P(Reading) = P(Reading | Occupied) P(Occupied) + P(Reading | Empty) P(Empty)
    """
    if not 0.0 <= prior <= 1.0:
        raise ValueError("prior must be between 0 and 1")
    likelihood_occupied = motion_if_occupied
    likelihood_empty = motion_if_empty
    if not motion_detected:
        likelihood_occupied = 1.0 - motion_if_occupied
        likelihood_empty = 1.0 - motion_if_empty
    occupied_and_reading = prior * likelihood_occupied
    empty_and_reading = (1.0 - prior) * likelihood_empty
    evidence = occupied_and_reading + empty_and_reading
    return {
        "prior": prior,
        "likelihood_occupied": likelihood_occupied,
        "likelihood_empty": likelihood_empty,
        "evidence": evidence,
        "posterior": occupied_and_reading / evidence,
    }


def bayes_occupancy(prior, motion_detected, motion_if_occupied, motion_if_empty):
    """Posterior probability that the room is occupied now."""
    return bayes_details(prior, motion_detected, motion_if_occupied, motion_if_empty)["posterior"]


def predict_occupancy(probability_now, stay_occupied, become_occupied):
    """Transition step of the occupancy Markov chain (one interval ahead).

    P(occ next) = P(occ now) x P(stay occupied) + P(empty now) x P(someone arrives)
    """
    return probability_now * stay_occupied + (1.0 - probability_now) * become_occupied


def filter_sequence(initial_prior, readings, motion_if_occupied, motion_if_empty,
                    stay_occupied, become_occupied):
    """HMM forward filtering over consecutive readings.

    The first reading uses ``initial_prior``; every later reading uses the
    prediction made from the previous posterior. Returns one dict per reading.
    """
    prior = initial_prior
    rows = []
    for motion in readings:
        details = bayes_details(prior, motion, motion_if_occupied, motion_if_empty)
        details["predicted"] = predict_occupancy(details["posterior"], stay_occupied, become_occupied)
        rows.append(details)
        prior = details["predicted"]
    return rows
