"""
THE HAVELI MYSTERY - Compact Screen-Fit Edition

Run:   python murder_mystery.py
Needs: Python 3 with Tkinter. No internet needed.
"""
import queue
import random
import sys
import threading
import tkinter as tk
from tkinter import scrolledtext

from engine import (SLOTS, ROOMS, EDGES, WEAPONS, VICTIM, Investigator, generate_case,
                    prove_guilty, rival_choose, refute, describe, DIST)
from llm_layer import Storyteller

AP = 35

# Color Palette
BG = "#0f172a"
CARD_BG = "#1e293b"
CARD_BORDER = "#334155"
TEXT_MAIN = "#f8fafc"
TEXT_MUTED = "#94a3b8"
ACCENT_GOLD = "#fbbf24"
ACCENT_BLUE = "#38bdf8"
ACCENT_RED = "#f87171"
ACCENT_GREEN = "#4ade80"


class Game:
    def __init__(self, root):
        self.root = root
        self.teller = Storyteller()
        self.q = queue.Queue()
        self.pending_n = 0
        self.rng = random.Random()

        self.selected_suspect = None
        self.selected_slot = 1  

        self.build_ui()
        self.poll()
        self.new_case()

    #UI BUILD
    def build_ui(self):
        r = self.root
        r.title("The Haveli Mystery — AI Detective Challenge")
        r.configure(bg=BG)
        r.geometry("1000x620")  # Compact height so everything fits!

        # Top Bar: Status & Budget
        top_bar = tk.Frame(r, bg=CARD_BG, padx=12, pady=6, highlightthickness=1, highlightbackground=CARD_BORDER)
        top_bar.pack(fill="x", padx=10, pady=(8, 4))

        tk.Label(top_bar, text="🕵️ THE HAVELI MYSTERY", bg=CARD_BG, fg=ACCENT_GOLD, font=("Segoe UI", 13, "bold")).pack(side="left")
        
        self.ap_var = tk.StringVar()
        tk.Label(top_bar, textvariable=self.ap_var, bg=CARD_BG, fg=TEXT_MAIN, font=("Segoe UI", 10, "bold")).pack(side="right")

        # Case Subheader
        self.info_var = tk.StringVar()
        tk.Label(r, textvariable=self.info_var, bg=BG, fg=ACCENT_BLUE, font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", padx=12, pady=(0, 4))

        # Main Workspace
        main_frame = tk.Frame(r, bg=BG)
        main_frame.pack(fill="both", expand=True, padx=10)

        # LEFT COLUMN: Compact Controls
        left_col = tk.Frame(main_frame, bg=BG, width=360)
        left_col.pack(side="left", fill="both", expand=False, padx=(0, 6))

        # Step 1: Choose Suspect
        s1_card = tk.LabelFrame(left_col, text=" 1. CHOOSE SUSPECT ", bg=CARD_BG, fg=ACCENT_GOLD,
                                font=("Segoe UI", 8, "bold"), padx=6, pady=4, highlightthickness=1, highlightbackground=CARD_BORDER)
        s1_card.pack(fill="x", pady=(0, 4))

        self.suspect_btn_frame = tk.Frame(s1_card, bg=CARD_BG)
        self.suspect_btn_frame.pack(fill="x")

        # Step 2: Time Slot & Question Button
        s2_card = tk.LabelFrame(left_col, text=" 2. QUESTIONING HOUR ", bg=CARD_BG, fg=ACCENT_GOLD,
                                font=("Segoe UI", 8, "bold"), padx=6, pady=4, highlightthickness=1, highlightbackground=CARD_BORDER)
        s2_card.pack(fill="x", pady=(0, 4))

        time_btn_frame = tk.Frame(s2_card, bg=CARD_BG)
        time_btn_frame.pack(fill="x")

        self.slot_btns = []
        for idx, slot in enumerate(SLOTS):
            btn = tk.Button(time_btn_frame, text=slot, bg=BG, fg=TEXT_MAIN,
                            relief="flat", font=("Segoe UI", 8, "bold"), padx=4, pady=2, cursor="hand2",
                            command=lambda i=idx: self.select_slot(i))
            btn.pack(side="left", fill="x", expand=True, padx=1)
            self.slot_btns.append(btn)

        self.ask_action_btn = tk.Button(s2_card, text="❓ Ask Question (1 AP)", bg=ACCENT_BLUE, fg="#000",
                                       font=("Segoe UI", 9, "bold"), relief="flat", pady=4, cursor="hand2",
                                       command=self.act_ask_selected)
        self.ask_action_btn.pack(fill="x", pady=(4, 0))

        # Step 3: Inspect Room
        s3_card = tk.LabelFrame(left_col, text=" 3. INSPECT ROOM ", bg=CARD_BG, fg=ACCENT_GOLD,
                                font=("Segoe UI", 8, "bold"), padx=6, pady=4, highlightthickness=1, highlightbackground=CARD_BORDER)
        s3_card.pack(fill="x", pady=(0, 6))

        room_grid = tk.Frame(s3_card, bg=CARD_BG)
        room_grid.pack(fill="x")

        for idx, room in enumerate(ROOMS):
            r_btn = tk.Button(room_grid, text="🔍 " + room, bg=BG, fg=TEXT_MAIN, relief="flat",
                              font=("Segoe UI", 8), padx=2, pady=2, cursor="hand2",
                              command=lambda rm=room: self.act_inspect(rm))
            r_btn.grid(row=idx // 3, column=idx % 3, sticky="nsew", padx=2, pady=2)
            room_grid.columnconfigure(idx % 3, weight=1)

        # CRITICAL CONTROL BUTTONS (Always Visible!)
        cmd_frame = tk.Frame(left_col, bg=BG)
        cmd_frame.pack(fill="x", pady=2)

        tk.Button(cmd_frame, text="⚙️ Run Deduction", bg=CARD_BG, fg=TEXT_MAIN, font=("Segoe UI", 9, "bold"),
                  relief="flat", pady=6, cursor="hand2", command=self.run_engine).pack(side="left", fill="x", expand=True, padx=(0, 2))

        tk.Button(cmd_frame, text="🚨 ACCUSE!", bg=ACCENT_RED, fg="#fff", font=("Segoe UI", 10, "bold"),
                  relief="flat", pady=6, cursor="hand2", command=self.open_accuse).pack(side="right", fill="x", expand=True, padx=(2, 0))

        # RIGHT COLUMN: Log
        right_col = tk.Frame(main_frame, bg=BG)
        right_col.pack(side="right", fill="both", expand=True, padx=(4, 0))

        diary_card = tk.LabelFrame(right_col, text=" 📜 INVESTIGATION LOG & ALIBIS ", bg=CARD_BG, fg=ACCENT_GOLD,
                                  font=("Segoe UI", 8, "bold"), padx=6, pady=6, highlightthickness=1, highlightbackground=CARD_BORDER)
        diary_card.pack(fill="both", expand=True)

        self.text = scrolledtext.ScrolledText(diary_card, bg=CARD_BG, fg=TEXT_MAIN, font=("Consolas", 9),
                                              wrap="word", padx=6, pady=6)
        self.text.pack(fill="both", expand=True)

        for tag, kw in {
            "name": dict(foreground=ACCENT_GOLD, font=("Consolas", 9, "bold")),
            "speech": dict(foreground=TEXT_MAIN),
            "dim": dict(foreground=TEXT_MUTED),
            "note": dict(foreground=ACCENT_BLUE, font=("Consolas", 8, "italic")),
            "conf": dict(foreground=ACCENT_RED, font=("Consolas", 9, "bold")),
            "good": dict(foreground=ACCENT_GREEN, font=("Consolas", 9, "bold")),
            "head": dict(foreground=ACCENT_GOLD, font=("Consolas", 10, "bold"))
        }.items():
            self.text.tag_configure(tag, **kw)

        #Bottom Bar
        bot_bar = tk.Frame(r, bg=BG)
        bot_bar.pack(fill="x", padx=10, pady=(2, 6))

        tk.Button(bot_bar, text="🔄 Restart", command=self.new_case, bg=CARD_BG, fg=TEXT_MUTED,
                  font=("Segoe UI", 8), relief="flat", padx=6, pady=2, cursor="hand2").pack(side="left")

        tk.Button(bot_bar, text="▶ Auto-Play Demo", command=self.start_auto, bg=CARD_BG, fg=ACCENT_GOLD,
                  font=("Segoe UI", 8, "bold"), relief="flat", padx=6, pady=2, cursor="hand2").pack(side="left", padx=6)

        self.rival_status_var = tk.StringVar(value="Rival: Inspector Wasim (Ready)")
        tk.Label(bot_bar, textvariable=self.rival_status_var, bg=BG, fg=TEXT_MUTED, font=("Segoe UI", 8, "italic")).pack(side="right")

    #LOGIC & UI UPDATES
    def new_case(self):
        self.seed = random.randint(1000, 9999)
        self.case = generate_case(self.seed)
        self.me = Investigator(self.case, AP)
        self.rival = Investigator(self.case, AP)
        self.state, self.busy, self.auto = "play", False, False
        self.acts = 0

        self.text.delete("1.0", "end")
        c = self.case
        self.info_var.set(f"🔎 CASE #{self.seed}: {VICTIM} killed at {SLOTS[c.T]} in {c.R} ({c.wound} wound)")
        self.write_head("--- NEW CASE STARTED ---")
        self.say_intro()

        self.build_suspect_buttons()
        self.select_suspect(c.names[0])
        self.select_slot(c.T)
        self.redraw()

    def build_suspect_buttons(self):
        for child in self.suspect_btn_frame.winfo_children():
            child.destroy()

        self.suspect_btns = {}
        for idx, name in enumerate(self.case.names):
            prof = self.case.profile(name)
            btn = tk.Button(self.suspect_btn_frame, text=f"{name} ({prof.role})", bg=BG, fg=TEXT_MAIN,
                            font=("Segoe UI", 8), relief="flat", pady=2, cursor="hand2",
                            command=lambda n=name: self.select_suspect(n))
            btn.pack(fill="x", pady=1)
            self.suspect_btns[name] = btn

    def select_suspect(self, name):
        self.selected_suspect = name
        for n, btn in self.suspect_btns.items():
            if n == name:
                btn.config(bg=ACCENT_GOLD, fg="#000", font=("Segoe UI", 8, "bold"))
            else:
                btn.config(bg=BG, fg=TEXT_MAIN, font=("Segoe UI", 8))
        self.update_action_button_text()

    def select_slot(self, slot_idx):
        self.selected_slot = slot_idx
        for idx, btn in enumerate(self.slot_btns):
            if idx == slot_idx:
                btn.config(bg=ACCENT_BLUE, fg="#000")
            else:
                btn.config(bg=BG, fg=TEXT_MAIN)
        self.update_action_button_text()

    def update_action_button_text(self):
        if self.selected_suspect is not None:
            time_name = SLOTS[self.selected_slot]
            self.ask_action_btn.config(text=f"❓ Ask {self.selected_suspect} about {time_name} (1 AP)")

    def redraw(self):
        left = self.me.remaining()
        self.ap_var.set(f"Action Points: {left} / {AP}")

    #LOGGING
    def write(self, s, *tags):
        self.text.insert("end", s, tags)
        self.text.see("end")

    def write_head(self, s):
        self.write("\n" + s + "\n", "head")

    def say_intro(self):
        if not self.teller.enabled:
            self.write(self.teller.intro(self.case)[0] + "\n", "speech")
            return
        tag = self.new_tag()
        self.write("(Narrator setting the scene...)\n", tag, "dim")
        case = self.case
        threading.Thread(target=lambda: self.q.put((self.text, tag, self.teller.intro(case)[0], "speech")), daemon=True).start()

    def new_tag(self):
        self.pending_n += 1
        return f"p{self.pending_n}"

    def say_suspect(self, stmt):
        self.write(f"\n🗣️ {stmt.speaker}: ", "name")
        if not self.teller.enabled:
            self.write(self.teller.suspect_line(self.case, stmt)[0] + "\n", "speech")
        else:
            tag = self.new_tag()
            self.write("(thinking...)\n", tag, "dim")
            case = self.case
            threading.Thread(target=lambda: self.q.put((self.text, tag, self.teller.suspect_line(case, stmt)[0], "speech")), daemon=True).start()
        self.write(f"   📌 [Fact] {stmt.speaker} | {SLOTS[stmt.slot]} | {stmt.room} | {stmt.with_part()}\n", "note")

    def poll(self):
        try:
            while True:
                widget, tag, txt, style = self.q.get_nowait()
                try:
                    rng = widget.tag_ranges(tag)
                    if rng:
                        start = rng[0]
                        widget.delete(rng[0], rng[1])
                        widget.insert(start, txt + "\n", (style,))
                except tk.TclError:
                    pass
        except queue.Empty:
            pass
        self.root.after(150, self.poll)

    #ACTIONS
    def act_ask_selected(self):
        if self.selected_suspect and self.state == "play":
            self.act_ask(self.selected_suspect, self.selected_slot)

    def act_ask(self, name, slot, from_auto=False):
        if not (from_auto or (self.state == "play" and not self.busy and not self.auto)):
            return
        if (name, slot) in self.me.answers:
            self.say_suspect(self.me.answers[(name, slot)])
            return
        if self.me.remaining() <= 0:
            self.write("\n⚠️ Out of Action Points! You must ACCUSE now.\n", "conf")
            return

        before = len(self.me.conflicts)
        st = self.me.interrogate(name, slot)
        self.say_suspect(st)

        if st.room == self.case.R and slot == self.case.T:
            self.write(f"   🚨 {name} admits to being at the CRIME SCENE!\n", "conf")

        for a, b, ct in self.me.conflicts[before:]:
            self.write("\n⚡ CONTRADICTION FOUND:\n", "conf")
            self.write(f'   • {a.speaker}: "{a.text()}"\n   • {b.speaker}: "{b.text()}"\n', "speech")
            self.write(f"   => Deduction: {describe(ct)}.\n", "note")

        self.after_action()

    def act_inspect(self, room, from_auto=False):
        if not (from_auto or (self.state == "play" and not self.busy and not self.auto)):
            return
        if self.me.remaining() <= 0:
            self.write("\n⚠️ Out of Action Points! You must ACCUSE now.\n", "conf")
            return
        res = self.me.inspect(room)
        self.write(f"\n🔍 INSPECTED: {room}\n", "head")
        if not res:
            self.write("No weapon is kept here.\n", "speech")
        for w, st in res:
            if st == "missing":
                self.write(f"🚨 MISSING WEAPON: {w}!\n", "conf")
            else:
                self.write(f"✓ {w} is in place.\n", "speech")
        self.after_action()

    def run_engine(self):
        if self.me.remaining() <= 0:
            self.write("\n⚠️ Out of Action Points! Time to ACCUSE.\n", "conf")
            return
        self.me.used += 1
        self.write("\n⚙️ DEDUCTION ENGINE ANALYSIS:\n", "head")
        left = []
        for y in self.case.names:
            why = refute(self.case.pub, self.me.stmts, y)
            if why:
                self.write(f"❌ Ruled Out {y}:\n", "good")
                for line in why[:3]:
                    self.write("   " + line + "\n", "speech")
            else:
                left.append(y)
        self.write("🔍 Suspects Remaining: " + ", ".join(left) + "\n", "good" if len(left) == 1 else "name")
        self.after_action()

    def after_action(self):
        self.acts += 1
        self.redraw()
        if self.state != "play" or self.auto:
            return
        if self.acts % 2 == 0 and not self.rival.out:
            self.busy = True
            self.root.after(600, self.rival_turn)

    def rival_turn(self):
        self.busy = False
        if self.state != "play" or self.rival.out:
            return
        mv = rival_choose(self.rival, self.rng)
        if mv[0] == "ask":
            self.rival.interrogate(mv[1], mv[2])
            self.rival_status_var.set(f"Rival: Asked {mv[1]} ({SLOTS[mv[2]]})")
        elif mv[0] == "inspect":
            self.rival.inspect(mv[1])
            self.rival_status_var.set(f"Rival: Inspected {mv[1]}")
        else:
            ok = (mv[1] == self.case.killer and mv[2] == self.case.weapon)
            if ok:
                self.end_game("rival", mv)
                return
            self.rival.out = True
            self.rival_status_var.set("Rival: Disqualified")

    #ACCUSATION
    def open_accuse(self):
        if self.state != "play" or self.auto:
            return
        win = tk.Toplevel(self.root)
        win.title("🚨 ACCUSATION")
        win.configure(bg=BG)
        win.geometry("420x360")
        win.grab_set()

        who, how = tk.StringVar(value=""), tk.StringVar(value="")

        tk.Label(win, text="MAKE ACCUSATION", bg=BG, fg=ACCENT_GOLD, font=("Segoe UI", 11, "bold")).pack(pady=8)

        grid = tk.Frame(win, bg=BG)
        grid.pack(padx=10, pady=6)

        f1 = tk.Frame(grid, bg=CARD_BG, padx=8, pady=8)
        f1.grid(row=0, column=0, padx=4)
        tk.Label(f1, text="SUSPECT", bg=CARD_BG, fg=ACCENT_GOLD, font=("Segoe UI", 8, "bold")).pack()
        for n in self.case.names:
            tk.Radiobutton(f1, text=n, variable=who, value=n, bg=CARD_BG, fg=TEXT_MAIN, selectcolor=BG).pack(anchor="w")

        f2 = tk.Frame(grid, bg=CARD_BG, padx=8, pady=8)
        f2.grid(row=0, column=1, padx=4)
        tk.Label(f2, text="WEAPON", bg=CARD_BG, fg=ACCENT_GOLD, font=("Segoe UI", 8, "bold")).pack()
        for w in WEAPONS:
            tk.Radiobutton(f2, text=w, variable=how, value=w, bg=CARD_BG, fg=TEXT_MAIN, selectcolor=BG).pack(anchor="w")

        def submit():
            if who.get() and how.get():
                win.destroy()
                self.do_accuse(who.get(), how.get())

        tk.Button(win, text="SUBMIT ACCUSATION", command=submit, bg=ACCENT_RED, fg="#fff", font=("Segoe UI", 9, "bold"), pady=4).pack(pady=10)

    def do_accuse(self, name, weapon):
        c = self.case
        if name == c.killer and weapon == c.weapon:
            self.end_game("me", (name, weapon))
            return
        self.me.used += 2
        self.write(f"\n❌ INCORRECT ACCUSATION! You accused {name} with {weapon}. (-2 AP Penalty)\n", "conf")
        self.redraw()
        if self.me.remaining() <= 0:
            self.end_game("cold", None)

    #ENDING
    def end_game(self, result, accusation):
        self.state = "over"
        self.auto = False
        c = self.case

        win = tk.Toplevel(self.root)
        win.title("🏆 CASE CLOSED")
        win.configure(bg=BG)
        win.geometry("650x500")

        t = scrolledtext.ScrolledText(win, bg=CARD_BG, fg=TEXT_MAIN, font=("Consolas", 9), wrap="word", padx=12, pady=12)
        t.pack(padx=12, pady=12, fill="both", expand=True)

        head = {"me": "🎉 VICTORY! YOU SOLVED IT!", "rival": "🤖 RIVAL AI SOLVED IT FIRST", "cold": "❄️ CASE WENT COLD"}[result]
        t.insert("end", head + "\n\n")

        k = c.profile(c.killer)
        t.insert("end", f"Killer: {c.killer} ({k.role})\nWeapon: {c.weapon}\nScene: {c.R} at {SLOTS[c.T]}\n\n")

        proved, _ = prove_guilty(c.pub, self.me.stmts, c.killer)
        if result == "me":
            t.insert("end", f"Proof Status: {'RIGOROUS LOGICAL PROOF!' if proved else 'Lucky guess!'}\n\n")

        t.insert("end", "--- EPILOGUE ---\n" + self.teller.epilogue(c)[0] + "\n")

    #DEMO
    def start_auto(self):
        if self.state != "play" or self.auto:
            return
        self.auto = True
        self.rival.out = True
        self.write("\n🤖 DEMO MODE ACTIVE...\n", "head")
        self.auto_step()

    def auto_step(self):
        if not self.auto or self.state != "play":
            return
        mv = rival_choose(self.me, self.rng)
        if mv[0] == "ask":
            self.act_ask(mv[1], mv[2], from_auto=True)
            self.auto and self.root.after(1000, self.auto_step)
        elif mv[0] == "inspect":
            self.act_inspect(mv[1], from_auto=True)
            self.auto and self.root.after(1000, self.auto_step)
        else:
            self.auto = False
            self.do_accuse(mv[1], mv[2])


def main():
    root = tk.Tk()
    Game(root)
    root.mainloop()


if __name__ == "__main__":
    main()