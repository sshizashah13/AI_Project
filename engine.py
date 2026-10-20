"""
engine.py  -  the BRAIN of the murder mystery. No GUI, no internet needed.

What lives here
  1. The world        : a house (graph of rooms), time slots, suspects, weapons
  2. Case generator   : makes a random murder case and PROVES it has exactly one solution
  3. Forward chaining : facts + rules  ->  derived facts  ->  contradictions (with justifications)
  4. Backward chaining: to prove  guilty(X)  we must refute every other suspect
  5. Investigator     : what one detective knows (the player and the rival AI each have one)
  6. Rival AI policy  : greedy best-first choice of the next question

Game rules the logic relies on
  * INNOCENTS ALWAYS TELL THE TRUTH. The killer may lie.
  * A statement is a full report of one room at one time:  "At 9 PM I was in the Library, with Dania."
    It means: I was there, Dania was there, and NOBODY ELSE was.
  * The killer was alone with the victim at the murder time and place.
  * People walk at most one room per hour, along the corridors of the house.

Run   python engine.py   for a self-test and benchmark.
"""
import random
import sys
from collections import deque
from dataclasses import dataclass

#the world
ROOMS = ["Study", "Library", "Mehfil Hall", "Garden", "Kitchen", "Cellar"]
EDGES = [("Study", "Library"), ("Library", "Mehfil Hall"), ("Mehfil Hall", "Garden"),
         ("Mehfil Hall", "Kitchen"), ("Garden", "Kitchen"), ("Kitchen", "Cellar")]
SLOTS = ["8 PM", "9 PM", "10 PM", "11 PM"]

ADJ = {r: set() for r in ROOMS}
for _a, _b in EDGES:
    ADJ[_a].add(_b)
    ADJ[_b].add(_a)


def _all_distances():
    out = {}
    for s in ROOMS:
        d, q = {s: 0}, deque([s])
        while q:
            u = q.popleft()
            for v in ADJ[u]:
                if v not in d:
                    d[v] = d[u] + 1
                    q.append(v)
        out[s] = d
    return out


DIST = _all_distances()          # DIST["Study"]["Cellar"] == 4  -> impossible within one evening

WEAPONS = {                       # name: (wound type, home room)
    "Brass Candlestick": ("blunt", "Library"),
    "Cricket Bat": ("blunt", "Mehfil Hall"),
    "Marble Paperweight": ("blunt", "Study"),
    "Kitchen Knife": ("sharp", "Kitchen"),
    "Garden Shears": ("sharp", "Garden"),
    "Letter Opener": ("sharp", "Study"),
}


@dataclass(frozen=True)
class Profile:
    name: str
    role: str
    trait: str
    secret: str
    motive: str


POOL = [
    Profile("Priyanka", "classmate", "nervous", "drowning in assignment deadlines",
            "Dr. Asif was about to fail her in the course project"),
    Profile("Moiz", "lab partner", "arrogant", "copypasted his entire assignment code",
            "Dr. Asif caught his plagiarized code submission"),
    Profile("Ayesha", "class representative", "chatty", "leaked the midterm exam paper",
            "Dr. Asif found out she had accessed the faculty portal"),
    Profile("Zainab", "research assistant", "sarcastic", "faked her experiment results",
            "Dr. Asif threatened to cancel her research credits"),
    Profile("Ahmed", "society treasurer", "calm", "misplaced the event sponsorship funds",
            "Dr. Asif was demanding an audit of the society bank account"),
    Profile("Azeem", "classmate", "arrogant", "using an AI bot during live quizzes",
            "Dr. Asif was about to report him to the academic board"),
]

VICTIM = "Dr. Asif"


@dataclass(frozen=True)
class Stmt:
    """A full report of one room at one time. comp = the OTHER suspects present."""
    speaker: str
    slot: int
    room: str
    comp: frozenset

    def with_part(self):
        c = sorted(self.comp)
        if not c:
            return "alone"
        return "with " + (c[0] if len(c) == 1 else ", ".join(c[:-1]) + " and " + c[-1])

    def text(self):
        return f"At {SLOTS[self.slot]} I was in the {self.room}, {self.with_part()}."


#forward chaining
# A fact is a tuple.  facts[fact] = (rule_name, premises)  -> every fact remembers WHY it is true.
#   ("said", Stmt)                       evidence
#   ("guilty", name)                     hypothesis
#   ("at", person, slot, room)           derived
#   ("not_at", person, slot, room)       derived
#   ("contradiction", kind, p, t1, r1, t2, r2)
def _rule_trust(facts, hyp, pub):
    """Innocent speakers tell the truth. Their report gives AT and NOT_AT facts."""
    names = pub[2]
    for f in list(facts):
        if f[0] != "said":
            continue
        s = f[1]
        if s.speaker == hyp:            # under the hypothesis, the killer's words are not trusted
            continue
        yield ("at", s.speaker, s.slot, s.room), "TRUST", (f,)
        for c in s.comp:
            yield ("at", c, s.slot, s.room), "TRUST-WITNESS", (f,)
        present = {s.speaker} | set(s.comp)
        for p in names:
            if p not in present:
                yield ("not_at", p, s.slot, s.room), "TRUST-EXCLUSIVE", (f,)


