from fastapi import FastAPI, Request
from context_store import context_store
from signal_engine import extract_signals
from decision_engine import decide_action
from composer_finalist import compose_final
from conversation_engine import handle_reply
import time

app = FastAPI()
START_TIME = time.time()

# 🔥 suppression memory (per test run)
sent_suppression_keys = set()


@app.get("/v1/healthz")
def healthz():
    return {
        "status": "ok",
        "uptime_seconds": int(time.time() - START_TIME),
        "contexts_loaded": context_store.counts() if hasattr(context_store, "counts") else {}
    }


@app.get("/v1/metadata")
def metadata():
    return {
        "team_name": "Your Team",
        "team_members": [],
        "model": "rule + context composer",
        "approach": "minimal-context composer with trigger-family routing",
        "contact_email": "",
        "version": "1.0.0",
        "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(START_TIME)),
    }


@app.post("/v1/context")
async def update_context(request: Request):
    data = await request.json()
    scope = data["scope"]
    context_id = data["context_id"]
    payload = data["payload"]
    version = data.get("version", 1)

    ok, msg = context_store.update(scope, context_id, payload, version)

    return {
        "accepted": ok,
        "reason": msg
    }


@app.post("/v1/tick")
async def tick(request: Request):
    data = await request.json()

    trigger_ids = data.get("available_triggers", [])
    now = data.get("now")  # 🔥 important for time-aware logic

    actions = []

    for trigger_id in trigger_ids:
        trigger = context_store.get("trigger", trigger_id)
        if not trigger:
            continue

        merchant_id = trigger.get("merchant_id") or trigger.get("merchant")
        customer_id = trigger.get("customer_id") or trigger.get("customer")

        if not merchant_id:
            continue

        # 🔥 suppression handling
        suppression_key = trigger.get("suppression_key")
        if suppression_key and suppression_key in sent_suppression_keys:
            continue

        context = context_store.get_full_context(merchant_id, trigger_id, customer_id)
        if not context:
            continue

        category = context.get("category") or {}
        merchant = context.get("merchant") or {}
        customer = context.get("customer") or None

        signals = extract_signals(category, merchant, trigger, customer)
        signals["now"] = now  # 🔥 pass time context

        action, scores = decide_action(signals)
        message = compose_final(signals, action)

        # 🔥 safe guards (avoid judge penalties)
        body = message.get("body", "").strip()
        if not body:
            continue

        if len(body) < 60:  # avoid low-specificity spam
            continue

        # 🔍 DEBUG PRINT
        print("\n" + "=" * 80)
        print(f"TRIGGER: {trigger_id}")
        print(f"ACTION: {action}")
        print("-" * 80)
        print(body)
        print("=" * 80 + "\n")

        # 🔥 mark suppression used
        if suppression_key:
            sent_suppression_keys.add(suppression_key)

        # 🔥 improved conversation id
        conversation_id = f"conv_{merchant_id}_{signals.get('trigger_kind')}_{trigger_id}"

        actions.append({
            "conversation_id": conversation_id,
            "merchant_id": merchant_id,
            "customer_id": customer_id,
            "send_as": message.get("send_as", "vera"),
            "trigger_id": trigger_id,

            # 🔥 optional but improves judge alignment
            "template_name": f"{action}_v1",
            "template_params": [
                signals.get("owner_first_name"),
                signals.get("best_offer"),
                signals.get("trigger_kind")
            ],
            "suppression_key": suppression_key or "",

            "body": body,
            "cta": message.get("cta", "open_ended"),
            "rationale": message.get("rationale", ""),
        })

        # 🔥 safety cap (judge max = 20)
        if len(actions) >= 10:
            break

    return {"actions": actions}


@app.post("/v1/reply")
async def reply(request: Request):
    data = await request.json()
    msg = data.get("message", "")

    return handle_reply(msg)