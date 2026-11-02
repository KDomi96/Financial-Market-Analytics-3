"""Close-time decisions for the fixed Phase 4 crossing rules."""

import math


def decide_signal(previous_z, z, position, entry_threshold=2.0, exit_threshold=0.0):
    """Return raw crossings and the action permitted by the current position."""
    if position not in (-1, 0, 1) or not math.isfinite(z):
        raise ValueError("Invalid position or Z-score")
    if previous_z is not None and not math.isfinite(previous_z):
        raise ValueError("Invalid previous Z-score")
    long_crossing = previous_z is not None and previous_z >= -entry_threshold and z < -entry_threshold
    short_crossing = previous_z is not None and previous_z <= entry_threshold and z > entry_threshold
    exit_signal = (position == 1 and z >= exit_threshold) or (position == -1 and z <= exit_threshold)
    eligible_long = position == 0 and long_crossing
    eligible_short = position == 0 and short_crossing
    action = ("exit" if exit_signal else "enter_long" if eligible_long else
              "enter_short" if eligible_short else "hold")
    ignored = ("exit_priority" if exit_signal else "position_open") if position and (long_crossing or short_crossing) else ""
    return {"outside_long": z < -entry_threshold, "outside_short": z > entry_threshold,
            "long_crossing": bool(long_crossing), "short_crossing": bool(short_crossing),
            "eligible_long": bool(eligible_long), "eligible_short": bool(eligible_short),
            "exit_signal": bool(exit_signal), "action": action, "ignored_reason": ignored}
