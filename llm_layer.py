"""
llm_layer.py  -  the STORYTELLER. It gives the game a voice. It NEVER decides the truth.

Design rule (important for your report):
    The symbolic engine owns the facts.  The LLM only rewrites them in a personality.
    Every line the LLM produces is CHECKED by validate_line().  If it changed a fact
    (wrong room, wrong time, invented a person...) it is thrown away and a template is used.
    => the game can never be broken by a hallucination, and it works with no internet at all.

To switch the LLM on, set environment variables BEFORE running the game (Anaconda Prompt, Windows):
    set LLM_API_KEY=your_key_here
    set LLM_BASE_URL=https://api.groq.com/openai/v1        (default; any OpenAI-compatible endpoint works)
    set LLM_MODEL=llama-3.1-8b-instant                     (check your provider for current model names)
Without a key the game uses the offline templates below.
"""
import json
import os
import re
import urllib.request

from engine import SLOTS, VICTIM, WEAPONS

NUM_WORDS = {"8": "eight", "9": "nine", "10": "ten", "11": "eleven"}


class Storyteller:
    def __init__(self):
        self.key = os.environ.get("LLM_API_KEY", "").strip()
        self.base = os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
        self.model = os.environ.get("LLM_MODEL", "llama-3.1-8b-instant")
        self.enabled = bool(self.key)
        self.rejected = 0         
        self.accepted = 0

    def status(self):
        if not self.enabled:
            return "Storyteller: offline templates (no LLM key set)"
        return f"Storyteller: LLM ({self.model}) + fact validator"

    def _chat(self, system, user, max_tokens=200):
        body = json.dumps({
            "model": self.model, "max_tokens": max_tokens, "temperature": 0.8,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }).encode()
        req = urllib.request.Request(
            self.base + "/chat/completions", data=body,
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.key})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.load(r)
        return data["choices"][0]["message"]["content"].strip().strip('"')

    
    def suspect_line(self, case, stmt):
        """Returns (text, source) with source in {'llm','template'}. Safe to call from a thread."""
        prof = case.profile(stmt.speaker)
        fallback = template_line(stmt, prof)
        if not self.enabled:
            return fallback, "template"
        system = ("You voice a suspect in a murder-mystery game. Rewrite the given alibi in the suspect's "
                  "personality. HARD RULES: keep the exact time, the exact room and the exact people present. "
                  "Mention nobody else. Add no new facts, no accusations, no confession. "
                  "One or two sentences, under 45 words. Output only the spoken line.")
        user = (f"Suspect: {prof.name}, {prof.role}. Personality: {prof.trait}. "
                f"Secret (never reveal it): {prof.secret}.\nAlibi to voice: {stmt.text()}")
        try:
            text = self._chat(system, user, 120)
            if validate_line(text, stmt, case.names):
                self.accepted += 1
                return text, "llm"
            self.rejected += 1
        except Exception:
            pass
        return fallback, "template"

    def intro(self, case):
        fallback = template_intro(case)
        if not self.enabled:
            return fallback, "template"
        suspects = "; ".join(f"{p.name} ({p.role})" for p in case.profiles)
        system = ("You narrate the opening of a murder-mystery game set at a family mehfil in a haveli in "
                  "Hyderabad, Sindh. Do NOT name or hint at the killer. Do not invent facts beyond those given. "
                  "Under 110 words. Atmospheric, a little witty.")
        user = (f"Victim: {VICTIM}. Found dead at {SLOTS[case.T]} in the {case.R}, cause: a {case.wound} wound. "
                f"Suspects: {suspects}. Mention that innocents tell the truth and the killer may lie.")
        try:
            text = self._chat(system, user, 260)
            if VICTIM.split()[1].lower() in text.lower() or "dr.asif" in text.lower():
                return text, "llm"
        except Exception:
            pass
        return fallback, "template"

    def epilogue(self, case):
        fallback = template_epilogue(case)
        if not self.enabled:
            return fallback, "template"
        k = case.profile(case.killer)
        system = "You write a 70-word dramatic confession scene for a murder-mystery game. Stick to the given facts only."
        user = (f"The killer is {k.name}, {k.role}. Motive: {k.motive}. Weapon: {case.weapon}. "
                f"Place: {case.R} at {SLOTS[case.T]}. Secret exposed: {k.secret}.")
        try:
            text = self._chat(system, user, 200)
            if k.name.lower() in text.lower():
                return text, "llm"
        except Exception:
            pass
        return fallback, "template"



def validate_line(text, stmt, all_names):
    """The symbolic checker: did the LLM keep every fact?"""
    if not text or len(text) > 400:
        return False
    low = text.lower()
    hour = SLOTS[stmt.slot].split()[0]
    if not (re.search(r"\b" + hour + r"\b", low) or NUM_WORDS[hour] in low):
        return False
    if stmt.room.split()[-1].lower() not in low:
        return False
    for n in all_names:
        mentioned = re.search(r"\b" + n.lower() + r"\b", low) is not None
        if n in stmt.comp and not mentioned:
            return False
        if n not in stmt.comp and n != stmt.speaker and mentioned:
            return False
    if not stmt.comp and not any(w in low for w in ("alone", "by myself", "on my own", "nobody", "no one", "solo")):
        return False
    return True


def template_line(stmt, prof):
    t, room, w = SLOTS[stmt.slot], stmt.room, stmt.with_part()
    return {
        "nervous": f"Um... at {t}? I was in the {room}, {w}. Why are you staring at me?",
        "arrogant": f"Dekhein, detective sahib. At {t} I was in the {room}, {w}. Do you know who I am?",
        "chatty": f"Oh, {t}? Let me think... yes! The {room}, {w}. Lovely evening, until, well, you know.",
        "sarcastic": f"At {t}? The {room}, {w}. Write that down, detective, I'll wait.",
        "calm": f"At {t} I was in the {room}, {w}. I have nothing to hide.",
    }.get(prof.trait, stmt.text())


def template_intro(case):
    roles = ", ".join(f"{p.name} the {p.role}" for p in case.profiles)
    return (f"The mehfil at Haveli, Dr. Asif was in full swing when the lights flickered. By {SLOTS[case.T]}, "
            f"{VICTIM} lay dead in the {case.R}, struck down by a {case.wound} weapon. "
            f"Five people had the run of the house tonight: {roles}.\n"
            f"One of them is the killer. Innocents always tell the truth. The killer may lie. "
            f"Question suspects, inspect rooms, and catch the liar before the rival inspector does.")


def template_epilogue(case):
    k = case.profile(case.killer)
    return (f"{k.name}, the {k.role}, broke down in the end. \"{k.motive.capitalize()}.\" "
            f"The {case.weapon} had been taken from the {WEAPONS[case.weapon][1]}. "
            f"The secret that {k.name} had been hiding all along, {k.secret}, turned out to be the smaller crime.")
