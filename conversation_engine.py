import re

AUTO_REPLY_RE = re.compile(
    r"(thank you for contacting|auto.?reply|away message|out of office|"
    r"currently unavailable|we'll get back|we will get back|"
    r"sent from my iphone|outside office hours|busy right now|"
    r"we have received your message|our team will respond|"
    r"this is an automated response|auto generated)",
    re.I,
)

ACCEPT_RE = re.compile(
    r"\b(yes|yeah|sure|ok|okay|done|go ahead|send it|lets do it|let's do it|proceed|"
    r"yes please|sounds good|start|do it|chal|haan|haan ji|theek hai|"
    r"hanji|han|hmm|achha|thik)\b",
    re.I,
)

REJECT_RE = re.compile(
    r"\b(no|not interested|later|stop|unsubscribe|spam|don't message|do not message|"
    r"not now|leave me|mat karo|mat bhejo|band karo|bas|nahi)\b",
    re.I,
)

QUESTION_RE = re.compile(
    r"\b(what|how|when|where|why|which|who|kya|kaise|kab|kahan|kitna|kitne)\b",
    re.I,
)


def detect_intent(msg):
    msg = (msg or "").strip().lower()

    if AUTO_REPLY_RE.search(msg):
        return "auto_reply"
    if REJECT_RE.search(msg):
        return "reject"
    if ACCEPT_RE.search(msg):
        return "accept"
    if "?" in msg or QUESTION_RE.search(msg):
        return "question"
    return "neutral"


def handle_reply(msg):
    text = (msg or "").strip()
    intent = detect_intent(text)

    if intent == "auto_reply":
        return {"action": "end", "rationale": "auto reply detected"}

    if intent == "reject":
        return {"action": "end", "rationale": "merchant rejected or opted out"}

    if intent == "accept":
        return {
            "action": "send",
            "body": "Done — I'm on it. I'll send the next step now.",
            "cta": "open_ended",
            "rationale": "merchant accepted; continue with action",
        }

    if intent == "question":
        return {
            "action": "send",
            "body": "Absolutely — I can handle that. What should I prepare first?",
            "cta": "open_ended",
            "rationale": "answer the question and keep momentum",
        }

    return {
        "action": "wait",
        "wait_seconds": 900,
        "rationale": "neutral reply; back off briefly",
    }