#!/usr/bin/env python3

import sys
from fractions import Fraction

from simulation.scheduler import SimulationConfig
from simulation.simulator import Simulator


def main():
    print("=" * 70)
    print("Лабораторная работа №1 - Симулятор однопроцессорной ВС (Вариант 3)")
    print("=" * 70)
    print()

    seed = int(input("Seed (default 42): ") or 42)
    p_hit = float(input("P_hit (0.65 или 0.85, default 0.65): ") or 0.65)
    words = int(input("Words per cache line (default 4): ") or 4)

    cfg = SimulationConfig(seed=seed, p_hit=p_hit, words_per_line=words)
    sim = Simulator(cfg)
    sim.generate_variant3()

    print(f"\nСгенерировано команд: {len(sim.command_stream)}")
    print("Команды: step, run <n>, all, reset, log, snapshot, exit")
    print()

    while True:
        cmd = input("> ").strip().lower()
        if not cmd:
            continue

        if cmd == "exit" or cmd == "quit":
            break

        elif cmd == "step":
            sim.step()
            print(sim.snapshot())
            print()
            if sim.finished:
                print(f"=== СИМУЛЯЦИЯ ЗАВЕРШЕНА за {sim.current_tick} тактов МП ===")
                print_stats(sim)

        elif cmd.startswith("run "):
            try:
                n = int(cmd.split()[1])
                sim.run_steps(n)
                print(sim.snapshot())
                print()
                if sim.finished:
                    print(f"=== СИМУЛЯЦИЯ ЗАВЕРШЕНА за {sim.current_tick} тактов МП ===")
                    print_stats(sim)
            except (ValueError, IndexError):
                print("Использование: run <число>")

        elif cmd == "all":
            sim.run_full()
            print(sim.snapshot())
            print()
            if sim.finished:
                print(f"=== СИМУЛЯЦИЯ ЗАВЕРШЕНА за {sim.current_tick} тактов МП ===")
                print_stats(sim)

        elif cmd == "reset":
            sim.reset()
            sim.generate_variant3()
            print(f"Симуляция сброшена. Команд: {len(sim.command_stream)}")

        elif cmd == "snapshot":
            print(sim.snapshot())
            print()

        elif cmd == "log":
            for line in sim.event_log[-20:]:
                print(line)
            print()

        elif cmd == "stats":
            print_stats(sim)

        else:
            print("Неизвестная команда. Доступные: step, run <n>, all, reset, log, snapshot, stats, exit")


def print_stats(sim: Simulator):
    st = sim.stats
    print()
    print("=" * 70)
    print("СТАТИСТИКА")
    print("=" * 70)
    print(f"Всего команд:           {st.total_commands}")
    print(f"Время (МП тактов):      {sim.current_tick}")
    print(f"Время (СШ тактов):      {st.sb_total_ticks}")
    print(f"Время (нс):             {float(sim.global_time * Fraction(10, 7)):.4f}")
    print(f"Cache HIT:              {st.hits} ({st.hit_rate()*100:.1f}%)")
    print(f"Cache MISS:             {st.misses}")
    print(f"Обращений ОП (слов):    {st.op_accesses_words}")
    print(f"Обращений УСО:          {st.uso_accesses}")
    print(f"Загрузка P1:            {st.pipeline1_busy_mp_ticks} / {st.mp_total_ticks} ({100*st.pipeline1_busy_mp_ticks/max(1,st.mp_total_ticks):.1f}%)")
    print(f"Загрузка P2:            {st.pipeline2_busy_mp_ticks} / {st.mp_total_ticks} ({100*st.pipeline2_busy_mp_ticks/max(1,st.mp_total_ticks):.1f}%)")
    print(f"Загрузка СШ:            {st.bus_busy_sb_ticks} / {st.sb_total_ticks} ({100*st.bus_busy_sb_ticks/max(1,st.sb_total_ticks):.1f}%)")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()
