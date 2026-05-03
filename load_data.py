# load_data.py

import json
import requests
import os

BASE_URL = "http://127.0.0.1:8000"

DATASET_PATH = r"C:\Users\mdtan\Downloads\magicpin-ai-challenge\expanded(1)"

CATEGORY_PATH = os.path.join(DATASET_PATH, "categories")
MERCHANT_PATH = os.path.join(DATASET_PATH, "merchants")
CUSTOMER_PATH = os.path.join(DATASET_PATH, "customers")
TRIGGER_PATH = os.path.join(DATASET_PATH, "triggers")


# -------------------------------
# SAFE PUSH
# -------------------------------
def push_context(scope, context_id, payload):
    try:
        url = f"{BASE_URL}/v1/context"

        data = {
            "scope": scope,
            "context_id": context_id,
            "version": 1,
            "payload": payload
        }

        r = requests.post(url, json=data, timeout=5)

        try:
            resp = r.json()
        except:
            resp = {"error": "invalid json response"}

        print(scope, context_id, resp)

    except Exception as e:
        print(f"[ERROR] {scope} {context_id}: {e}")


# -------------------------------
# SAFE JSON LOAD
# -------------------------------
def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] loading {path}: {e}")
        return None


# -------------------------------
# MAIN LOAD FUNCTION
# -------------------------------
def load_all():

    # -------------------------------
    # CATEGORIES
    # -------------------------------
    for file in os.listdir(CATEGORY_PATH):
        path = os.path.join(CATEGORY_PATH, file)
        data = load_json(path)

        if data and "slug" in data:
            push_context("category", data["slug"], data)

    # -------------------------------
    # MERCHANTS (EXPANDED)
    # -------------------------------
    for file in os.listdir(MERCHANT_PATH):
        path = os.path.join(MERCHANT_PATH, file)
        m = load_json(path)

        if m and "merchant_id" in m:
            push_context("merchant", m["merchant_id"], m)

    # -------------------------------
    # CUSTOMERS (EXPANDED)
    # -------------------------------
    for file in os.listdir(CUSTOMER_PATH):
        path = os.path.join(CUSTOMER_PATH, file)
        c = load_json(path)

        if c and "customer_id" in c:
            push_context("customer", c["customer_id"], c)

    # -------------------------------
    # TRIGGERS (EXPANDED)
    # -------------------------------
    for file in os.listdir(TRIGGER_PATH):
        path = os.path.join(TRIGGER_PATH, file)
        t = load_json(path)

        if t and "id" in t:
            push_context("trigger", t["id"], t)


# -------------------------------
# RUN
# -------------------------------
if __name__ == "__main__":
    load_all()