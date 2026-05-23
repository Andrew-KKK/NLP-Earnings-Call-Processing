# -*- coding: utf-8 -*-
"""
Earnings-call transcript preprocessor.

Cleans raw ASR transcript text into TWO paragraph-segmented plain-text files
matching the input contract of 恩泓's qa_pipeline.py:

    {prefix}_earnings_call.txt   — full call (prepared remarks + Q&A)
    {prefix}_qna.txt             — Q&A portion only

Format contract: plain text, one speaker turn per `\n`-separated line,
prefixed with a closed-enum role marker (Operator: / [CFO] Name: /
[Analyst] Name, Firm: / etc.). ASR errors are corrected from an embedded
lookup; speaker fillers / stutters / repetitions are preserved verbatim
because downstream sentiment & keyphrase analysis depends on them.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors

MODEL_NAME = "gemini-2.5-flash"
QNA_MARKER = "### Q&A SECTION START ###"

# Matches the speaker prefix at the start of a line. Captures the prefix
# (without the trailing colon) so we can re-prepend it to continuation lines.
_PREFIX_RE = re.compile(
    r"^(?P<prefix>"
    r"Operator"
    r"|\[(?:IR|CFO|CEO|COO|Other|Other Executive|Analyst)\][^:]*?"
    r")\s*:\s*"
)


def _normalize_speaker_prefixes(lines: list[str]) -> list[str]:
    """Ensure every line begins with a known speaker prefix.

    Gemini occasionally splits a long monologue into topical sub-paragraphs
    and drops the prefix on each continuation line. Downstream consumers
    expect one speaker turn per line with the prefix attached, so we
    re-prepend the most recent prefix to any orphan line.
    """
    out: list[str] = []
    last_prefix: str | None = None
    for raw in lines:
        line = raw.rstrip()
        if not line:
            continue
        m = _PREFIX_RE.match(line)
        if m:
            last_prefix = m.group("prefix")
            out.append(line)
        elif last_prefix is not None:
            out.append(f"{last_prefix}: {line}")
        else:
            # Output started without a recognizable prefix — keep verbatim
            # rather than guess; the file-level sanity check below will catch it.
            out.append(line)
    return out

PROMPT_TEMPLATE = """You are a senior earnings-call transcript editor. Convert raw speech-to-text (ASR) output of an earnings call into a clean, paragraph-segmented transcript that downstream NLP modules can parse.

# OUTPUT CONTRACT

Output PLAIN TEXT only — NO Markdown headers, NO JSON, NO commentary, NO code fences.
The output is a sequence of LINES separated by single newlines.
Each line is ONE speaker turn formatted as:

    <Speaker prefix>: <utterance>

For very long monologues (>3 sentences AND >500 chars), you MAY split into topical sub-paragraphs, each on its own line and each REPEATING the same speaker prefix.

You MUST emit exactly ONE marker line `{marker}` at the boundary between the prepared remarks and the analyst Q&A session, on its own line. Do not emit any other marker lines or any other Markdown headers.

# SPEAKER PREFIX GRAMMAR (closed enum — do NOT invent new forms)

    Operator:                        — the conference operator
    [IR] {{Name}}:                   — investor relations host (e.g. Tasha Hari)
    [CFO] {{Name}}:                  — chief financial officer (e.g. Colette Kress)
    [CEO] {{Name}}:                  — chief executive officer (e.g. Jensen Huang)
    [COO] {{Name}}:                  — chief operating officer
    [Other] {{Title}} {{Name}}:      — any other executive whose role is stated
    [Analyst] {{Name}}, {{Firm}}:    — analyst asking a question

If a speaker's name cannot be identified with confidence, use the role-only form:
    [Analyst]:    [Other Executive]:    [IR]:

# RULES

## ALLOWED corrections (these are ASR SYSTEM errors, not speaker behavior)

- Correct mistranscribed proper nouns using the lookup table below.
- Fix casing of brand names and acronyms: cuda → CUDA, gpt → GPT, nvidia → NVIDIA, ai → AI, q4 → Q4, rtx → RTX, hpc → HPC, eps → EPS, gaap → GAAP, p&l → P&L, capex → capex, csp → CSP.
- Insert punctuation (periods, commas, question marks, apostrophes). ASR output has none.
- Strip pre-call ASR garbage at the very start (the "heat heat heat" / "happy birthday" gibberish that appears before the first coherent sentence). Begin output at the first real speech.
- Segment the run-on text into speaker turns.

## PRESERVED VERBATIM (these are SPEAKER behaviors — load-bearing signal for downstream sentiment & keyphrase analysis; DO NOT touch)

- Filler words: "uh", "um", "you know", "I mean", "kind of", "like", "sort of", "basically", "actually"
- Stutters: "the the", "I I think", "we we", "to to", "u u"
- False starts: "I I'd I'd like to ask...", "you you know"
- Repetition for emphasis: "really, really fast", "very, very tight"
- Trailing fragments and unfinished sentences
- All hesitations and verbal tics

