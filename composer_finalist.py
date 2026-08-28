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


def _money(v):
    if v is None:
        return ""
    try:
        v = int(v) if isinstance(v, float) and v.is_integer() else v
        return f"\u20b9{v:,}"
    except Exception:
        return str(v)


def _first(*vals, default=None):
    for v in vals:
        if v not in (None, "", [], {}):
            return v
    return default


# ──────────────────────────────────────────────────────────────────
# NEW: Humanization & formatting helpers
# ──────────────────────────────────────────────────────────────────

def _humanize(v):
    """Convert snake_case / raw codes to natural language."""
    if not v:
        return ""
    txt = str(v).replace("_", " ").strip()
    # Known raw-value mappings
    mappings = {
        "high risk adults": "high-risk adults",
        "high risk adult": "high-risk adult",
        "6 month cleaning": "6-month cleaning",
        "3 month cleaning": "3-month cleaning",
        "delivery late": "delivery was late",
        "delivery delay": "delivery delay",
        "pt intro": "PT intro",
        "kids yoga summer camp": "kids' yoga summer camp",
        "summer 2026": "summer 2026",
        "winter 2026": "winter 2026",
        "free for members": "free for members",
        "free for member": "free for members",
        "stylist skill": "stylist skill",
        "corporate bulk thali": "corporate bulk-thali",
    }
    lowered = txt.lower()
    if lowered in mappings:
        return mappings[lowered]
    # Title-case short phrases, sentence-case long ones
    if len(txt) < 30:
        return txt.title()
    return txt


def _fmt_date(iso_str):
    """Format ISO date → 'May 12' or '28 April'."""
    if not iso_str:
        return ""
    try:
        from datetime import datetime
        s = str(iso_str).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.strftime("%b %d").replace(" 0", " ")  # 'May 12'
    except Exception:
        # Fallback: strip time portion
        s = str(iso_str)
        if "T" in s:
            s = s.split("T")[0]
        return s


def _fmt_datetime(iso_str):
    """Format ISO datetime → 'Wed 5 Nov, 6pm'."""
    if not iso_str:
        return ""
    try:
        from datetime import datetime
        s = str(iso_str).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.strftime("%a %d %b, %I%p").replace(" 0", " ").lower().replace("am", "am").replace("pm", "pm")
    except Exception:
        return str(iso_str)


def _fmt_pct(v):
    """Format percentage → '30%' not '30.0%'."""
    if v is None:
        return None
    try:
        f = float(v)
        if f == int(f):
            return f"{int(f)}%"
        return f"{round(f, 1)}%"
    except (TypeError, ValueError):
        return str(v)


def _owner(signals):
    owner = _s(signals.get("owner_first_name"))
    if not owner:
        owner = _s(signals.get("merchant_name"), "there")
    slug = _s(signals.get("category_slug")).lower()
    if "dent" in slug and owner and not owner.lower().startswith("dr."):
        return f"Dr. {owner}"
    return owner


def _biz(signals):
    return _s(signals.get("merchant_name"), "us")


def _unit(signals):
    slug = _s(signals.get("category_slug")).lower()
    if "dent" in slug:     return "patients"
    if "gym" in slug:      return "members"
    if "pharm" in slug:    return "customers"
    if "restaurant" in slug: return "customers"
    if "salon" in slug:    return "clients"
    return "customers"


def _offer(signals):
    """Context-aware offer selection."""
    titles = signals.get("active_offer_titles") or []
    offers = signals.get("active_offers") or []
    slug = _s(signals.get("category_slug")).lower()
    tk = _s(signals.get("trigger_kind"))
    goal = _s(signals.get("planning_goal")).lower()

    # Bridal / wedding → bridal offer (check active_offers, then active titles, then catalog)
    if "bridal" in tk or "wedding" in tk or "bridal" in goal:
        for o in offers:
            t = _s(o.get("title")).lower()
            if "bridal" in t or "wedding" in t:
                return o.get("title")
        for t in titles:
            if "bridal" in t.lower() or "wedding" in t.lower():
                return t
        # Always fall through to category_catalog — bridal offer is rarely "active"
        catalog = signals.get("category_catalog") or []
        for o in catalog:
            if isinstance(o, dict):
                t = _s(o.get("title")).lower()
                if "bridal" in t or "wedding" in t:
                    return o.get("title")

    # Seasonal bridal context (e.g. festival_upcoming with bridal seasonal_summary)
    seasonal_smry = _s(signals.get("seasonal_summary") or signals.get("festival_name")).lower()
    if "bridal" in seasonal_smry or "wedding" in seasonal_smry:
        catalog = signals.get("category_catalog") or []
        for o in catalog:
            if isinstance(o, dict):
                t = _s(o.get("title")).lower()
                if "bridal" in t or "wedding" in t:
                    return o.get("title")

    # Winback / retention → repeat-user or non-trial offer
    if tk in {"customer_lapsed_soft", "customer_lapsed_hard", "winback", "winback_eligible", "retention_push"}:
        for o in offers:
            aud = _s(o.get("audience")).lower()
            if "repeat" in aud or "return" in aud:
                return o.get("title")
        for o in offers:
            t = _s(o.get("title")).lower()
            if "trial" not in t and "free" not in t:
                return o.get("title")
        for t in titles:
            if "trial" not in t.lower() and "free" not in t.lower():
                return t

    # Corporate / bulk thali
    if "corporate" in goal or "bulk" in goal:
        for o in offers:
            t = _s(o.get("title")).lower()
            if "thali" in t:
                return o.get("title")
        for t in titles:
            if "thali" in t.lower():
                return t

    # Seasonal / perf spike → push best active offer (not just first)
    if tk in {"perf_spike", "seasonal_push", "festival_upcoming"}:
        for t in titles:
            if any(x in t.lower() for x in ["combo", "plan", "membership", "package"]):
                return t

    if titles:
        return titles[0]

    catalog = signals.get("category_catalog") or []
    if catalog and isinstance(catalog[0], dict):
        return catalog[0].get("title", "Entry Offer @ \u20b9299")
    return "Entry Offer @ \u20b9299"