def _rule_scene(facts, hyp, pub):
    """If X is the killer: X was at the scene, and nobody else was."""
    if hyp is None:
        return
    T, R, names = pub
    g = ("guilty", hyp)
    yield ("at", hyp, T, R), "SCENE-KILLER", (g,)
    for p in names:
        if p != hyp:
            yield ("not_at", p, T, R), "SCENE-ALONE", (g,)


def _rule_clash(facts, hyp, pub):
    """Detect impossible situations: two places at once, AT vs NOT_AT, or too far to walk."""
    ats, nots = {}, set()
    for f in facts:
        if f[0] == "at":
            ats.setdefault(f[1], []).append(f)
        elif f[0] == "not_at":
            nots.add(f)
    for p, lst in ats.items():
        for i, a in enumerate(lst):
            neg = ("not_at", p, a[2], a[3])
            if neg in nots:
                yield ("contradiction", "NEG", p, a[2], a[3], a[2], a[3]), "CLASH", (a, neg)
            for b in lst[i + 1:]:
                (t1, r1), (t2, r2) = sorted([(a[2], a[3]), (b[2], b[3])])
                fa, fb = (a, b) if (a[2], a[3]) == (t1, r1) else (b, a)
                if t1 == t2:
                    if r1 != r2:
                        yield ("contradiction", "DOUBLE", p, t1, r1, t2, r2), "CLASH", (fa, fb)
                elif DIST[r1][r2] > t2 - t1:
                    yield ("contradiction", "TRAVEL", p, t1, r1, t2, r2), "CLASH", (fa, fb)


RULES = [_rule_trust, _rule_scene, _rule_clash]


def fc_run(pub, stmts, hyp=None):
    """FORWARD CHAINING to a fixpoint. Returns (facts, contradictions)."""
    facts = {}
    for s in stmts:
        facts[("said", s)] = ("EVIDENCE", ())
    if hyp is not None:
        facts[("guilty", hyp)] = ("HYPOTHESIS", ())
    changed = True
    while changed:
        changed = False
        for rule in RULES:
            for f, name, prem in list(rule(facts, hyp, pub)):
                if f not in facts:
                    facts[f] = (name, tuple(prem))
                    changed = True
    return facts, [f for f in facts if f[0] == "contradiction"]


def candidates_from(pub, stmts):
    """Suspects who are still POSSIBLE killers: hypothesis leads to no contradiction."""
    return [h for h in pub[2] if not fc_run(pub, stmts, h)[1]]


#explanations
def describe(f):
    k = f[0]
    if k == "said":
        return f'{f[1].speaker} said: "{f[1].text()}"'
    if k == "at":
        return f"{f[1]} was in the {f[3]} at {SLOTS[f[2]]}"
    if k == "not_at":
        return f"{f[1]} was NOT in the {f[3]} at {SLOTS[f[2]]}"
    if k == "guilty":
        return f"Suppose {f[1]} is the killer"
    if k == "contradiction":
        _, kind, p, t1, r1, t2, r2 = f
        if kind == "DOUBLE":
            return f"IMPOSSIBLE: {p} would be in the {r1} and the {r2} at {SLOTS[t1]}"
        if kind == "NEG":
            return f"IMPOSSIBLE: {p} would be both in and not in the {r1} at {SLOTS[t1]}"
        return (f"IMPOSSIBLE: {p} cannot get from the {r1} ({SLOTS[t1]}) "
                f"to the {r2} ({SLOTS[t2]}) in time")
    return str(f)


def explain(facts, contra):
    lines = [describe(contra)]
    for p in facts[contra][1]:
        lines.append("   - " + describe(p))
        rule, prem = facts[p]
        if rule == "SCENE-KILLER":
            lines.append("       because the killer must have been at the scene")
        elif rule == "SCENE-ALONE":
            lines.append("       because the killer was alone with the victim")
        else:
            for q in prem:
                if q[0] == "said":
                    lines.append("       because " + describe(q))
    return lines


def refute(pub, stmts, hyp):
    """Try to show 'hyp is NOT the killer'. Returns explanation lines or None."""
    facts, contras = fc_run(pub, stmts, hyp)
    if not contras:
        return None
    best = min(contras, key=lambda c: len(explain(facts, c)))
    return explain(facts, best)


