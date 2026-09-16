from fractions import Fraction
from simulation.time_freq import sb_tick

for t in range(10):
    sb = sb_tick(Fraction(t))
    print(f"t={t} MP -> sb={sb} SB")
    
print("\nUSO: start t=3")
t_start = Fraction(3)
sb_start = sb_tick(t_start)
print(f"  sb_start = {sb_start}")
sb_end = sb_start + 1
print(f"  sb_end = {sb_end}")
t_finish = Fraction(sb_end * 50, 19)
print(f"  t_finish = {t_finish} ≈ {float(t_finish)}")
