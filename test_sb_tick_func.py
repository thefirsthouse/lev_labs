from fractions import Fraction

def sb_tick(t_mp: Fraction) -> int:
    return int((t_mp * Fraction(19, 50)))

for t in [0, 1, 2, 3, 4, 5]:
    result = sb_tick(Fraction(t))
    print(f"sb_tick({t}) = {result}")
    
print(f"\nsb_tick(3) = {sb_tick(Fraction(3))}")
print(f"3 * 19/50 = {3 * Fraction(19, 50)} = {float(3 * Fraction(19, 50))}")