#backward chaining
def prove_guilty(pub, stmts, goal):
    """BACKWARD CHAINING.
         goal:      guilty(X)
         sub-goals: for every other suspect Y,  refuted(Y)
         refuted(Y) is proven by FORWARD chaining under the hypothesis guilty(Y) until a contradiction appears.
       Returns (proved?, [(Y, explanation lines or None), ...])"""
    steps, ok = [], True
    for y in pub[2]:
        if y == goal:
            continue
        why = refute(pub, stmts, y)
        steps.append((y, why))
        ok = ok and why is not None
    return ok, steps


#case generator
class Case:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    @property
    def pub(self):
        return (self.T, self.R, tuple(self.names))

    def profile(self, name):
        return next(p for p in self.profiles if p.name == name)

    def answer(self, name, slot):
        return self.pool[(name, slot)]

    def inspect(self, room):
        return [(w, "missing" if w == self.weapon else "in place")
                for w, (_, home) in WEAPONS.items() if home == room]

    def is_lie(self, name, slot):
        return (name, slot) in self.lies

    def timeline(self):
        return {n: [self.loc[(n, t)] for t in range(len(SLOTS))] for n in self.names}


def _walk(rng):
    path = [rng.choice(ROOMS)]
    for _ in range(len(SLOTS) - 1):
        path.append(path[-1] if rng.random() < 0.35 else rng.choice(sorted(ADJ[path[-1]])))
    return path


def minimal_solving_set(pub, stmts, target, rng):
    """Greedy shrink: smallest set of statements that still points only at the killer."""
    cur = list(stmts)
    order = cur[:]
    rng.shuffle(order)
    for s in order:
        trial = [x for x in cur if x != s]
        if candidates_from(pub, trial) == [target]:
            cur = trial
    return cur


def generate_case(seed=None, k_range=(3, 6), max_tries=20000):
    rng = random.Random(seed)
    for _ in range(max_tries):
        profiles = rng.sample(POOL, 5)
        names = [p.name for p in profiles]
        killer, T, R = rng.choice(names), rng.choice([1, 2]), rng.choice(ROOMS)
        loc = {}
        for n in names:
            for t, r in enumerate(_walk(rng)):
                loc[(n, t)] = r
        if loc[(killer, T)] != R or any(loc[(n, T)] == R for n in names if n != killer):
            continue

        pool = {}
        for n in names:
            for t in range(len(SLOTS)):
                room = loc[(n, t)]
                comp = frozenset(o for o in names if o != n and loc[(o, t)] == room)
                pool[(n, t)] = Stmt(n, t, room, comp)

        # the killer's lie at the murder hour: must not contradict his OWN other statements
        options = [r for r in ROOMS if r != R
                   and (T == 0 or DIST[loc[(killer, T - 1)]][r] <= 1)
                   and (T == len(SLOTS) - 1 or DIST[r][loc[(killer, T + 1)]] <= 1)]
        if not options:
            continue
        fake_room = rng.choice(options)
        others = [n for n in names if n != killer]
        fake_comp = frozenset([rng.choice(others)]) if rng.random() < 0.6 else frozenset()
        pool[(killer, T)] = Stmt(killer, T, fake_room, fake_comp)

        pub = (T, R, tuple(names))
        stmts = list(pool.values())
        if candidates_from(pub, stmts) != [killer]:
            continue                                   # not uniquely solvable -> reject
        core = minimal_solving_set(pub, stmts, killer, rng)
        if not (k_range[0] <= len(core) <= k_range[1]):
            continue                                   # too easy or too hard -> reject

        wound = rng.choice(["blunt", "sharp"])
        weapon = rng.choice([w for w, (ty, _) in WEAPONS.items() if ty == wound])
        return Case(seed=seed, profiles=profiles, names=names, killer=killer, T=T, R=R,
                    loc=loc, pool=pool, lies={(killer, T)}, wound=wound, weapon=weapon,
                    core=core)
    raise RuntimeError("could not generate a case")


#investigator
class Investigator:
    """Everything ONE detective (human or AI) has learned so far."""

    def __init__(self, case, ap):
        self.case, self.ap, self.used = case, ap, 0
        self.stmts, self.answers = [], {}
        self.inspected, self.weapon_status = {}, {}
        self.conflicts = []                   # (older stmt, newer stmt, contradiction fact)
        self._cache = {}
        self.out = False

    def remaining(self):
        return max(0, self.ap - self.used)

    def interrogate(self, name, slot):
        s = self.case.answer(name, slot)
        self.used += 1
        self.answers[(name, slot)] = s
        for old in self.stmts:
            _, cs = fc_run(self.case.pub, [old, s], None)
            if cs:
                self.conflicts.append((old, s, cs[0]))
        self.stmts.append(s)
        return s

    def inspect(self, room):
        res = self.case.inspect(room)
        self.used += 1
        self.inspected[room] = res
        for w, st in res:
            self.weapon_status[w] = st
        return res

    def candidates(self):
        k = len(self.stmts)
        if k not in self._cache:
            self._cache[k] = candidates_from(self.case.pub, self.stmts)
        return self._cache[k]

    def weapon_candidates(self):
        pool = [w for w, (ty, _) in WEAPONS.items() if ty == self.case.wound]
        missing = [w for w in pool if self.weapon_status.get(w) == "missing"]
        if missing:
            return missing
        return [w for w in pool if self.weapon_status.get(w) != "in place"]

    def hearsay(self):
        """cells nobody has asked yet, but someone mentioned: (name, slot) -> [(speaker, room)]"""
        h = {}
        for s in self.stmts:
            for c in s.comp:
                if (c, s.slot) not in self.answers:
                    h.setdefault((c, s.slot), []).append((s.speaker, s.room))
        return h

    def conflicted_people(self):
        out = set()
        for a, b, _ in self.conflicts:
            out |= {a.speaker, b.speaker} | set(a.comp) | set(b.comp)
        return out


