"""
Central config.

SIMULATED_NOW: the seed data's departure times are fixed to Sept 2025
(see data/seed.py). Refund eligibility depends on "hours until
departure," which only makes sense if "now" is a date inside the
data's own timeline. Using the real wall-clock datetime.now() would
put every route in the past regardless of what the customer's
message says, so we pin a fixed reference date instead. Documented
in README as an explicit assumption.
"""
from datetime import datetime

SIMULATED_NOW = datetime.fromisoformat("2025-09-16T00:00:00")

MAX_RETRIES = 2