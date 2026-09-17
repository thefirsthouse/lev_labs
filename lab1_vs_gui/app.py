from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk, messagebox
from dataclasses import replace
from fractions import Fraction

from lab1.entities import TaskType
from lab1.scheduler import SimulationConfig
from lab1.simulator import Simulator
from lab1.trace import ResourceEvent

TASK_NAMES = {
    "MDO": "МДО",
    "MSO": "МСО",
    "UPR": "Управление",
    "DISP": "Диспетчеризация",
}

TASK_COLORS = {
    "MDO": "#6d8cff",
    "MSO": "#71c7a5",
    "UPR": "#e7a64b",
    "DISP": "#c17ce5",
}

GROUP_COLORS = {
    "task": "#5f7fe7",
    "lookup": "#4f8fb8",
    "cache": "#4f9d87",
    "cache_hit": "#4aa77d",
    "cache_miss": "#d06464",
    "transfer": "#d79252",
    "bus": "#d3a249",
    "memory": "#a777d6",
    "uso": "#d97895",
    "wait": "#666b78",
    "neutral": "#5d6370",
}

LANES = [
    ("PIPELINE_1", "КОНВЕЙЕР 1"),
    ("PIPELINE_2", "КОНВЕЙЕР 2"),
    ("CACHE", "КЭШ"),
    ("CACHE_CONTROLLER", "КЭШ-КОНТРОЛЛЕР"),
    ("SYSTEM_BUS", "СШ"),
    ("BUFFER_ELEMENT", "БЭ"),
    ("MEMORY", "ОП"),
    ("USO", "УСО"),
]

LANE_INDEX = {key: i for i, (key, _) in enumerate(LANES)}


