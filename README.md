# Vera Bot — AI Challenge

A rule-based WhatsApp merchant assistant that composes context-aware messages
using signal extraction, trigger routing, and template composition —
**no LLM required**.

---

## Folder Structure

```
vera-bot/
│
├── main.py                  ← FastAPI bot (start this first)
├── context_store.py         ← In-memory context store with versioning
├── signal_engine.py         ← Extracts signals from category/merchant/trigger/customer
├── decision_engine.py       ← Routes trigger kind → action family
├── composer_finalist.py     ← Composes final WhatsApp message from signals
├── conversation_engine.py   ← Handles merchant replies (auto-reply, opt-out, intent)
├── load_data.py             ← Pushes expanded dataset into the bot
├── judge_simulator.py       ← Judge script (challenge bundle)
└── requirements.txt         ← Python dependencies
```

---

## How It Works

```
load_data.py
    │
    └─▶ POST /v1/context  (pushes all categories, merchants, customers, triggers)
                │
                ▼
         context_store.py  (stores everything in memory)
                │
judge_simulator.py
    │
    └─▶ POST /v1/tick
              │
              ▼
         signal_engine.py       (extract signals from context)
              │
              ▼
         decision_engine.py     (decide action: perf_fix, winback, recall, etc.)
              │
              ▼
         composer_finalist.py   (compose WhatsApp message from signals)
              │
              ▼
         {"body": "...", "cta": "...", "send_as": "vera"}
              │
              ▼
    └─▶ POST /v1/reply
              │
              ▼
         conversation_engine.py (detect intent, handle auto-reply, opt-out)
```

---

## Quick Command Reference

| What | Command |
|------|---------|
| Install deps | `pip install -r requirements.txt` |
| Start bot | `python main.py` |
| Load data | `python load_data.py` |
| Run judge | `python judge_simulator.py` |
| Check bot health | `curl http://127.0.0.1:8080/v1/healthz` |

---


## Architecture Notes

- **No LLM calls** — messages are composed entirely from rules and templates
- **Idempotent context store** — re-pushing the same data is safe (returns `no_op`)
- **Suppression** — same trigger won't fire twice in one session
- **Flat structure** — all files in one folder, no subpackages