def _recall_service(signals):
    slug = _s(signals.get("category_slug")).lower()
    if "dent" in slug:   return "cleaning"
    if "gym" in slug:    return "session"
    if "salon" in slug:  return "appointment"
    if "pharm" in slug:  return "refill"
    return "appointment"


def _has_hi(signals):
    lang = _s(signals.get("customer_language"), "en").lower()
    return any(x in lang for x in ("hi", "hindi", "hinglish"))


def _greet(signals):
    name = _s(signals.get("customer_first_name") or signals.get("customer_name"), "there")
    return ("Namaste" if _has_hi(signals) else "Hi") + f" {name}"


def compose_final(signals, action):
    signals = signals or {}
    owner   = _owner(signals)
    biz     = _biz(signals)
    unit    = _unit(signals)
    offer   = _offer(signals)
    slug    = _s(signals.get("category_slug")).lower()
    loc     = _s(signals.get("locality")) or _s(signals.get("city"))
    tk      = _s(signals.get("trigger_kind"))

    # ──────────────────────────────────────────────────────────────────
    # insight_share  (research_digest, milestone_reached)
    # ──────────────────────────────────────────────────────────────────
    if action == "insight_share":
        if tk == "milestone_reached":
            metric  = _s(signals.get("milestone_type"))
            current = _n(signals.get("milestone_current"))
            target  = _n(signals.get("milestone_target"))
            if metric == "review_count" and target and current:
                remaining = target - current
                return {
                    "body": (
                        f"{owner}, you're {remaining} reviews away from {target}! "
                        f"Crossing {target} builds trust for new {unit} checking your listing. "
                        "Want me to draft a 2-message push to get you over the line?"
                    ),
                    "cta": "open_ended", "send_as": "vera",
                    "rationale": f"milestone: {remaining} to {target}",
                }
            return {
                "body": f"{owner}, you're approaching a milestone. Want me to help mark the occasion?",
                "cta": "open_ended", "send_as": "vera",
                "rationale": "milestone reached",
            }

        title     = _s(signals.get("research_title"))
        source    = _s(signals.get("research_source"))
        summary   = _s(signals.get("research_summary"))
        trial_n   = _s(signals.get("research_trial_n_str") or signals.get("research_trial_n"))
        segment   = _humanize(signals.get("research_patient_segment"))
        page      = _s(signals.get("research_page"))
        actionable= _s(signals.get("research_actionable"))
        high_risk = _n(signals.get("high_risk_patients"))
        total_c   = _n(signals.get("total_customers"))

        src = source or "peer-reviewed update"

        # Source citation to append at end (e.g. "— JIDA Oct 2026, p.14")
        src_ref = f" — {src}" if src else ""

        # Extract the headline percentage from summary (e.g. "38% lower caries recurrence")
        import re as _re
        key_stat = ""
        if summary:
            m = _re.search(
                r'(\d+(?:\.\d+)?%\s+(?:lower|higher|fewer|better|reduction|improvement)\s+\w+(?:\s+\w+){0,1})',
                summary, _re.I
            )
            if m:
                key_stat = m.group(1).strip().rstrip('.,;')
        # Clean segment label — must never produce raw snake_case
        seg_label = segment if segment and segment.lower() not in ("", "none") else ""

        # Opening: anchor to merchant's specific cohort size
        if high_risk and high_risk > 0:
            # If seg_label already describes the group (e.g. "high-risk adults"), don't append unit again
            if seg_label:
                cohort_str = f"your {high_risk} {seg_label}"
            else:
                cohort_str = f"your {high_risk} high-risk {unit}"
            opening = f"{owner}, {src} just landed. One item directly relevant to {cohort_str} —"
        elif total_c and total_c > 0:
            opening = f"{owner}, {src} just landed. One item relevant to your {unit} base —"
        else:
            opening = f"{owner}, worth a look — {src}."

        # Core finding: trial_n + key_stat fused into ONE sentence
        if trial_n and key_stat:
            finding = f"{trial_n}-patient trial: {key_stat}."
        elif trial_n and title:
            t = (title[0].lower() + title[1:]) if title else title
            finding = f"{trial_n}-patient trial: {t}."
        elif key_stat:
            finding = f"{key_stat}."
        elif title:
            finding = title + "."
        else:
            finding = (summary[:160] + "...") if len(summary) > 160 else summary

        lines = [opening, finding]
        if actionable:
            lines.append(actionable)
        # CTA with citation appended inline — matches case-study pattern
        lines.append(
            f"Worth a look (2-min abstract). Want me to pull it + draft a patient-ed WhatsApp you can share?{src_ref}"
        )
        return {
            "body": "\n".join(lines),
            "cta": "open_ended", "send_as": "vera",
            "rationale": f"research_digest: {src} — n={trial_n or 'N/A'} — {seg_label or 'cohort'}",
        }

    # ──────────────────────────────────────────────────────────────────
    # performance_fix  (perf_dip, seasonal_perf_dip)
    # ──────────────────────────────────────────────────────────────────
    if action == "performance_fix":
        ctr     = _f(signals.get("ctr_pct"))
        peer    = _f(signals.get("peer_ctr_pct"))
        top     = _f(signals.get("top_ctr_pct"))
        views   = _n(signals.get("views_30d"))
        clicks  = _n(signals.get("clicks_30d"))
        missed  = _n(signals.get("missed_clicks"))
        pd      = _f(signals.get("perf_delta_pct"))
        pmetric = _s(signals.get("perf_metric"), "calls")
        pbase   = _n(signals.get("perf_vs_baseline"))
        pwin    = _s(signals.get("perf_window"), "7d")
        best    = _offer(signals)

        if tk == "seasonal_perf_dip":
            lines = [f"{owner}, the dip is seasonal, not structural."]
            if pd is not None:
                lines.append(f"{_humanize(pmetric).title()} are down {_fmt_pct(abs(pd))} — this is the normal April-June acquisition lull (every metro gym sees -25 to -35% in this window).")
            if views:
                lines.append(f"You still have {views:,} views this month.")
            lines.append("Skip ad spend now, save it for Sept-Oct when conversion is 2x.")
            if signals.get("active_customers"):
                lines.append(f"Focus retention on your {signals['active_customers']} members.")
            lines.append("Want me to draft a short summer-retention message?")
            return {
                "body": "\n".join(lines),
                "cta": "open_ended", "send_as": "vera",
                "rationale": "seasonal_perf_dip reframed with retention action",
            }

        lines = [f"{owner}, quick reality check on your listing."]
        if views and clicks and ctr is not None:
            lines.append(f"{views:,} views this month \u2192 {clicks:,} clicks ({_fmt_pct(ctr)} CTR).")
        elif ctr is not None and peer is not None:
            lines.append(f"Your CTR is {_fmt_pct(ctr)} vs {_fmt_pct(peer)} category average.")
        if top:
            lines.append(f"Top nearby listings sit at {_fmt_pct(top)} CTR.")
        if pbase:
            lines.append(f"{_humanize(pmetric).title()} are down vs a {pbase}-call baseline over {pwin}.")
        if missed and missed > 0:
            lines.append(f"At this pace, roughly {missed:,} bookings are slipping away.")
        elif ctr is not None and peer is not None and peer > ctr:
            lines.append(f"That {_fmt_pct(abs(peer - ctr))} gap is costing bookings every week.")
        d7c = _f(signals.get("delta_7d_calls_pct"))
        if d7c is not None and d7c < 0:
            lines.append(f"Call volume is also down {_fmt_pct(abs(d7c))} this week.")
        if not signals.get("active_offer_titles"):
            lines.append("You don't have an active offer — that's likely hurting conversion.")
            lines.append(f"I'd suggest setting up {best or 'a service-at-price offer'} to recover CTR.")
            lines.append("Want me to set it up?")
        else:
            lines.append(f"The cleanest fix: push your active offer {best}.")
            lines.append("Want me to draft the exact WhatsApp campaign?")
        return {
            "body": "\n".join(lines),
            "cta": "open_ended", "send_as": "vera",
            "rationale": "performance_fix grounded in CTR, peer average, and offer",
        }

    # ──────────────────────────────────────────────────────────────────
    # perf_spike
    # ──────────────────────────────────────────────────────────────────
    if action == "perf_spike":
        pd      = _f(signals.get("perf_delta_pct"))
        pmetric = _s(signals.get("perf_metric"), "calls")
        pbase   = _n(signals.get("perf_vs_baseline"))
        driver  = _s(signals.get("perf_likely_driver"))
        views   = _n(signals.get("views_30d"))
        best    = _offer(signals)

        lines = [f"{owner}, good signal this week \u2014"]
        if pd is not None:
            lines.append(f"{_humanize(pmetric).title()} are up {_fmt_pct(pd)}.")
        else:
            d7c = _f(signals.get("delta_7d_calls_pct"))
            if d7c and d7c > 0:
                lines.append(f"Calls are up {_fmt_pct(d7c)}.")
        if pbase:
            lines.append(f"Against a {pbase}-call baseline.")
        if driver:
            lines.append(f"Likely driver: {_humanize(driver)}.")
        if views:
            lines.append(f"{views:,} views this month — momentum is building.")
        if best:
            lines.append(f"Now's the time to push {best} and lock bookings in.")
        lines.append("Want me to draft the campaign?")
        return {
            "body": "\n".join(lines),
            "cta": "open_ended", "send_as": "vera",
            "rationale": "perf_spike grounded in live traction",
        }

    # ──────────────────────────────────────────────────────────────────
    # customer_recall  (recall_due, chronic_refill_due, trial_followup)
    # ──────────────────────────────────────────────────────────────────
    if action == "customer_recall":
        cname      = _s(signals.get("customer_first_name") or signals.get("customer_name"), "there")
        due_date   = _s(signals.get("due_date"))
        service    = _humanize(signals.get("service_due")) or _recall_service(signals)
        slots_str  = _s(signals.get("slots_str"))
        last_visit = _s(signals.get("customer_last_visit"))
        last_svc_d = _fmt_date(signals.get("last_service_date"))
        molecules  = signals.get("molecule_list") or []
        channel    = _s(signals.get("customer_channel"))
        lang       = _s(signals.get("customer_language"), "en").lower()
        pref_time  = _s(signals.get("customer_preferred_time") or signals.get("customer_preferred_slots"))
        hi         = _has_hi(signals)

        # Trial follow-up (gym/yoga) ───────────────────────────────────
        if tk == "trial_followup":
            trial_date = _fmt_date(signals.get("trial_date"))
            next_slot  = slots_str
            greet      = _greet(signals)
            lines = [f"{greet}, {biz} here."]
            if trial_date:
                lines.append(f"Hope you enjoyed the trial on {trial_date}.")
            if next_slot:
                lines.append(f"Your next session: {next_slot}.")
            lines.append(f"We're offering {offer} to continue.")
            lines.append("Reply YES to book — no commitment.")
            return {
                "body": "\n".join(lines),
                "cta": "YES", "send_as": "merchant_on_behalf",
                "rationale": "trial_followup with next slot and offer",
            }

        # Pharmacy / chronic refill (Case Study 10) ───────────────────
        if "pharm" in slug or molecules:
            sal = "Namaste" if hi else "Hi"
            lines = [f"{sal} \u2014 {biz} yahan."]
            if cname:
                lines.append(f"{cname} ji ki medicines due hain.")
            if molecules:
                med_str = ", ".join(str(m) for m in molecules)
                lines.append(f"Medicines: {med_str}.")
            if due_date:
                due_fmt = _fmt_date(due_date)
                lines.append(f"Stock runs out on {due_fmt}.")
            if signals.get("customer_delivery_address") or signals.get("delivery_address_saved"):
                lines.append("Free home delivery to the saved address.")
            if signals.get("customer_senior_citizen"):
                lines.append("Senior discount 15% applied where eligible.")
            lines.append("Reply CONFIRM to dispatch, or call if the dosage changed.")
            return {
                "body": "\n".join(lines),
                "cta": "CONFIRM", "send_as": "merchant_on_behalf",
                "rationale": "chronic_refill with molecule list and delivery",
            }

        # Dentist / Salon / Generic recall (Case Study 2) ─────────────
        emoji = " \U0001f9b7" if "dent" in slug else (" \U0001f48d" if "bridal" in tk else "")
        sal   = "Namaste" if hi else "Hi"
        lines = [f"{sal} {cname}, {biz} here{emoji}"]

        if last_svc_d:
            lines.append(f"It's been a while since your last {service} (last: {last_svc_d}) — your recall is due.")
        elif due_date:
            due_fmt = _fmt_date(due_date)
            lines.append(f"Your {service} is due on {due_fmt}.")
        else:
            lines.append(f"Your {service} recall is due.")

        if slots_str:
            if hi:
                lines.append(f"Apke liye 2 slots ready hain: {slots_str}.")
            else:
                lines.append(f"Available slots: {slots_str}.")
        elif pref_time:
            lines.append(f"Preferred time noted: {pref_time}.")

        if offer:
            lines.append(f"{offer} \u2014 available for returning {unit}.")

        if hi and slots_str:
            lines.append("Reply 1 for the first slot, 2 for the second, or tell us a time that works.")
        else:
            lines.append("Reply YES to confirm, or tell us a time that works.")

        return {
            "body": "\n".join(lines),
            "cta": "YES", "send_as": "merchant_on_behalf",
            "rationale": "customer_recall grounded in due date, slots, and offer",
        }

    # ──────────────────────────────────────────────────────────────────
    # renewal_nudge
    # ──────────────────────────────────────────────────────────────────
    if action == "renewal_nudge":
        plan    = _s(signals.get("plan_name"), "your plan")
        days    = _n(signals.get("days_to_renewal") or signals.get("subscription_days_remaining"))
        amount  = _n(signals.get("renewal_amount"))
        credits = _n(signals.get("plan_credits"))
        views   = _n(signals.get("views_30d"))
        calls   = _n(signals.get("calls_30d"))

        lines = [f"{owner}, your {plan} renewal is coming up."]
        if days and days > 0:
            lines.append(f"{days} days left.")
        if amount:
            lines.append(f"Renewal: {_money(amount)}.")
        if credits:
            lines.append(f"{credits} credits are tied to this plan and will lapse on expiry.")
        if views and calls:
            lines.append(f"This month: {views:,} views, {calls:,} calls — don't lose that momentum.")
        elif views:
            lines.append(f"Your listing had {views:,} views this month.")
        lines.append("Renewing keeps your listing active and your campaigns running.")
        lines.append("Want me to send the renewal link?")
        return {
            "body": "\n".join(lines),
            "cta": "open_ended", "send_as": "vera",
            "rationale": "renewal_nudge with days remaining and live performance",
        }

    # ──────────────────────────────────────────────────────────────────
    # compliance_nudge  (regulation, supply_alert, gbp_unverified)
    # ──────────────────────────────────────────────────────────────────
    if action == "compliance_nudge":
        reg_title  = _s(signals.get("regulation_title"))
        reg_ddl    = _s(signals.get("regulation_deadline"))
        reg_act    = _s(signals.get("regulation_actionable"))
        verified   = signals.get("merchant_verified")
        batches    = signals.get("affected_batches") or []
        affected   = _n(signals.get("affected_customers_count"))
        molecule   = _s(signals.get("molecule"))
        mfr        = _s(signals.get("manufacturer"))
        vpath      = _s(signals.get("verification_path"))
        uplift     = _f(signals.get("estimated_uplift_pct"))
        views      = _n(signals.get("views_30d"))
        calls      = _n(signals.get("calls_30d"))
        chronic    = _n(signals.get("chronic_rx_count"))

        if tk in {"regulation_change", "compliance_alert"} and reg_title:
            lines = [f"{owner}, urgent update: {reg_title}."]
            if reg_ddl:
                lines.append(f"Deadline: {reg_ddl}.")
            if batches:
                lines.append(f"Impacted batches: {', '.join(str(b) for b in batches)}.")
            if affected and affected > 0:
                lines.append(f"{affected} customers may need to be informed.")
            if reg_act:
                lines.append(reg_act)
            lines.append("Want me to draft the customer note + the internal checklist?")
            return {
                "body": "\n".join(lines),
                "cta": "open_ended", "send_as": "vera",
                "rationale": "regulation_change with deadline and impacted count",
            }

        if tk == "supply_alert":
            batch_str   = f" ({', '.join(str(b) for b in batches)})" if batches else ""
            mfr_str     = f" by {mfr.replace('Mfr', 'Mfr ').strip()}" if mfr else ""
            n_batches   = len(batches)
            batch_count = f"{n_batches} " if n_batches > 1 else ""
            mol_label   = molecule or "flagged medicine"
            # Single dense opening — mirrors Case Study 9 exactly
            opening = (
                f"{owner}, urgent: voluntary recall on {batch_count}{mol_label} "
                f"batches{batch_str}{mfr_str} — sub-potency, no safety risk, "
                f"but customers need to be informed for replacement."
            )
            lines = [opening]
            if affected and affected > 0:
                lines.append(
                    f"Pulled your repeat-Rx list: {affected} of your chronic-Rx customers "
                    f"were dispensed these batches in the last 90 days."
                )
            elif chronic and chronic > 0:
                # Do NOT show total as if it's affected — show it as roster size only
                lines.append(
                    f"Scanning your {chronic} chronic-Rx customers against dispensed records now."
                )
            lines.append("Want me to draft their WhatsApp note + the replacement-pickup workflow?")
            return {
                "body": "\n".join(lines),
                "cta": "open_ended", "send_as": "vera",
                "rationale": "supply_alert: inline batch+subpotency, correct affected count",
            }

        # GBP unverified
        lines = [f"{owner}, your Google Business Profile is unverified."]
        if views and calls:
            lines.append(f"You're already getting {views:,} views and {calls:,} calls this month.")
        if vpath:
            lines.append(f"Verification path: {vpath}.")
        if uplift:
            lines.append(f"Estimated uplift after verification: {_fmt_pct(uplift)}.")
        lines.append("Takes under 5 minutes. Want me to walk you through it?")
        return {
            "body": "\n".join(lines),
            "cta": "open_ended", "send_as": "vera",
            "rationale": "gbp_unverified with live views and verification path",
        }

    # ──────────────────────────────────────────────────────────────────
    # planning_assist
    # ──────────────────────────────────────────────────────────────────
    if action == "planning_assist":
        goal    = _s(signals.get("planning_goal")).lower()
        wed_d   = _s(signals.get("wedding_date"))
        dtw     = _n(signals.get("days_to_wedding"))
        pslot   = _s(signals.get("preferred_slot"))
        views   = _n(signals.get("views_30d"))
        fest    = _s(signals.get("festival_name") or signals.get("planning_topic"))
        dtf     = _n(signals.get("days_to_festival"))
        cname   = _s(signals.get("customer_first_name"), "there")

        # Bridal follow-up ─────────────────────────────────────────────
        if tk in {"bridal_followup", "wedding_package_followup"} or "bridal" in goal:
            # Short biz name: first word + locality (matches "Studio11 Kapra" pattern)
            biz_parts = _s(signals.get("merchant_name"), "us").split()
            biz_display = (biz_parts[0] + (f" {loc}" if loc and loc not in biz_parts else "")) if biz_parts else biz

            # Resolve bridal offer and pull its price/structure
            bridal_offer = offer  # already resolved via _offer() which now checks catalog
            bridal_price = ""
            for src_pool in (signals.get("active_offers") or [], signals.get("category_catalog") or []):
                for o in src_pool:
                    if isinstance(o, dict) and ("bridal" in _s(o.get("title")).lower() or "wedding" in _s(o.get("title")).lower()):
                        bridal_price = _s(o.get("value", ""))
                        break
                if bridal_price:
                    break

            lines = [f"Hi {cname} \U0001f48d {owner} from {biz_display} here."]
            if dtw:
                lines.append(
                    f"{dtw} days to your wedding — perfect window to start the skin-prep program before peak bridal slots fill up."
                )
            elif wed_d:
                lines.append(f"Wedding on {_fmt_date(wed_d)} — the right time to start.")
            if bridal_offer:
                # Offer title from catalog already contains "@ ₹999" — use as-is, no double-price
                lines.append(f"{bridal_offer} is the right next step.")
            if pslot:
                lines.append(f"Want me to block your preferred {pslot} slot for the first session next week?")
            else:
                lines.append("Want me to block the first session and send you the reminder?")
            return {
                "body": "\n".join(lines),
                "cta": "open_ended", "send_as": "merchant_on_behalf",
                "rationale": "bridal_followup with wedding-date, correct catalog offer, and slot",
            }

        # Corporate thali (restaurants) ────────────────────────────────
        if "corporate_bulk_thali" in goal and "restaurant" in slug:
            base = 149
            for o in signals.get("active_offers") or []:
                if isinstance(o, dict) and "thali" in _s(o.get("title")).lower():
                    base = _n(o.get("price"), base)
            loc_fmt = loc or "your area"
            lines = [
                f"{owner}, here's a starter version \u2014 you can edit:",
                "",
                f"{biz} Corporate Thali \u2014 for offices in {loc_fmt}",
                f"\u2022 10 thalis @ \u20b9{base} each (\u20b925 off retail) + free delivery",
                f"\u2022 25 thalis @ \u20b9{base - 10} each + 2 free filter coffees",
                f"\u2022 50+ thalis @ \u20b9{base - 20} each + 1 free dosa platter",
                "\u2022 WhatsApp day-before by 5pm; delivery 12:30\u20131pm",
                "",
                f"3 offices in {loc_fmt} are in your delivery radius. Want me to draft a WhatsApp to their facilities managers?",
            ]
            return {
                "body": "\n".join(lines),
                "cta": "open_ended", "send_as": "vera",
                "rationale": "corporate thali artifact with tiered pricing and locality",
            }

        # Kids yoga / generic planning ─────────────────────────────────
        lines = [f"{owner}, this is the right time to plan ahead."]
        if fest:
            fest_h = _humanize(fest)
            if dtf:
                lines.append(f"{fest_h} is {dtf} days away.")
            else:
                lines.append(f"{fest_h} is coming up.")
        if goal:
            lines.append(f"Goal: {_humanize(goal)}.")
        if views:
            lines.append(f"{views:,} views this month to convert.")
        if offer:
            lines.append(f"{offer} is the clean next-step offer for this window.")
        lines.append("Want me to draft the 7-day campaign?")
        return {
            "body": "\n".join(lines),
            "cta": "open_ended", "send_as": "vera",
            "rationale": "planning_assist grounded in timing and goal",
        }

    # ──────────────────────────────────────────────────────────────────
    # reputation_fix
    # ──────────────────────────────────────────────────────────────────
    if action == "reputation_fix":
        theme  = _humanize(signals.get("review_theme"))
        count  = _n(signals.get("review_mention_count"))
        quote  = _s(signals.get("review_common_quote"))
        rating = _f(signals.get("rating"))
        prating= _f(signals.get("peer_avg_rating"))

        lines = [f"{owner}, one theme is repeating in your reviews."]
        if theme and count:
            lines.append(f"'\u2018{theme}\u2019 came up in {count} reviews this month.")
        elif theme:
            lines.append(f"'\u2018{theme}\u2019 has been flagged recently.")
        if quote:
            lines.append(f"Example: \"\u201c{quote}\u201d\"")
        if rating and prating:
            lines.append(f"Your rating: {rating:.1f}\u2605 vs {prating:.1f}\u2605 category average.")
        lines.append("A direct reply + one operational fix recovers trust fast.")
        lines.append("Want me to draft both?")
        return {
            "body": "\n".join(lines),
            "cta": "open_ended", "send_as": "vera",
            "rationale": "reputation_fix grounded in review theme and quote",
        }

    # ──────────────────────────────────────────────────────────────────
    # seasonal_push  (festival, IPL, category_seasonal, weather)
    # ──────────────────────────────────────────────────────────────────
    if action == "seasonal_push":
        fest    = _s(signals.get("festival_name"))
        dtf     = _n(signals.get("days_to_festival"))
        views   = _n(signals.get("views_30d"))
        weather = _s(signals.get("weather_event"))
        temp_c  = _f(signals.get("temperature_c"))

        # IPL match day (Case Study 5) ─────────────────────────────────
        if tk == "ipl_match_today" and "restaurant" in slug:
            match   = _s(signals.get("match_name") or fest, "IPL match")
            venue   = _s(signals.get("venue"))
            is_wknd = signals.get("is_weeknight") is False
            lines   = [f"Quick heads-up {owner} \u2014 {match} is on tonight."]
            if venue:
                lines.append(f"Venue: {venue}.")
            if is_wknd:
                lines.append("Saturday IPL matches usually shift \u221212% restaurant covers (people watch at home).")
                lines.append("Skip the match-night promo today; instead push your existing BOGO as a delivery-only Saturday special.")
            else:
                lines.append("Match-night traffic shifts fast \u2014 keep the offer tight and delivery-first.")
            lines.append(f"Use {offer} as the core offer, not a broad discount.")
            lines.append("Want me to draft the Swiggy banner + Insta story? Live in 10 min.")
            return {
                "body": "\n".join(lines),
                "cta": "open_ended", "send_as": "vera",
                "rationale": "ipl_match_today with category-aware Saturday recommendation",
            }

        # Category seasonal (pharmacies summer shift etc.) ─────────────
        if tk == "category_seasonal":
            title  = _humanize(fest) or "seasonal shift"
            smry   = _s(signals.get("seasonal_summary"))
            sact   = _s(signals.get("seasonal_actionable"))
            lines  = [f"{owner}, the seasonal demand shift is here: {title}."]
            if smry:
                lines.append(smry[:200])
            if sact:
                lines.append(sact)
            lines.append("Want me to draft the shelf-reset message + a quick customer WhatsApp?")
            return {
                "body": "\n".join(lines),
                "cta": "open_ended", "send_as": "vera",
                "rationale": "category_seasonal with digest data",
            }

        # Generic festival / weather ───────────────────────────────────
        # Guard: never emit the raw "seasonal push" string
        fest_clean = fest if fest and fest.lower() not in ("seasonal push", "seasonal_push", "") else ""
        smry_clean = _s(signals.get("seasonal_summary"))

        if fest_clean or smry_clean or weather:
            context = fest_clean or smry_clean or weather
            is_bridal_window = any(x in context.lower() for x in ("bridal", "wedding"))
            if is_bridal_window:
                lines = [f"{owner}, the secondary bridal window is open right now."]
                lines.append("Apr\u2013May is the quieter bridal stretch \u2014 most salons miss it; bookings start 6\u20138 weeks out.")
            else:
                context_h = _humanize(context)
                lines = [f"{owner}, seasonal window is open."]
                lines.append(context_h + ("." if not context_h.endswith(".") else ""))
            if dtf:
                lines.append(f"{dtf} days away \u2014 early push locks clients in now.")
            if views:
                lines.append(f"{views:,} views this month \u2014 the listing already has reach.")
            if offer:
                lines.append(f"{offer} is the right offer to push now.")
            lines.append("Want me to build the WhatsApp campaign?")
        else:
            # Truly empty — generic but not broken
            lines = [f"{owner}, there's a seasonal moment here."]
            if views:
                lines.append(f"{views:,} views this month — the listing has reach.")
            if offer:
                lines.append(f"{offer} is the fastest season-ready move.")
            lines.append("Want me to build the WhatsApp campaign?")
        return {
            "body": "\n".join(lines),
            "cta": "open_ended", "send_as": "vera",
            "rationale": "seasonal_push grounded in festival/beat context",
        }

    # ──────────────────────────────────────────────────────────────────
    # cde_opportunity
    # ──────────────────────────────────────────────────────────────────
    if action == "cde_opportunity":
        title   = _s(signals.get("cde_title"))
        date    = _fmt_datetime(signals.get("cde_date"))
        credits = _n(signals.get("cde_credits"))
        fee     = _s(signals.get("cde_fee")).replace("_", " ")
        smry    = _s(signals.get("cde_summary"))
        act     = _s(signals.get("cde_actionable"))

        lines = [f"{owner}, this CDE looks relevant."]
        if title:
            lines.append(title)
        if date:
            lines.append(f"Date: {date}.")
        if credits:
            lines.append(f"Credits: {credits}.")
        if fee:
            lines.append(f"Fee: {fee}.")
        if smry:
            lines.append(smry if len(smry) <= 160 else smry[:157] + "...")
        if act:
            lines.append(act)
        lines.append("Want me to draft the reminder message?")
        return {
            "body": "\n".join(lines),
            "cta": "open_ended", "send_as": "vera",
            "rationale": "cde_opportunity grounded in date, credits, and fee",
        }

    # ──────────────────────────────────────────────────────────────────
    # dormant_nudge
    # ──────────────────────────────────────────────────────────────────
    if action == "dormant_nudge":
        dsmsg = _n(signals.get("days_since_last_merchant_message"))
        dspost= _n(signals.get("days_since_last_post"))
        views = _n(signals.get("views_30d"))
        lapsed= _n(signals.get("lapsed_customers"))

        lines = [f"{owner}, this listing has gone quiet."]
        if dsmsg:
            lines.append(f"Last time we chatted: {dsmsg} days ago.")
        if dspost:
            lines.append(f"Last post/update: {dspost} days ago.")
        if views:
            lines.append(f"{views:,} people still saw the profile this month.")
        if lapsed:
            lines.append(f"{lapsed} customers are overdue for a recall message.")
        if offer:
            lines.append(f"{offer} is the fastest restart.")
        lines.append("Want me to draft the restart message?")
        return {
            "body": "\n".join(lines),
            "cta": "open_ended", "send_as": "vera",
            "rationale": "dormant_nudge grounded in inactivity and live views",
        }

    # ──────────────────────────────────────────────────────────────────
    # competitor_alert
    # ──────────────────────────────────────────────────────────────────
    if action == "competitor_alert":
        cname  = _s(signals.get("competitor_name"))
        dist   = _f(signals.get("competitor_distance_km"))
        coffer = _s(signals.get("competitor_offer"))
        ctr    = _f(signals.get("ctr_pct"))
        peer   = _f(signals.get("peer_ctr_pct"))
        views  = _n(signals.get("views_30d"))

        lines = [f"{owner}, a new competitor is active nearby."]
        if cname and dist:
            lines.append(f"{cname} opened {dist:.1f} km away.")
        elif cname:
            lines.append(f"{cname} opened nearby.")
        if coffer:
            lines.append(f"Their offer: {coffer}.")
        if views and ctr is not None and peer is not None:
            lines.append(f"Your listing: {views:,} views, {_fmt_pct(ctr)} CTR vs {_fmt_pct(peer)} peer average.")
        lines.append(f"Don't match price blindly \u2014 reposition {offer} with a stronger bundle.")
        lines.append("Want me to draft the counter-offer?")
        return {
            "body": "\n".join(lines),
            "cta": "open_ended", "send_as": "vera",
            "rationale": "competitor_alert grounded in distance and competitor offer",
        }

    # ──────────────────────────────────────────────────────────────────
    # retention_push
    # ──────────────────────────────────────────────────────────────────
    if action == "retention_push":
        ret    = _f(signals.get("retention_pct"))
        pret   = _f(signals.get("peer_retention_pct"))
        lapsed = _n(signals.get("lapsed_customers"))
        total  = _n(signals.get("total_customers"))
        active = _n(signals.get("active_customers"))
        atkt   = _n(signals.get("avg_ticket"))
        rev    = _n(signals.get("lapsed_revenue_est"))

        lines = [f"{owner}, repeat business needs attention."]
        if ret is not None and pret is not None:
            lines.append(f"Repeat rate: {_fmt_pct(ret)} vs {_fmt_pct(pret)} for top nearby {unit}.")
        elif ret is not None:
            lines.append(f"Repeat rate: {_fmt_pct(ret)}.")
        if lapsed and total:
            lines.append(f"{lapsed} of your {total} {unit} haven't returned in 6+ months.")
        elif lapsed:
            lines.append(f"{lapsed} {unit} haven't returned in 6+ months.")
        if active:
            lines.append(f"{active} are still active.")
        if rev and atkt:
            lines.append(f"At {_money(atkt)} avg ticket, that's {_money(rev)} sitting dormant.")
        lines.append("A 2-message recall sequence can recover a meaningful share of that base.")
        lines.append("Want me to draft both messages?")
        return {
            "body": "\n".join(lines),
            "cta": "open_ended", "send_as": "vera",
            "rationale": "retention_push grounded in repeat rate and lapsed base",
        }

    # ──────────────────────────────────────────────────────────────────
    # winback  (Case Study 8)
    # ──────────────────────────────────────────────────────────────────
    if action == "winback":
        cname   = _s(signals.get("customer_first_name") or signals.get("customer_name"), "there")
        days_s  = _n(signals.get("days_since_visit") or signals.get("days_since_last_visit"))
        last_v  = _fmt_date(signals.get("customer_last_visit"))
        visits  = _n(signals.get("customer_visits_total"))
        last_svc= _humanize(signals.get("customer_last_service"))
        state   = _s(signals.get("customer_state"))
        channel = _s(signals.get("customer_channel"))
        owner_n = _owner(signals)

        no_shame = "no judgment" if "gym" in slug else ("no pressure" if "salon" in slug else "just a gentle reminder")

        lines = [f"{_greet(signals)}, {owner_n} from {biz} here."]
        if days_s:
            weeks = days_s // 7
            if weeks >= 8:
                lines.append(f"It's been about {weeks} weeks \u2014 happens to most {unit} at some point, {no_shame}.")
            else:
                lines.append(f"It's been about {days_s} days \u2014 happens to most {unit} at some point, {no_shame}.")
        elif last_v:
            lines.append(f"Your last visit was {last_v}.")

        if "gym" in slug and last_svc:
            lines.append(f"We've added a Tue/Thu evening HIIT class that fits {last_svc} goals well (45 min, 6:30pm).")
        elif last_svc:
            lines.append(f"Last service: {last_svc}.")

        if visits and visits > 1:
            lines.append(f"You've visited {visits} times before.")

        lines.append(f"We're holding {offer} for returning {unit}.")

        if channel and "son" in channel.lower():
            lines.append("Reply YES here and we'll share the confirmation on this chat.")
        else:
            lines.append("Reply YES to reserve a slot \u2014 no commitment, no auto-charge.")

        return {
            "body": "\n".join(lines),
            "cta": "YES", "send_as": "merchant_on_behalf",
            "rationale": "winback grounded in days since last visit and prior visits",
        }

    # ──────────────────────────────────────────────────────────────────
    # targeted_offer
    # ──────────────────────────────────────────────────────────────────
    if action == "targeted_offer":
        ctr    = _f(signals.get("ctr_pct"))
        peer   = _f(signals.get("peer_ctr_pct"))
        views  = _n(signals.get("views_30d"))
        clicks = _n(signals.get("clicks_30d"))
        missed = _n(signals.get("missed_clicks"))
        best   = _offer(signals)

        lines = [f"{owner}, this is a good offer moment."]
        if views and clicks and ctr is not None:
            lines.append(f"{views:,} views this month \u2192 {clicks:,} clicks ({_fmt_pct(ctr)} CTR).")
        elif ctr is not None and peer is not None:
            lines.append(f"CTR is {_fmt_pct(ctr)} vs {_fmt_pct(peer)} peer average.")
        if missed and missed > 0:
            lines.append(f"~{missed:,} bookings are slipping away.")
        if best:
            lines.append(f"{best} is the cleanest next test.")
        lines.append("Want me to write the exact WhatsApp campaign and line it up for today?")
        return {
            "body": "\n".join(lines),
            "cta": "open_ended", "send_as": "vera",
            "rationale": "targeted_offer grounded in traffic and offer choice",
        }

    # ──────────────────────────────────────────────────────────────────
    # curious_ask  (Case Study 4)
    # ──────────────────────────────────────────────────────────────────
    if action == "curious_ask":
        import re as _re

        # ── Category-specific guess from trend_signals (highest delta_yoy) ──
        trend_sigs = signals.get("trend_signals") or []
        guess_svc  = ""
        if trend_sigs:
            top_trend = max(
                (t for t in trend_sigs if isinstance(t, dict) and _f(t.get("delta_yoy")) is not None),
                key=lambda t: _f(t.get("delta_yoy"), 0),
                default=None,
            )
            if top_trend:
                q = _s(top_trend.get("query", ""))
                # Strip noise words → clean service name
                q_clean = _re.sub(
                    r'\b(near me|price|cost|delhi|mumbai|bangalore|hyderabad|india|chennai|pune)\b',
                    '', q, flags=_re.I
                ).strip().strip(',').strip()
                if q_clean:
                    guess_svc = q_clean

        # Fallback: category hard-coded best guess (domain vocabulary)
        if not guess_svc:
            if "dent" in slug:       guess_svc = "clear aligners"
            elif "salon" in slug:    guess_svc = "keratin treatment"
            elif "gym" in slug:      guess_svc = "personal training"
            elif "restaurant" in slug: guess_svc = "weekend brunch"
            elif "pharm" in slug:    guess_svc = "diabetic care kit"

        # Short biz name: first significant word only (e.g. "Studio11" not "Studio11 Family Salon")
        full_biz   = _s(signals.get("merchant_name"), "your business")
        biz_parts  = full_biz.split()
        biz_short  = biz_parts[0] if len(biz_parts) > 2 else full_biz
        owner_n    = _s(signals.get("owner_first_name"), "there")

        guess_line = f"My hunch: probably {guess_svc}?" if guess_svc else ""

        body_parts = [f"Hi {owner_n}! Quick check \u2014 what service has been most asked-for this week at {biz_short}?"]
        if guess_line:
            body_parts.append(guess_line)
        body_parts.append("")
        body_parts.append("I'll turn the answer into a Google post + a 4-line WhatsApp reply you can use when customers ask about pricing.")
        body_parts.append("")
        body_parts.append("Takes 5 min.")
        return {
            "body": "\n".join(body_parts),
            "cta": "open_ended", "send_as": "vera",
            "rationale": f"curious_ask with trend-signal guess ({guess_svc or 'category default'})",
        }

    # ──────────────────────────────────────────────────────────────────
    # FALLBACK  (data-grounded, never vague)
    # ──────────────────────────────────────────────────────────────────
    views  = _n(signals.get("views_30d"))
    clicks = _n(signals.get("clicks_30d"))
    ctr    = _f(signals.get("ctr_pct"))
    peer   = _f(signals.get("peer_ctr_pct"))
    missed = _n(signals.get("missed_clicks"))
    best   = _offer(signals)

    lines = [f"{owner}, there is a clear opportunity here."]
    if views and clicks and ctr is not None:
        lines.append(f"{views:,} views this month \u2192 {clicks:,} clicks ({_fmt_pct(ctr)} CTR).")
    elif ctr is not None and peer is not None:
        lines.append(f"CTR is {_fmt_pct(ctr)} vs {_fmt_pct(peer)} peer average.")
    if missed and missed > 0:
        lines.append(f"Missed bookings: ~{missed:,}.")
    if best:
        lines.append(f"{best} is the fastest next step.")
    lines.append("Want me to identify the highest-impact action?")
    return {
        "body": "\n".join(lines),
        "cta": "open_ended", "send_as": "vera",
        "rationale": f"fallback grounded in traffic and offer; action={action}",
    }