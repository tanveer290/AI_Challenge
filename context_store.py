# context_store.py

from typing import Dict, Any
from datetime import datetime


class ContextStore:
    def __init__(self):
        self.store: Dict[str, Dict[str, Any]] = {}
        self.versions: Dict[str, int] = {}

    def update(self, scope: str, context_id: str, payload: dict, version: int):
        key = f"{scope}:{context_id}"

        current_version = self.versions.get(key)

        # ✅ idempotent handling (IMPORTANT)
        if current_version is not None:
            if version < current_version:
                return False, "stale_version"
            elif version == current_version:
                return True, "no_op"

        self.versions[key] = version

        self.store[key] = {
            "payload": payload,
            "version": version,
            "updated_at": datetime.utcnow().isoformat()
        }

        return True, "stored"

    def get(self, scope, context_id):
        key = f"{scope}:{context_id}"
        item = self.store.get(key)
        return item["payload"] if item else None

    def get_full_context(self, merchant_id, trigger_id, customer_id=None):
        merchant = self.get("merchant", merchant_id)
        if not merchant:
            return None

        category = self.get("category", merchant["category_slug"])
        trigger = self.get("trigger", trigger_id)
        customer = self.get("customer", customer_id) if customer_id else None

        return {
            "category": category,
            "merchant": merchant,
            "trigger": trigger,
            "customer": customer
        }


context_store = ContextStore()