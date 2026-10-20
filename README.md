
# 🕵️ The Haveli Mystery: Neuro-Symbolic AI Detective Engine

An interactive, logic-driven murder mystery engine where a human detective races against an autonomous AI inspector (**Inspector Wasim**) to solve a procedurally generated case before running out of action points.

Built using a **Neuro-Symbolic Architecture**, the project combines the mathematical precision of classical symbolic logic (Expert Systems, Forward/Backward Chaining) with the natural language flexibility of Large Language Models (LLMs) under strict fact-validation guardrails.

---

## 🌟 Key Features & AI Concepts

- **Neuro-Symbolic Architecture:** A pure separation of concerns—the Symbolic Logic Engine owns 100% of the ground truth facts, while the Generative LLM acts strictly as a natural language voice wrapper.
- **Expert System & Knowledge Representation:** Stores structured facts as tuples with built-in justification tracking for full Explainable AI (XAI) transparency.
- **Forward Chaining (Inference Engine):** Iteratively derives facts and catches physical contradictions (e.g., suspects placed in two rooms simultaneously or traveling faster than graph limits allow).
- **Backward Chaining (Goal-Driven Proof):** Mathematically proves a suspect's guilt by systematically refuting every alternative hypothesis via proof-by-contradiction.
- **Graph BFS Search:** Computes exact room-to-room shortest paths on a spatial house graph to enforce movement constraints across time slots.
- **Autonomous Greedy Agent:** The rival AI detective employs a **Greedy Best-First Search** heuristic policy to query the most informative unasked alibis under an action budget.
- **Zero-Hallucination Guardrail:** Every LLM response is symbolically parsed (`validate_line`) before display. If the LLM alters time, room, or companions present, it is discarded in favor of a safe symbolic template.

---

## 🛠️ System Architecture


```

+-------------------------------------------------------+
|                   GUI CLIENT                          |
|                 (Tkinter Interface)                   |
+--------------------------+----------------------------+
|
v
+-------------------------------------------------------+
|                SYMBOLIC LOGIC ENGINE                  |
|  - World Model (Room Graph & Distance via BFS)        |
|  - Forward Chaining (Fact derivation & Clash detection)|
|  - Backward Chaining (Sub-goal proof generation)      |
|  - Greedy Search Policy (Rival AI Agent)              |
+--------------------------+----------------------------+
|
v
+-------------------------------------------------------+
|               LLM STORYTELLER LAYER                   |
|  - Prompt Formatter (Suspect personalities)           |
|  - Symbolic Validator (Rejects hallucinations)        |
+-------------------------------------------------------+

```

---

## 🚀 Quickstart & Running Locally

### Requirements
- Python 3.8+
- Tkinter (pre-installed with standard Python / Anaconda distributions)

### 1. Run Logic Self-Test & Benchmark
```bash
python engine.py

```

### 2. Launch the Interactive GUI

```bash
python murder_mystery.py

```

---

## 📊 Empirical Performance & Benchmarks

Tested across 150 procedurally generated test cases:

* **Case Generation:** 100% uniquely solvable cases (~22ms generation time per case).
* **Engine Accuracy:** 0% false-positive eliminations across all benchmark runs.
* **Agent Efficiency:** The full greedy heuristic solves cases in an average of **6.6 actions** (compared to 14.3 actions for random questioning).

---

## 📄 License

This project is open-source and available under the [MIT License](https://www.google.com/search?q=LICENSE).


