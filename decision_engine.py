STRICT_MAP = {
    "research_digest":          "insight_share",
    "perf_dip":                 "performance_fix",
    "seasonal_perf_dip":        "performance_fix",
    "perf_spike":               "perf_spike",
    "ipl_match_today":          "seasonal_push",
    "recall_due":               "customer_recall",
    "chronic_refill_due":       "customer_recall",
    "trial_followup":           "customer_recall",
    "appointment_tomorrow":     "customer_recall",
    "renewal_due":              "renewal_nudge",
    "gbp_unverified":           "compliance_nudge",
    "compliance_alert":         "compliance_nudge",
    "regulation_change":        "compliance_nudge",
    "supply_alert":             "compliance_nudge",
    "competitor_opened":        "competitor_alert",
    "review_theme_emerged":     "reputation_fix",
    "active_planning_intent":   "planning_assist",
    "bridal_followup":          "planning_assist",
    "wedding_package_followup": "planning_assist",
    "festival_upcoming":        "seasonal_push",
    "weather_heatwave":         "seasonal_push",
    "category_seasonal":        "seasonal_push",
    "cde_opportunity":          "cde_opportunity",
    "cde":                      "cde_opportunity",
    "targeted_offer":           "targeted_offer",
    "retention_push":           "retention_push",
    "dormant_with_vera":        "dormant_nudge",
    "customer_lapsed_soft":     "winback",
    "customer_lapsed_hard":     "winback",
    "winback_eligible":         "winback",
    "winback":                  "winback",
    "milestone_reached":        "insight_share",
    "curious_ask_due":          "curious_ask",
    "unplanned_slot_open":      "targeted_offer",
}


def _safe_str(v, default=""):
    if v in (None, "", [], {}):
        return default
    try:
        s = str(v)
        return s if s.strip() else default
    except Exception:
        return default


def _safe_int(v, default=None):
    if v in (None, "", [], {}):
        return default
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _override(action):
    return action, {action: 100}


def decide_action(signals):
    signals = signals or {}
    trigger = _safe_str(signals.get("trigger_kind")).strip()

    if trigger in STRICT_MAP:
        return _override(STRICT_MAP[trigger])

    scores = {
        "insight_share":    0,
        "performance_fix":  0,
        "targeted_offer":   0,
        "retention_push":   0,
        "winback":          0,
        "customer_recall":  0,
        "renewal_nudge":    0,
        "compliance_nudge": 0,
        "planning_assist":  0,
        "reputation_fix":   0,
        "seasonal_push":    0,
        "cde_opportunity":  0,
        "dormant_nudge":    0,
        "perf_spike":       0,
        "competitor_alert": 0,
        "curious_ask":      0,
    }

    if signals.get("research_title"):
        scores["insight_share"] += 5
    if signals.get("is_low_performing") or signals.get("ctr_below_peer"):
        scores["performance_fix"] += 5
    perf_delta = signals.get("perf_delta_pct")
    if perf_delta is not None:
        try:
            scores["performance_fix" if float(perf_delta) < 0 else "perf_spike"] += 4
        except (TypeError, ValueError):
            pass
    if not signals.get("has_active_offer"):
        scores["targeted_offer"] += 3
    if _safe_str(signals.get("customer_state")).lower() in {"lapsed_soft", "lapsed", "lapsed_hard"}:
        scores["winback"] += 6
    if signals.get("due_date") or signals.get("service_due"):
        scores["customer_recall"] += 6
    days_left = _safe_int(signals.get("subscription_days_remaining"), 999)
    if days_left is not None and days_left <= 15:
        scores["renewal_nudge"] += 6
    if signals.get("regulation_title"):
        scores["compliance_nudge"] += 6
    if signals.get("planning_goal"):
        scores["planning_assist"] += 6
    if signals.get("review_theme"):
        scores["reputation_fix"] += 5
    if signals.get("festival_name") or signals.get("weather_event"):
        scores["seasonal_push"] += 5
    if signals.get("cde_title"):
        scores["cde_opportunity"] += 5
    if signals.get("days_since_last_merchant_message") is not None:
        scores["dormant_nudge"] += 6
    if signals.get("competitor_name"):
        scores["competitor_alert"] += 6
    if signals.get("ask_template"):
        scores["curious_ask"] += 7
    ret = signals.get("retention_pct")
    peer_ret = signals.get("peer_retention_pct")
    if ret is not None and peer_ret is not None:
        try:
            if float(ret) < float(peer_ret):
                scores["retention_push"] += 4
        except (TypeError, ValueError):
            pass
    if _safe_int(signals.get("lapsed_customers"), 0) > 0:
        scores["retention_push"] += 2
    if _safe_int(signals.get("high_risk_patients"), 0) > 0 and trigger == "research_digest":
        scores["insight_share"] += 2

    best_action = max(scores, key=scores.get)
    return best_action, scores