class TimelineCanvas(tk.Frame):
    def __init__(self, master, on_event_click, **kwargs):
        super().__init__(master, **kwargs)
        self.on_event_click = on_event_click
        self.zoom = 14.0
        self.left_label_width = 150
        self.top_axis_height = 58
        self.lane_height = 54
        self.tick_height = 15
        self.events: list[ResourceEvent] = []
        self.current_tick = 0
        self._canvas_items: list[tuple[int, ResourceEvent]] = []
        self._tooltip = None
        self._last_width = 1000

        self.canvas = tk.Canvas(self, background="#17191e", highlightthickness=0)
        self.hbar = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=self.hbar.set, yscrollcommand=self.vbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.hbar.grid(row=1, column=0, sticky="ew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.canvas.bind("<MouseWheel>", self._wheel)
        self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))

    def _wheel(self, event):
        if event.state & 0x0004:  # Ctrl
            self.set_zoom(self.zoom * (1.12 if event.delta > 0 else 1 / 1.12))
        else:
            self.canvas.yview_scroll(-int(event.delta / 120), "units")

    def set_zoom(self, value: float):
        self.zoom = min(40.0, max(5.0, value))
        self.redraw()

    def set_data(self, events: list[ResourceEvent], current_tick: int):
        self.events = list(events)
        self.current_tick = current_tick
        self.redraw()

    def _event_lanes(self, resource):
        return LANE_INDEX.get(resource)

    def _make_slots(self, events):
        slots: dict[str, list[list[float]]] = {}
        assignments: dict[int, int] = {}
        for idx, ev in sorted(enumerate(events), key=lambda x: (float(x[1].start), float(x[1].end))):
            lane = ev.resource
            if lane not in slots:
                slots[lane] = []
            placed = False
            for slot_idx, slot_ends in enumerate(slots[lane]):
                if all(float(ev.start) >= end - 1e-9 for end in slot_ends):
                    slot_ends.append(float(ev.end))
                    assignments[idx] = slot_idx
                    placed = True
                    break
            if not placed:
                slots[lane].append([float(ev.end)])
                assignments[idx] = len(slots[lane]) - 1
        return assignments, {k: len(v) for k, v in slots.items()}

    def _x(self, tick: float) -> float:
        return self.left_label_width + tick * self.zoom

    def redraw(self):
        self.canvas.delete("all")
        self._canvas_items.clear()
        assignments, slot_counts = self._make_slots(self.events)
        max_tick = max(float(self.current_tick) + 20.0, 20.0)
        for ev in self.events:
            max_tick = max(max_tick, float(ev.end) + 4.0)
        max_tick = max(max_tick, 1)

        width = int(self._x(max_tick) + 80)
        height = self.top_axis_height + len(LANES) * self.lane_height + 10
        self._last_width = width

        # Background / lane labels.
        for i, (key, title) in enumerate(LANES):
            y0 = self.top_axis_height + i * self.lane_height
            y1 = y0 + self.lane_height
            if i % 2 == 0:
                self.canvas.create_rectangle(0, y0, width, y1, fill="#1b1e24", outline="")
            self.canvas.create_text(
                10, (y0 + y1) / 2,
                text=title,
                anchor="w",
                fill="#d7dbe3",
                font=("TkDefaultFont", 10, "bold"),
            )
            self.canvas.create_line(self.left_label_width, y0, width, y0, fill="#343a44")

        # Time grid.
        for tick in range(math.ceil(max_tick) + 1):
            x = self._x(tick)
            if tick % 10 == 0:
                color = "#626a78"
                dash = None
                font = ("TkDefaultFont", 9, "bold")
                self.canvas.create_text(x + 2, 17, text=str(tick), anchor="w", fill="#dfe3ea", font=font)
            elif tick % 5 == 0:
                color = "#454c58"
                dash = None
            else:
                color = "#2f343d"
                dash = (2, 3)
            self.canvas.create_line(x, self.top_axis_height, x, height, fill=color, dash=dash)

        self.canvas.create_text(
            10, 17,
            text="ВРЕМЯ (ТАКТЫ МП)",
            anchor="w",
            fill="#8fc9e8",
            font=("TkDefaultFont", 9, "bold"),
        )
        self.canvas.create_text(
            self.left_label_width + 5, 39,
            text="Такт СШ: 1 такт ≈ 2.63 такта МП",
            anchor="w",
            fill="#808898",
            font=("TkDefaultFont", 8),
        )

        # Current position.
        now_x = self._x(self.current_tick)
        self.canvas.create_line(now_x, self.top_axis_height - 3, now_x, height, fill="#f3dc7a", width=2)
        self.canvas.create_text(now_x + 5, 39, text=f"NOW {self.current_tick}", anchor="w", fill="#f3dc7a", font=("TkDefaultFont", 8, "bold"))

        # Group events by resource, draw connectors between phases of each command.
        by_command: dict[int, list[tuple[int, ResourceEvent]]] = {}
        for idx, ev in enumerate(self.events):
            if ev.command_id is not None:
                by_command.setdefault(ev.command_id, []).append((idx, ev))
        for cmd_id, pairs in by_command.items():
            pairs.sort(key=lambda x: (float(x[1].start), float(x[1].end), LANE_INDEX.get(x[1].resource, 99)))
            for (_, a), (_, b) in zip(pairs, pairs[1:]):
                if a.resource == b.resource:
                    continue
                ay = self.top_axis_height + (LANE_INDEX.get(a.resource, 0) + 0.5) * self.lane_height
                by = self.top_axis_height + (LANE_INDEX.get(b.resource, 0) + 0.5) * self.lane_height
                ax = self._x(float(a.end))
                bx = self._x(float(b.start))
                if abs(ax - bx) > 1:
                    self.canvas.create_line(ax, ay, bx, by, fill="#737b8a", dash=(3, 4), arrow="last", width=1)
                else:
                    self.canvas.create_line(ax, ay, bx, by, fill="#737b8a", arrow="last", width=1)

        # Event blocks.
        self._canvas_items.clear()
        for idx, ev in enumerate(self.events):
            lane = self._event_lanes(ev.resource)
            if lane is None:
                continue
            y0 = self.top_axis_height + lane * self.lane_height
            slots = slot_counts.get(ev.resource, 1)
            slot = assignments.get(idx, 0)
            slot_h = min(20, max(12, (self.lane_height - 12) / max(1, slots)))
            y = y0 + 6 + slot * (slot_h + 2)
            x0 = self._x(float(ev.start))
            x1 = self._x(float(ev.end))
            if x1 - x0 < 3:
                x1 = x0 + 3
            if ev.resource.startswith("PIPELINE") and ev.operation == "EXECUTE":
                fill = TASK_COLORS.get(ev.task or "", GROUP_COLORS["task"])
            else:
                fill = GROUP_COLORS.get(ev.color_group, GROUP_COLORS["neutral"])
            outline = "#f0f2f5" if ev.color_group in {"cache_miss", "wait"} else "#121418"
            rect = self.canvas.create_rectangle(x0 + 1, y, x1 - 1, y + slot_h, fill=fill, outline=outline, width=1, tags=(f"event_{idx}",))
            if x1 - x0 > 55:
                label = ev.operation
                if ev.resource.startswith("PIPELINE") and ev.command_id is not None and ev.task:
                    label = f"{TASK_NAMES.get(ev.task, ev.task)} #{ev.command_id}"
                self.canvas.create_text(x0 + 5, y + slot_h / 2, text=label, anchor="w", fill="#111318", font=("TkDefaultFont", 8, "bold"), tags=(f"event_{idx}",))
            self._canvas_items.append((rect, ev))
            self.canvas.tag_bind(f"event_{idx}", "<Button-1>", lambda e, event=ev: self.on_event_click(event))
            self.canvas.tag_bind(f"event_{idx}", "<Enter>", lambda e, event=ev: self._show_tooltip(event, e.x_root, e.y_root))
            self.canvas.tag_bind(f"event_{idx}", "<Leave>", lambda e: self._hide_tooltip())

        self.canvas.configure(scrollregion=(0, 0, width, height))

    def _show_tooltip(self, ev: ResourceEvent, x: int, y: int):
        self._hide_tooltip()
        tip = tk.Toplevel(self)
        tip.wm_overrideredirect(True)
        tip.configure(bg="#0f1115")
        text = (
            f"Ресурс: {dict(LANES).get(ev.resource, ev.resource)}\n"
            f"Операция: {ev.operation}\n"
            f"Такты МП: {float(ev.start):g} → {float(ev.end):g}\n"
            f"Длительность: {float(ev.duration):g} МП\n"
            f"Команда: {TASK_NAMES.get(ev.task, ev.task or '—')} #{ev.command_id if ev.command_id is not None else '—'}\n"
            f"{ev.detail}"
        )
        tk.Label(tip, text=text, justify="left", bg="#0f1115", fg="#e7eaf0", padx=8, pady=6, font=("TkDefaultFont", 9)).pack()
        tip.geometry(f"+{x+12}+{y+12}")
        self._tooltip = tip

    def _hide_tooltip(self):
        if self._tooltip is not None:
            try:
                self._tooltip.destroy()
            except tk.TclError:
                pass
            self._tooltip = None


class LabApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Имитационная модель ВС — Вариант 3")
        self.geometry("1500x920")
        self.minsize(1100, 720)
        self.configure(bg="#111318")

        self.sim: Simulator | None = None
        self.mode = tk.StringVar(value="full")
        self.cache_hit = tk.DoubleVar(value=0.65)
        self.seed_var = tk.IntVar(value=42)
        self.period_var = tk.IntVar(value=120)
        self.status_var = tk.StringVar(value="Готово. Создайте симуляцию.")
        self.detail_var = tk.StringVar(value="Выберите событие на диаграмме.")
        self.zoom_var = tk.StringVar(value="100%")
        self._after_id = None
        self._running = False
        self.test_commands: list[tuple[TaskType, int]] = [
            (TaskType.MDO, 5),
            (TaskType.MSO, 2),
            (TaskType.UPR, 2),
            (TaskType.DISP, 1),
        ]

        self._build_style()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _build_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#14161b")
        style.configure("Panel.TFrame", background="#1a1d23")
        style.configure("TLabel", background="#14161b", foreground="#dbe0e8")
        style.configure("Header.TLabel", background="#14161b", foreground="#f0f2f5", font=("TkDefaultFont", 11, "bold"))
        style.configure("TButton", padding=7, font=("TkDefaultFont", 9))
        style.configure("TCombobox", fieldbackground="#23262d", background="#23262d", foreground="#e3e7ee")
        style.configure("Treeview", background="#171a20", fieldbackground="#171a20", foreground="#dfe4ec", rowheight=24)
        style.configure("Treeview.Heading", background="#282c34", foreground="#e7eaf0")

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=(10, 6))
        for text, command in [
            ("▶ Старт", self.start_run),
            ("⏸ Пауза", self.pause_run),
            ("⏭ Следующий такт", self.step_once),
            ("↺ Сброс", self.reset_sim),
        ]:
            ttk.Button(top, text=text, command=command).pack(side="left", padx=(0, 8))
        ttk.Label(top, text="Период (мс):").pack(side="left", padx=(12, 4))
        ttk.Spinbox(top, from_=10, to=2000, textvariable=self.period_var, width=7).pack(side="left")
        ttk.Label(top, textvariable=self.status_var).pack(side="right")

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=10, pady=4)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        left = ttk.Frame(body, style="Panel.TFrame", padding=12)
        left.grid(row=0, column=0, sticky="nsw", padx=(0, 8))
        center = ttk.Frame(body)
        center.grid(row=0, column=1, sticky="nsew")
        center.rowconfigure(0, weight=1)
        center.columnconfigure(0, weight=1)
        right = ttk.Frame(body, style="Panel.TFrame", padding=12)
        right.grid(row=0, column=2, sticky="nse", padx=(8, 0))

        self._build_left(left)
        self.timeline = TimelineCanvas(center, self._event_clicked)
        self.timeline.grid(row=0, column=0, sticky="nsew")
        self._build_right(right)

    def _build_left(self, frame):
        ttk.Label(frame, text="РЕЖИМ", style="Header.TLabel").pack(anchor="w", pady=(0, 6))
        ttk.Radiobutton(frame, text="Полная симуляция — вариант 3", variable=self.mode, value="full").pack(anchor="w")
        ttk.Radiobutton(frame, text="Тестовый режим", variable=self.mode, value="test").pack(anchor="w", pady=(0, 10))

        ttk.Label(frame, text="КЭШ", style="Header.TLabel").pack(anchor="w", pady=(4, 6))
        cache_row = ttk.Frame(frame, style="Panel.TFrame")
        cache_row.pack(fill="x")
        ttk.Radiobutton(cache_row, text="65%", variable=self.cache_hit, value=0.65).pack(side="left")
        ttk.Radiobutton(cache_row, text="85%", variable=self.cache_hit, value=0.85).pack(side="left", padx=10)

        ttk.Label(frame, text="SEED", style="Header.TLabel").pack(anchor="w", pady=(14, 6))
        ttk.Entry(frame, textvariable=self.seed_var, width=12).pack(anchor="w")

        ttk.Label(frame, text="ТЕСТОВЫЕ КОМАНДЫ", style="Header.TLabel").pack(anchor="w", pady=(18, 6))
        add = ttk.Frame(frame, style="Panel.TFrame")
        add.pack(fill="x")
        self.test_task = ttk.Combobox(add, values=["МДО", "МСО", "Управление", "Диспетчеризация"], state="readonly", width=15)
        self.test_task.set("МДО")
        self.test_task.pack(side="left")
        self.test_dur = tk.IntVar(value=2)
        ttk.Spinbox(add, from_=1, to=5, textvariable=self.test_dur, width=4).pack(side="left", padx=4)
        ttk.Button(add, text="+", width=3, command=self.add_test_command).pack(side="left")
        self.test_tree = ttk.Treeview(frame, columns=("task", "dur"), show="headings", height=7)
        self.test_tree.heading("task", text="Тип")
        self.test_tree.heading("dur", text="Такты")
        self.test_tree.column("task", width=130)
        self.test_tree.column("dur", width=50, anchor="center")
        self.test_tree.pack(fill="x", pady=6)
        ttk.Button(frame, text="Удалить выбранную", command=self.remove_test_command).pack(anchor="e")

        ttk.Button(frame, text="Создать симуляцию", command=self.create_simulation).pack(fill="x", pady=(18, 5))
        ttk.Button(frame, text="Очистить диаграмму", command=self.clear_timeline).pack(fill="x")

        ttk.Label(frame, text="МАСШТАБ", style="Header.TLabel").pack(anchor="w", pady=(18, 6))
        zoom = ttk.Frame(frame, style="Panel.TFrame")
        zoom.pack(fill="x")
        ttk.Button(zoom, text="−", width=3, command=lambda: self.adjust_zoom(0.85)).pack(side="left")
        ttk.Label(zoom, textvariable=self.zoom_var, width=8, anchor="center").pack(side="left")
        ttk.Button(zoom, text="+", width=3, command=lambda: self.adjust_zoom(1.18)).pack(side="left")
        ttk.Button(zoom, text="Сброс", command=lambda: self.set_zoom(14)).pack(side="left", padx=5)

        ttk.Label(
            frame,
            text="Подсказка:\nцвет = тип операции,\nстрока = ресурс,\nX = время, длина = длительность.\nCtrl+колесо — zoom.",
            foreground="#939ba9",
        ).pack(anchor="w", pady=(18, 0))
        self.refresh_test_tree()

    def _build_right(self, frame):
        ttk.Label(frame, text="ТЕКУЩЕЕ СОСТОЯНИЕ", style="Header.TLabel").pack(anchor="w")
        self.snapshot = tk.Text(frame, width=44, height=16, bg="#111318", fg="#dfe4ec", insertbackground="#dfe4ec", relief="flat", wrap="word")
        self.snapshot.pack(fill="x", pady=(6, 12))
        self.snapshot.configure(state="disabled")

        ttk.Label(frame, text="СОБЫТИЕ", style="Header.TLabel").pack(anchor="w")
        self.detail = tk.Text(frame, width=44, height=8, bg="#111318", fg="#dfe4ec", relief="flat", wrap="word")
        self.detail.pack(fill="x", pady=(6, 12))
        self.detail.configure(state="disabled")

        ttk.Label(frame, text="СТАТИСТИКА", style="Header.TLabel").pack(anchor="w")
        self.stats_label = ttk.Label(frame, text="—", justify="left")
        self.stats_label.pack(anchor="w", pady=(6, 12))

        ttk.Label(frame, text="ПОСЛЕДНИЕ СОБЫТИЯ", style="Header.TLabel").pack(anchor="w")
        self.log = tk.Text(frame, width=44, height=13, bg="#111318", fg="#aeb6c5", relief="flat", wrap="word")
        self.log.pack(fill="both", expand=True, pady=(6, 0))
        self.log.configure(state="disabled")

    def add_test_command(self):
        mapping = {"МДО": TaskType.MDO, "МСО": TaskType.MSO, "Управление": TaskType.UPR, "Диспетчеризация": TaskType.DISP}
        self.test_commands.append((mapping[self.test_task.get()], self.test_dur.get()))
        self.refresh_test_tree()

    def remove_test_command(self):
        sel = self.test_tree.selection()
        if not sel:
            return
        indices = sorted([self.test_tree.index(i) for i in sel], reverse=True)
        for idx in indices:
            self.test_commands.pop(idx)
        self.refresh_test_tree()

    def refresh_test_tree(self):
        for item in self.test_tree.get_children():
            self.test_tree.delete(item)
        for task, dur in self.test_commands:
            self.test_tree.insert("", "end", values=(TASK_NAMES[task.name], dur))

    def make_cfg(self):
        return SimulationConfig(seed=self.seed_var.get(), p_hit=float(self.cache_hit.get()))

    def create_simulation(self):
        try:
            cfg = self.make_cfg()
        except tk.TclError:
            messagebox.showerror("Ошибка", "Seed должен быть целым числом.")
            return
        self.sim = Simulator(cfg)
        if self.mode.get() == "full":
            self.sim.generate_variant3()
        else:
            self.sim.generate_test(self.test_commands)
        self._sync_ui()
        self.status_var.set(f"Создано команд: {len(self.sim.command_stream)}")

    def reset_sim(self):
        self.pause_run()
        if self.sim is None:
            self.create_simulation()
            return
        cfg = self.make_cfg()
        self.sim = Simulator(cfg)
        if self.mode.get() == "full":
            self.sim.generate_variant3()
        else:
            self.sim.generate_test(self.test_commands)
        self._sync_ui()
        self.status_var.set("Симуляция сброшена")

    def clear_timeline(self):
        if self.sim:
            self.sim.trace_events.clear()
        self.timeline.set_data([], 0)
        self.status_var.set("Диаграмма очищена")

    def start_run(self):
        if self.sim is None:
            self.create_simulation()
        if self.sim is None or self.sim.finished or self._running:
            return
        self._running = True
        self.status_var.set("Симуляция выполняется…")
        self._after_id = self.after(max(10, int(self.period_var.get())), self._auto_step)

    def _auto_step(self):
        self._after_id = None
        if not self._running or self.sim is None:
            return
        if self.sim.finished:
            self._running = False
            self._sync_ui()
            return
        self.sim.step()
        self._sync_ui(auto_scroll=True)
        if not self.sim.finished and self._running:
            self._after_id = self.after(max(10, int(self.period_var.get())), self._auto_step)
        else:
            self._running = False
            self.status_var.set("Симуляция завершена")

    def pause_run(self):
        self._running = False
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
        self.status_var.set("Пауза")

    def step_once(self):
        self.pause_run()
        if self.sim is None:
            self.create_simulation()
        if self.sim is None or self.sim.finished:
            return
        self.sim.step()
        self._sync_ui(auto_scroll=True)
        self.status_var.set("Следующий такт выполнен")

    def _sync_ui(self, auto_scroll=False):
        if self.sim is None:
            return
        self.timeline.set_data(self.sim.trace_events, self.sim.current_tick)
        self._set_text(self.snapshot, self.sim.snapshot())
        stats = self.sim.stats
        text = (
            f"Команд: {stats.total_commands}\n"
            f"Выполнено: {sum(1 for c in self.sim.command_stream if c.status == 'DONE')}\n"
            f"HIT: {stats.hits}\n"
            f"MISS: {stats.misses}\n"
            f"Hit rate: {stats.hit_rate():.1%}\n"
            f"Обращений ОП (слов): {stats.op_accesses_words}\n"
            f"Обращений УСО: {stats.uso_accesses}\n"
            f"Занято СШ: {stats.bus_busy_sb_ticks} SB\n"
            f"Такт МП: {self.sim.current_tick}\n"
            f"Такт СШ: {self.sim.snapshot_dict()['tick_sb']}\n"
        )
        self.stats_label.configure(text=text)
        log_text = "\n".join(self.sim.event_log[-18:])
        self._set_text(self.log, log_text)
        self.status_var.set(f"tМП={self.sim.current_tick} | tСШ={self.sim.snapshot_dict()['tick_sb']} | FIFO={len(self.sim.bus.fifo)}")
        if auto_scroll:
            self.after_idle(lambda: self.timeline.canvas.xview_moveto(max(0.0, min(1.0, (self.timeline._x(self.sim.current_tick) - 700) / max(1, self.timeline._last_width - 700)))))

    @staticmethod
    def _set_text(widget: tk.Text, text: str):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def _event_clicked(self, ev: ResourceEvent):
        detail = (
            f"Ресурс: {dict(LANES).get(ev.resource, ev.resource)}\n"
            f"Операция: {ev.operation}\n"
            f"Такты МП: {float(ev.start):g} → {float(ev.end):g}\n"
            f"Длительность: {float(ev.duration):g}\n"
            f"Команда: {TASK_NAMES.get(ev.task, ev.task or '—')} #{ev.command_id if ev.command_id is not None else '—'}\n"
            f"Детали: {ev.detail}"
        )
        self._set_text(self.detail, detail)

    def set_zoom(self, value):
        self.timeline.set_zoom(value)
        self.zoom_var.set(f"{self.timeline.zoom / 14 * 100:.0f}%")

    def adjust_zoom(self, factor):
        self.set_zoom(self.timeline.zoom * factor)


if __name__ == "__main__":
    LabApp().mainloop()
