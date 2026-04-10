"""PSDG exact solver: crystal assignment, draft (minimax + alpha-beta), exchange, scoring."""

from .solver import (
    Die,
    DraftState,
    PLAYER_A,
    PLAYER_B,
    EXAMPLE_BOARD,
    EXAMPLE_BOARDS,
    board_from_tops,
    format_line,
    legal_exchange_indices,
    random_board,
    score_player,
    solve_boards,
    solve_exchange,
    solve_from_roll,
    side_faces,
)

__all__ = [
    "Die",
    "DraftState",
    "EXAMPLE_BOARD",
    "EXAMPLE_BOARDS",
    "PLAYER_A",
    "PLAYER_B",
    "board_from_tops",
    "format_line",
    "legal_exchange_indices",
    "random_board",
    "score_player",
    "solve_boards",
    "solve_exchange",
    "solve_from_roll",
    "side_faces",
]
