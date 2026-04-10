"""
Curated PSDG benchmark boards.

Hand-picked adversarial or structurally interesting positions.
Each is (board, note) where board is 6-count histogram.
Values are computed by the generator using the oracle.
"""

# Format: (board_tuple, short_note)
# board: (c1,c2,c3,c4,c5,c6) for tops 1..6, sum=4|6|8
CURATED_8 = [
    ((0, 0, 0, 0, 0, 8), "All 6s"),
    ((8, 0, 0, 0, 0, 0), "All 1s"),
    ((4, 4, 0, 0, 0, 0), "Four 1s four 2s"),
    ((2, 2, 2, 2, 0, 0), "No 5s or 6s"),
    ((0, 0, 0, 0, 4, 4), "Four 5s four 6s"),
    ((1, 1, 1, 1, 1, 3), "One player can get three 6s"),
    ((1, 1, 2, 2, 1, 1), "Balanced 8d"),
    ((0, 2, 2, 2, 2, 0), "No 1s or 6s"),
    ((2, 0, 0, 0, 0, 6), "Extreme: many 6s"),
    ((3, 3, 1, 1, 0, 0), "Low pairs"),
    ((0, 0, 2, 2, 2, 2), "No 1s or 2s"),
    ((1, 2, 2, 2, 2, 1), "Bookends"),
]

CURATED_4 = [
    ((2, 0, 2, 0, 0, 0), "1,1,3,3"),
    ((0, 0, 0, 0, 2, 2), "Two 5s two 6s"),
    ((1, 1, 1, 1, 0, 0), "One of each 1-4"),
    ((0, 0, 0, 2, 2, 0), "Two 4s two 5s"),
]

CURATED_6 = [
    ((1, 1, 1, 1, 1, 1), "Uniform 6d"),
    ((0, 0, 3, 3, 0, 0), "Three 3s three 4s"),
]
