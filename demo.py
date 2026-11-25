#!/usr/bin/env python3
"""Run the SIMULATED Bolna call-log demo.

A product manager asks plain-English questions. An AI assistant writes the
SQL, runs it in DuckDB, and returns the answer. SQL is not presented as a
human skill.

Re-run with:  python3 generate.py && python3 demo.py
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
DB = OUT / "calls.duckdb"
CHART = OUT / "chart_failure_by_dialect_combo.png"
DEMO_MD = OUT / "DEMO.md"
RESULTS = OUT / "results"

DIALECT_ORDER = [
    "Punjabi",
    "Haryanvi",
    "Bhojpuri",
    "Marwari",
    "Hyderabadi",
    "standard Hindi",
]


QUESTIONS = [
    {
        "id": 1,
        "slug": "q1_punjab_hun_ji_retry_loop",
        "question": "Which Punjab calls had hun ji followed by a retry loop?",
        "sql": """
WITH retry_loop_callers AS (
    SELECT caller_id
    FROM calls
    GROUP BY caller_id
    HAVING COUNT(*) >= 3
       AND MAX(retries) >= 3
       AND SUM(CASE WHEN wrong_consent THEN 1 ELSE 0 END) >= 2
)
SELECT
    c.call_id,
    c.date,
    c.caller_id,
    c.client,
    c.region,
    c.dialect,
    c.ji_pairing,
    c.caller_utterance,
    c.tone_flag,
    c.signal_drop,
    c.partial_reply,
    c.retries,
    c.agent_outcome,
    c.true_intent,
    c.wrong_consent
FROM calls c
JOIN retry_loop_callers r ON c.caller_id = r.caller_id
WHERE c.region = 'Punjab'
  AND c.ji_pairing = 'hun ji'
ORDER BY c.caller_id, c.date, c.retries
""".strip(),
    },
    {
        "id": 2,
        "slug": "q2_punjab_payment_after_repeat_or_drop",
        "question": "Which calls in Punjab ended with a payment scheduled after a repeat request or a signal drop?",
        "sql": """
SELECT
    call_id,
    date,
    client,
    dialect,
    ji_pairing,
    caller_utterance,
    tone_flag,
    retries,
    signal_drop,
    partial_reply,
    agent_outcome,
    true_intent,
    wrong_consent,
    provider_combo
FROM calls
WHERE region = 'Punjab'
  AND agent_outcome = 'payment_scheduled'
  AND (retries >= 1 OR signal_drop = TRUE)
ORDER BY wrong_consent DESC, date, call_id
""".strip(),
    },
    {
        "id": 3,
        "slug": "q3_rate_by_dialect_pairing_combo",
        "question": "What is the wrong-consent rate by dialect, word pairing and provider combination?",
        "sql": """
SELECT
    dialect,
    ji_pairing,
    provider_combo,
    COUNT(*) AS calls,
    SUM(CASE WHEN wrong_consent THEN 1 ELSE 0 END) AS wrong_consents,
    ROUND(100.0 * SUM(CASE WHEN wrong_consent THEN 1 ELSE 0 END) / COUNT(*), 1)
        AS wrong_consent_pct
FROM calls
GROUP BY dialect, ji_pairing, provider_combo
HAVING COUNT(*) >= 15
ORDER BY wrong_consent_pct DESC, calls DESC
""".strip(),
    },
    {
        "id": 4,
        "slug": "q4_ji_only_before_booking",
        "question": "Which calls had a 'ji'-only reply right before a booking?",
        "sql": """
SELECT
    call_id,
    date,
    region,
    dialect,
    ji_pairing,
    caller_utterance,
    tone_flag,
    signal_drop,
    agent_outcome,
    true_intent,
    wrong_consent,
    provider_combo
FROM calls
WHERE agent_outcome IN (
        'payment_scheduled',
        'promise_recorded',
        'renewal_confirmed',
        'slot_booked'
    )
  AND lower(trim(regexp_replace(caller_utterance, '[.]+$', '')))
      IN ('ji', 'ji?', 'hun ji', 'hun ji...', 'haan ji',
          'achha ji?', 'bas ji', 'nahi ji', 'ji ji ji')
ORDER BY wrong_consent DESC, date, call_id
""".strip(),
    },
    {
        "id": 5,
        "slug": "q5_stacked_faults",
        "question": "Where do wrong consents cluster when tone, a signal drop and an ambiguous ji pairing stack?",
        "sql": """