#rival AI
def rival_choose(inv, rng):
    """Greedy best-first policy.
       1. certain about killer?  -> examine the weapon, then accuse
       2. otherwise ask the question with the best heuristic score:
            + importance of the time slot (murder hour matters most)
            + CROSS-CHECK bonus  (someone mentioned this person: verify their story)
            + suspect bonus      (still a candidate)
            + conflict bonus     (already tangled in a contradiction)"""
    case = inv.case
    T, names = case.T, case.names
    cands, wc, left = inv.candidates(), inv.weapon_candidates(), inv.remaining()

    if len(cands) == 1 and len(wc) == 1:
        return ("accuse", cands[0], wc[0])
    if left <= 0:
        return ("accuse", rng.choice(cands), rng.choice(wc))
    if (len(cands) == 1 or left <= 2) and len(wc) > 1:
        homes = {}
        for w in wc:
            h = WEAPONS[w][1]
            if h not in inv.inspected:
                homes[h] = homes.get(h, 0) + 1
        if homes:
            return ("inspect", max(homes, key=lambda h: (homes[h], rng.random())))

    hear, tangled = inv.hearsay(), inv.conflicted_people()
    best, best_score = None, -1
    for n in names:
        for t in range(len(SLOTS)):
            if (n, t) in inv.answers:
                continue
            score = {0: 1.0, 1: 2.0, 2: 1.0}.get(abs(t - T), 0.5) + (2.0 if t == T else 0.0)
            score += 4.0 if (n, t) in hear else 0.0
            score += 1.5 if n in cands else 0.0
            score += 1.0 if n in tangled else 0.0
            score += rng.random() * 0.3
            if score > best_score:
                best, best_score = (n, t), score
    return ("ask", best[0], best[1])


def run_rival_alone(case, ap=40, seed=0):
    """Play the rival by itself. Returns (actions used, correct accusation?)."""
    rng = random.Random(seed)
    inv = Investigator(case, ap)
    while True:
        move = rival_choose(inv, rng)
        if move[0] == "ask":
            inv.interrogate(move[1], move[2])
        elif move[0] == "inspect":
            inv.inspect(move[1])
        else:
            return inv.used, (move[1] == case.killer and move[2] == case.weapon)


#self-test
def selftest(n=60):
    print(f"Generating {n} cases and checking them...")
    ks, solved, rounds = [], 0, []
    for seed in range(n):
        c = generate_case(seed)
        assert candidates_from(c.pub, list(c.pool.values())) == [c.killer], "not unique!"
        # soundness: with only TRUE statements the killer is never ruled out
        ks.append(len(c.core))
        used, ok = run_rival_alone(c, ap=40, seed=seed)
        rounds.append(used)
        solved += ok
    print(f"  every case has exactly one valid killer: OK")
    print(f"  statements really needed to crack a case: min {min(ks)}, avg {sum(ks)/len(ks):.1f}, max {max(ks)}")
    rounds.sort()
    print(f"  Rival AI solves {solved}/{n} correctly; actions needed: "
          f"median {rounds[len(rounds)//2]}, 90th pct {rounds[int(len(rounds)*.9)]}, max {rounds[-1]}")
    c = generate_case(7)
    print(f"\nDemo case #7: {c.killer} killed {VICTIM} at {SLOTS[c.T]} in the {c.R} with the {c.weapon}.")
    print("The killer lied:", c.answer(c.killer, c.T).text(), " (truth: in the", c.R + ")")
    ok, steps = prove_guilty(c.pub, list(c.pool.values()), c.killer)
    print(f"\nBACKWARD CHAINING proof that {c.killer} did it (proved={ok}):")
    for y, why in steps:
        print(f"  Refute {y}:")
        for line in why[:4]:
            print("     ", line)


if __name__ == "__main__":
    selftest(int(sys.argv[1]) if len(sys.argv) > 1 else 60)
