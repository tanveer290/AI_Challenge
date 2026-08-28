def _s(v, default=""):
    if v in (None, "", [], {}):
        return default
    try:
        s = str(v)
        return s if s.strip() else default
    except Exception:
        return default


def _n(v, default=None):
    if v in (None, "", [], {}):
        return default
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _f(v, default=None):
    if v in (None, "", [], {}):
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _pct(v, default=None):
    x = _f(v, default=None)
    if x is None:
        return default
    return round(x * 100, 1) if abs(x) <= 1.5 else round(x, 1)


def _first(*vals, default=None):
    for v in vals:
        if v not in (None, "", [], {}):
            return v
    return default


def _format_slots(slots):
    if not slots or not isinstance(slots, list):
        return ""
    labels = []
    for s in slots[:3]:
        if isinstance(s, dict):
            label = s.get("label") or s.get("time") or s.get("iso") or ""
            if label:
                labels.append(str(label))
        elif isinstance(s, str) and s:
            labels.append(s)
    return " / ".join(labels)


def _find_digest_item(digest, item_id):
    if not digest or not item_id or not isinstance(digest, list):
        return None
    for item in digest:
        if isinstance(item, dict) and item.get("id") == item_id:
            return item
    return None


def _safe_dict(v):
    return v if isinstance(v, dict) else {}


def _safe_list(v):
    return v if isinstance(v, list) else []