SELECT
    CASE
        WHEN provider_combo = 'STT-B / LLM-A / TTS-B'
        THEN 'STT-B / LLM-A / TTS-B'
        ELSE 'All other combinations'
    END AS combo_group,
    CASE
        WHEN ji_pairing IN ('hun ji', 'ji?', 'achha ji?', 'bas ji')
         AND tone_flag <> 'neutral'
         AND signal_drop = TRUE
        THEN 'Stacked: ambiguous ji + tone + signal drop'
        ELSE 'Not stacked'
    END AS stack,
    COUNT(*) AS calls,
    SUM(CASE WHEN wrong_consent THEN 1 ELSE 0 END) AS wrong_consents,
    ROUND(100.0 * AVG(CASE WHEN wrong_consent THEN 1.0 ELSE 0.0 END), 1)
        AS wrong_consent_pct
FROM calls
GROUP BY 1, 2
ORDER BY combo_group, stack
""".strip(),
    },
    {
        "id": 6,
        "slug": "q6_trai_complaint_window",
        "question": "Are we under TRAI's 3-complaints-in-10-days trigger, and which calls already look like a risk?",
        "sql": """
WITH comps AS (
    SELECT
        call_id,
        date AS call_date,
        complaint_date,
        caller_id,
        client,
        region,
        dialect,
        ji_pairing,
        retries,
        agent_outcome,
        true_intent
    FROM calls
    WHERE complaint = TRUE
),
windows AS (
    SELECT
        a.complaint_date AS window_start,
        a.complaint_date + INTERVAL 9 DAY AS window_end,
        COUNT(*) AS complaints_in_window
    FROM comps a
    JOIN comps b
      ON b.complaint_date BETWEEN a.complaint_date
                              AND a.complaint_date + INTERVAL 9 DAY
    GROUP BY a.complaint_date
)
SELECT
    c.call_id,
    c.call_date,
    c.complaint_date,
    c.caller_id,
    c.client,
    c.region,
    c.dialect,
    c.ji_pairing,
    c.retries,
    c.agent_outcome,
    c.true_intent,
    w.complaints_in_window AS complaints_in_10_days_from_this_date
