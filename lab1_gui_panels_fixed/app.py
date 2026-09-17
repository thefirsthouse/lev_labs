from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk, messagebox
from collections import Counter

from lab1.model import Simulator, TaskType, Event

LANES = [
    ('PIPELINE_1', 'КОНВЕЙЕР 1'),
    ('PIPELINE_2', 'КОНВЕЙЕР 2'),
    ('CACHE', 'КЭШ'),
    ('CACHE_CONTROLLER', 'КЭШ-КОНТРОЛЛЕР'),
    ('SYSTEM_BUS', 'СШ'),
    ('BUFFER_ELEMENT', 'БЭ'),
    ('MEMORY', 'ОП'),
    ('USO', 'УСО'),
]
LANE = {key: i for i, (key, _) in enumerate(LANES)}
TASK_NAME = {'MDO': 'МДО', 'MSO': 'МСО', 'UPR': 'Управление', 'DISP': 'Диспетчеризация'}
TASK_COLOR = {'MDO': '#6688e8', 'MSO': '#5db991', 'UPR': '#e3a057', 'DISP': '#bf78df'}
GROUP_COLOR = {
    'lookup': '#4e92b8', 'cache': '#4e9f83', 'cache_hit': '#4ca87f',
    'cache_miss': '#d05e5e', 'transfer': '#d28c49', 'bus': '#d2a43e',
    'memory': '#9775d1', 'uso': '#d47591', 'wait': '#676d78',
    'task': '#6688e8', 'neutral': '#5d6370',
}