## FORBIDDEN

- Paraphrasing or summarizing — copy the speaker's exact wording.
- Dropping any substantive content.
- Changing any number, percentage, date, or named entity (other than ASR fixes from the lookup table).
- Splitting one speaker turn across multiple lines UNLESS the monologue exceeds 3 sentences AND 500 chars, in which case sub-paragraphs MUST repeat the same prefix.
- Adding any commentary, preamble, header, or trailing text of your own.

When in doubt, preserve the original wording.

# ASR CORRECTION LOOKUP

## People (NVIDIA earnings call)

    Jensen Wong                           → Jensen Huang
    Colette Crest                         → Colette Kress
    Toshia / Tasha Harry / Tasha Hari     → Tasha Hari
    Jonathan (when addressing Jensen)     → Jensen

## Companies, products, technologies

    MVLink, Envy Link, Envy-Link          → NVLink
    Reuben (chip codename)                → Rubin
    Grock (the inference company)         → Groq
    Ampear                                → Ampere
    Melanox                               → Mellanox
    Whimo                                 → Waymo
    Zuks                                  → Zoox
    Disso Systems                         → Dassault Systèmes
    Seammens                              → Siemens
    Synopsis (the company)                → Synopsys
    Franco Robotics                       → Figure Robotics
    Neuroo Robotics                       → Neura Robotics
    Caner Fitzgerald                      → Cantor Fitzgerald
    Boston Dynamics / Caterpillar / LG    → keep as written
    EOS (when meaning ecosystem)          → ecosystem
    cloud claw / open claw                → Claude / Open Claude
    cloud code / claud code               → Claude Code
    cloud co-work / claude codework       → ClaudeWork
    chad GPT / chat GPT                   → ChatGPT
    XAI                                   → xAI
    Aenic / Aentic                        → Agentic
    AMD doll's law                        → Amdahl's Law
    GAP / GAP margin / non-GAP            → GAAP / GAAP margin / non-GAAP
    Hopper, Blackwell, Vera, Spectrum, ConnectX, Bluefield, Grace, CUDA — keep as written.

Numbers, percentages, dates, and units: NEVER change.

# FEW-SHOT EXAMPLES

## Example 1 — Prepared remarks turn

RAW INPUT:
    thanks Toshia we delivered another outstanding quarter with record revenue operating income and free cash flow total revenue of 68 billion was up 73% yearover-year accelerating from Q3 growth on a sequential basis was also a record as we added 11 billion in data center revenue across a diverse and expanding set of customers including cloud providers hyperscalers AI model makers enterprises and sovereign nations

EXPECTED OUTPUT (single line):
    [CFO] Colette Kress: Thanks, Tasha. We delivered another outstanding quarter with record revenue, operating income and free cash flow. Total revenue of 68 billion was up 73% year-over-year, accelerating from Q3. Growth on a sequential basis was also a record as we added 11 billion in data center revenue across a diverse and expanding set of customers, including cloud providers, hyperscalers, AI model makers, enterprises and sovereign nations.

Notice: "Toshia" → "Tasha" via lookup. Punctuation added. "yearover-year" → "year-over-year". ONE line for the whole turn.

## Example 2 — Q&A turn with operator + analyst + CEO

RAW INPUT:
    your first question comes from VC area with Bank of America Securities your line is open uh thanks for taking my question um I think you mentioned that uh you now have growth uh visibility into uh calendar uh 27 also and I think your your purchase commitments kind of reflect that confidence but Jensen I'm curious u you know when you look at uh your uh top cloud customers uh cloud capex close to 700 billion this year many investors are concerned

EXPECTED OUTPUT (two lines):
    Operator: Your first question comes from VC area with Bank of America Securities. Your line is open.
    [Analyst] VC Area, Bank of America: uh thanks for taking my question. um I think you mentioned that uh you now have growth uh visibility into uh calendar uh 27 also, and I think your your purchase commitments kind of reflect that confidence. But Jensen, I'm curious, u you know, when you look at uh your uh top cloud customers, uh cloud capex close to 700 billion this year, many investors are concerned.

Notice: ALL "uh", "um", "u" fillers PRESERVED. "your your" stutter PRESERVED. "kind of" PRESERVED. Punctuation added. Two distinct speaker turns → two distinct lines.

## Example 3 — Q&A boundary

RAW INPUT (tail of prepared remarks, then Q&A transition):
    ... we look forward to sharing more at GTC next month okay back to you we will now transition to Q&A operator please pull for questions at this time I would like to remind everyone in order to ask a question press star then the number one on your telephone keypad

EXPECTED OUTPUT (note the marker line):
    [CEO] Jensen Huang: ... we look forward to sharing more at GTC next month. Okay, back to you.
    {marker}
    Operator: We will now transition to Q&A. Operator, please pull for questions. At this time, I would like to remind everyone, in order to ask a question, press star then the number one on your telephone keypad.

