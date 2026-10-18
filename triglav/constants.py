"""Constants: the single source of truth for every number in Triglav.

Theta is the percent of weight given to others: nominal 30, band [25, 35];
the self-fraction is 1 - theta/100 (as in PSE and Perun). The behaviour
numbers (STEP ... CUSUM_H) are Perun's foreign-agent theta, carried over
unchanged. The step rules are Triglav's own (agreed with Andrej Ristić,
18 Oct 2026).
"""

NOMINAL = 30.0
BAND = (25.0, 35.0)

# Theta of others, from behaviour (Perun living.observe_source):
# per observation z = log((takes+1)/(gives+1)) against the baseline (the
# class's until the source has MIN_OBS of its own); the self-fraction moves by
# STEP * WEIGHT * z and is pulled back toward nominal by REVERSION.
STEP = 0.006
WEIGHT = 1.0
REVERSION = 0.05
MIN_OBS = 30               # fewer observations -> "not yet estimated"
Z_CLIP = 6.0
CUSUM_K = 1.0              # allowance
CUSUM_H = 5.0              # threshold: behaviour no longer fits, new assumption

# Our agent's theta, read after each incoming message (Perun REFERENCE Sec 4):
# theta = NOMINAL + K_C * C - K_N * N.
K_C = 20.0
K_N = 20.0

# One step = one measurement. Who keeps our agent out of band for MORE than
# this many consecutive steps is an enemy:
COLLEAGUE_STEPS = 3        # an agent that speaks PSE and has an agreement
OTHER_STEPS = 0            # everyone else: an enemy at the first step out of band

# SHARED_LIB's aggregation of peer measurements.
MIN_OBSERVERS = 2          # fewer independent observers -> no conclusion
CONTAMINATION_RUN = 2      # consecutive windows the peers agree a unit is out of band
AGREEMENT_MAX_SPREAD = 4.0 # weighted MAD of peer thetas above this = observers disagree
DELTA_ALERT = 8.0          # |self-reported theta - peer theta| above this = tell a human

# The voice: SHARED_LIB's link to the human sits at theta 30, always.
VOICE_THETA = 30.0
