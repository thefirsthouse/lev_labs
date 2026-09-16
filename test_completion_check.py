from fractions import Fraction

finish_time = Fraction(100, 19)
print(f"finish_time = {finish_time} ≈ {float(finish_time)}")

for t in range(10):
    t0 = Fraction(t)
    t1 = t0 + 1
    in_interval = t0 < finish_time <= t1
    print(f"t={t}: ({t0}, {t1}] contains {finish_time}? {in_interval}")
