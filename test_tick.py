# test_tick.py

import requests
import json
import os

BASE_URL = "http://127.0.0.1:8000"
DATASET_PATH = r"C:\Users\mdtan\Downloads\magicpin-ai-challenge\dataset"


# -------------------------------
# LOAD JSON SAFELY
# -------------------------------
def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR loading file]: {e}")
        return None


# -------------------------------
# EXTRACT TRIGGER IDS (ROBUST)
# -------------------------------
def extract_trigger_ids(data):
    ids = []

    if not data:
        return ids

    # Case 1: list
    if isinstance(data, list):
        for t in data:
            if isinstance(t, dict):
                if "trigger_id" in t:
                    ids.append(t["trigger_id"])
                elif "id" in t:
                    ids.append(t["id"])

    # Case 2: dict
    elif isinstance(data, dict):

        # nested under "triggers"
        if "triggers" in data:
            return extract_trigger_ids(data["triggers"])

        # scan all keys
        for k, v in data.items():
            if isinstance(v, dict):
                if "trigger_id" in v:
                    ids.append(v["trigger_id"])
                elif "id" in v:
                    ids.append(v["id"])

    return ids

# -------------------------------
# MAIN TEST
# -------------------------------
def main():
    print("\n--- LOADING TRIGGERS ---")

    trigger_file = os.path.join(DATASET_PATH, "triggers_seed.json")
    trigger_data = load_json(trigger_file)

    if not trigger_data:
        print("No trigger data found ❌")
        return

    # DEBUG (important)
    print("Trigger data type:", type(trigger_data))

    trigger_ids = extract_trigger_ids(trigger_data)

    if not trigger_ids:
        print("No trigger_ids extracted ❌")
        print("Sample data:", str(trigger_data)[:300])
        return

    # take first few triggers
    trigger_ids = trigger_ids[:5]

    print("Testing triggers:", trigger_ids)

    # -------------------------------
    # CALL API
    # -------------------------------
    url = f"{BASE_URL}/v1/tick"

    try:
        response = requests.post(url, json={
            "available_triggers": trigger_ids
        }, timeout=5)

        result = response.json()

    except Exception as e:
        print(f"[API ERROR]: {e}")
        return

    # -------------------------------
    # PRINT OUTPUT
    # -------------------------------
    print("\n=== OUTPUT ===\n")
    print(json.dumps(result, indent=2))


# -------------------------------
# RUN
# -------------------------------
if __name__ == "__main__":
    main()