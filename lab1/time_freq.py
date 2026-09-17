from __future__ import annotations

from fractions import Fraction

T_MP = Fraction(1, 700_000_000)
T_SB = Fraction(1, 266_000_000)
SB_PER_MP = Fraction(19, 50)
MP_PER_SB = Fraction(50, 19)


def mp_tick(t_mp: Fraction) -> int:
    return int(t_mp)


def sb_tick(t_mp: Fraction) -> int:
    return int(t_mp * SB_PER_MP)


def to_ns(t_mp: Fraction) -> Fraction:
    return t_mp * Fraction(10, 7)


def schedule_finish_from_sb(start_sb: int, duration_sb: int) -> Fraction:
    return Fraction((start_sb + duration_sb) * 50, 19)
