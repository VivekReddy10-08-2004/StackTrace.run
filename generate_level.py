#!/usr/bin/env python3
"""
generate_level.py — DEV-SIM level generator pipeline.

    Stack Overflow API  ->  prune  ->  LLM (Groq)  ->  level_N.json

Implements the flow described in project_Architecture.md:

  1. Fetch high-quality, accepted-answer troubleshooting threads for a
     DevOps tag (linux;bash, python;sql, postgresql;python, ...).
  2. Prune the verbose SO payload down to a minimal context to save tokens.
  3. Ask an LLM (Groq, OpenAI-compatible) to convert it into a STRICT
     game-level JSON object — nothing else.
  4. Save the validated JSON to src/levels/level_N.json so the web
     terminal can load it later with zero runtime API calls.

Usage:
    python generate_level.py                      # one level, auto tag
    python generate_level.py --tag "python;sql" --count 3
    python generate_level.py --difficulty easy    # scale problem down
    python generate_level.py --offline            # no network, sample data

Keys are read from project.env (or .env):
    STACK_API_KEY=...
    Groq_API_key=...
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import dotenv_values

# Windows consoles default to cp1252 and choke on arrows/checkmarks.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / "project.env"
LEVELS_DIR = ROOT / "src" / "levels"

SE_BASE = "https://api.stackexchange.com/2.3"
SE_SITE = "stackoverflow"
# `withbody` includes the rendered HTML body of questions/answers on top of
# the default fields (which already carry accepted_answer_id, score, tags…).
SE_FILTER = "withbody"

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"

# The three DevOps "misery" tag sets from the architecture doc.
DEFAULT_TAGS = ["linux;bash", "python;sql", "postgresql;python"]

# Step 3: the system prompt. Constrains the LLM to emit ONLY raw JSON so the
# web app's parser never chokes on "Sure! Here is a level…" preambles.
SYSTEM_PROMPT = """\
You are a backend game engine data generator.
Analyze the provided Stack Overflow question and accepted answer.
You must output a raw, minified JSON object and NOTHING else. No markdown \
formatting, no backticks, no introduction.