# YOUR TASK

Below is the raw ASR transcript. Apply ALL rules above and produce the cleaned output now. Begin output immediately with the first speaker line — NO preamble, NO trailing remarks.

---RAW TRANSCRIPT BEGINS---
{transcript_text}
---RAW TRANSCRIPT ENDS---
"""


def build_prompt(transcript_text: str) -> str:
    return PROMPT_TEMPLATE.format(marker=QNA_MARKER, transcript_text=transcript_text)


def process_transcript(
    input_file: Path,
    out_dir: Path | None,
    prefix: str | None,
) -> None:
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not set in .env")
        sys.exit(1)

    if not input_file.is_file():
        print(f"Error: input file not found: {input_file}")
        sys.exit(1)

    raw = input_file.read_text(encoding="utf-8")
    print(f"Read {len(raw):,} chars from {input_file}")

    output_dir = out_dir or input_file.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    out_prefix = prefix or input_file.stem
    full_path = output_dir / f"{out_prefix}_earnings_call.txt"
    qna_path = output_dir / f"{out_prefix}_qna.txt"

    client = genai.Client(api_key=api_key)
    print(f"Calling Gemini ({MODEL_NAME}) — long transcripts may take ~30–90 s...")

    prompt = build_prompt(raw)
    response = None
    last_err: Exception | None = None
    for attempt in range(1, 6):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config={
                    "temperature": 0.1,
                    "top_p": 0.95,
                    "max_output_tokens": 65000,
                },
            )
            break
        except genai_errors.ServerError as e:
            last_err = e
            wait = 2 ** attempt
            print(f"  [attempt {attempt}/5] Gemini server error ({e}). Retrying in {wait}s...")
            time.sleep(wait)
        except genai_errors.APIError as e:
            # Rate-limit etc.
            if getattr(e, "code", None) in (429, 503):
                last_err = e
                wait = 2 ** attempt
                print(f"  [attempt {attempt}/5] Gemini transient error ({e}). Retrying in {wait}s...")
                time.sleep(wait)
                continue
            raise
    if response is None:
        print(f"Error: Gemini call failed after 5 attempts. Last error: {last_err}")
        sys.exit(1)

    cleaned = (response.text or "").strip()
    if not cleaned:
        print("Error: Gemini returned an empty response.")
        sys.exit(1)

    if QNA_MARKER not in cleaned:
        print(f"Error: Gemini output is missing the marker line '{QNA_MARKER}'.")
        print(f"\nFirst 500 chars of response:\n{cleaned[:500]}\n...")
        print(f"\nLast 500 chars of response:\n...{cleaned[-500:]}")
        sys.exit(1)

    # Split on first marker occurrence; strip any duplicate markers from each side.
    prep_part, _, qna_part = cleaned.partition(QNA_MARKER)
    prep_part = prep_part.replace(QNA_MARKER, "").strip()
    qna_part = qna_part.replace(QNA_MARKER, "").strip()

    prep_lines = _normalize_speaker_prefixes(prep_part.splitlines())
    qna_lines = _normalize_speaker_prefixes(qna_part.splitlines())

    if len(prep_lines) < 3:
        print(f"Warning: prepared-remarks section has only {len(prep_lines)} lines.")
    if len(qna_lines) < 3:
        print(f"Warning: Q&A section has only {len(qna_lines)} lines.")

    orphan_prep = sum(1 for ln in prep_lines if not _PREFIX_RE.match(ln))
    orphan_qna = sum(1 for ln in qna_lines if not _PREFIX_RE.match(ln))
    if orphan_prep or orphan_qna:
        print(f"Warning: {orphan_prep} orphan prep lines, {orphan_qna} orphan Q&A lines "
              "(no speaker prefix could be inferred — check output).")

    full_lines = prep_lines + qna_lines
    full_path.write_text("\n".join(full_lines) + "\n", encoding="utf-8")
    qna_path.write_text("\n".join(qna_lines) + "\n", encoding="utf-8")

    print("\nDone.")
    print(f"  Full call: {full_path}  ({len(full_lines)} lines, {full_path.stat().st_size:,} bytes)")
    print(f"  Q&A only : {qna_path}  ({len(qna_lines)} lines, {qna_path.stat().st_size:,} bytes)")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Preprocess raw ASR earnings-call transcript into 恩泓-format text files."
    )
    ap.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=Path("input.txt"),
        help="Path to raw ASR transcript .txt (default: input.txt)",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory (default: same directory as input)",
    )
    ap.add_argument(
        "--prefix",
        type=str,
        default=None,
        help="Output filename prefix, e.g. 'nvda' (default: input file stem)",
    )
    args = ap.parse_args()

    out_dir = args.out_dir.resolve() if args.out_dir else None
    process_transcript(args.input.resolve(), out_dir, args.prefix)


if __name__ == "__main__":
    main()