def extract_signals(category, merchant, trigger, customer=None):
    signals = {}

    category  = _safe_dict(category)
    merchant  = _safe_dict(merchant)
    trigger   = _safe_dict(trigger)
    customer  = _safe_dict(customer or {})

    identity       = _safe_dict(merchant.get("identity"))
    perf           = _safe_dict(merchant.get("performance"))
    peer           = _safe_dict(category.get("peer_stats"))
    payload        = _safe_dict(trigger.get("payload"))
    voice          = _safe_dict(category.get("voice"))
    agg            = _safe_dict(merchant.get("customer_aggregate"))
    subscription   = _safe_dict(merchant.get("subscription"))
    offers         = _safe_list(merchant.get("offers"))
    raw_signals    = _safe_list(merchant.get("signals"))
    review_themes  = _safe_list(merchant.get("review_themes"))
    digest         = _safe_list(category.get("digest"))
    trend_signals  = _safe_list(category.get("trend_signals"))
    seasonal_beats = _safe_list(category.get("seasonal_beats"))
    delta_7d       = _safe_dict(perf.get("delta_7d"))
    delta_30d      = _safe_dict(perf.get("delta_30d"))

    # ── IDENTITY ──────────────────────────────────────────────────────
    slug         = _s(category.get("slug")).lower()
    merchant_name = _first(identity.get("name"), merchant.get("merchant_name"), default="there")
    owner_first  = _first(identity.get("owner_first_name"), merchant.get("owner_first_name"))
    if not owner_first and merchant_name and merchant_name != "there":
        owner_first = merchant_name.split()[0]
    merchant_langs = _safe_list(identity.get("languages"))

    signals["merchant_name"]        = merchant_name
    signals["owner_first_name"]     = owner_first or "there"
    signals["category_slug"]        = slug
    signals["category_display_name"]= _s(category.get("display_name"), slug.title())
    signals["locality"]             = _s(identity.get("locality"))
    signals["city"]                 = _s(identity.get("city"))
    signals["merchant_verified"]    = identity.get("verified")
    signals["merchant_languages"]   = merchant_langs
    signals["primary_language"]     = merchant_langs[0] if merchant_langs else "en"

    # ── VOICE ─────────────────────────────────────────────────────────
    signals["voice_tone"]     = _s(voice.get("tone"), "professional")
    signals["voice_register"] = _s(voice.get("register"), "professional")
    signals["voice_code_mix"] = _s(voice.get("code_mix"), "en")
    signals["voice_allowed"]  = _safe_list(voice.get("vocab_allowed"))
    signals["voice_taboos"]   = _safe_list(voice.get("vocab_taboo"))

    # ── OFFERS ────────────────────────────────────────────────────────
    active_offer_titles = []
    active_offers = []
    for o in offers:
        if not isinstance(o, dict):
            continue
        status = _s(o.get("status"), "").lower()
        title  = _s(o.get("title"))
        if title and status in {"active", "live", "published", ""}:
            active_offer_titles.append(title)
            active_offers.append(o)
    catalog = _safe_list(category.get("offer_catalog"))
    catalog_first_title = _s(catalog[0].get("title")) if catalog and isinstance(catalog[0], dict) else ""
    signals["active_offers"]        = active_offers
    signals["active_offer_titles"]  = active_offer_titles
    signals["best_offer"]           = active_offer_titles[0] if active_offer_titles else catalog_first_title
    signals["offer_count"]          = len(active_offer_titles)
    signals["has_active_offer"]     = bool(active_offer_titles)
    signals["category_catalog"]     = catalog  # NEW: pass catalog for context-aware selection

    # ── PERFORMANCE ───────────────────────────────────────────────────
    ctr      = _f(perf.get("ctr"))
    views    = _n(perf.get("views"))
    calls    = _n(perf.get("calls"))
    clicks   = _n(perf.get("clicks"))
    peer_ctr = _f(_first(peer.get("avg_ctr"), peer.get("median_ctr")))
    peer_views = _n(peer.get("avg_views_30d"))
    peer_calls = _n(peer.get("avg_calls_30d"))

    signals["ctr"]              = ctr
    signals["ctr_pct"]          = _pct(ctr)
    signals["peer_avg_ctr"]     = peer_ctr
    signals["peer_ctr_pct"]     = _pct(peer_ctr)
    signals["top_ctr_pct"]      = _pct(_first(peer.get("top_ctr_pct"), peer.get("p90_ctr")))
    signals["peer_avg_views_30d"]= peer_views
    signals["peer_avg_calls_30d"]= peer_calls
    signals["peer_avg_directions_30d"] = _n(peer.get("avg_directions_30d"))
    signals["peer_avg_rating"]  = _f(peer.get("avg_rating"))
    signals["peer_avg_review_count"] = _n(peer.get("avg_review_count"))
    signals["peer_retention_pct"] = _pct(peer.get("avg_retention_pct"))

    signals["views_30d"]  = views
    signals["calls_30d"]  = calls
    signals["clicks_30d"] = clicks
    signals["leads_30d"]  = _n(perf.get("leads"))
    signals["directions_30d"] = _n(perf.get("directions"))
    signals["rating"]     = _f(perf.get("rating"))

    signals["delta_7d_views_pct"] = _pct(delta_7d.get("views_pct"))
    signals["delta_7d_calls_pct"] = _pct(delta_7d.get("calls_pct"))
    signals["delta_7d_ctr_pct"]   = _pct(delta_7d.get("ctr_pct"))
    signals["delta_30d_views_pct"]= _pct(delta_30d.get("views_pct"))

    if views and ctr is not None and peer_ctr is not None:
        mc = int(views * (peer_ctr - ctr))
        signals["missed_clicks"] = mc if mc > 0 else None
    else:
        signals["missed_clicks"] = None

    signals["is_low_performing"] = (ctr is not None and peer_ctr is not None and ctr < peer_ctr)
    signals["ctr_below_peer"]    = signals["is_low_performing"]

    # ── SUBSCRIPTION ─────────────────────────────────────────────────
    signals["subscription_status"]      = _s(subscription.get("status"))
    signals["plan_name"]                = _s(subscription.get("plan"))
    signals["subscription_days_remaining"] = _n(subscription.get("days_remaining"))
    signals["days_to_renewal"]          = _n(subscription.get("days_to_renewal"))
    signals["renewal_amount"]           = _n(subscription.get("renewal_amount"))
    signals["renewal_due_date"]         = _s(subscription.get("renewal_due_date"))
    signals["plan_credits"]             = _n(subscription.get("credits"))
    signals["days_since_expiry"]        = _n(subscription.get("days_since_expiry"))
    signals["renewed_at"]               = _s(subscription.get("renewed_at"))

    # ── AGGREGATE ────────────────────────────────────────────────────
    signals["total_customers"] = _first(
        _n(agg.get("total_unique_ytd")),
        _n(agg.get("total_active_members")),
        _n(agg.get("total_customers")),
    )
    signals["active_customers"] = _first(
        _n(agg.get("total_active_members")),
        _n(agg.get("active_customers")),
    )
    signals["lapsed_customers"] = _first(
        _n(agg.get("lapsed_180d_plus")),
        _n(agg.get("lapsed_90d_plus")),
        _n(agg.get("lapsed_customers")),
    )
    signals["retention_pct"] = _pct(_first(
        agg.get("retention_6mo_pct"),
        agg.get("retention_3mo_pct"),
        agg.get("repeat_customer_pct"),
        agg.get("monthly_retention_pct"),
    ))
    signals["repeat_customer_pct"] = _pct(agg.get("repeat_customer_pct"))
    signals["monthly_churn_pct"]   = _pct(agg.get("monthly_churn_pct"))
    signals["high_risk_patients"]  = _n(agg.get("high_risk_adult_count"))
    signals["chronic_rx_count"]    = _n(agg.get("chronic_rx_count"))
    signals["avg_ticket"]          = _n(agg.get("avg_ticket"))
    signals["lapsed_revenue_est"]  = _n(agg.get("lapsed_revenue_est"))
    signals["raw_signals"]         = raw_signals
    signals["review_themes"]       = review_themes
    signals["trend_signals"]       = trend_signals
    signals["seasonal_beats"]      = seasonal_beats

    # ── REVIEW THEMES ─────────────────────────────────────────────────
    if review_themes:
        top = review_themes[0]
        if isinstance(top, dict):
            signals["review_theme"]        = _s(top.get("theme"))
            signals["review_common_quote"] = _s(top.get("common_quote"))
            signals["review_mention_count"]= _n(top.get("occurrences_30d"))
            signals["review_sentiment"]    = _s(top.get("sentiment"))

    # ── TRIGGER CORE ─────────────────────────────────────────────────
    trigger_kind = _s(trigger.get("kind"))
    signals["trigger_id"]       = _s(trigger.get("id"))
    signals["trigger_kind"]     = trigger_kind
    signals["trigger_source"]   = _s(trigger.get("source"))
    signals["trigger_scope"]    = _s(trigger.get("scope"))
    signals["trigger_urgency"]  = _n(trigger.get("urgency"))
    signals["suppression_key"]  = _s(trigger.get("suppression_key"))

    # ── CUSTOMER ─────────────────────────────────────────────────────
    if customer:
        c_id   = _safe_dict(customer.get("identity"))
        rel    = _safe_dict(customer.get("relationship"))
        prefs  = _safe_dict(customer.get("preferences"))
        consent= _safe_dict(customer.get("consent"))

        cname = _s(c_id.get("name"))
        signals["customer_name"]       = cname
        signals["customer_first_name"] = _s(c_id.get("first_name") or c_id.get("name"))
        signals["customer_language"]   = _s(c_id.get("language_pref"), signals["primary_language"])
        signals["customer_age_band"]   = _s(c_id.get("age_band"))
        signals["customer_senior_citizen"] = c_id.get("senior_citizen")

        signals["customer_first_visit"]      = _s(rel.get("first_visit"))
        signals["customer_last_visit"]       = _s(rel.get("last_visit"))
        signals["customer_visits_total"]     = _n(rel.get("visits_total"))
        signals["customer_lifetime_value"]   = _n(rel.get("lifetime_value"))
        signals["customer_services_received"]= _safe_list(rel.get("services_received"))
        signals["customer_chronic_conditions"]= _safe_list(rel.get("chronic_conditions"))

        signals["customer_state"]           = _s(customer.get("state"))
        signals["customer_channel"]         = _s(prefs.get("channel"))
        signals["customer_preferred_slots"] = _s(prefs.get("preferred_slots"))
        signals["customer_reminder_opt_in"] = prefs.get("reminder_opt_in")
        signals["customer_delivery_address"]= _s(prefs.get("delivery_address"))
        signals["customer_consent_scope"]   = _safe_list(consent.get("scope"))

        # payload fields for customer-scoped triggers
        if trigger_kind in {"recall_due", "customer_lapsed_soft", "customer_lapsed_hard",
                             "winback", "chronic_refill_due"}:
            signals["due_date"]          = _s(payload.get("due_date") or payload.get("stock_runs_out_iso"))
            signals["last_service_date"] = _s(payload.get("last_service_date") or payload.get("last_refill"))
            signals["service_due"]       = _s(payload.get("service_due") or payload.get("service"))
            signals["slots_str"]         = _format_slots(payload.get("available_slots"))
            signals["available_slots"]   = _safe_list(payload.get("available_slots"))
            signals["molecule_list"]     = _safe_list(payload.get("molecule_list"))
            signals["delivery_address_saved"] = payload.get("delivery_address_saved")
            signals["customer_preferred_time"] = signals.get("customer_preferred_slots")

        if trigger_kind in {"customer_lapsed_soft", "customer_lapsed_hard", "winback"}:
            signals["days_since_visit"]    = _n(payload.get("days_since_visit") or payload.get("days_since_last_visit"))
            svc_list = signals.get("customer_services_received") or []
            signals["customer_last_service"] = _first(
                payload.get("last_service"),
                svc_list[-1] if svc_list else None,
            )

        if trigger_kind == "trial_followup":
            signals["trial_date"]       = _s(payload.get("trial_date"))
            signals["slots_str"]        = _format_slots(payload.get("next_session_options"))
            signals["available_slots"]  = _safe_list(payload.get("next_session_options"))

    # ── MERCHANT-SIDE TRIGGER PAYLOADS ────────────────────────────────

    if trigger_kind == "research_digest":
        top_item_id = _s(payload.get("top_item_id"))
        item = _find_digest_item(digest, top_item_id) or (digest[0] if digest else None)
        if isinstance(item, dict):
            signals["research_title"]          = _s(item.get("title"))
            signals["research_source"]         = _s(item.get("source"))
            signals["research_summary"]        = _s(item.get("summary"))
            signals["research_actionable"]     = _s(item.get("actionable"))
            signals["research_trial_n"]        = _n(item.get("trial_n"))
            signals["research_trial_n_str"]    = str(_n(item.get("trial_n"))) if item.get("trial_n") else ""
            signals["research_patient_segment"]= _s(item.get("patient_segment"))
            signals["research_page"]           = _s(item.get("page") or item.get("source"))
            signals["research_kind"]           = _s(item.get("kind"))
        signals["high_risk_patients"] = signals.get("high_risk_patients") or _n(agg.get("high_risk_adult_count"))
        signals["total_customers"]    = signals.get("total_customers") or _n(agg.get("total_unique_ytd"))

    elif trigger_kind in {"regulation_change", "compliance_alert", "supply_alert"}:
        top_item_id = _s(payload.get("top_item_id") or payload.get("alert_id"))
        item = _find_digest_item(digest, top_item_id)
        if isinstance(item, dict):
            signals["regulation_title"]    = _s(item.get("title"))
            signals["regulation_source"]   = _s(item.get("source"))
            signals["regulation_deadline"] = _s(payload.get("deadline_iso") or item.get("date"))
            signals["regulation_summary"]  = _s(item.get("summary"))
            signals["regulation_actionable"] = _s(item.get("actionable"))
        else:
            signals["regulation_title"]    = _s(payload.get("title"))
            signals["regulation_deadline"] = _s(payload.get("deadline_iso"))
            signals["regulation_summary"]  = _s(payload.get("summary"))
        signals["affected_batches"]         = _safe_list(payload.get("affected_batches"))
        signals["affected_customers_count"] = _n(payload.get("affected_customers_count"))
        signals["manufacturer"]             = _s(payload.get("manufacturer"))
        signals["molecule"]                 = _s(payload.get("molecule"))
        signals["alert_id"]                 = _s(payload.get("alert_id"))

    elif trigger_kind in {"ipl_match_today", "festival_upcoming", "weather_heatwave"}:
        fest_raw = _s(payload.get("match") or payload.get("festival_name") or payload.get("event_name"))
        seasonal_note = ""
        if not fest_raw and seasonal_beats:
            # Resolve to current seasonal_beats window — never leak a raw default
            try:
                from datetime import datetime as _dt
                mo_abbr = _dt.now().strftime("%b")   # e.g. "May", "Apr"
                for beat in seasonal_beats:
                    mr = _s(beat.get("month_range", ""))
                    if mo_abbr in mr:
                        fest_raw    = _s(beat.get("note", ""))
                        seasonal_note = fest_raw
                        break
            except Exception:
                pass
        signals["festival_name"]   = fest_raw   # empty string if nothing resolved — composer must handle
        signals["seasonal_summary"] = seasonal_note
        signals["match_name"]      = _s(payload.get("match"))
        signals["venue"]           = _s(payload.get("venue"))
        signals["match_time"]      = _s(payload.get("match_time_iso"))
        signals["is_weeknight"]    = payload.get("is_weeknight")
        signals["weather_event"]   = _s(payload.get("weather_event"))
        signals["temperature_c"]   = _f(payload.get("temperature_c"))
        signals["days_to_festival"]= _n(payload.get("days_to_festival"))

    elif trigger_kind == "category_seasonal":
        season = _s(payload.get("season"), "").lower()
        sd = next((d for d in digest if isinstance(d, dict)
                   and d.get("kind") == "seasonal"
                   and season in _s(d.get("title")).lower()), None)
        if sd:
            signals["festival_name"]       = _s(sd.get("title"))
            signals["seasonal_summary"]    = _s(sd.get("summary"))
            signals["seasonal_actionable"] = _s(sd.get("actionable"))
        else:
            signals["festival_name"] = _s(payload.get("season"), "seasonal push")
        signals["shelf_action_recommended"] = payload.get("shelf_action_recommended")

    elif trigger_kind in {"perf_dip", "seasonal_perf_dip", "perf_spike"}:
        signals["perf_metric"]      = _s(payload.get("metric") or payload.get("perf_metric"), "calls")
        signals["perf_delta_pct"]   = _pct(payload.get("delta_pct"))
        signals["perf_window"]      = _s(payload.get("window"), "7d")
        signals["perf_vs_baseline"] = _n(payload.get("vs_baseline"))
        signals["perf_likely_driver"] = _s(payload.get("likely_driver"))

    elif trigger_kind in {"active_planning_intent", "bridal_followup", "wedding_package_followup"}:
        signals["planning_goal"]    = _s(payload.get("planning_goal") or payload.get("ask_template") or payload.get("intent_topic") or payload.get("topic"))
        signals["planning_topic"]   = _s(payload.get("topic") or payload.get("planning_topic"))
        signals["wedding_date"]     = _s(payload.get("wedding_date"))
        signals["days_to_wedding"]  = _n(payload.get("days_to_wedding"))
        signals["preferred_slot"]   = _s(payload.get("preferred_slot"))

    elif trigger_kind == "curious_ask_due":
        signals["ask_template"]  = _s(payload.get("ask_template"))
        signals["last_ask_at"]   = _s(payload.get("last_ask_at"))

    elif trigger_kind in {"cde_opportunity", "cde"}:
        top_item_id = _s(payload.get("digest_item_id") or payload.get("top_item_id"))
        item = _find_digest_item(digest, top_item_id)
        if isinstance(item, dict):
            signals["cde_title"]     = _s(item.get("title"))
            signals["cde_date"]      = _s(item.get("date"))
            signals["cde_credits"]   = _n(item.get("credits"))
            signals["cde_summary"]   = _s(item.get("summary"))
            signals["cde_actionable"]= _s(item.get("actionable"))
            signals["cde_fee"]       = _s(payload.get("fee"))
        else:
            signals["cde_title"]     = _s(payload.get("title"))
            signals["cde_date"]      = _s(payload.get("date"))
            signals["cde_credits"]   = _n(payload.get("credits"))
            signals["cde_fee"]       = _s(payload.get("fee"))
            signals["cde_summary"]   = _s(payload.get("summary"))
            signals["cde_actionable"]= _s(payload.get("actionable"))

    elif trigger_kind == "dormant_with_vera":
        signals["days_since_last_merchant_message"] = _n(payload.get("days_since_last_merchant_message"))
        signals["days_since_last_post"]             = _n(payload.get("days_since_last_post"))
        signals["last_topic"]                       = _s(payload.get("last_topic"))

    elif trigger_kind == "competitor_opened":
        signals["competitor_name"]        = _s(payload.get("competitor_name"))
        signals["competitor_distance_km"] = _f(payload.get("distance_km"))
        signals["competitor_offer"]       = _s(payload.get("their_offer") or payload.get("competitor_offer"))
        signals["competitor_rating"]      = _f(payload.get("competitor_rating"))

    elif trigger_kind == "milestone_reached":
        signals["milestone_type"]        = _s(payload.get("metric"))
        signals["milestone_current"]     = _n(payload.get("value_now"))
        signals["milestone_target"]      = _n(payload.get("milestone_value"))
        signals["milestone_is_imminent"] = payload.get("is_imminent")

    elif trigger_kind == "renewal_due":
        signals["days_to_renewal"]  = _n(payload.get("days_remaining")) or signals.get("subscription_days_remaining")
        signals["plan_name"]        = _s(payload.get("plan")) or signals.get("plan_name")
        signals["renewal_amount"]   = _n(payload.get("renewal_amount")) or signals.get("renewal_amount")

    signals["top_service"]          = signals.get("best_offer")
    signals["merchant_signal_tags"] = raw_signals

    return signals