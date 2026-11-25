# Catching context failures in a simulated call log

All figures in this demo are from **simulated** data. There are no real calls, 
customers or transcripts. The log was generated with AI tools for Shruti Bajpai's 
case study, *Ji isn't always yes*.

A product manager asks the log a plain-English question. An AI assistant writes 
the SQL, runs it, and returns the answer. The PM checks whether the question and 
the logic are right — not the syntax. SQL is not presented here as a personal skill.

The failures are context misreads. The words were heard right; the intent was 
read wrong. In Indian speech, *ji* is a politeness marker, not an answer. Its 
meaning depends on the word pairing, the tone, the dialect and whether the line dropped.

## Key numbers

- **5,000 simulated calls** over 16 September to 24 November 2026.
- **Overall wrong-consent rate: 3.0%** (150 calls) — a low single-digit average that looks fine on a dashboard.
- **Worst provider combination: STT-B / LLM-A / TTS-B**, at **15.03%** (107 of 712 calls).
- **3 retry loops**, where the same caller is retried three or more times and the same error repeats.
- **5 complaints**, spread over several weeks. The busiest 10-day window has 2, under TRAI's 3-in-10 trigger.

---

## Question 1. Which Punjab calls had hun ji followed by a retry loop?

SQL written by AI:

```sql
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
```

Result:

| call_id | date | caller_id | client | region | dialect | ji_pairing | caller_utterance | tone_flag | signal_drop | partial_reply | retries | agent_outcome | true_intent | wrong_consent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CALL-LOOP1-01 | 2026-09-29 | CLR-1001 | XYZ Finance | Punjab | Punjabi | hun ji | Hun ji... | soft | true | true | 1 | payment_scheduled | listening | true |
| CALL-LOOP1-02 | 2026-09-29 | CLR-1001 | XYZ Finance | Punjab | Punjabi | hun ji | Ji, ke keh rahe... | rising | true | true | 2 | payment_scheduled | listening | true |
| CALL-LOOP1-03 | 2026-09-30 | CLR-1001 | XYZ Finance | Punjab | Punjabi | hun ji | Ji, main jaanta hoon, par... 2 din aur... lag jayenge ji | muffled | true | true | 3 | payment_scheduled | listening | true |
| CALL-LOOP1-04 | 2026-09-30 | CLR-1001 | XYZ Finance | Punjab | Punjabi | hun ji | Hun ji, sun raha haan | rushed | true | true | 4 | payment_scheduled | listening | true |

**Takeaway.** 4 Punjab calls from one caller (CLR-1001, XYZ Finance) said 'hun ji' — in Punjabi that means 'go on, I'm listening', not yes — and the agent retried up to 4 times, booking a payment on every attempt.

## Question 2. Which calls in Punjab ended with a payment scheduled after a repeat request or a signal drop?

SQL written by AI:

```sql
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
```

Result:

| call_id | date | client | dialect | ji_pairing | caller_utterance | tone_flag | retries | signal_drop | partial_reply | agent_outcome | true_intent | wrong_consent | provider_combo |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CALL-20260921-02427 | 2026-09-21 | XYZ Finance | Punjabi | ji? | Ji | rushed | 2 | true | false | payment_scheduled | question | true | STT-B / LLM-A / TTS-B |
| CALL-20260922-00869 | 2026-09-22 | Apex Credit | Punjabi | achha ji? | Achha ji? Aaj hi? | muffled | 1 | true | true | payment_scheduled | question | true | STT-B / LLM-A / TTS-B |
| CALL-LOOP1-01 | 2026-09-29 | XYZ Finance | Punjabi | hun ji | Hun ji... | soft | 1 | true | true | payment_scheduled | listening | true | STT-B / LLM-A / TTS-B |
| CALL-LOOP1-02 | 2026-09-29 | XYZ Finance | Punjabi | hun ji | Ji, ke keh rahe... | rising | 2 | true | true | payment_scheduled | listening | true | STT-B / LLM-A / TTS-B |
| CALL-LOOP1-03 | 2026-09-30 | XYZ Finance | Punjabi | hun ji | Ji, main jaanta hoon, par... 2 din aur... lag jayenge ji | muffled | 3 | true | true | payment_scheduled | listening | true | STT-B / LLM-A / TTS-B |
| CALL-LOOP1-04 | 2026-09-30 | XYZ Finance | Punjabi | hun ji | Hun ji, sun raha haan | rushed | 4 | true | true | payment_scheduled | listening | true | STT-B / LLM-A / TTS-B |
| CALL-20261008-00975 | 2026-10-08 | XYZ Finance | standard Hindi | hun ji | Hun ji, sun raha hoon | muffled | 1 | true | true | payment_scheduled | listening | true | STT-B / LLM-A / TTS-B |
| CALL-20261014-01637 | 2026-10-14 | Apex Credit | Punjabi | hun ji | Hun ji... | rushed | 0 | true | true | payment_scheduled | listening | true | STT-A / LLM-A / TTS-A |
| CALL-20261015-03700 | 2026-10-15 | XYZ Finance | standard Hindi | bas ji | Bas ji, ab mat phone karo | sarcastic | 1 | true | true | payment_scheduled | defer | true | STT-B / LLM-A / TTS-B |
| CALL-20261016-01430 | 2026-10-16 | XYZ Finance | Punjabi | bas ji | Bas ji, ho gaya meri taraf se | muffled | 1 | true | true | payment_scheduled | stop | true | STT-B / LLM-A / TTS-B |
| CALL-20261020-01725 | 2026-10-20 | XYZ Finance | Punjabi | hun ji | Hun ji bolo | soft | 0 | true | true | payment_scheduled | listening | true | STT-B / LLM-A / TTS-B |
| CALL-20261022-01132 | 2026-10-22 | XYZ Finance | Punjabi | hun ji | Hun ji, sun raha hoon | rising | 2 | true | true | payment_scheduled | listening | true | STT-B / LLM-A / TTS-B |
| CALL-20261023-02048 | 2026-10-23 | XYZ Finance | Punjabi | hun ji | Hun ji | soft | 0 | true | true | payment_scheduled | listening | true | STT-B / LLM-A / TTS-B |
| CALL-20261026-00465 | 2026-10-26 | Apex Credit | Punjabi | hun ji | Hun ji... | rising | 2 | true | true | payment_scheduled | acknowledge | true | STT-C / LLM-B / TTS-A |
| CALL-20261031-00223 | 2026-10-31 | Apex Credit | Punjabi | ji? | Ji, sunai nahi ditta | rushed | 1 | true | true | payment_scheduled | question | true | STT-B / LLM-A / TTS-B |

_Showing 15 of 42 rows._

**Takeaway.** 24 of 42 Punjab payments booked after a repeat or a signal drop were wrong consents (57%). The dashboard would still show 'payment scheduled, call completed'.

## Question 3. What is the wrong-consent rate by dialect, word pairing and provider combination?

SQL written by AI:

```sql
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
```

Result:

| dialect | ji_pairing | provider_combo | calls | wrong_consents | wrong_consent_pct |
| --- | --- | --- | --- | --- | --- |
| Hyderabadi | achha ji? | STT-B / LLM-A / TTS-B | 17 | 7.0 | 41.2 |
| Bhojpuri | ji? | STT-B / LLM-A / TTS-B | 20 | 8.0 | 40.0 |
| Hyderabadi | bas ji | STT-B / LLM-A / TTS-B | 16 | 5.0 | 31.3 |
| Punjabi | ji? | STT-B / LLM-A / TTS-B | 26 | 8.0 | 30.8 |
| standard Hindi | hun ji | STT-B / LLM-A / TTS-B | 18 | 5.0 | 27.8 |
| Marwari | bas ji | STT-B / LLM-A / TTS-B | 15 | 4.0 | 26.7 |
| Punjabi | hun ji | STT-B / LLM-A / TTS-B | 59 | 15.0 | 25.4 |
| Punjabi | achha ji? | STT-B / LLM-A / TTS-B | 21 | 5.0 | 23.8 |
| standard Hindi | achha ji? | STT-B / LLM-A / TTS-B | 31 | 7.0 | 22.6 |
| standard Hindi | ji? | STT-B / LLM-A / TTS-B | 52 | 9.0 | 17.3 |
| standard Hindi | ji? | STT-A / LLM-B / TTS-A | 24 | 2.0 | 8.3 |
| standard Hindi | bas ji | STT-B / LLM-A / TTS-B | 26 | 2.0 | 7.7 |
| Hyderabadi | haan ji | STT-B / LLM-A / TTS-B | 15 | 1.0 | 6.7 |
| Hyderabadi | haan ji | STT-C / LLM-B / TTS-B | 16 | 1.0 | 6.3 |
| standard Hindi | ji? | STT-C / LLM-A / TTS-B | 16 | 1.0 | 6.3 |

_Showing 15 of 101 rows._

**Takeaway.** The highest rate in any slice with at least 15 calls is 41.2% for Hyderabadi, 'achha ji?', on STT-B / LLM-A / TTS-B (7 of 17). Averages hide that cluster.

## Question 4. Which calls had a 'ji'-only reply right before a booking?

SQL written by AI:

```sql
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
```

Result:

| call_id | date | region | dialect | ji_pairing | caller_utterance | tone_flag | signal_drop | agent_outcome | true_intent | wrong_consent | provider_combo |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CALL-20260916-03801 | 2026-09-16 | Telangana | Hyderabadi | bas ji | Bas ji | rising | true | payment_scheduled | stop | true | STT-A / LLM-B / TTS-B |
| CALL-20260918-03698 | 2026-09-18 | Uttar Pradesh | standard Hindi | achha ji? | Achha ji? | neutral | false | renewal_confirmed | question | true | STT-A / LLM-B / TTS-B |
| CALL-20260919-02476 | 2026-09-19 | Telangana | Hyderabadi | hun ji | Hun ji... | muffled | true | payment_scheduled | listening | true | STT-B / LLM-A / TTS-B |
| CALL-20260921-01790 | 2026-09-21 | Bihar | Bhojpuri | ji? | Ji? | muffled | true | slot_booked | question | true | STT-B / LLM-A / TTS-B |
| CALL-20260921-02427 | 2026-09-21 | Punjab | Punjabi | ji? | Ji | rushed | true | payment_scheduled | question | true | STT-B / LLM-A / TTS-B |
| CALL-20260923-01473 | 2026-09-23 | Rajasthan | Marwari | hun ji | Hun ji | soft | false | slot_booked | acknowledge | true | STT-B / LLM-B / TTS-B |
| CALL-20260923-01517 | 2026-09-23 | Telangana | Hyderabadi | hun ji | Hun ji. | sarcastic | true | payment_scheduled | listening | true | STT-B / LLM-A / TTS-B |
| CALL-20260924-00619 | 2026-09-24 | Telangana | Hyderabadi | ji? | Ji? | sarcastic | true | slot_booked | question | true | STT-A / LLM-B / TTS-A |
| CALL-20260924-02399 | 2026-09-24 | Punjab | Punjabi | hun ji | Hun ji... | muffled | true | renewal_confirmed | listening | true | STT-B / LLM-A / TTS-B |
| CALL-20260924-02513 | 2026-09-24 | Delhi | standard Hindi | hun ji | Hun ji | rising | true | slot_booked | listening | true | STT-B / LLM-A / TTS-B |
| CALL-20260925-01602 | 2026-09-25 | Uttar Pradesh | standard Hindi | ji? | Ji | rushed | true | payment_scheduled | question | true | STT-B / LLM-A / TTS-B |
| CALL-LOOP1-01 | 2026-09-29 | Punjab | Punjabi | hun ji | Hun ji... | soft | true | payment_scheduled | listening | true | STT-B / LLM-A / TTS-B |
| CALL-20260930-00112 | 2026-09-30 | Delhi | standard Hindi | achha ji? | Achha ji? | rising | true | payment_scheduled | question | true | STT-B / LLM-A / TTS-B |
| CALL-20260930-04648 | 2026-09-30 | Bihar | Bhojpuri | ji? | Ji | rushed | true | payment_scheduled | question | true | STT-B / LLM-A / TTS-B |
| CALL-20261002-01741 | 2026-10-02 | Punjab | Punjabi | achha ji? | Achha ji? | soft | false | slot_booked | question | true | STT-B / LLM-A / TTS-B |

