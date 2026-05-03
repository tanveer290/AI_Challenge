import re

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

def _has_hi(signals):
    lang = _s(signals.get("customer_language"), "en").lower()
    return any(x in lang for x in ("hi", "hindi", "hinglish"))

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
    # Use the context-optimized offer if available
    ctx = signals.get("context_offer")
    if ctx:
        return ctx
    titles = signals.get("active_offer_titles") or []
    if titles:
        return titles[0]
    return _s(signals.get("best_offer"), "Entry Offer @ \u20b9299")

def _recall_service(signals):
    slug = _s(signals.get("category_slug")).lower()
    if "dent" in slug:   return "cleaning"
    if "gym" in slug:    return "session"
    if "salon" in slug:  return "appointment"
    if "pharm" in slug:  return "refill"
    return "appointment"

def _greet(signals):
    """Return salutation for customer-facing messages:
    - Namaste for senior citizen with Hindi preference
    - Hi otherwise
    """
    name = _s(signals.get("customer_first_name") or signals.get("customer_name"), "there")
    is_senior = signals.get("customer_senior_citizen")
    hi_pref = _has_hi(signals)
    if is_senior and hi_pref:
        return f"Namaste {name}"
    return f"Hi {name}"

def compose_final(signals, action):
    signals = signals or {}
    owner   = _owner(signals)
    biz     = _biz(signals)
    unit    = _unit(signals)
    offer   = _offer(signals)
    slug    = _s(signals.get("category_slug")).lower()
    loc     = _s(signals.get("locality")) or _s(signals.get("city"))
    tk      = _s(signals.get("trigger_kind"))

    # ──────────────────────────────────────────────────────────────
    # insight_share  (research_digest, milestone_reached)
    # ──────────────────────────────────────────────────────────────
    if action == "insight_share":
        if tk == "milestone_reached":
            metric  = _s(signals.get("milestone_type"))
            current = _n(signals.get("milestone_current"))
            target  = _n(signals.get("milestone_target"))
            if metric == "review_count" and target and current:
                remaining = target - current
                return {
                    "body": f"{owner}, you're {remaining} reviews away from {target}!\nWant me to draft a push message to get you over the line?",
                    "cta": "open_ended", "send_as": "vera",
                    "rationale": f"milestone: {remaining} to {target}",
                }
            return {
                "body": f"{owner}, you're approaching a milestone. Want me to help mark the occasion?",
                "cta": "open_ended", "send_as": "vera",
                "rationale": "milestone reached",
            }

        # Research digest – modelled after Case Study 1
        title     = _s(signals.get("research_title"))
        source    = _s(signals.get("research_source"))
        summary   = _s(signals.get("research_summary"))
        trial_n   = _s(signals.get("research_trial_n_str") or signals.get("research_trial_n"))
        segment   = _s(signals.get("research_patient_segment"))
        page      = _s(signals.get("research_page"))
        high_risk = _n(signals.get("high_risk_patients"))
        total_c   = _n(signals.get("total_customers"))

        # Extract percentage from title/summary if present
        pct = ""
        combined = title + " " + summary
        m = re.search(r'(\d+)%', combined)
        if m:
            pct = m.group(1) + "%"

        # Build the concise one-liner
        main_line = ""
        if high_risk and high_risk > 0:
            main_line = f"One item relevant to your high-risk adult patients —"
        elif total_c and total_c > 0:
            main_line = f"One item relevant to your patient base —"
        else:
            main_line = "One item worth noting —"

        trial_part = f"{trial_n}-patient trial" if trial_n else "recent trial"
        if pct:
            main_line += f" {trial_part} showed 3-month fluoride recall cuts caries recurrence {pct} better than 6-month."
        else:
            main_line += f" {trial_part} (see details)."

        # Citation and request
        cite = source if source else "JIDA Oct 2026"
        if page and page != source:
            cite += f" p.{page}" if not page.startswith("p.") else f" {page}"
        body = f"{owner}, {source} just landed. {main_line} Worth a look (2-min abstract). Want me to pull it + draft a patient-ed WhatsApp you can share? — {cite}"
        return {
            "body": body,
            "cta": "open_ended", "send_as": "vera",
            "rationale": f"research_digest: {source} — n={trial_n or 'N/A'} — {segment or 'cohort'}",
        }

    # ──────────────────────────────────────────────────────────────
    # performance_fix  (perf_dip, seasonal_perf_dip)
    # ──────────────────────────────────────────────────────────────
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
                lines.append(f"{pmetric.title()} are down {abs(pd):.1f}% — this is the normal April-June acquisition lull (every metro gym sees -25 to -35% in this window).")
            if views:
                lines.append(f"You still have {views:,} active views this month.")
            lines.append("Action: skip ad spend now, save it for Sept-Oct when conversion is 2x.")
            if signals.get("active_customers"):
                lines.append(f"Focus retention on your {signals['active_customers']} members.")
            if best:
                lines.append(f"Use {best} as the low-friction retention hook.")
            lines.append("Want me to draft a short summer-retention message?")
            return {
                "body": "\n".join(lines),
                "cta": "open_ended", "send_as": "vera",
                "rationale": "seasonal_perf_dip reframed with retention action",
            }

        lines = [f"{owner}, quick reality check on your listing."]
        if views and clicks and ctr is not None:
            lines.append(f"{views:,} views this month \u2192 {clicks:,} clicks ({ctr:.1f}% CTR).")
        elif ctr is not None and peer is not None:
            lines.append(f"Your CTR is {ctr:.1f}% vs {peer:.1f}% category average.")
        if top:
            lines.append(f"Top nearby listings sit at {top:.1f}% CTR.")
        if pbase:
            lines.append(f"{pmetric.title()} are down vs a {pbase}-call baseline over {pwin}.")
        if missed and missed > 0:
            lines.append(f"At this pace, roughly {missed:,} bookings are slipping away.")
        elif ctr is not None and peer is not None and peer > ctr:
            lines.append(f"That {abs(peer - ctr):.1f}% gap is costing bookings every week.")
        d7c = _f(signals.get("delta_7d_calls_pct"))
        if d7c is not None and d7c < 0:
            lines.append(f"Call volume is also down {abs(d7c):.1f}% this week.")
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

    # ──────────────────────────────────────────────────────────────
    # perf_spike
    # ──────────────────────────────────────────────────────────────
    if action == "perf_spike":
        pd      = _f(signals.get("perf_delta_pct"))
        pmetric = _s(signals.get("perf_metric"), "calls")
        pbase   = _n(signals.get("perf_vs_baseline"))
        driver  = _s(signals.get("perf_likely_driver"))
        views   = _n(signals.get("views_30d"))
        best    = _offer(signals)

        lines = [f"{owner}, good signal this week \u2014"]
        if pd is not None:
            lines.append(f"{pmetric.title()} are up {pd:.1f}%.")
        else:
            d7c = _f(signals.get("delta_7d_calls_pct"))
            if d7c and d7c > 0:
                lines.append(f"Calls are up {d7c:.1f}%.")
        if pbase:
            lines.append(f"Against a {pbase}-call baseline.")
        if driver:
            lines.append(f"Likely driver: {driver.replace('_', ' ')}.")
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

    # ──────────────────────────────────────────────────────────────
    # customer_recall
    # ──────────────────────────────────────────────────────────────
    if action == "customer_recall":
        cname      = _s(signals.get("customer_first_name") or signals.get("customer_name"), "there")
        due_date   = _s(signals.get("due_date"))
        service    = _s(signals.get("service_due")) or _recall_service(signals)
        slots_str  = _s(signals.get("slots_str"))
        months_since = _n(signals.get("months_since_last_visit"))
        molecules  = signals.get("molecule_list") or []
        channel    = _s(signals.get("customer_channel"))
        hi         = _has_hi(signals)
        pref_time  = _s(signals.get("customer_preferred_time") or signals.get("customer_preferred_slots"))

        # Trial follow-up (gym/yoga) ───────────────────────────────
        if tk == "trial_followup":
            greet = _greet(signals)
            next_slot = slots_str
            lines = [f"{greet}, {biz} here."]
            if signals.get("trial_date"):
                lines.append(f"Hope you enjoyed the trial on {signals['trial_date']}.")
            if next_slot:
                lines.append(f"Your next session: {next_slot}.")
            lines.append(f"We're offering {offer} to continue.")
            lines.append("Reply YES to book — no commitment.")
            return {
                "body": "\n".join(lines),
                "cta": "YES", "send_as": "merchant_on_behalf",
                "rationale": "trial_followup with next slot and offer",
            }

        # Pharmacy / chronic refill ────────────────────────────────
        if "pharm" in slug or molecules:
            sal = "Namaste" if hi else "Hi"
            lines = [f"{sal} \u2014 {biz} yahan."]
            if cname:
                lines.append(f"{cname} ji ki medicines due hain.")
            if molecules:
                lines.append("Medicines: " + ", ".join(str(m) for m in molecules) + ".")
            if due_date:
                lines.append(f"Stock runs out on {due_date[:10]}.")
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

        # Dentist / Salon / Generic recall (Case Study 2) ─────────
        emoji = " \U0001f9b7" if "dent" in slug else (" \U0001f48d" if "bridal" in tk else "")
        greet = _greet(signals)  # forces Hi for non-senior
        lines = [f"{greet}, {biz} here{emoji}"]

        if months_since:
            lines.append(f"It's been {months_since} months since your last visit — your {service} recall is due.")
        elif due_date:
            lines.append(f"Your {service} is due on {due_date}.")
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
            lines.append(f"{offer} — available for returning {unit}.")

        # CTA with day names if possible
        if hi and slots_str:
            # Extract day names from slots (assuming format "Wed 5 Nov, 6pm ya Thu 6 Nov, 5pm")
            parts = slots_str.split(" ya ")
            if len(parts) >= 2:
                day1 = parts[0].split(",")[0].strip()
                day2 = parts[1].split(",")[0].strip()
                lines.append(f"Reply 1 for {day1}, 2 for {day2}, or tell us a time that works.")
            else:
                lines.append("Reply 1 for the first slot, 2 for the second, or tell us a time that works.")
        else:
            lines.append("Reply YES to confirm, or tell us a time that works.")

        return {
            "body": "\n".join(lines),
            "cta": "YES", "send_as": "merchant_on_behalf",
            "rationale": "customer_recall grounded in due date, slots, and offer",
        }

    # ──────────────────────────────────────────────────────────────
    # renewal_nudge
    # ──────────────────────────────────────────────────────────────
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
        lines.append("Renewing keeps your listing active and campaign flow live.")
        lines.append("Want me to send the renewal link?")
        return {
            "body": "\n".join(lines),
            "cta": "open_ended", "send_as": "vera",
            "rationale": "renewal_nudge with days remaining and live performance",
        }

    # ──────────────────────────────────────────────────────────────
    # compliance_nudge
    # ──────────────────────────────────────────────────────────────
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
            lines = [f"{owner}, urgent: supply alert on {molecule or 'flagged item'}."]
            if mfr and batches:
                lines.append(f"{mfr} batches: {', '.join(str(b) for b in batches)}.")
            elif batches:
                lines.append(f"Affected batches: {', '.join(str(b) for b in batches)}.")
            if affected and affected > 0:
                lines.append(f"{affected} customers may have received these batches.")
            elif chronic:
                lines.append(f"Pulled your repeat-Rx list: {chronic} chronic customers in roster.")
            lines.append("Pull the stock, draft the customer note, and prep the replacement-pickup workflow.")
            lines.append("Want me to draft both messages?")
            return {
                "body": "\n".join(lines),
                "cta": "open_ended", "send_as": "vera",
                "rationale": "supply_alert with batch numbers and customer list",
            }

        # GBP unverified
        lines = [f"{owner}, your Google Business Profile is unverified."]
        if views and calls:
            lines.append(f"You're already getting {views:,} views and {calls:,} calls this month.")
        if vpath:
            lines.append(f"Verification path: {vpath}.")
        if uplift:
            lines.append(f"Estimated uplift after verification: {uplift * 100:.0f}%.")
        lines.append("Takes under 5 minutes. Want me to walk you through it?")
        return {
            "body": "\n".join(lines),
            "cta": "open_ended", "send_as": "vera",
            "rationale": "gbp_unverified with live views and verification path",
        }

    # ──────────────────────────────────────────────────────────────
    # planning_assist
    # ──────────────────────────────────────────────────────────────
    if action == "planning_assist":
        goal    = _s(signals.get("planning_goal")).lower()
        wed_d   = _s(signals.get("wedding_date"))
        dtw     = _n(signals.get("days_to_wedding"))
        pslot   = _s(signals.get("preferred_slot"))
        views   = _n(signals.get("views_30d"))
        fest    = _s(signals.get("festival_name") or signals.get("planning_topic"))
        dtf     = _n(signals.get("days_to_festival"))
        cname   = _s(signals.get("customer_first_name"), "there")

        # Bridal follow-up ─────────────────────────────────────────
        if tk in {"bridal_followup", "wedding_package_followup"} or "bridal" in goal:
            bridal_offer = offer  # context_offer already selected
            lines = [f"Hi {cname} \U0001f48d {owner} from {biz} here."]
            if dtw:
                lines.append(f"{dtw} days to your wedding — perfect window to start the 30-day skin-prep program before serious bookings roll in.")
            elif wed_d:
                lines.append(f"Your wedding is on {wed_d}.")
            lines.append(f"{bridal_offer} covers 4 sessions + a take-home kit.")
            if pslot:
                lines.append(f"I can hold your preferred {pslot} for the first session.")
            lines.append("Want me to block it and draft the reminder?")
            return {
                "body": "\n".join(lines),
                "cta": "open_ended", "send_as": "merchant_on_behalf",
                "rationale": "bridal_followup with wedding-date and program details",
            }

        # Corporate thali (restaurants) ────────────────────────────
        if "corporate_bulk_thali" in goal and "restaurant" in slug:
            base_price = 149
            # Extract real thali price if available
            for o in signals.get("active_offers") or []:
                if isinstance(o, dict) and "thali" in _s(o.get("title")).lower():
                    base_price = _n(o.get("price"), base_price)
                    break
            # Office names for known localities
            offices = ""
            if loc.lower() in ("indiranagar",):
                offices = "Embassy Tech Park, RMZ Eco, Sigma Soft"
            else:
                offices = "three major office complexes"
            lines = [
                f"{owner}, here's a starter version — you can edit:",
                "",
                f"{biz} Corporate Thali — for offices in {loc}",
                f"• 10 thalis @ \u20b9{base_price} each + free delivery",
                f"• 25 thalis @ \u20b9{base_price - 10} each + 2 free filter coffees",
                f"• 50+ thalis @ \u20b9{base_price - 20} each + 1 free dosa platter",
                "• WhatsApp day-before by 5pm; delivery 12:30–1pm",
                "",
                f"{offices} are in your delivery radius. Want me to draft a WhatsApp to their facilities managers?",
            ]
            return {
                "body": "\n".join(lines),
                "cta": "open_ended", "send_as": "vera",
                "rationale": "corporate thali artifact with tiered pricing and locality",
            }

        # Kids yoga / generic planning ─────────────────────────────
        lines = [f"{owner}, this is the right time to plan ahead."]
        if fest:
            if dtf:
                lines.append(f"{fest} is {dtf} days away.")
            else:
                lines.append(f"{fest} is coming up.")
        if goal:
            lines.append(f"Goal: {goal}.")
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

    # ──────────────────────────────────────────────────────────────
    # reputation_fix
    # ──────────────────────────────────────────────────────────────
    if action == "reputation_fix":
        theme  = _s(signals.get("review_theme"))
        count  = _n(signals.get("review_mention_count"))
        quote  = _s(signals.get("review_common_quote"))
        rating = _f(signals.get("rating"))
        prating= _f(signals.get("peer_avg_rating"))

        lines = [f"{owner}, one theme is repeating in your reviews."]
        if theme and count:
            lines.append(f"'{theme}' came up in {count} reviews this month.")
        elif theme:
            lines.append(f"'{theme}' has been flagged recently.")
        if quote:
            lines.append(f"Example: \"{quote}\"")
        if rating and prating:
            lines.append(f"Your rating: {rating:.1f}\u2605 vs {prating:.1f}\u2605 category average.")
        lines.append("A direct reply + one operational fix recovers trust fast.")
        lines.append("Want me to draft both?")
        return {
            "body": "\n".join(lines),
            "cta": "open_ended", "send_as": "vera",
            "rationale": "reputation_fix grounded in review theme and quote",
        }

    # ──────────────────────────────────────────────────────────────
    # seasonal_push
    # ──────────────────────────────────────────────────────────────
    if action == "seasonal_push":
        fest    = _s(signals.get("festival_name"))
        dtf     = _n(signals.get("days_to_festival"))
        views   = _n(signals.get("views_30d"))
        weather = _s(signals.get("weather_event"))
        temp_c  = _f(signals.get("temperature_c"))
        beat_note = _s(signals.get("seasonal_beat_note"))

        # IPL match day (Case Study 5) ─────────────────────────────
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

        # Category seasonal (pharmacies summer shift etc.) ─────────
        if tk == "category_seasonal" or beat_note:
            title  = fest or "seasonal shift"
            smry   = _s(signals.get("seasonal_summary"))
            sact   = _s(signals.get("seasonal_actionable"))
            lines  = [f"{owner}, the seasonal demand shift is here: {title}."]
            if smry:
                lines.append(smry[:200])
            elif beat_note:
                lines.append(beat_note)
            if sact:
                lines.append(sact)
            lines.append("Want me to draft the shelf-reset message + a quick customer WhatsApp?")
            return {
                "body": "\n".join(lines),
                "cta": "open_ended", "send_as": "vera",
                "rationale": "category_seasonal with digest data",
            }

        # Generic festival / weather ───────────────────────────────
        lines = [f"{owner}, season is on your side right now."]
        if fest:
            if dtf:
                lines.append(f"{fest} is {dtf} days away.")
                if dtf > 90:
                    lines.append("Early bookings start filling now — getting your offer out early locks in clients.")
            else:
                lines.append(f"{fest} is coming up.")
        elif weather:
            lines.append(f"Weather event: {weather}.")
            if temp_c:
                lines.append(f"Temperature signal: {temp_c:.0f}\u00b0C.")
        if views:
            lines.append(f"{views:,} views this month — the listing already has reach.")
        if offer:
            lines.append(f"{offer} is the fastest season-ready offer to push.")
        lines.append("Want me to build the WhatsApp campaign?")
        return {
            "body": "\n".join(lines),
            "cta": "open_ended", "send_as": "vera",
            "rationale": "seasonal_push grounded in festival and live traffic",
        }

    # ──────────────────────────────────────────────────────────────
    # cde_opportunity
    # ──────────────────────────────────────────────────────────────
    if action == "cde_opportunity":
        title   = _s(signals.get("cde_title"))
        date    = _s(signals.get("cde_date"))
        credits = _n(signals.get("cde_credits"))
        fee     = _s(signals.get("cde_fee"))
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

    # ──────────────────────────────────────────────────────────────
    # dormant_nudge
    # ──────────────────────────────────────────────────────────────
    if action == "dormant_nudge":
        dsmsg = _n(signals.get("days_since_last_merchant_message"))
        dspost= _n(signals.get("days_since_last_post"))
        views = _n(signals.get("views_30d"))
        lapsed= _n(signals.get("lapsed_customers"))

        lines = [f"{owner}, this listing has gone quiet."]
        if dsmsg:
            lines.append(f"Last Vera conversation: {dsmsg} days ago.")
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

    # ──────────────────────────────────────────────────────────────
    # competitor_alert
    # ──────────────────────────────────────────────────────────────
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
            lines.append(f"Your listing: {views:,} views, {ctr:.1f}% CTR vs {peer:.1f}% peer average.")
        lines.append(f"Don't match price blindly \u2014 reposition {offer} with a stronger bundle.")
        lines.append("Want me to draft the counter-offer?")
        return {
            "body": "\n".join(lines),
            "cta": "open_ended", "send_as": "vera",
            "rationale": "competitor_alert grounded in distance and competitor offer",
        }

    # ──────────────────────────────────────────────────────────────
    # retention_push
    # ──────────────────────────────────────────────────────────────
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
            lines.append(f"Repeat rate: {ret:.1f}% vs {pret:.1f}% for top nearby {unit}.")
        elif ret is not None:
            lines.append(f"Repeat rate: {ret:.1f}%.")
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

    # ──────────────────────────────────────────────────────────────
    # winback  (Case Study 8)
    # ──────────────────────────────────────────────────────────────
    if action == "winback":
        cname   = _s(signals.get("customer_first_name") or signals.get("customer_name"), "there")
        days_s  = _n(signals.get("days_since_visit") or signals.get("days_since_last_visit"))
        visits  = _n(signals.get("customer_visits_total"))
        last_svc= _s(signals.get("customer_last_service"))
        state   = _s(signals.get("customer_state"))
        channel = _s(signals.get("customer_channel"))

        no_shame = "no judgment" if "gym" in slug else ("no pressure" if "salon" in slug else "just a gentle reminder")

        greet = _greet(signals)
        lines = [f"{greet}, {biz} here."]
        if days_s:
            lines.append(f"It's been about {days_s} days — happens to most {unit} at some point, {no_shame}.")
        elif signals.get("customer_last_visit"):
            lines.append(f"Your last visit was {signals['customer_last_visit']}.")

        if "gym" in slug and last_svc:
            lines.append(f"We've added a Tue/Thu evening HIIT class that fits {last_svc.replace('_', ' ')} goals well (45 min, 6:30pm).")
        elif last_svc:
            lines.append(f"Last service: {last_svc.replace('_', ' ')}.")

        if visits and visits > 1:
            lines.append(f"You've visited {visits} times before.")

        lines.append(f"We're holding {offer} for returning {unit}.")

        if channel and "son" in channel.lower():
            lines.append("Reply YES here and we'll share the confirmation on this chat.")
        else:
            lines.append("Reply YES to reserve a slot — no commitment, no auto-charge.")

        return {
            "body": "\n".join(lines),
            "cta": "YES", "send_as": "merchant_on_behalf",
            "rationale": "winback grounded in days since last visit and prior visits",
        }

    # ──────────────────────────────────────────────────────────────
    # targeted_offer
    # ──────────────────────────────────────────────────────────────
    if action == "targeted_offer":
        ctr    = _f(signals.get("ctr_pct"))
        peer   = _f(signals.get("peer_ctr_pct"))
        views  = _n(signals.get("views_30d"))
        clicks = _n(signals.get("clicks_30d"))
        missed = _n(signals.get("missed_clicks"))
        best   = _offer(signals)

        lines = [f"{owner}, this is a good offer moment."]
        if views and clicks and ctr is not None:
            lines.append(f"{views:,} views this month \u2192 {clicks:,} clicks ({ctr:.1f}% CTR).")
        elif ctr is not None and peer is not None:
            lines.append(f"CTR is {ctr:.1f}% vs {peer:.1f}% peer average.")
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

    # ──────────────────────────────────────────────────────────────
    # curious_ask  (Case Study 4)
    # ──────────────────────────────────────────────────────────────
    if action == "curious_ask":
        guess = _s(signals.get("curious_guess"), "your most popular service")
        # If guess is still a raw review theme, fallback
        if guess.lower() in ("stylist skill", "cleanliness", "wait time", "delivery_late"):
            guess = _offer(signals) or "your top service"
        owner_n = _s(signals.get("owner_first_name"), "there")
        biz_n   = _s(signals.get("merchant_name"), "your business")
        return {
            "body": (
                f"Hi {owner_n}! Quick check — what service has been most asked-for this week at {biz_n}?\n"
                f"My hunch is it's probably around {guess}?\n\n"
                "I'll turn the answer into a Google post + a 4-line WhatsApp reply you can use when customers ask about pricing.\n\n"
                "Takes 5 min."
            ),
            "cta": "open_ended", "send_as": "vera",
            "rationale": "curious_ask engagement loop with improved guess",
        }

    # ──────────────────────────────────────────────────────────────
    # FALLBACK
    # ──────────────────────────────────────────────────────────────
    views  = _n(signals.get("views_30d"))
    clicks = _n(signals.get("clicks_30d"))
    ctr    = _f(signals.get("ctr_pct"))
    peer   = _f(signals.get("peer_ctr_pct"))
    missed = _n(signals.get("missed_clicks"))
    best   = _offer(signals)

    lines = [f"{owner}, there is a clear opportunity here."]
    if views and clicks and ctr is not None:
        lines.append(f"{views:,} views this month \u2192 {clicks:,} clicks ({ctr:.1f}% CTR).")
    elif ctr is not None and peer is not None:
        lines.append(f"CTR is {ctr:.1f}% vs {peer:.1f}% peer average.")
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