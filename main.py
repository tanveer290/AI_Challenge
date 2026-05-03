from fastapi import FastAPI, Request
from context_store import context_store
from signal_engine import extract_signals
from decision_engine import decide_action
from composer_finalist import compose_final
from conversation_engine import handle_reply
import time

app = FastAPI()
START_TIME = time.time()


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
    actions = []

    for trigger_id in trigger_ids:
        trigger = context_store.get("trigger", trigger_id)
        if not trigger:
            continue

        merchant_id = trigger.get("merchant_id") or trigger.get("merchant")
        customer_id = trigger.get("customer_id") or trigger.get("customer")
        if not merchant_id:
            continue

        context = context_store.get_full_context(merchant_id, trigger_id, customer_id)
        if not context:
            continue

        category = context.get("category") or {}
        merchant = context.get("merchant") or {}
        customer = context.get("customer") or None

        signals = extract_signals(category, merchant, trigger, customer)
        action, scores = decide_action(signals)
        message = compose_final(signals, action)

        actions.append({
            "conversation_id": f"conv_{trigger_id}",
            "merchant_id": merchant_id,
            "customer_id": customer_id,
            "send_as": message["send_as"],
            "trigger_id": trigger_id,
            "body": message["body"],
            "cta": message["cta"],
            "rationale": message["rationale"],
        })



    return {"actions": actions[:5]}


@app.post("/v1/reply")
async def reply(request: Request):
    data = await request.json()
    msg = data.get("message", "")
    return handle_reply(msg)
