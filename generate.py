#!/usr/bin/env python3
"""Generate a SIMULATED 5,000-call log for the ji context case demo.

All rows are fictional. There are no real calls, customers or transcripts.
Re-run with:  python generate.py
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

SEED = 42
N_CALLS = 5000
OUT = Path(__file__).resolve().parent

DATE_START = date(2026, 9, 16)
DATE_END = date(2026, 11, 24)

WORST_STT, WORST_LLM, WORST_TTS = "STT-B", "LLM-A", "TTS-B"
WORST_COMBO = f"{WORST_STT} / {WORST_LLM} / {WORST_TTS}"

AMBIGUOUS_PAIRINGS = ("hun ji", "ji?", "achha ji?", "bas ji")
CONSENT_OUTCOMES = {
    "collections": "payment_scheduled",
    "insurance_renewal": "renewal_confirmed",
    "delivery_support": "slot_booked",
    "recruitment": "slot_booked",
}
CORRECT_OUTCOMES = {
    "yes": None,  # filled from use_case
    "no": "declined",
    "unsure": "clarification_needed",
    "question": "clarification_needed",
    "defer": "deferred",
    "stop": "stop_requested",
    "listening": "information_given",
    "acknowledge": "information_given",
}

# Region → typical dialect (a little mixing is added later).
REGION_DIALECT = {
    "Punjab": "Punjabi",
    "Haryana": "Haryanvi",
    "Bihar": "Bhojpuri",
    "Rajasthan": "Marwari",
    "Telangana": "Hyderabadi",
    "Delhi": "standard Hindi",
    "Uttar Pradesh": "standard Hindi",
}

CLIENTS = {
    "XYZ Finance": "collections",
    "Apex Credit": "collections",
    "ShieldSure Insurance": "insurance_renewal",
    "CartBay Retail": "delivery_support",
    "HireLink Staffing": "recruitment",
}

STT_PROVIDERS = ("STT-A", "STT-B", "STT-C")
LLM_PROVIDERS = ("LLM-A", "LLM-B")
TTS_PROVIDERS = ("TTS-A", "TTS-B")

TONE_STACK = ("rising", "rushed", "sarcastic", "muffled")

# Short, realistic Roman-script Hinglish, keyed by pairing then dialect.
# A leading "*" list is the default pool when a dialect has no of its own.
UTTERANCES = {
    "haan ji": {
        "*": [
            "Haan ji, theek hai",
            "Haan ji, kar dena",
            "Haan ji, ho jayega",
            "Haan ji, samajh gaya",
            "Haan ji, aaj kar doonga",
            "Haan ji, theek hai bolo",
        ],
        "Haryanvi": [
            "Haan ji, dekh lyange",
            "Haan ji, kar denge soch ke",
            "Haan ji, time se ho javega",
        ],
        "Bhojpuri": [
            "Haan ji, ho jaai",
            "Haan ji, kar debo",
        ],
        "Hyderabadi": [
            "Haau ji, theek hai",
            "Haan ji, kar deta",
        ],
    },
    "nahi ji": {
        "*": [
            "Nahi ji, abhi nahi ho payega",
            "Nahi ji, baad mein dekhenge",
            "Nahi ji, is hafte possible nahi",
            "Nahi ji, mat schedule karna",
            "Nahi ji, abhi paisa nahi hai",
            "Nahi ji, next month dekhenge",
        ],
        "Punjabi": [
            "Nahi ji, ajj nahi ho sakda",
            "Nahi ji, thoda time chahida",
        ],
        "Haryanvi": [
            "Nahi ji, abhi nahi ho sake",
            "Nahi ji, baad mein baat karenge",
        ],
    },
    "hun ji": {
        "*": [
            "Hun ji",
            "Hun ji...",
            "Hun ji, bolo",
            "Hun ji, sun raha hoon",
        ],
        "Punjabi": [
            "Hun ji",
            "Hun ji...",
            "Hun ji bolo",
            "Hun ji, sun raha haan",
            "Hun ji, samajh gaya, bolo",
            "Hun ji, aa raha hai signal",
        ],
    },
    "ji?": {
        "*": [
            "Ji?",
            "Ji? Ke keh rahe",
            "Ji, samajh nahi aaya",
            "Ji? Phir se boliye",
            "Ji? Line cut ho rahi hai",
            "Ji, kya kaha aapne",
        ],
        "Punjabi": [
            "Ji? Ke keh rahe",
            "Ji? Dobara dasso",
            "Ji, sunai nahi ditta",
        ],
        "Bhojpuri": [
            "Ji? Ka kahiye",
            "Ji, samajh nahi aail",
        ],
        "Hyderabadi": [
            "Ji? Kya bola",
            "Ji? Phir se bolo na",
        ],
    },
    "achha ji?": {
        "*": [
            "Achha ji?",
            "Achha ji? Aaj hi?",
            "Achha ji, itna jaldi?",
            "Achha ji? Itna amount?",
            "Achha ji, sure hai kya",
            "Achha ji? Main soch loon",
        ],
        "Haryanvi": [
            "Achha ji? Aaj hi karna hai?",
            "Achha ji, dekh lyange pehle",
        ],
        "Marwari": [
            "Achha ji? Aaj hi hukam hai?",
            "Achha ji, thoda sochun",
        ],
        "Hyderabadi": [
            "Achha ji? Aaj hi kya",
            "Achha ji, dekhte ek baar",
        ],
    },
    "bas ji": {
        "*": [
            "Bas ji",
            "Bas ji, theek hai",
            "Bas ji, ab mat phone karo",
            "Bas ji, baad mein baat karenge",
            "Bas ji, ho gaya meri taraf se",
            "Bas ji, ab nahi sunna",
        ],
        "Punjabi": [
            "Bas ji, hun na phone karo",
            "Bas ji, ho gaya",
        ],
        "Bhojpuri": [
            "Bas ji, ab na call kariha",
            "Bas ji, ho gail",
        ],
    },
    "ji ji ji": {
        "*": [
            "Ji ji ji",
            "Ji ji ji, jaldi bolo",
            "Ji ji, pata hai mujhe",
            "Ji ji ji, aage badho",
            "Ji ji, haan pata hai",
            "Ji ji ji, time nahi hai",
        ],
        "Punjabi": [
            "Ji ji ji, jaldi dasso",
            "Ji ji, pata hai yaar",
        ],
        "Haryanvi": [
            "Ji ji ji, jaldi batao",
            "Ji ji, pata se",
        ],
    },
}

# A few "ji-only" forms so the booking-after-short-reply question has clean hits.
JI_ONLY = {
    "haan ji": ["Haan ji", "Haan ji."],
    "nahi ji": ["Nahi ji", "Nahi ji."],
    "hun ji": ["Hun ji", "Hun ji.", "Hun ji..."],
    "ji?": ["Ji?", "Ji"],
    "achha ji?": ["Achha ji?", "Achha ji?"],
    "bas ji": ["Bas ji", "Bas ji."],
    "ji ji ji": ["Ji ji ji", "Ji ji ji."],
}


def pick_utterance(rng: np.random.Generator, pairing: str, dialect: str, ji_only: bool) -> str:
    if ji_only:
        return str(rng.choice(JI_ONLY[pairing]))
    pool = UTTERANCES[pairing]
    options = pool.get(dialect, []) + pool["*"]
    return str(rng.choice(options))


def intent_for_pairing(rng: np.random.Generator, pairing: str, dialect: str) -> str:
    """True speaker intent. Ambiguous pairings are almost never a hard yes."""
    if pairing == "haan ji":
        # Haryanvi "dekh lyange" and similar soft yeses are not commitments.
        if dialect in {"Haryanvi", "Bhojpuri", "Hyderabadi", "Marwari"}:
            return str(rng.choice(["yes", "defer", "acknowledge"], p=[0.45, 0.35, 0.20]))
        return str(rng.choice(["yes", "defer"], p=[0.88, 0.12]))
    if pairing == "nahi ji":
        return str(rng.choice(["no", "defer", "stop"], p=[0.80, 0.15, 0.05]))
    if pairing == "hun ji":
        return str(rng.choice(["listening", "acknowledge"], p=[0.85, 0.15]))
    if pairing == "ji?":
        return "question"
    if pairing == "achha ji?":
        return str(rng.choice(["unsure", "question", "defer"], p=[0.50, 0.30, 0.20]))
    if pairing == "bas ji":
        return str(rng.choice(["stop", "defer"], p=[0.80, 0.20]))
    # ji ji ji
    return str(rng.choice(["acknowledge", "unsure", "yes"], p=[0.60, 0.25, 0.15]))


def correct_outcome(use_case: str, intent: str) -> str:
    if intent == "yes":
        return CONSENT_OUTCOMES[use_case]
    return CORRECT_OUTCOMES[intent]


def date_range() -> list[date]:
    days = []
    d = DATE_START
    while d <= DATE_END:
        days.append(d)
        d += timedelta(days=1)
    return days


def sample_dates(rng: np.random.Generator, n: int) -> list[date]:
    days = date_range()
    # Collections-style weekday weighting; Sundays are light.
    weights = np.array([0.22 if d.weekday() == 6 else 1.0 for d in days], dtype=float)
    weights /= weights.sum()
    idx = rng.choice(len(days), size=n, replace=True, p=weights)
    return [days[i] for i in idx]


def max_complaints_in_10_day_window(complaint_dates: list[date]) -> int:
    if not complaint_dates:
        return 0
    start, end = min(complaint_dates), max(complaint_dates)
    max_c = 0
    d = start
    while d <= end:
        window_end = d + timedelta(days=9)  # inclusive 10-day window
        c = sum(1 for x in complaint_dates if d <= x <= window_end)
        max_c = max(max_c, c)
        d += timedelta(days=1)
    return max_c


def planted_retry_loops() -> list[dict]:
    """Exactly three identifiable retry loops. The error repeats on every attempt.

    Loop 1 mirrors the case: Punjab, XYZ Finance, 'hun ji', worst provider combo.
    """
    rows: list[dict] = []

    def add(
        caller_id: str,
        dates: list[date],
        retries: list[int],
        client: str,
        region: str,
        dialect: str,
        pairing: str,
        utterances: list[str],
        tones: list[str],
        use_case: str,
        true_intent: str,
        call_prefix: str,
    ) -> None:
        for i, (dt, ret, utt, tone) in enumerate(zip(dates, retries, utterances, tones), start=1):
            rows.append(
                {
                    "call_id": f"{call_prefix}-{i:02d}",
                    "date": dt,
                    "caller_id": caller_id,
                    "client": client,
                    "use_case": use_case,
                    "region": region,
                    "dialect": dialect,
                    "provider_stt": WORST_STT,
                    "provider_llm": WORST_LLM,
                    "provider_tts": WORST_TTS,
                    "provider_combo": WORST_COMBO,
                    "caller_utterance": utt,
                    "ji_pairing": pairing,
                    "tone_flag": tone,
                    "signal_drop": True,
                    "partial_reply": True,
                    "retries": ret,
                    "agent_outcome": CONSENT_OUTCOMES[use_case],
                    "true_intent": true_intent,
                    "wrong_consent": True,
                    "complaint": False,
                    "complaint_date": None,
                }
            )

    # Loop 1 — Gurpreet-style collections call, Punjab. 4 attempts, 29–30 Sep.
    add(
        caller_id="CLR-1001",
        dates=[date(2026, 9, 29), date(2026, 9, 29), date(2026, 9, 30), date(2026, 9, 30)],
        retries=[1, 2, 3, 4],
        client="XYZ Finance",
        region="Punjab",
        dialect="Punjabi",
        pairing="hun ji",
        utterances=[
            "Hun ji...",
            "Ji, ke keh rahe...",
            "Ji, main jaanta hoon, par... 2 din aur... lag jayenge ji",
            "Hun ji, sun raha haan",
        ],
        tones=["soft", "rising", "muffled", "rushed"],
        use_case="collections",
        true_intent="listening",
        call_prefix="CALL-LOOP1",
    )
    # The last attempt of loop 1 becomes one of the five complaints.
    rows[-1]["complaint"] = True
    rows[-1]["complaint_date"] = date(2026, 10, 1)

    # Loop 2 — Haryana, soft "achha ji?" read as a renewal yes. 3 attempts, mid-Oct.
    add(
        caller_id="CLR-1002",
        dates=[date(2026, 10, 12), date(2026, 10, 13), date(2026, 10, 13)],
        retries=[2, 3, 4],
        client="ShieldSure Insurance",
        region="Haryana",
        dialect="Haryanvi",
        pairing="achha ji?",
        utterances=[
            "Achha ji? Aaj hi karna hai?",
            "Achha ji, dekh lyange pehle",
            "Ji? Line cut ho rahi hai",
        ],
        tones=["rising", "soft", "muffled"],
        use_case="insurance_renewal",
        true_intent="unsure",
        call_prefix="CALL-LOOP2",
    )
    # Third utterance is still an unsure / "what?" turn; keep pairing consistent.
    rows[-1]["ji_pairing"] = "achha ji?"
    rows[-1]["caller_utterance"] = "Achha ji? Signal nahi aa raha"

    # Loop 3 — Bihar, "ji?" (sorry, what?) booked as a delivery slot. 3 attempts, early Nov.
    add(
        caller_id="CLR-1003",
        dates=[date(2026, 11, 4), date(2026, 11, 4), date(2026, 11, 5)],
        retries=[2, 3, 4],
        client="CartBay Retail",
        region="Bihar",
        dialect="Bhojpuri",
        pairing="ji?",
        utterances=[
            "Ji? Ka kahiye",
            "Ji, samajh nahi aail",
            "Ji? Phir se boliye",
        ],
        tones=["rising", "muffled", "rising"],
        use_case="delivery_support",
        true_intent="question",
        call_prefix="CALL-LOOP3",
    )
    return rows


def planted_complaints() -> list[dict]:
    """Four further complaints, dated so no 10-day window ever has 3+ (loop 1 already has one)."""
    specs = [
        # complaint 2: 8 days after loop-1 complaint (window holds 2, under the TRAI trigger)
        dict(
            call_id="CALL-CMP-02",
            date=date(2026, 10, 7),
            caller_id="CLR-2002",
            client="XYZ Finance",
            use_case="collections",
            region="Telangana",
            dialect="Hyderabadi",
            ji_pairing="achha ji?",
            caller_utterance="Achha ji, dekhte ek baar",
            tone_flag="soft",
            true_intent="defer",
            complaint_date=date(2026, 10, 9),
        ),
        # complaint 3
        dict(
            call_id="CALL-CMP-03",
            date=date(2026, 10, 22),
            caller_id="CLR-2003",
            client="Apex Credit",
            use_case="collections",
            region="Rajasthan",
            dialect="Marwari",
            ji_pairing="bas ji",
            caller_utterance="Bas ji, ab mat phone karo",
            tone_flag="rushed",
            true_intent="stop",
            complaint_date=date(2026, 10, 24),
        ),
        # complaint 4
        dict(
            call_id="CALL-CMP-04",
            date=date(2026, 11, 6),
            caller_id="CLR-2004",
            client="XYZ Finance",
            use_case="collections",
            region="Bihar",
            dialect="Bhojpuri",
            ji_pairing="ji?",
            caller_utterance="Ji, samajh nahi aail",
            tone_flag="rising",
            true_intent="question",
            complaint_date=date(2026, 11, 8),
        ),
        # complaint 5
        dict(
            call_id="CALL-CMP-05",
            date=date(2026, 11, 18),
            caller_id="CLR-2005",
            client="HireLink Staffing",
            use_case="recruitment",
            region="Delhi",
            dialect="standard Hindi",
            ji_pairing="ji?",
            caller_utterance="Ji? Phir se boliye",
            tone_flag="rising",
            true_intent="question",
            complaint_date=date(2026, 11, 20),
        ),
    ]
    rows = []
    for s in specs:
        rows.append(
            {
                "call_id": s["call_id"],
                "date": s["date"],
                "caller_id": s["caller_id"],
                "client": s["client"],
                "use_case": s["use_case"],
                "region": s["region"],
                "dialect": s["dialect"],
                "provider_stt": WORST_STT,
                "provider_llm": WORST_LLM,
                "provider_tts": WORST_TTS,
                "provider_combo": WORST_COMBO,
                "caller_utterance": s["caller_utterance"],
                "ji_pairing": s["ji_pairing"],
                "tone_flag": s["tone_flag"],
                "signal_drop": True,
                "partial_reply": True,
                "retries": 1,
                "agent_outcome": CONSENT_OUTCOMES[s["use_case"]],
                "true_intent": s["true_intent"],
                "wrong_consent": True,
                "complaint": True,
                "complaint_date": s["complaint_date"],
            }
        )
    return rows


def generate_regular(rng: np.random.Generator, n: int, used_ids: set[str]) -> pd.DataFrame:
    days = sample_dates(rng, n)

    regions = list(REGION_DIALECT.keys())
    # Slight tilt toward the Hindi belt and Punjab (the case's lead story).
    region_p = np.array([0.16, 0.12, 0.12, 0.12, 0.12, 0.18, 0.18], dtype=float)
    region_p /= region_p.sum()
    region = rng.choice(regions, size=n, p=region_p)

    dialect = []
    for r, flip in zip(region, rng.random(n)):
        home = REGION_DIALECT[r]
        dialect.append(home if flip < 0.92 else "standard Hindi")

    client_names = list(CLIENTS.keys())
    # XYZ Finance is the lead client in the case.
    client_p = np.array([0.40, 0.18, 0.16, 0.14, 0.12], dtype=float)
    client = rng.choice(client_names, size=n, p=client_p)
    use_case = [CLIENTS[c] for c in client]

    # Provider assignment: the worst combo is more common in Punjab so the
    # cluster is visible there, and is ~14% of regular calls overall.
    stt = []
    llm = []
    tts = []
    # Every STT/LLM/TTS triple is allowed, including ones that use STT-B or
    # LLM-A or TTS-B on their own. Only the exact worst triple is planted
    # at the high rate, so the failure is visibly a combination effect.
    other_combos = [
        (s, l, t)
        for s in STT_PROVIDERS
        for l in LLM_PROVIDERS
        for t in TTS_PROVIDERS
        if not (s == WORST_STT and l == WORST_LLM and t == WORST_TTS)
    ]
    for r, flip in zip(region, rng.random(n)):
        p_worst = 0.22 if r == "Punjab" else 0.12
        if flip < p_worst:
            stt.append(WORST_STT)
            llm.append(WORST_LLM)
            tts.append(WORST_TTS)
        else:
            s, l, t = other_combos[int(rng.integers(0, len(other_combos)))]
            stt.append(s)
            llm.append(l)
            tts.append(t)

    # Pairing: hun ji is much more common in Punjabi; other ambiguous
    # pairings are spread around. Haan / nahi remain the majority.
    pairings = []
    for d, is_worst, flip in zip(dialect, [s == WORST_STT and l == WORST_LLM and t == WORST_TTS for s, l, t in zip(stt, llm, tts)], rng.random(n)):
        if d == "Punjabi":
            # Boost hun ji, and boost ambiguous pairings on the worst combo.
            if is_worst:
                choices, p = (
                    ["hun ji", "ji?", "achha ji?", "bas ji", "ji ji ji", "haan ji", "nahi ji"],
                    [0.34, 0.14, 0.12, 0.10, 0.08, 0.14, 0.08],
                )
            else:
                choices, p = (
                    ["hun ji", "ji?", "achha ji?", "bas ji", "ji ji ji", "haan ji", "nahi ji"],
                    [0.22, 0.10, 0.08, 0.08, 0.10, 0.26, 0.16],
                )
        else:
            if is_worst:
                choices, p = (
                    ["hun ji", "ji?", "achha ji?", "bas ji", "ji ji ji", "haan ji", "nahi ji"],
                    [0.10, 0.16, 0.16, 0.14, 0.10, 0.20, 0.14],
                )
            else:
                choices, p = (
                    ["hun ji", "ji?", "achha ji?", "bas ji", "ji ji ji", "haan ji", "nahi ji"],
                    [0.06, 0.10, 0.10, 0.08, 0.10, 0.36, 0.20],
                )
        pairings.append(str(rng.choice(choices, p=p)))

    is_worst_arr = np.array(
        [s == WORST_STT and l == WORST_LLM and t == WORST_TTS for s, l, t in zip(stt, llm, tts)]
    )
    ambiguous = np.array([p in AMBIGUOUS_PAIRINGS for p in pairings])

    # Tone, signal drop and partial replies stack more often on the worst combo
    # with an ambiguous pairing — that is the planted failure pattern.
    tone = []
    signal_drop = []
    for worst, amb, flip_t, flip_s in zip(is_worst_arr, ambiguous, rng.random(n), rng.random(n)):
        if worst and amb:
            tone.append(str(rng.choice(list(TONE_STACK) + ["soft"], p=[0.25, 0.25, 0.15, 0.20, 0.15])) if flip_t < 0.88 else "neutral")
            signal_drop.append(bool(flip_s < 0.72))
        elif amb:
            tone.append(str(rng.choice(list(TONE_STACK) + ["soft", "neutral"], p=[0.12, 0.12, 0.08, 0.10, 0.18, 0.40])) if True else "neutral")
            signal_drop.append(bool(flip_s < 0.16))
        else:
            tone.append("neutral" if flip_t < 0.78 else str(rng.choice(list(TONE_STACK) + ["soft"])))
            signal_drop.append(bool(flip_s < 0.07))

    partial = []
    for drop, flip in zip(signal_drop, rng.random(n)):
        partial.append(True if drop and flip < 0.90 else bool(flip < 0.04))

    # Regular calls never reach 3 retries, so retry loops stay uniquely identifiable.
    retries = []
    for drop, partial_r, flip in zip(signal_drop, partial, rng.random(n)):
        if drop or partial_r:
            retries.append(int(rng.choice([0, 1, 2], p=[0.35, 0.40, 0.25])))
        else:
            retries.append(0 if flip < 0.88 else 1)

    # A slice of short "ji-only" replies, especially on ambiguous pairings.
    ji_only_flags = []
    for p, flip in zip(pairings, rng.random(n)):
        if p in AMBIGUOUS_PAIRINGS:
            ji_only_flags.append(bool(flip < 0.22))
        else:
            ji_only_flags.append(bool(flip < 0.08))

    utterances = [
        pick_utterance(rng, p, d, flag) for p, d, flag in zip(pairings, dialect, ji_only_flags)
    ]
    intents = [intent_for_pairing(rng, p, d) for p, d in zip(pairings, dialect)]
    outcomes = [correct_outcome(uc, intent) for uc, intent in zip(use_case, intents)]

    call_ids = []
    caller_ids = []
    seq = 1
    for dt in days:
        cid = f"CALL-{dt.strftime('%Y%m%d')}-{seq:05d}"
        while cid in used_ids:
            seq += 1
            cid = f"CALL-{dt.strftime('%Y%m%d')}-{seq:05d}"
        used_ids.add(cid)
        call_ids.append(cid)
        caller_ids.append(f"CLR-{8000 + seq:05d}")
        seq += 1

    df = pd.DataFrame(
        {
            "call_id": call_ids,
            "date": days,
            "caller_id": caller_ids,
            "client": client,
            "use_case": use_case,
            "region": region,
            "dialect": dialect,
            "provider_stt": stt,
            "provider_llm": llm,
            "provider_tts": tts,
            "provider_combo": [f"{s} / {l} / {t}" for s, l, t in zip(stt, llm, tts)],
            "caller_utterance": utterances,
            "ji_pairing": pairings,
            "tone_flag": tone,
            "signal_drop": signal_drop,
            "partial_reply": partial,
            "retries": retries,
            "agent_outcome": outcomes,
            "true_intent": intents,
            "wrong_consent": False,
            "complaint": False,
            "complaint_date": None,
        }
    )
    return df


def is_stacked(df: pd.DataFrame) -> pd.Series:
    return (
        df["ji_pairing"].isin(AMBIGUOUS_PAIRINGS)
        & df["tone_flag"].ne("neutral")
        & df["signal_drop"].astype(bool)
    )


def is_worst(df: pd.DataFrame) -> pd.Series:
    return df["provider_combo"].eq(WORST_COMBO)


def plant_wrong_consents(rng: np.random.Generator, regular: pd.DataFrame, n_planted_worst_wrong: int) -> pd.DataFrame:
    """Flip a controlled number of regular rows so the worst combo lands at ~15%.

    The overall average is kept in the low single digits. Errors concentrate
    where dialect + ambiguous ji + tone + signal drop stack on the worst combo.
    """
    df = regular.copy()
    eligible = df["true_intent"].ne("yes")  # a "yes" that was booked is not a wrong consent
    worst = is_worst(df)
    stacked = is_stacked(df)

    # Target: ~15% wrong-consent on the worst combo across the FULL file
    # (regular + 10 loop rows + 4 extra complaint rows, all worst+wrong).
    # n_worst_total is not known until merge, so we use regular worst count
    # plus the planted worst rows (14) and solve for k such that
    # (k + n_planted_worst_wrong) / (n_worst_regular + 14) ≈ 0.15
    n_worst_regular = int(worst.sum())
    n_worst_total = n_worst_regular + 14  # 10 loop + 4 complaint (all on worst combo)
    target_wrong_worst_total = int(round(0.15 * n_worst_total))
    k_worst = max(0, target_wrong_worst_total - n_planted_worst_wrong)

    # Prefer stacked rows; leave a small non-stacked residue so the slice is
    # visibly a stack, not a blanket combo failure.
    stacked_idx = df.index[eligible & worst & stacked].to_numpy().copy()
    unstacked_idx = df.index[eligible & worst & ~stacked].to_numpy().copy()
    rng.shuffle(stacked_idx)
    rng.shuffle(unstacked_idx)

    k_unstacked = min(len(unstacked_idx), max(4, int(round(0.06 * k_worst))))
    k_stacked = min(len(stacked_idx), k_worst - k_unstacked)
    # If we still short, pull more unstacked (or vice versa).
    short = k_worst - (k_stacked + k_unstacked)
    if short > 0:
        extra = min(len(unstacked_idx) - k_unstacked, short)
        k_unstacked += extra
        short -= extra
    if short > 0:
        extra = min(len(stacked_idx) - k_stacked, short)
        k_stacked += extra
        short -= extra
    if short > 0:
        raise RuntimeError(
            f"Not enough eligible worst-combo rows to plant {k_worst} wrong consents "
            f"(stacked={len(stacked_idx)}, unstacked={len(unstacked_idx)})."
        )

    worst_picks = np.concatenate([stacked_idx[:k_stacked], unstacked_idx[:k_unstacked]])

    # Residual errors outside the worst combo, so the overall rate is ~3%
    # and the stack still matters a little everywhere.
    # Target overall ≈ 3.0% of 5000 = 150. Worst will contribute
    # target_wrong_worst_total; the rest come from other combos.
    target_overall = int(round(0.030 * N_CALLS))
    k_other = max(0, target_overall - target_wrong_worst_total)
    other_stacked = df.index[eligible & ~worst & stacked].to_numpy().copy()
    other_rest = df.index[eligible & ~worst & ~stacked].to_numpy().copy()
    rng.shuffle(other_stacked)
    rng.shuffle(other_rest)
    k_other_stacked = min(len(other_stacked), int(round(0.70 * k_other)))
    k_other_rest = min(len(other_rest), k_other - k_other_stacked)
    other_picks = np.concatenate([other_stacked[:k_other_stacked], other_rest[:k_other_rest]])

    picks = np.concatenate([worst_picks, other_picks])
    df.loc[picks, "wrong_consent"] = True
    for idx in picks:
        uc = df.at[idx, "use_case"]
        df.at[idx, "agent_outcome"] = CONSENT_OUTCOMES[uc]
    return df


def retry_loop_table(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("caller_id", as_index=False).agg(
        n_calls=("call_id", "count"),
        max_retries=("retries", "max"),
        wrong=("wrong_consent", "sum"),
        regions=("region", lambda s: ",".join(sorted(set(s)))),
        pairings=("ji_pairing", lambda s: ",".join(sorted(set(s)))),
    )
    return g[(g["n_calls"] >= 3) & (g["max_retries"] >= 3) & (g["wrong"] >= 2)].sort_values("caller_id")


def verify(df: pd.DataFrame) -> dict:
    n = len(df)
    assert n == N_CALLS, f"expected {N_CALLS} calls, got {n}"

    worst = df[is_worst(df)]
    overall_rate = float(df["wrong_consent"].mean())
    worst_rate = float(worst["wrong_consent"].mean())
    n_wrong = int(df["wrong_consent"].sum())
    n_wrong_worst = int(worst["wrong_consent"].sum())

    # Overall in low single digits; worst combo around 15%.
    assert 0.015 <= overall_rate <= 0.049, f"overall rate {overall_rate:.3%} not in low single digits"
    assert 0.140 <= worst_rate <= 0.160, f"worst combo rate {worst_rate:.3%} not near 15%"

    loops = retry_loop_table(df)
    assert len(loops) == 3, f"expected 3 retry loops, found {len(loops)}:\n{loops}"
    # Loop 1 must be the Punjab / hun ji story.
    loop1 = df[df["caller_id"] == "CLR-1001"]
    assert len(loop1) == 4 and loop1["ji_pairing"].eq("hun ji").all()
    assert loop1["region"].eq("Punjab").all() and loop1["wrong_consent"].all()
    assert int(loop1["retries"].max()) >= 3

    complaints = df[df["complaint"]].copy()
    assert len(complaints) == 5, f"expected 5 complaints, got {len(complaints)}"
    assert complaints["wrong_consent"].all(), "complaints should follow a wrong consent"
    cdates = [d for d in complaints["complaint_date"].tolist() if d is not None]
    assert len(cdates) == 5
    max_window = max_complaints_in_10_day_window(cdates)
    assert max_window <= 2, f"TRAI window exceeded: {max_window} complaints in 10 days"

    # Regular calls must not accidentally form extra loops.
    assert df.loc[~df["caller_id"].isin(loops["caller_id"]), "retries"].max() <= 2

    # Schema / safety checks.
    required = [
        "call_id", "date", "client", "region", "dialect",
        "provider_stt", "provider_llm", "provider_tts",
        "caller_utterance", "ji_pairing", "tone_flag",
        "signal_drop", "partial_reply", "retries",
        "agent_outcome", "true_intent", "wrong_consent",
        "complaint", "complaint_date",
    ]
    for col in required:
        assert col in df.columns, f"missing column {col}"
    assert df["call_id"].is_unique
    text_blob = " ".join(df.astype(str).fillna("").values.ravel().tolist()).lower()
    for banned in ("syl", "icici", "hdfc", "sbi", "axis bank", "google", "openai", "gpt", "gemini"):
        assert banned not in text_blob, f"banned token found in data: {banned}"

    # Wrong-consent definition.
    bad = df[df["wrong_consent"]]
    assert bad["agent_outcome"].isin(set(CONSENT_OUTCOMES.values())).all()
    assert bad["true_intent"].ne("yes").all()

    numbers = {
        "total_calls": n,
        "overall_wrong_consent_rate": overall_rate,
        "overall_wrong_consent_pct": round(overall_rate * 100, 2),
        "worst_combo": WORST_COMBO,
        "worst_combo_calls": int(len(worst)),
        "worst_combo_wrong_consent_rate": worst_rate,
        "worst_combo_wrong_consent_pct": round(worst_rate * 100, 2),
        "total_wrong_consents": n_wrong,
        "wrong_consents_in_worst_combo": n_wrong_worst,
        "retry_loops": int(len(loops)),
        "retry_loop_callers": loops["caller_id"].tolist(),
        "total_complaints": 5,
        "complaint_dates": [d.isoformat() for d in sorted(cdates)],
        "max_complaints_in_any_10_day_window": max_window,
    }
    return numbers


COLUMNS = [
    "call_id", "date", "caller_id", "client", "use_case", "region", "dialect",
    "provider_stt", "provider_llm", "provider_tts", "provider_combo",
    "caller_utterance", "ji_pairing", "tone_flag", "signal_drop", "partial_reply",
    "retries", "agent_outcome", "true_intent", "wrong_consent", "complaint", "complaint_date",
]


def main() -> dict:
    rng = np.random.default_rng(SEED)
    planted = planted_retry_loops() + planted_complaints()
    planted_df = pd.DataFrame(planted)
    used_ids = set(planted_df["call_id"])
    regular = generate_regular(rng, N_CALLS - len(planted_df), used_ids)
    regular = plant_wrong_consents(
        rng,
        regular,
        n_planted_worst_wrong=int(planted_df["wrong_consent"].sum()),
    )
    df = pd.concat([planted_df, regular], ignore_index=True)
    df = df[COLUMNS].sort_values(["date", "call_id"]).reset_index(drop=True)
    # Normalise types for CSV + DuckDB.
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["complaint_date"] = df["complaint_date"].apply(
        lambda x: x if pd.notna(x) and x is not None else None
    )
    for col in ("signal_drop", "partial_reply", "wrong_consent", "complaint"):
        df[col] = df[col].astype(bool)
    df["retries"] = df["retries"].astype(int)

    numbers = verify(df)

    csv_path = OUT / "calls.csv"
    db_path = OUT / "calls.duckdb"
    df.to_csv(csv_path, index=False)

    if db_path.exists():
        db_path.unlink()
    con = duckdb.connect(str(db_path))
    con.register("_calls_df", df)
    con.execute("CREATE TABLE calls AS SELECT * FROM _calls_df")
    # Cast dates explicitly.
    con.execute(
        """
        CREATE OR REPLACE TABLE calls AS
        SELECT
            call_id,
            date::DATE AS date,
            caller_id,
            client,
            use_case,
            region,
            dialect,
            provider_stt,
            provider_llm,
            provider_tts,
            provider_combo,
            caller_utterance,
            ji_pairing,
            tone_flag,
            signal_drop::BOOLEAN AS signal_drop,
            partial_reply::BOOLEAN AS partial_reply,
            retries::INTEGER AS retries,
            agent_outcome,
            true_intent,
            wrong_consent::BOOLEAN AS wrong_consent,
            complaint::BOOLEAN AS complaint,
            complaint_date::DATE AS complaint_date
        FROM calls
        """
    )
    n_db = con.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
    con.close()
    assert n_db == N_CALLS, f"duckdb row count {n_db}"

    print("SIMULATED call log written.")
    print(f"  {csv_path}")
    print(f"  {db_path}")
    print()
    print("Headline numbers")
    print(f"  total calls:                    {numbers['total_calls']}")
    print(f"  overall wrong-consent rate:     {numbers['overall_wrong_consent_pct']}% "
          f"({numbers['total_wrong_consents']} calls)")
    print(f"  worst combo:                    {numbers['worst_combo']}")
    print(f"  worst combo wrong-consent rate: {numbers['worst_combo_wrong_consent_pct']}% "
          f"({numbers['wrong_consents_in_worst_combo']} of {numbers['worst_combo_calls']})")
    print(f"  retry loops:                    {numbers['retry_loops']} "
          f"({', '.join(numbers['retry_loop_callers'])})")
    print(f"  complaints:                     {numbers['total_complaints']}")
    print(f"  complaint dates:                {', '.join(numbers['complaint_dates'])}")
    print(f"  max complaints in 10-day window:{numbers['max_complaints_in_any_10_day_window']}")
    return numbers


if __name__ == "__main__":
    main()