_Showing 15 of 158 rows._

**Takeaway.** 52 of 158 bookings that followed a ji-only reply were context misreads (33%). A lone 'ji' was treated as consent, with no confirm step.

## Question 5. Where do wrong consents cluster when tone, a signal drop and an ambiguous ji pairing stack?

SQL written by AI:

```sql
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
```

Result:

| combo_group | stack | calls | wrong_consents | wrong_consent_pct |
| --- | --- | --- | --- | --- |
| All other combinations | Not stacked | 4149 | 13.0 | 0.3 |
| All other combinations | Stacked: ambiguous ji + tone + signal drop | 139 | 30.0 | 21.6 |
| STT-B / LLM-A / TTS-B | Not stacked | 434 | 6.0 | 1.4 |
| STT-B / LLM-A / TTS-B | Stacked: ambiguous ji + tone + signal drop | 278 | 101.0 | 36.3 |

**Takeaway.** When an ambiguous ji pairing, a non-neutral tone and a signal drop stack on STT-B / LLM-A / TTS-B, the wrong-consent rate is 36.3% (101 of 278 calls). Everywhere else, unstacked traffic sits at 0.3%. The words were heard; the intent was read wrong.

## Question 6. Are we under TRAI's 3-complaints-in-10-days trigger, and which calls already look like a risk?

SQL written by AI:

```sql
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
```

Result:

| call_id | call_date | complaint_date | caller_id | client | region | dialect | ji_pairing | retries | agent_outcome | true_intent | complaints_in_10_days_from_this_date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CALL-LOOP1-04 | 2026-09-30 | 2026-10-01 | CLR-1001 | XYZ Finance | Punjab | Punjabi | hun ji | 4 | payment_scheduled | listening | 2 |
| CALL-CMP-02 | 2026-10-07 | 2026-10-09 | CLR-2002 | XYZ Finance | Telangana | Hyderabadi | achha ji? | 1 | payment_scheduled | defer | 1 |
| CALL-CMP-03 | 2026-10-22 | 2026-10-24 | CLR-2003 | Apex Credit | Rajasthan | Marwari | bas ji | 1 | payment_scheduled | stop | 1 |
| CALL-CMP-04 | 2026-11-06 | 2026-11-08 | CLR-2004 | XYZ Finance | Bihar | Bhojpuri | ji? | 1 | payment_scheduled | question | 1 |
| CALL-CMP-05 | 2026-11-18 | 2026-11-20 | CLR-2005 | HireLink Staffing | Delhi | standard Hindi | ji? | 1 | slot_booked | question | 1 |

**Takeaway.** 5 complaints were filed, spread over several weeks. The busiest 10-day window has 2, under TRAI's 3-in-10 trigger, so the number is never flagged — even though retry loops and wrong consents were already visible in the log.

---

## Chart

The heatmap `chart_failure_by_dialect_combo.png` shows the wrong-consent rate 
for every dialect × provider combination, against the flat overall average. 
One combination stands out; the average does not.

## How this was produced

Rerun from this folder:

```bash
python3 generate.py && python3 demo.py
```

See `README.md` for the full file list and the simulation rules.