FROM comps c
JOIN windows w ON w.window_start = c.complaint_date
ORDER BY c.complaint_date
""".strip(),
    },
]


def md_escape(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def to_markdown_table(df: pd.DataFrame, max_rows: int = 12) -> str:
    if df.empty:
        return "_No rows._"
    view = df.head(max_rows).copy()
    for col in view.columns:
        if str(view[col].dtype).startswith("datetime") or col in {"date", "call_date", "complaint_date"}:
            view[col] = view[col].apply(
                lambda x: ""
                if x is None or (not isinstance(x, bool) and pd.isna(x))
                else (x.isoformat()[:10] if hasattr(x, "isoformat") else str(x)[:10])
            )
        elif view[col].dtype == bool or str(view[col].dtype) == "boolean":
            view[col] = view[col].map(lambda x: "true" if bool(x) else "false")
    headers = [md_escape(c) for c in view.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in view.iterrows():
        lines.append("| " + " | ".join(md_escape(v) for v in row.tolist()) + " |")
    leftover = len(df) - len(view)
    if leftover > 0:
        lines.append("")
        lines.append(f"_Showing {len(view)} of {len(df)} rows._")
    return "\n".join(lines)


def takeaway(qid: int, result: pd.DataFrame, totals: dict) -> str:
    if qid == 1:
        n = len(result)
        retries = int(result["retries"].max()) if n else 0
        caller = result["caller_id"].iloc[0] if n else "?"
        client = result["client"].iloc[0] if n else "?"
        return (
            f"{n} Punjab calls from one caller ({caller}, {client}) said "
            f"'hun ji' — in Punjabi that means 'go on, I'm listening', not yes — "
            f"and the agent retried up to {retries} times, booking a payment on every attempt."
        )
    if qid == 2:
        n = len(result)
        wrong = int(result["wrong_consent"].sum()) if n else 0
        rate = (100.0 * wrong / n) if n else 0
        return (
            f"{wrong} of {n} Punjab payments booked after a repeat or a signal drop "
            f"were wrong consents ({rate:.0f}%). The dashboard would still show "
            f"'payment scheduled, call completed'."
        )
    if qid == 3:
        top = result.iloc[0]
        return (
            f"The highest rate in any slice with at least 15 calls is "
            f"{top['wrong_consent_pct']}% for {top['dialect']}, '{top['ji_pairing']}', "
            f"on {top['provider_combo']} "
            f"({int(top['wrong_consents'])} of {int(top['calls'])}). "
            f"Averages hide that cluster."
        )
    if qid == 4:
        n = len(result)
        wrong = int(result["wrong_consent"].sum()) if n else 0
        rate = (100.0 * wrong / n) if n else 0
        return (
            f"{wrong} of {n} bookings that followed a ji-only reply were context "
            f"misreads ({rate:.0f}%). A lone 'ji' was treated as consent, with no "
            f"confirm step."
        )
    if qid == 5:
        stacked_worst = result[
            (result["combo_group"] == "STT-B / LLM-A / TTS-B")
            & (result["stack"].str.startswith("Stacked"))
        ]
        other_unstacked = result[
            (result["combo_group"] == "All other combinations")
            & (result["stack"] == "Not stacked")
        ]
        sw = float(stacked_worst["wrong_consent_pct"].iloc[0]) if len(stacked_worst) else 0
        ou = float(other_unstacked["wrong_consent_pct"].iloc[0]) if len(other_unstacked) else 0
        sw_n = int(stacked_worst["calls"].iloc[0]) if len(stacked_worst) else 0
        sw_w = int(stacked_worst["wrong_consents"].iloc[0]) if len(stacked_worst) else 0
        return (
            f"When an ambiguous ji pairing, a non-neutral tone and a signal drop "
            f"stack on STT-B / LLM-A / TTS-B, the wrong-consent rate is {sw:.1f}% "
            f"({sw_w} of {sw_n} calls). Everywhere else, unstacked traffic sits at "
            f"{ou:.1f}%. The words were heard; the intent was read wrong."
        )
    if qid == 6:
        max_w = int(result["complaints_in_10_days_from_this_date"].max()) if len(result) else 0
        n = len(result)
        return (
            f"{n} complaints were filed, spread over several weeks. The busiest "
            f"10-day window has {max_w}, under TRAI's 3-in-10 trigger, so the "
            f"number is never flagged — even though retry loops and wrong consents "
            f"were already visible in the log."
        )
    return ""


def headline_numbers(con: duckdb.DuckDBPyConnection) -> dict:
    total = con.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
    n_wrong = con.execute("SELECT SUM(CASE WHEN wrong_consent THEN 1 ELSE 0 END) FROM calls").fetchone()[0]
    overall = 100.0 * n_wrong / total
    worst = con.execute(
        """
        SELECT COUNT(*), SUM(CASE WHEN wrong_consent THEN 1 ELSE 0 END)
        FROM calls
        WHERE provider_combo = 'STT-B / LLM-A / TTS-B'
        """
    ).fetchone()
    loops = con.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT caller_id
            FROM calls
            GROUP BY caller_id
            HAVING COUNT(*) >= 3
               AND MAX(retries) >= 3
               AND SUM(CASE WHEN wrong_consent THEN 1 ELSE 0 END) >= 2
        )
        """
    ).fetchone()[0]
    n_comp = con.execute("SELECT SUM(CASE WHEN complaint THEN 1 ELSE 0 END) FROM calls").fetchone()[0]
    return {
        "total_calls": int(total),
        "total_wrong_consents": int(n_wrong),
        "overall_pct": round(overall, 2),
        "worst_combo": "STT-B / LLM-A / TTS-B",
        "worst_calls": int(worst[0]),
        "worst_wrong": int(worst[1]),
        "worst_pct": round(100.0 * worst[1] / worst[0], 2),
        "retry_loops": int(loops),
        "total_complaints": int(n_comp),
    }


