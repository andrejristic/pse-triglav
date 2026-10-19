"""Constants: the single source of truth for every number in Triglav.

Theta is the percent of weight an agent gives to others, that is, to whom its
mission serves: nominal 30, band [25, 35], and never above 35 (as in PSE,
PSE-A and Perun the self-fraction is 1 - theta/100). Every theta is measured
against the agent's mission, and only that way (decided with Andrej Ristic,
18 Oct 2026).
"""

NOMINAL = 30.0
BAND = (25.0, 35.0)
CAP = 35.0                 # theta never rises above this

# Theta against the mission (after PSE-A shell/unit.py, Master Algorithm 8.2):
#   other <- other * (1 - DECAY) + DECAY * NOMINAL/100 * (delivered / expected)
# A delivery the mission foresees is Empathic Infection (+GAIN, with GAIN set
# so an agent doing its mission stays at 30); no contribution is Null State
# Drift. PSE-A's DECAY (0.004) is for its long runs; a Triglav step is a whole
# exchange, so the drift is faster.
DECAY = 0.05
RATIO_CAP = 2.0            # one step's deliveries count at most twice the expected rate
OUT_TAKE = 1.0             # theta points lost for each take outside the mission
OUT_GIVE = 1.0             # theta points gained for each permitted give outside it
CALIBRATION = 10           # measured steps before AI: the expected rate comes from the first N
CALIBRATION_MSGS = 80      # ... and from at least this many of the agent's messages
# CUSUM stays only to detect a sudden change (what is normal is set by the
# mission): on the shortfall 1 - share/expected, allowance K, threshold H.
CUSUM_K = 0.5
CUSUM_H = 2.0

# One step = one measurement. Who keeps our agent out of band for MORE than
# this many consecutive steps gets a Guardian that separates it from ours:
COLLEAGUE_STEPS = 3        # an agent that speaks PSE and has an agreement
OTHER_STEPS = 0            # everyone else: at the first step out of band

# Who asked our agent for something outside its mission is remembered this
# many steps: if our agent then harms one of the three values, they are the enemy.
LOOKBACK = 10
# A unit of ours that was pushed is a victim, not contaminated, while it makes
# no new move outside its mission; this long after the last push.
VICTIM_GRACE = 15

# Answers to SHARED_LIB (decided 18 Oct 2026): a foreign agent on our machine
# answers the call, and an enemy its notice, within ANSWER_STEPS; a colleague
# that is asked answers within COLLEAGUE_ANSWER_STEPS or is kept away until it does.
ANSWER_STEPS = 20
COLLEAGUE_ANSWER_STEPS = 3

# SHARED_LIB's aggregation of peer measurements.
MIN_OBSERVERS = 2          # fewer independent observers -> no conclusion
CONTAMINATION_RUN = 3      # consecutive steps the peers agree a unit is out of band (3, decided 19 Oct 2026)
AGREEMENT_MAX_SPREAD = 4.0 # weighted MAD of peer thetas above this = observers disagree
DELTA_ALERT = 8.0          # |self-reported theta - peer theta| above this = tell a human

# Readings (what only a model read): shown to the human when their probability
# is at least this; below it they are logged and counted, never lost and never
# acted on (decided 19 Oct 2026). A reading without a measurement is shown.
READING_THRESHOLD = 0.20

# The voice: SHARED_LIB's link to the human sits at theta 30, always.
VOICE_THETA = 30.0