class Timeline(tk.Frame):
    def __init__(self, master, on_event):
        super().__init__(master, bg='#12151a')
        self.on_event = on_event
        self.zoom = 12
        self.lane_h = 58
        self.left = 130
        self.top = 52
        self.events = []
        self.now = 0
        self.tip = None
        self.c = tk.Canvas(self, bg='#12151a', highlightthickness=0)
        self.xs = ttk.Scrollbar(self, orient='horizontal', command=self.c.xview)
        self.ys = ttk.Scrollbar(self, orient='vertical', command=self.c.yview)
        self.c.configure(xscrollcommand=self.xs.set, yscrollcommand=self.ys.set)
        self.c.grid(row=0, column=0, sticky='nsew')
        self.ys.grid(row=0, column=1, sticky='ns')
        self.xs.grid(row=1, column=0, sticky='ew')
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.c.bind('<MouseWheel>', self.wheel)
        self.c.bind('<Button-4>', lambda e: self.c.yview_scroll(-1, 'units'))
        self.c.bind('<Button-5>', lambda e: self.c.yview_scroll(1, 'units'))
        self.c.bind('<Control-KeyPress-plus>', lambda e: self.adjust_zoom(1.2))
        self.c.bind('<Control-KeyPress-equal>', lambda e: self.adjust_zoom(1.2))
        self.c.bind('<Control-KeyPress-minus>', lambda e: self.adjust_zoom(1 / 1.2))

    def wheel(self, e):
        if e.state & 4:
            self.adjust_zoom(1.15 if e.delta > 0 else 1 / 1.15)
        else:
            self.c.yview_scroll(-1 if e.delta > 0 else 1, 'units')

    def adjust_zoom(self, f):
        self.zoom = max(5, min(36, self.zoom * f))
        self.draw()

    def set_zoom(self, z):
        self.zoom = max(5, min(36, float(z)))
        self.draw()

    def set_lane_h(self, h):
        self.lane_h = max(42, min(100, int(h)))
        self.draw()

    def set_data(self, events, now):
        self.events = list(events)
        self.now = now
        self.draw()

    def x(self, t):
        return self.left + t * self.zoom

    def _slots(self):
        slots = {}
        slot_idx = {}
        for idx, e in sorted(enumerate(self.events), key=lambda x: (float(x[1].start), float(x[1].end))):
            slots.setdefault(e.resource, [])
            placed = False
            for i, ends in enumerate(slots[e.resource]):
                if float(e.start) >= max(ends) - 1e-9:
                    ends.append(float(e.end))
                    slot_idx[idx] = i
                    placed = True
                    break
            if not placed:
                slots[e.resource].append([float(e.end)])
                slot_idx[idx] = len(slots[e.resource]) - 1
        return slot_idx, {k: len(v) for k, v in slots.items()}

    def draw(self):
        self.c.delete('all')
        self.tip_hide()
        slot_idx, nslots = self._slots()
        max_t = max(20, float(self.now) + 20, max([float(e.end) for e in self.events], default=0) + 4)
        W = int(self.x(max_t) + 60)
        H = int(self.top + len(LANES) * self.lane_h + 10)

        for i, (k, name) in enumerate(LANES):
            y0 = self.top + i * self.lane_h
            y1 = y0 + self.lane_h
            self.c.create_rectangle(0, y0, W, y1, fill='#191c22' if i % 2 == 0 else '#16191f', outline='')
            self.c.create_text(8, (y0 + y1) / 2, text=name, anchor='w', fill='#d9dee7', font=('TkDefaultFont', 9, 'bold'))
            self.c.create_line(self.left, y0, W, y0, fill='#303640')

        for t in range(int(max_t) + 1):
            xx = self.x(t)
            col = '#66707e' if t % 10 == 0 else ('#424a55' if t % 5 == 0 else '#292e36')
            self.c.create_line(xx, self.top, xx, H, fill=col, dash=None if t % 5 == 0 else (2, 3))
            if t % 10 == 0:
                self.c.create_text(xx + 2, 15, text=str(t), anchor='w', fill='#e2e6ed', font=('TkDefaultFont', 8, 'bold'))

        self.c.create_text(8, 15, text='ВРЕМЯ — ТАКТЫ МП', anchor='w', fill='#8fc7e3', font=('TkDefaultFont', 8, 'bold'))
        nx = self.x(self.now)
        self.c.create_line(nx, self.top - 2, nx, H, fill='#f0d66e', width=2)
        self.c.create_text(nx + 4, 34, text=f'NOW {self.now}', anchor='w', fill='#f0d66e', font=('TkDefaultFont', 8, 'bold'))

        # One logical command may occupy several hardware resources.
        by = {}
        for e in self.events:
            if e.command_id is not None:
                by.setdefault(e.command_id, []).append(e)
        for es in by.values():
            es.sort(key=lambda e: (float(e.start), float(e.end), LANE.get(e.resource, 99)))
            for a, b in zip(es, es[1:]):
                if a.resource == b.resource or float(b.start) < float(a.end):
                    continue
                ya = self.top + (LANE[a.resource] + .5) * self.lane_h
                yb = self.top + (LANE[b.resource] + .5) * self.lane_h
                self.c.create_line(self.x(float(a.end)), ya, self.x(float(b.start)), yb, fill='#687180', dash=(3, 4), arrow='last')

        for idx, e in enumerate(self.events):
            li = LANE.get(e.resource)
            if li is None:
                continue
            cnt = max(1, nslots.get(e.resource, 1))
            slot = slot_idx.get(idx, 0)
            bh = max(17, min(38, (self.lane_h - 10 - (cnt - 1) * 3) / cnt))
            y = self.top + li * self.lane_h + 5 + slot * (bh + 3)
            x0 = self.x(float(e.start))
            x1 = max(x0 + 5, self.x(float(e.end)))
            fill = TASK_COLOR.get(e.task, GROUP_COLOR.get(e.group, '#5d6370')) if e.resource.startswith('PIPELINE') and e.operation == 'EXECUTE' else GROUP_COLOR.get(e.group, '#5d6370')
            tag = f'e{idx}'
            self.c.create_rectangle(x0 + 1, y, x1 - 1, y + bh, fill=fill, outline='#0d0f13', tags=(tag,))

            # Visually split the 4-1-1-1 memory transfer without changing its timing.
            if e.resource in {'MEMORY', 'BUFFER_ELEMENT', 'SYSTEM_BUS'} and e.operation in ('READ', 'BUFFER', 'MEMORY TRANSFER') and e.duration >= 4:
                total_sb = 7
                for sb_off in (4, 5, 6):
                    xx = x0 + (x1 - x0) * sb_off / total_sb
                    self.c.create_line(xx, y + 2, xx, y + bh - 2, fill='#343a45', width=1, tags=(tag,))

            label = e.operation
            if e.resource.startswith('PIPELINE') and e.command_id is not None:
                label = f'{TASK_NAME.get(e.task, e.task)} #{e.command_id}'
            elif e.resource == 'CACHE' and e.operation in ('HIT', 'MISS'):
                label = f'{e.operation} #{e.command_id}'
            if x1 - x0 > 46:
                self.c.create_text(x0 + 5, y + bh / 2, text=label, anchor='w', fill='#111318', font=('TkDefaultFont', 8, 'bold'), tags=(tag,))

            self.c.tag_bind(tag, '<Button-1>', lambda ev, obj=e: self.on_event(obj))
            self.c.tag_bind(tag, '<Enter>', lambda ev, obj=e: self.tip_show(obj, ev.x_root, ev.y_root))
            self.c.tag_bind(tag, '<Leave>', lambda ev: self.tip_hide())

        self.c.configure(scrollregion=(0, 0, W, H))

    def tip_show(self, e, x, y):
        self.tip_hide()
        top = tk.Toplevel(self)
        top.wm_overrideredirect(True)
        top.configure(bg='#0e1115')
        task = f'{TASK_NAME.get(e.task, e.task)} #{e.command_id}' if e.command_id is not None else '—'
        text = (
            f'Ресурс: {dict(LANES)[e.resource]}\n'
            f'Операция: {e.operation}\n'
            f'Команда: {task}\n'
            f'МП: {float(e.start):g} → {float(e.end):g}\n'
            f'{e.detail}'
        )
        tk.Label(top, text=text, justify='left', bg='#0e1115', fg='#edf0f5', padx=7, pady=6, font=('TkDefaultFont', 9)).pack()
        top.geometry(f'+{x + 12}+{y + 12}')
        self.tip = top

    def tip_hide(self):
        if self.tip:
            try:
                self.tip.destroy()
            except tk.TclError:
                pass
            self.tip = None


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Имитационная модель ВС — вариант 3')
        self.geometry('1500x900')
        self.minsize(1100, 720)
        self.configure(bg='#111317')

        self.sim = None
        self.mode = tk.StringVar(value='full')
        self.hit = tk.DoubleVar(value=.65)
        self.seed = tk.IntVar(value=42)
        self.period = tk.IntVar(value=120)
        self.zoom_label = tk.StringVar(value='100%')
        self.thickness = tk.IntVar(value=58)
        self.status = tk.StringVar(value='Готово')
        self.phase = tk.StringVar(value='Фаза: —')
        self.running = False
        self.after_id = None
        self.test_commands = [
            (TaskType.MDO, 5),
            (TaskType.MSO, 2),
            (TaskType.UPR, 2),
            (TaskType.DISP, 1),
        ]

        self.style()
        self.build()
        self.create_simulation()

    def style(self):
        st = ttk.Style(self)
        try:
            st.theme_use('clam')
        except tk.TclError:
            pass
        st.configure('TFrame', background='#171a20')
        st.configure('Panel.TFrame', background='#171a20')
        st.configure('TLabel', background='#171a20', foreground='#d8dde6')
        st.configure('Header.TLabel', background='#171a20', foreground='#e5e9ef', font=('TkDefaultFont', 9, 'bold'))
        st.configure('TButton', padding=(6, 4))
        st.configure('TRadiobutton', background='#171a20', foreground='#d8dde6')
        st.configure('TCheckbutton', background='#171a20', foreground='#d8dde6')
        st.configure('TScale', background='#171a20')

    def build(self):
        top = ttk.Frame(self, style='Panel.TFrame')
        top.pack(fill='x', padx=10, pady=(10, 6))
        for text, command in [
            ('▶ Старт', self.start_run),
            ('⏸ Пауза', self.pause_run),
            ('⏭ Следующий такт', self.step_once),
            ('↺ Сброс', self.reset_sim),
            ('⏩ До следующей фазы', self.next_phase),
        ]:
            ttk.Button(top, text=text, command=command).pack(side='left', padx=(0, 7))
        ttk.Label(top, text='Период (мс):').pack(side='left', padx=(8, 4))
        ttk.Spinbox(top, from_=10, to=2000, textvariable=self.period, width=7).pack(side='left')
        ttk.Label(top, textvariable=self.phase).pack(side='right', padx=10)
        ttk.Label(top, textvariable=self.status, foreground='#858d9b').pack(side='right', padx=10)

        main = ttk.Frame(self, style='Panel.TFrame')
        main.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        # ONLY these two fixed widths are reduced compared with the previous UI.
        left = ttk.Frame(main, style='Panel.TFrame', width=220)
        left.grid(row=0, column=0, sticky='nsw', padx=(0, 8))
        left.pack_propagate(False)
        center = ttk.Frame(main, style='Panel.TFrame')
        center.grid(row=0, column=1, sticky='nsew')
        center.columnconfigure(0, weight=1)
        center.rowconfigure(0, weight=1)
        right = ttk.Frame(main, style='Panel.TFrame', width=260)
        right.grid(row=0, column=2, sticky='nse', padx=(8, 0))
        right.pack_propagate(False)

        self.build_left(left)
        self.timeline = Timeline(center, self.event_detail)
        self.timeline.grid(row=0, column=0, sticky='nsew')
        self.build_right(right)
        self.protocol('WM_DELETE_WINDOW', self.close)

    def build_left(self, f):
        ttk.Label(f, text='РЕЖИМ', style='Header.TLabel').pack(anchor='w', pady=(4, 6))
        ttk.Radiobutton(f, text='Полная симуляция — вариант 3', variable=self.mode, value='full').pack(anchor='w')
        ttk.Radiobutton(f, text='Тестовый режим', variable=self.mode, value='test').pack(anchor='w', pady=(0, 10))

        ttk.Label(f, text='КЭШ', style='Header.TLabel').pack(anchor='w', pady=(4, 6))
        cache = ttk.Frame(f, style='Panel.TFrame')
        cache.pack(fill='x')
        ttk.Radiobutton(cache, text='65%', variable=self.hit, value=.65).pack(side='left')
        ttk.Radiobutton(cache, text='85%', variable=self.hit, value=.85).pack(side='left', padx=8)

        ttk.Label(f, text='SEED', style='Header.TLabel').pack(anchor='w', pady=(12, 5))
        ttk.Entry(f, textvariable=self.seed, width=12).pack(anchor='w')

        ttk.Label(f, text='ТЕСТОВЫЕ КОМАНДЫ', style='Header.TLabel').pack(anchor='w', pady=(14, 5))
        add = ttk.Frame(f, style='Panel.TFrame')
        add.pack(fill='x')
        self.test_task = ttk.Combobox(add, values=['МДО', 'МСО', 'Управление', 'Диспетчеризация'], state='readonly', width=13)
        self.test_task.set('МДО')
        self.test_task.pack(side='left')
        self.test_dur = tk.IntVar(value=2)
        ttk.Spinbox(add, from_=1, to=5, textvariable=self.test_dur, width=4).pack(side='left', padx=4)
        ttk.Button(add, text='+', width=3, command=self.add_test_command).pack(side='left')
        self.test_tree = ttk.Treeview(f, columns=('task', 'dur'), show='headings', height=6)
        self.test_tree.heading('task', text='Тип')
        self.test_tree.heading('dur', text='Такты')
        self.test_tree.column('task', width=120)
        self.test_tree.column('dur', width=45, anchor='center')
        self.test_tree.pack(fill='x', pady=5)
        ttk.Button(f, text='Удалить выбранную', command=self.remove_test_command).pack(anchor='e')

        ttk.Button(f, text='Создать симуляцию', command=self.create_simulation).pack(fill='x', pady=(14, 5))
        ttk.Button(f, text='Очистить диаграмму', command=self.clear_timeline).pack(fill='x')

        ttk.Label(f, text='МАСШТАБ', style='Header.TLabel').pack(anchor='w', pady=(14, 5))
        z = ttk.Frame(f, style='Panel.TFrame')
        z.pack(fill='x')
        ttk.Button(z, text='−', width=3, command=lambda: self.adjust_zoom(1 / 1.25)).pack(side='left')
        ttk.Label(z, textvariable=self.zoom_label, width=7, anchor='center').pack(side='left')
        ttk.Button(z, text='+', width=3, command=lambda: self.adjust_zoom(1.25)).pack(side='left')
        ttk.Button(z, text='100%', command=lambda: self.set_zoom_percent(100)).pack(side='left', padx=4)
        ttk.Button(z, text='200%', command=lambda: self.set_zoom_percent(200)).pack(side='left')

        ttk.Label(f, text='ТОЛЩИНА БЛОКОВ', style='Header.TLabel').pack(anchor='w', pady=(13, 4))
        ttk.Scale(f, from_=42, to=90, variable=self.thickness, command=self.thickness_changed).pack(fill='x')
        ttk.Label(f, text='ползунок меняет толщину дорожек', foreground='#838b99').pack(anchor='w')

        ttk.Label(f, text='Смысл Timeline', style='Header.TLabel').pack(anchor='w', pady=(13, 4))
        ttk.Label(
            f,
            text='Строка = ресурс.\nX = время.\nБлок = реальная операция.\n\nОдна команда может иметь события на разных ресурсах.',
            foreground='#929aa8', justify='left', wraplength=205,
        ).pack(anchor='w')
        self.refresh_test_tree()

    def build_right(self, f):
        ttk.Label(f, text='ТЕКУЩЕЕ СОСТОЯНИЕ', style='Header.TLabel').pack(anchor='w')
        self.snapshot = tk.Text(f, height=16, bg='#101318', fg='#dde3ec', relief='flat', wrap='word')
        self.snapshot.pack(fill='x', pady=(5, 10))
        self.snapshot.configure(state='disabled')

        ttk.Label(f, text='СОБЫТИЕ', style='Header.TLabel').pack(anchor='w')
        self.detail = tk.Text(f, height=8, bg='#101318', fg='#dde3ec', relief='flat', wrap='word')
        self.detail.pack(fill='x', pady=(5, 10))
        self.detail.configure(state='disabled')

        ttk.Label(f, text='СТАТИСТИКА', style='Header.TLabel').pack(anchor='w')
        self.stats = ttk.Label(f, text='—', justify='left')
        self.stats.pack(anchor='w', pady=(5, 10))

        ttk.Label(f, text='ПОСЛЕДНИЕ СОБЫТИЯ', style='Header.TLabel').pack(anchor='w')
        self.log = tk.Text(f, height=12, bg='#101318', fg='#aeb6c5', relief='flat', wrap='word')
        self.log.pack(fill='both', expand=True, pady=(5, 0))
        self.log.configure(state='disabled')

    def refresh_test_tree(self):
        for item in self.test_tree.get_children():
            self.test_tree.delete(item)
        for task, dur in self.test_commands:
            self.test_tree.insert('', 'end', values=(TASK_NAME[task.name], dur))

    def add_test_command(self):
        mapping = {'МДО': TaskType.MDO, 'МСО': TaskType.MSO, 'Управление': TaskType.UPR, 'Диспетчеризация': TaskType.DISP}
        self.test_commands.append((mapping[self.test_task.get()], int(self.test_dur.get())))
        self.refresh_test_tree()

    def remove_test_command(self):
        selected = self.test_tree.selection()
        if not selected:
            return
        for idx in sorted((self.test_tree.index(item) for item in selected), reverse=True):
            self.test_commands.pop(idx)
        self.refresh_test_tree()

    def create_simulation(self):
        try:
            seed = int(self.seed.get())
        except (TypeError, ValueError):
            messagebox.showerror('Ошибка', 'Seed должен быть целым числом.')
            return
        self.pause_run()
        self.sim = Simulator(seed, float(self.hit.get()))
        if self.mode.get() == 'full':
            self.sim.generate_variant3()
        else:
            self.sim.generate_test(self.test_commands)
        self.sync()

    def reset_sim(self):
        self.create_simulation()
        self.status.set('Симуляция сброшена')

    def clear_timeline(self):
        if self.sim:
            self.sim.events.clear()
        self.timeline.set_data([], self.sim.current_tick if self.sim else 0)
        self.status.set('Диаграмма очищена')

    def start_run(self):
        if self.sim is None:
            self.create_simulation()
        if self.sim is None or self.sim.finished or self.running:
            return
        self.running = True
        self.status.set('Симуляция выполняется…')
        self.after_id = self.after(max(10, int(self.period.get())), self.auto_step)

    def auto_step(self):
        self.after_id = None
        if not self.running or self.sim is None:
            return
        self.sim.step()
        self.sync(True)
        if not self.sim.finished and self.running:
            self.after_id = self.after(max(10, int(self.period.get())), self.auto_step)
        else:
            self.running = False
            self.status.set('Симуляция завершена')

    def pause_run(self):
        self.running = False
        if self.after_id is not None:
            try:
                self.after_cancel(self.after_id)
            except tk.TclError:
                pass
            self.after_id = None
        self.status.set('Пауза')

    def step_once(self):
        self.pause_run()
        if self.sim is None:
            self.create_simulation()
        if self.sim is None or self.sim.finished:
            return
        self.sim.step()
        self.sync(True)
        self.status.set('Следующий такт выполнен')

    def next_phase(self):
        self.pause_run()
        if self.sim is None:
            self.create_simulation()
        if self.sim is None or self.sim.finished:
            return
        before = self.active_tasks()
        for _ in range(20000):
            if self.sim.finished:
                break
            self.sim.step()
            after = self.active_tasks()
            if any(t not in before for t in after):
                break
        self.sync(True)
        self.status.set('Остановлено на следующей фазе')

    def active_tasks(self):
        if self.sim is None:
            return set()
        return {p.command.task.name for p in self.sim.pipelines if p.command is not None}

    def sync(self, scroll=False):
        if self.sim is None:
            return
        self.timeline.set_data(self.sim.events, self.sim.current_tick)
        self.set_text(self.snapshot, self.sim.snapshot())

        cnt = Counter(c.task.name for c in self.sim.commands)
        done = Counter(c.task.name for c in self.sim.commands if c.status == 'DONE')
        issued = Counter(c.task.name for c in self.sim.commands if c.status != 'WAITING')
        total = len(self.sim.commands)
        completed = sum(done.values())
        hit_total = self.sim.hits + self.sim.misses
        hit_rate = self.sim.hits / hit_total if hit_total else 0.0

        self.stats.configure(
            text=(
                f'Команд: {total}\n'
                f'Выполнено: {completed}\n'
                f'HIT: {self.sim.hits}\n'
                f'MISS: {self.sim.misses}\n'
                f'Hit rate: {hit_rate:.1%}\n'
                f'ОП: {self.sim.op_words} слов\n'
                f'УСО: {self.sim.uso_accesses} обращений\n'
                f'СШ: {self.sim.bus_busy_sb_ticks} SB\n'
                f'Такт МП: {self.sim.current_tick}\n'
                f'Такт СШ: {self.sim.tick_sb}'
            )
        )
        self.phase.set(self.current_phase(cnt, issued, done))
        self.set_text(self.log, '\n'.join(self.sim.log[-18:]))
        self.status.set(f'tМП={self.sim.current_tick} | tСШ={self.sim.tick_sb} | FIFO={len(self.sim.bus_fifo)}')

        if scroll:
            self.after_idle(lambda: self.timeline.c.xview_moveto(0.0))

    def current_phase(self, cnt, issued, done):
        for task in ('MDO', 'MSO', 'UPR', 'DISP'):
            if done.get(task, 0) < cnt.get(task, 0):
                return f'Фаза: {TASK_NAME[task]} {done.get(task, 0)}/{cnt.get(task, 0)}'
        return 'Фаза: завершено'

    def event_detail(self, e: Event):
        task = f'{TASK_NAME.get(e.task, e.task)} #{e.command_id}' if e.command_id is not None else '—'
        self.set_text(
            self.detail,
            f'Ресурс: {dict(LANES)[e.resource]}\n'
            f'Операция: {e.operation}\n'
            f'Команда: {task}\n'
            f'Начало: {float(e.start):g}\n'
            f'Конец: {float(e.end):g}\n'
            f'Длительность: {float(e.end - e.start):g}\n\n'
            f'{e.detail}'
        )

    @staticmethod
    def set_text(widget, text):
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', text)
        widget.configure(state='disabled')

    def set_zoom_percent(self, pct):
        self.timeline.set_zoom(12 * pct / 100)
        self.zoom_label.set(f'{pct}%')

    def adjust_zoom(self, factor):
        self.timeline.adjust_zoom(factor)
        self.zoom_label.set(f'{self.timeline.zoom / 12 * 100:.0f}%')

    def thickness_changed(self, value):
        self.timeline.set_lane_h(float(value))

    def close(self):
        self.pause_run()
        self.destroy()


if __name__ == '__main__':
    App().mainloop()