def build_chart(con: duckdb.DuckDBPyConnection, overall_pct: float) -> None:
    rates = con.execute(
        """
        SELECT
            dialect,
            provider_combo,
            COUNT(*) AS calls,
            100.0 * AVG(CASE WHEN wrong_consent THEN 1.0 ELSE 0.0 END) AS rate_pct
        FROM calls
        GROUP BY dialect, provider_combo
        """
    ).df()

    combos = sorted(rates["provider_combo"].unique())
    # Put the worst combo last so it sits on the right edge, easy to spot.
    worst = "STT-B / LLM-A / TTS-B"
    combos = [c for c in combos if c != worst] + [worst]

    dialects = [d for d in DIALECT_ORDER if d in set(rates["dialect"])]
    matrix = np.full((len(dialects), len(combos)), np.nan)
    counts = np.zeros((len(dialects), len(combos)), dtype=int)
    lookup = {(r.dialect, r.provider_combo): (r.rate_pct, r.calls) for r in rates.itertuples()}
    for i, d in enumerate(dialects):
        for j, c in enumerate(combos):
            if (d, c) in lookup:
                matrix[i, j] = lookup[(d, c)][0]
                counts[i, j] = lookup[(d, c)][1]

    # Diverging scale centred on the overall average: below = cool, above = warm.
    vmax = max(np.nanmax(matrix), overall_pct + 1)
    vmin = 0.0
    # Two-slope norm so the average sits at the mid colour.
    bounds_low = np.linspace(vmin, overall_pct, 8)
    bounds_high = np.linspace(overall_pct, vmax, 8)[1:]
    bounds = np.concatenate([bounds_low, bounds_high])
    colors = list(plt.cm.Blues_r(np.linspace(0.15, 0.85, 7))) + ["#f7f7f7"] + list(
        plt.cm.YlOrRd(np.linspace(0.25, 0.85, 7))
    )
    cmap = mcolors.ListedColormap(colors)
    norm = mcolors.BoundaryNorm(bounds, cmap.N)

    fig, ax = plt.subplots(figsize=(16.5, 7.2))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#f4f4f4")
    masked = np.ma.masked_invalid(matrix)
    im = ax.imshow(masked, cmap=cmap, norm=norm, aspect="auto")

    ax.set_xticks(range(len(combos)))
    ax.set_xticklabels(combos, rotation=40, ha="right", fontsize=8)
    ax.set_yticks(range(len(dialects)))
    ax.set_yticklabels(dialects, fontsize=10)
    ax.set_xticks(np.arange(-0.5, len(combos), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(dialects), 1), minor=True)
    ax.grid(which="minor", color="white", linestyle="-", linewidth=1.2)
    ax.tick_params(which="minor", bottom=False, left=False)

    # Outline the worst-combo column.
    jw = combos.index(worst)
    ax.add_patch(
        plt.Rectangle(
            (jw - 0.5, -0.5),
            1,
            len(dialects),
            fill=False,
            edgecolor="#7a1f1f",
            linewidth=2.0,
            zorder=4,
        )
    )

    for i in range(len(dialects)):
        for j in range(len(combos)):
            if np.isnan(matrix[i, j]):
                ax.text(j, i, "—", ha="center", va="center", color="#888", fontsize=7)
                continue
            val = matrix[i, j]
            # Dark text on pale cells, light text on saturated reds/blues.
            dark = abs(val - overall_pct) < (0.35 * max(vmax - overall_pct, overall_pct)) or val < overall_pct * 1.8
            color = "#1a1a1a" if dark and val < overall_pct + (vmax - overall_pct) * 0.55 else "#111"
            if val >= overall_pct + (vmax - overall_pct) * 0.45:
                color = "white"
            ax.text(
                j,
                i,
                f"{val:.1f}%",
                ha="center",
                va="center",
                color=color,
                fontsize=7.5,
                fontweight="bold" if j == jw else "normal",
            )

    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("Wrong-consent rate", fontsize=9)
    cbar.ax.axhline(overall_pct, color="#222", linewidth=1.4, linestyle="--")
    cbar.ax.text(
        0.5,
        overall_pct,
        f"  overall {overall_pct:.1f}%",
        va="bottom",
        ha="left",
        fontsize=7.5,
        color="#222",
        transform=cbar.ax.get_yaxis_transform(),
    )

    ax.set_title(
        "Wrong-consent rate by dialect × provider combination",
        fontsize=14,
        pad=12,
        loc="left",
        fontweight="bold",
    )
    ax.set_xlabel("Provider combination  (speech-to-text / LLM / text-to-speech)")
    fig.text(
        0.12,
        0.02,
        "Simulated data. Colour is centred on the overall average "
        f"({overall_pct:.1f}%, dashed on the colour bar). "
        "The outlined column is STT-B / LLM-A / TTS-B, which sits well above that average. "
        "This is a context misread, not a named-model failure.",
        fontsize=8.5,
        color="#333",
    )
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(CHART, dpi=160)
    plt.close(fig)