The JSON schema must strictly match:
{
  "ticket_id": "Generate a unique string",
  "category": "Choose exactly one: [Unix, SQL, Python]",
  "title": "A short, realistic IT Support Ticket title",
  "problem_description": "A summarized 3-sentence description of the symptom based on the question.",
  "starting_state": {
    "files": {
      "filename.ext": "The simulated broken code or configuration block"
    },
    "db_schema": "If SQL, a short CREATE TABLE string, otherwise null"
  },
  "winning_condition_hint": "What code pattern, command, or string must exist for the issue to be fixed?"
}"""

DIFFICULTY_NOTES = {
    "easy": "Scale this DOWN to an easy difficulty for a beginner: a single "
            "obvious bug, minimal files, generous hint.",
    "medium": "Keep this at a medium difficulty for a confident junior engineer.",
    "hard": "Scale this UP to a hard difficulty: add realistic surrounding "
            "code/config so the real bug is harder to spot. Keep it solvable.",
    "original": "Stay faithful to the original problem's difficulty.",
}

REQUIRED_KEYS = {
    "ticket_id", "category", "title", "problem_description",
    "starting_state", "winning_condition_hint",
}


# --------------------------------------------------------------------------
# Env / keys
# --------------------------------------------------------------------------

def load_keys() -> dict:
    """Read API keys from project.env / .env (case-insensitive lookup)."""
    values = {}
    for candidate in (ENV_FILE, ROOT / ".env"):
        if candidate.exists():
            values.update(dotenv_values(candidate))
    # also allow real environment variables to override
    values.update({k: v for k, v in os.environ.items()
                   if k.lower() in ("stack_api_key", "groq_api_key", "groq_model")})

    def pick(*names):
        for name in names:
            for k, v in values.items():
                if k.lower() == name.lower() and v:
                    return v
        return None

    return {
        "stack": pick("STACK_API_KEY"),
        "groq": pick("Groq_API_key", "GROQ_API_KEY"),
        "model": pick("GROQ_MODEL") or DEFAULT_MODEL,
    }


# --------------------------------------------------------------------------
# Step 1 + 2: Stack Overflow fetch + prune
# --------------------------------------------------------------------------

def html_to_text(raw: str, limit: int = 4000) -> str:
    """Light HTML -> text so we don't burn tokens on markup/styling."""
    if not raw:
        return ""
    # keep code blocks readable, drop tags, unescape entities
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw, flags=re.S | re.I)
    text = re.sub(r"</?(p|div|br|li|h[1-6]|pre)[^>]*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:limit]


def fetch_question(keys: dict, tag: str, skip: int = 0) -> dict:
    """
    Step 1: pull one highly-upvoted, accepted-answer thread for `tag`.
    Returns the minimized context dict (Step 2).
    """
    params = {
        "site": SE_SITE,
        "order": "desc",
        "sort": "votes",
        "tagged": tag,
        "accepted": "True",          # only questions with an accepted answer
        "answers": "1",              # at least one answer
        "pagesize": str(skip + 5),   # grab a few so --count can advance
        "filter": SE_FILTER,
    }
    if keys.get("stack"):
        params["key"] = keys["stack"]

    data = _se_get(f"{SE_BASE}/search/advanced", params)
    items = data.get("items", [])
    if not items:
        raise RuntimeError(f"No accepted-answer questions found for tag '{tag}'.")
    question = items[min(skip, len(items) - 1)]

    answer_body = fetch_accepted_answer(keys, question.get("accepted_answer_id"))

    # Step 2: prune the verbose payload to just what the LLM needs.
    return {
        "source_url": question.get("link"),
        "score": question.get("score"),
        "title": html.unescape(question.get("title", "")),
        "tags": question.get("tags", []),
        "error_report": html_to_text(question.get("body", "")),
        "solution_notes": html_to_text(answer_body),
    }


def fetch_accepted_answer(keys: dict, answer_id) -> str:
    if not answer_id:
        return ""
    params = {"site": SE_SITE, "filter": SE_FILTER}
    if keys.get("stack"):
        params["key"] = keys["stack"]
    data = _se_get(f"{SE_BASE}/answers/{answer_id}", params)
    items = data.get("items", [])
    return items[0].get("body", "") if items else ""


def _se_get(url: str, params: dict) -> dict:
    """GET helper that respects Stack Exchange backoff/quota signalling."""
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("error_message"):
        raise RuntimeError(f"Stack Exchange API error: {data['error_message']}")
    if data.get("backoff"):
        time.sleep(int(data["backoff"]) + 1)
    return data


# --------------------------------------------------------------------------
# Step 3: LLM orchestration (Groq)
# --------------------------------------------------------------------------

def generate_with_llm(keys: dict, context: dict, difficulty: str) -> dict:
    if not keys.get("groq"):
        raise RuntimeError("No Groq API key found in project.env (Groq_API_key=...).")

    user_payload = {
        "title": context["title"],
        "tags": context["tags"],
        "error_report": context["error_report"],
        "solution_notes": context["solution_notes"],
    }
    user_prompt = (
        f"DIFFICULTY DIRECTIVE: {DIFFICULTY_NOTES.get(difficulty, DIFFICULTY_NOTES['original'])}\n\n"
        "Stack Overflow source data:\n"
        f"{json.dumps(user_payload, ensure_ascii=False)}"
    )

    body = {
        "model": keys["model"],
        "temperature": 0.4,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {
        "Authorization": f"Bearer {keys['groq']}",
        "Content-Type": "application/json",
    }
    resp = requests.post(GROQ_URL, headers=headers, json=body, timeout=60)
    if resp.status_code >= 400:
        raise RuntimeError(f"Groq API error {resp.status_code}: {resp.text[:300]}")
    content = resp.json()["choices"][0]["message"]["content"]
    return parse_level_json(content)


def parse_level_json(content: str) -> dict:
    """Defensively extract a JSON object even if the model adds fences."""
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", content).strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # last resort: grab the outermost {...}
        match = re.search(r"\{.*\}", content, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def validate_level(level: dict) -> None:
    missing = REQUIRED_KEYS - level.keys()
    if missing:
        raise ValueError(f"Generated level missing keys: {sorted(missing)}")
    if level["category"] not in ("Unix", "SQL", "Python"):
        raise ValueError(f"Invalid category: {level['category']!r}")
    ss = level.get("starting_state") or {}
    if "files" not in ss:
        raise ValueError("starting_state.files is required")


# --------------------------------------------------------------------------
# Save
# --------------------------------------------------------------------------

def next_level_path(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = [int(m.group(1)) for f in out_dir.glob("level_*.json")
                if (m := re.match(r"level_(\d+)\.json$", f.name))]
    n = max(existing, default=0) + 1
    return out_dir / f"level_{n}.json"


def save_level(level: dict, context: dict, out_dir: Path) -> Path:
    # keep provenance so we can trace a level back to its SO thread
    level["_source"] = {
        "url": context.get("source_url"),
        "score": context.get("score"),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    path = next_level_path(out_dir)
    path.write_text(json.dumps(level, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_manifest(out_dir: Path) -> Path:
    """
    Browsers can't list a directory, so index the generated levels into a
    manifest the web terminal can fetch and iterate over.
    """
    files = sorted(out_dir.glob("level_*.json"),
                   key=lambda f: int(re.match(r"level_(\d+)\.json$", f.name).group(1)))
    entries = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        entries.append({
            "file": f.name,
            "ticket_id": data.get("ticket_id"),
            "category": data.get("category"),
            "title": data.get("title"),
        })
    manifest = out_dir / "manifest.json"
    manifest.write_text(
        json.dumps({"levels": entries, "count": len(entries)}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return manifest


# --------------------------------------------------------------------------
# Offline sample (lets you exercise the pipeline with no network/keys)
# --------------------------------------------------------------------------

OFFLINE_CONTEXT = {
    "source_url": "https://stackoverflow.com/q/000000",
    "score": 4242,
    "title": "Bash script fails with 'Permission denied' even though file exists",
    "tags": ["linux", "bash"],
    "error_report": "I wrote deploy.sh but running ./deploy.sh returns "
                    "'bash: ./deploy.sh: Permission denied'. The file is clearly there.",
    "solution_notes": "The script is not executable. Run chmod +x deploy.sh "
                      "to add the execute bit, then ./deploy.sh works.",
}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_one(keys, tag, difficulty, skip, offline, out_dir, verbose):
    if offline:
        context = dict(OFFLINE_CONTEXT)
    else:
        print(f"  → fetching Stack Overflow thread for [{tag}] (skip={skip})…")
        context = fetch_question(keys, tag, skip=skip)
    print(f"  → source: {context['title'][:70]}  (score {context.get('score')})")

    if offline and not keys.get("groq"):
        # fully offline demo level so the pipeline is testable end-to-end
        level = _offline_level(context)
    else:
        print(f"  → asking {keys['model']} to generate the level JSON…")
        level = generate_with_llm(keys, context, difficulty)

    validate_level(level)
    path = save_level(level, context, out_dir)
    print(f"  ✓ saved {path.relative_to(ROOT)}  [{level['category']}] \"{level['title']}\"")
    if verbose:
        print(json.dumps(level, indent=2, ensure_ascii=False))
    return path


def _offline_level(context):
    return {
        "ticket_id": "OPS-OFFLINE-001",
        "category": "Unix",
        "title": "deploy.sh won't run — Permission denied",
        "problem_description": "A deploy script exists but refuses to execute. "
                               "Running it returns 'Permission denied'. The file "
                               "is present in the directory.",
        "starting_state": {
            "files": {"deploy.sh": "#!/bin/bash\necho 'Deploying...'\n"},
            "db_schema": None,
        },
        "winning_condition_hint": "chmod +x deploy.sh",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate DEV-SIM levels from Stack Overflow + an LLM.")
    parser.add_argument("--tag", help="SO tag set, e.g. 'python;sql'. Default cycles the built-in DevOps tags.")
    parser.add_argument("--count", type=int, default=1, help="How many levels to generate.")
    parser.add_argument("--difficulty", choices=list(DIFFICULTY_NOTES), default="original",
                        help="Scale the generated problem's difficulty.")
    parser.add_argument("--model", help="Override the Groq model id.")
    parser.add_argument("--out-dir", default=str(LEVELS_DIR), help="Where to write level_N.json files.")
    parser.add_argument("--offline", action="store_true", help="Use bundled sample data (no network).")
    parser.add_argument("--verbose", action="store_true", help="Print each generated level JSON.")
    args = parser.parse_args(argv)

    keys = load_keys()
    if args.model:
        keys["model"] = args.model

    if not args.offline and not keys.get("stack"):
        print("⚠  No STACK_API_KEY found — proceeding anonymously (lower quota).", file=sys.stderr)

    out_dir = Path(args.out_dir)
    print(f"DEV-SIM level generator → {out_dir}")

    made = 0
    for i in range(args.count):
        tag = args.tag or DEFAULT_TAGS[i % len(DEFAULT_TAGS)]
        try:
            build_one(keys, tag, args.difficulty, skip=i, offline=args.offline,
                      out_dir=out_dir, verbose=args.verbose)
            made += 1
        except Exception as exc:
            print(f"  ✗ failed for tag '{tag}': {exc}", file=sys.stderr)

    if made:
        manifest = write_manifest(out_dir)
        print(f"  ✓ wrote {manifest.relative_to(ROOT) if manifest.is_relative_to(ROOT) else manifest}")

    print(f"\nDone. {made}/{args.count} level(s) generated in {out_dir}.")
    return 0 if made else 1


if __name__ == "__main__":
    raise SystemExit(main())
