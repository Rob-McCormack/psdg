"""Frozen experimental position (Phase 0).

The official fixed opening for the single-opening ML experiment: the
YouTube-demo board. Board tops 2,2,3,4,5,6 -> histogram (0,2,1,1,1,1).
Crystals are (top, facing). Root minimax value is +1 (A wins under optimal
play); this is asserted at import-adjacent test time, not trusted blindly.
"""

# Board as 6-count histogram for tops 1..6 (tops 2,2,3,4,5,6).
BOARD = (0, 2, 1, 1, 1, 1)
BOARD_TOPS = (2, 2, 3, 4, 5, 6)

# (top, facing). A: top 2 facing 6.  B: top 1 facing 2.
A_CRYSTAL = (2, 6)
B_CRYSTAL = (1, 2)

FIRST_PLAYER = "A"
EXCHANGE_TIMING = "simultaneous"
RULES_VERSION = "v1.13"
EXPECTED_ROOT_VALUE = 1

SPEC = {
    "name": "youtube_demo_v1",
    "rules_version": RULES_VERSION,
    "board_tops": list(BOARD_TOPS),
    "board_histogram": list(BOARD),
    "a_crystal": list(A_CRYSTAL),
    "b_crystal": list(B_CRYSTAL),
    "first_player": FIRST_PLAYER,
    "exchange_timing": EXCHANGE_TIMING,
    "expected_root_value": EXPECTED_ROOT_VALUE,
}