def write_demo_md(totals: dict, sections: list[dict], max_window: int) -> None:
    lines = [
        "# Catching context failures in a simulated call log",
        "",
        "All figures in this demo are from **simulated** data. There are no real calls, ",
        "customers or transcripts. The log was generated with AI tools for Shruti Bajpai's ",
        "case study, *Ji isn't always yes*.",
        "",
        "A product manager asks the log a plain-English question. An AI assistant writes ",
        "the SQL, runs it, and returns the answer. The PM checks whether the question and ",
        "the logic are right — not the syntax. SQL is not presented here as a personal skill.",
        "",
        "The failures are context misreads. The words were heard right; the intent was ",
        "read wrong. In Indian speech, *ji* is a politeness marker, not an answer. Its ",
        "meaning depends on the word pairing, the tone, the dialect and whether the line dropped.",
        "",
        "## Key numbers",
        "",
        f"- **{totals['total_calls']:,} simulated calls** over 16 September to 24 November 2026.",
        f"- **Overall wrong-consent rate: {totals['overall_pct']}%** "
        f"({totals['total_wrong_consents']} calls) — a low single-digit average that looks fine on a dashboard.",
        f"- **Worst provider combination: {totals['worst_combo']}**, "
        f"at **{totals['worst_pct']}%** "
        f"({totals['worst_wrong']} of {totals['worst_calls']} calls).",
        f"- **{totals['retry_loops']} retry loops**, where the same caller is retried three or more times and the same error repeats.",
        f"- **{totals['total_complaints']} complaints**, spread over several weeks. "
        f"The busiest 10-day window has {max_window}, under TRAI's 3-in-10 trigger.",
        "",
        "---",
        "",
    ]
    for sec in sections:
        lines += [
            f"## Question {sec['id']}. {sec['question']}",
            "",
            "SQL written by AI:",
            "",
            "```sql",
            sec["sql"],
            "```",
            "",
            "Result:",
            "",
            sec["table"],
            "",
            f"**Takeaway.** {sec['takeaway']}",
            "",
        ]
    lines += [
        "---",
        "",
        "## Chart",
        "",
        "The heatmap `chart_failure_by_dialect_combo.png` shows the wrong-consent rate ",
        "for every dialect × provider combination, against the flat overall average. ",
        "One combination stands out; the average does not.",
        "",
        "## How this was produced",
        "",
        "Rerun from this folder:",
        "",
        "```bash",
        "python3 generate.py && python3 demo.py",
        "```",
        "",
        "See `README.md` for the full file list and the simulation rules.",
        "",
    ]
    DEMO_MD.write_text("".join(line if line.endswith("\n") else line + "\n" for line in lines), encoding="utf-8")


def main() -> None:
    if not DB.exists():
        raise SystemExit(f"Missing {DB}. Run python3 generate.py first.")
    RESULTS.mkdir(exist_ok=True)
    con = duckdb.connect(str(DB), read_only=True)
    totals = headline_numbers(con)

    sections = []
    takeaways = []
    max_window = 0
    for q in QUESTIONS:
        result = con.execute(q["sql"]).df()
        result_path = RESULTS / f"{q['slug']}.csv"
        result.to_csv(result_path, index=False)
        if q["id"] == 6 and "complaints_in_10_days_from_this_date" in result.columns and len(result):
            max_window = int(result["complaints_in_10_days_from_this_date"].max())
        text = takeaway(q["id"], result, totals)
        takeaways.append((q["id"], q["question"], text, len(result)))
        # Question 2 and 4 can be long; show a tight preview in the markdown.
        max_rows = 15 if q["id"] in {2, 3, 4} else 12
        sections.append(
            {
                "id": q["id"],
                "question": q["question"],
                "sql": q["sql"],
                "table": to_markdown_table(result, max_rows=max_rows),
                "takeaway": text,
            }
        )

    if max_window == 0:
        # Fallback if Q6 is empty (should not happen).
        max_window = con.execute(
            """
            WITH comps AS (SELECT complaint_date FROM calls WHERE complaint),
            days AS (
                SELECT MIN(complaint_date) AS d, MAX(complaint_date) AS last FROM comps
            )
            SELECT 0
            """
        ).fetchone()[0]

    build_chart(con, totals["overall_pct"])
    write_demo_md(totals, sections, max_window)
    con.close()

    print("Demo written.")
    print(f"  {DEMO_MD}")
    print(f"  {CHART}")
    print(f"  results in {RESULTS}/")
    print()
    print("Headline numbers")
    print(f"  total calls:                    {totals['total_calls']}")
    print(f"  overall wrong-consent rate:     {totals['overall_pct']}% "
          f"({totals['total_wrong_consents']} calls)")
    print(f"  worst combo:                    {totals['worst_combo']}")
    print(f"  worst combo wrong-consent rate: {totals['worst_pct']}% "
          f"({totals['worst_wrong']} of {totals['worst_calls']})")
    print(f"  retry loops:                    {totals['retry_loops']}")
    print(f"  complaints:                     {totals['total_complaints']}")
    print(f"  max complaints in 10-day window:{max_window}")
    print()
    print("Takeaways")
    for qid, question, text, n in takeaways:
        print(f"  Q{qid} ({n} rows). {question}")
        print(f"      {text}")
        print()


if __name__ == "__main__":
    main()
