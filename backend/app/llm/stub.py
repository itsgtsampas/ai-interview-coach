"""Deterministic, offline LLM provider.

Runs the whole product with no API key and no network.  It is not a mock that
returns canned text: every stage derives its output from the *actual* CV and job
description supplied by the user, using rule-based analysis.  Citations are real
verbatim slices of the retrieved chunks, so the demo shows genuine grounding.

Swap it for OpenAIProvider by setting LLM_PROVIDER=openai; no calling code changes.
"""

import json
import re
from typing import Any

from pydantic import BaseModel

from app.llm.base import AgentStep, LLMResponse, RenderedPrompt, ToolSpec
from app.llm.tokens import estimate_tokens
from app.textutil import (
    best_evidence,
    build_idf,
    coverage,
    keywords,
    reflow,
    salient_terms,
    tokens,
    weighted_coverage,
)

_NUMBER = re.compile(r"\b\d+([.,]\d+)?\s*(%|x|ms|s|k|m|bn|million|users|rps|qps)?\b", re.I)

_STAR_MARKERS = {
    "situation": ["when i", "when we", "at the time", "we were", "our team", "the problem was",
                  "back at", "in my role", "during", "we had", "there was", "context"],
    "task": ["i was responsible", "my job", "i had to", "i needed", "my task", "i owned",
             "asked me", "i was asked", "goal was", "i was tasked"],
    "action": ["i built", "i implemented", "i designed", "i decided", "i wrote", "i introduced",
               "i migrated", "i refactored", "i led", "i proposed", "i set up", "i added",
               "i changed", "i created", "i chose", "i profiled", "i debugged"],
    "result": ["as a result", "resulted in", "reduced", "increased", "improved", "cut ",
               "dropped", "went from", "we shipped", "the outcome", "impact was", "saved",
               "grew", "eliminated"],
}

_BEHAVIOURAL_BANK = [
    ("Tell me about a time you disagreed with a technical decision your team had already "
     "committed to. What did you do, and how did it end?", "Influence and disagreement"),
    ("Describe something you shipped that did not have the impact you expected. How did you "
     "find out, and what changed afterwards?", "Ownership and learning"),
    ("Tell me about a time you had to deliver against a deadline with requirements that kept "
     "moving. What did you cut, and how did you decide?", "Prioritisation under pressure"),
    ("Describe a time you had to explain a technical trade-off to someone non-technical who "
     "disagreed with you.", "Communication"),
    ("Tell me about the last production problem you were responsible for. Walk me through what "
     "you did in the first hour.", "Incident ownership"),
    ("Describe a time you inherited code or a system you thought was wrong. What did you do "
     "about it?", "Pragmatism"),
    ("Tell me about a time you had to say no to a request from someone more senior than you.",
     "Boundaries and judgement"),
    ("Describe the piece of work you are most proud of from the last two years, and why.",
     "Motivation and self-assessment"),
]

# Headings that introduce actual requirements, and headings that introduce prose
# we must not mistake for requirements (company blurb, benefits, legal).
_INCLUDE_HEAD = re.compile(
    r"^\s*(requirements?|qualifications?|what\s+you.{0,3}ll\s+need|what\s+we.{0,3}re\s+looking\s+for|"
    r"must[\s-]?haves?|nice[\s-]?to[\s-]?haves?|responsibilities|about\s+you|your\s+profile|"
    r"skills?|preferred|bonus|desirable|essential|the\s+ideal\s+candidate)"
    r"\b.{0,24}$",
    re.I,
)
_EXCLUDE_HEAD = re.compile(
    r"^\s*(about\b|what\s+we\s+offer|benefits?|perks?|"
    r"how\s+to\s+apply|our\s+mission|why\s+join|compensation|salary|equal\s+opportunity|"
    r"the\s+role|overview|company|compensation|salary|pay|package|"
    r"important\s+notice|by\s+submitting|refer\s+a\s+friend|"
    r"additional\s+information|being\s+a\s+part\s+of|you\s+will\s+be\s+provided|"
    r"we\s+(?:will\s+)?(?:offer|provide)|what\s+we\s+provide|job\s+description|"
    r"company\s+description|responsibilities)"
    r"\b.{0,24}$",
    re.I,
)
_SOFT_BUCKET = re.compile(r"nice|bonus|preferred|desirable|a\s+plus|advantage", re.I)

# A line ending in a colon introduces a list; it is never itself a requirement.
# Postings lean on these heavily ("What would make you a fit for the role:",
# "Being a part of the team, you will be provided with:").
_LEAD_IN = re.compile(r":\s*$")

# Below this a quote is a list entry rather than a statement about work.
_FRAGMENT_CHARS = 25

# Benefits read like requirements to a keyword matcher but are what the employer
# gives, not what it asks for.
_BENEFIT = re.compile(
    r"\b(insurance|allowance|bonus\s+scheme|well[\s-]being|onboarding|buddy|"
    r"career\s+growth|development\s+plan|hybrid\s+working|day\s+off|holiday|"
    r"pension|perks?|udemy|learning\s+opportunit)", re.I,
)

# Used only by the headingless fallback, to tell a requirement from company
# marketing. A requirement either names a technology (which shows up as a
# capitalised term) or uses the vocabulary of asking for something.
# Traits a CV cannot demonstrate. Deliberately narrow: "mentoring engineers" and
# "collaborating with designers" describe things a person did and belong in the
# score, whereas "excellent communication skills" describes what they are like.
# Bare "team" is excluded for that reason — "mentoring within a team" is
# evidenced work; "work well as part of a team" is a disposition.
_BEHAVIOURAL_TRAIT = re.compile(
    r"\b(communication|organisational|organizational|interpersonal|attitude|"
    r"personality|motivated|passionate|enthusiastic|ambitious|proactive|"
    r"self[\s-]starter|autonomous|independently|teamwork|team\s+player|"
    r"part\s+of\s+a\s+team|team\s+environment|fast[\s-]paced|quick\s+learner|"
    r"mindset|work\s+ethic|detail[\s-]oriented|adaptable|resilient|"
    r"results[\s-]driven|can[\s-]do|willingness\s+to\s+learn)\b",
    re.I,
)


def _classify_kind(text: str) -> str:
    """Can a CV evidence this, or only an interview?

    A requirement naming a technology is evidenceable regardless of the words
    around it: "strong communication skills in Python code review" is still
    about Python.
    """
    if salient_terms(text):
        return "evidenceable"
    return "behavioural" if _BEHAVIOURAL_TRAIT.search(text) else "evidenceable"


_REQUIREMENT_SIGNAL = re.compile(
    r"\b(years?|experience|degree|proficien\w*|knowledge|abilit\w*|familiar\w*|"
    r"fluen\w*|skills?|understanding|expertise|background\s+in|comfortable|"
    r"track\s+record|required|must\s+have|competen\w*|qualified|hands[\s-]on)\b",
    re.I,
)

_BULLET = re.compile(r"^\s*[-•*·–—]\s+|^\s*\d+[.)]\s+")


def _clip(text: str, n: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


class StubLLMProvider:
    """Rule-based provider. Deterministic: same input always yields same output."""

    name = "stub"

    # -- public API ---------------------------------------------------------
    def complete_json(
        self,
        prompt: RenderedPrompt,
        schema: type[BaseModel],
        *,
        model: str,
        temperature: float,
    ) -> LLMResponse:
        handler = {
            "extract_requirements": self._extract_requirements,
            "analyse_match": self._analyse_match,
            "generate_questions": self._generate_questions,
            "evaluate_answer": self._evaluate_answer,
            "build_scorecard": self._build_scorecard,
        }.get(prompt.stage)
        if handler is None:
            raise ValueError(f"stub provider has no handler for stage {prompt.stage!r}")
        data = handler(prompt.payload)
        text = json.dumps(data, ensure_ascii=False)
        return LLMResponse(
            text=text,
            model=f"stub:{prompt.stage}",
            prompt_tokens=estimate_tokens(prompt.system + prompt.user),
            completion_tokens=estimate_tokens(text),
        )

    @staticmethod
    def _conclusive(observation: str | None) -> bool:
        """Did the lookup settle the question?

        A negative result counts: "nothing in the CV matched that" is the correct
        answer to "does my CV mention Kubernetes?", not a failed lookup. Only a
        tool error leaves the question open.
        """
        return bool(observation) and not observation.startswith("That lookup failed")

    def plan_step(
        self, prompt: RenderedPrompt, tools: list[ToolSpec], history: list[AgentStep]
    ) -> AgentStep:
        """One ReAct iteration: pick a tool, or answer from what has been observed."""
        message: str = prompt.payload.get("message", "")
        used = {s.tool for s in history if s.tool}
        low = message.lower()

        # Stop at the first lookup that settles the question. Chaining more tools
        # only adds unrelated material to the answer.
        settled = [s.observation for s in history if self._conclusive(s.observation)]
        if settled:
            return AgentStep(
                thought="That lookup settles the question; no further tools needed.",
                final_answer="\n\n".join(settled)
                + "\n\nAsk a follow-up if you want me to go deeper on this.",
            )

        intents = [
            ("get_match_report", ["gap", "match", "fit", "missing", "score", "ready", "weak",
                                  "strong", "chance"]),
            ("search_job_description", ["role", "job", "they want", "employer", "company",
                                        "requirement", "expect", "posting"]),
            ("search_cv", ["my cv", "my resume", "my experience", "have i", "did i", "my background"]),
            ("get_score_history", ["progress", "improv", "history", "previous", "so far",
                                   "practice", "answers"]),
        ]
        for tool, cues in intents:
            if tool in used:
                continue
            if any(c in low for c in cues):
                return AgentStep(
                    thought=f"The question mentions {next(c for c in cues if c in low)!r}. "
                            f"I should consult {tool} before answering.",
                    tool=tool,
                    tool_input={"query": message},
                )

        if not history:
            return AgentStep(
                thought="No specific signal in the question; the gap analysis is the most "
                        "useful general context.",
                tool="get_match_report",
                tool_input={"query": message},
            )

        tried = ", ".join(sorted(used)) or "no tools"
        return AgentStep(
            thought="No lookup returned anything useful.",
            final_answer=(
                "I could not find anything in your file that answers that. "
                f"I checked {tried}. Try naming a specific skill or technology, "
                "or run the gap analysis first if you have not already."
            ),
        )

    # -- stage handlers -----------------------------------------------------
    def _extract_requirements(self, payload: dict[str, Any]) -> dict:
        # Reflow first: PDF extraction hard-wraps lines, so without this a
        # requirement arrives truncated mid-clause ("...and workload").
        jd_text: str = reflow(payload.get("jd_text", ""))

        found: list[tuple[str, str]] = []
        in_requirements = False
        bucket = "must_have"

        for raw in jd_text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if _INCLUDE_HEAD.match(line):
                in_requirements = True
                bucket = "nice_to_have" if _SOFT_BUCKET.search(line) else "must_have"
                continue
            if _EXCLUDE_HEAD.match(line):
                in_requirements = False
                continue
            if not in_requirements:
                continue

            cleaned = _BULLET.sub("", raw).strip(" .;")

            # A colon-terminated line introduces the list that follows. It sets
            # the bucket, and is never emitted as a requirement itself.
            if _LEAD_IN.search(line):
                if _SOFT_BUCKET.search(line):
                    bucket = "nice_to_have"
                continue
            if _BENEFIT.search(cleaned):
                continue

            # Requirements are often a bare technology name — "Java", "Docker",
            # "Spring Boot" — so a flat minimum length discards the most
            # important ones. A short line is kept when it names something.
            long_enough = len(cleaned) >= 12 or (
                len(cleaned) >= 3 and bool(salient_terms(cleaned))
            )
            if not long_enough or len(cleaned) > 260:
                continue
            letters = [ch for ch in cleaned if ch.isalpha()]
            if letters and all(ch.isupper() for ch in letters):
                continue  # an unrecognised heading, not a requirement
            if len(keywords(cleaned)) < 1:
                continue

            low = cleaned.lower()
            if _SOFT_BUCKET.search(low):
                item_bucket = "nice_to_have"
            elif any(w in low for w in ("must", "required", "strong", "solid", "proven")):
                item_bucket = "must_have"
            else:
                item_bucket = bucket
            found.append((cleaned, item_bucket))

        # Fallback for postings with no recognisable section heading: take every
        # substantive line outside the sections we know to be boilerplate.
        # Returning a generic placeholder instead — the previous behaviour —
        # produced a flawless score against a requirement nobody had stated.
        if not found:
            skipping = False
            for raw in jd_text.splitlines():
                line = raw.strip()
                if not line:
                    continue
                if _INCLUDE_HEAD.match(line):
                    skipping = False
                    continue
                if _EXCLUDE_HEAD.match(line):
                    skipping = True
                    continue
                if skipping:
                    continue
                cleaned = _BULLET.sub("", raw).strip(" .;")
                letters = [ch for ch in cleaned if ch.isalpha()]
                if not (20 <= len(cleaned) <= 260) or not letters:
                    continue
                if all(ch.isupper() for ch in letters):
                    continue
                # Without this the fallback swallows the company blurb, and a
                # CV then scores perfectly against "we are growing fast".
                looks_like_requirement = (
                    bool(salient_terms(cleaned)) or bool(_REQUIREMENT_SIGNAL.search(cleaned))
                )
                if looks_like_requirement and len(keywords(cleaned)) >= 3:
                    found.append((cleaned, "must_have"))

        seen: set[str] = set()
        out: list[dict] = []
        for text, item_bucket in found:
            key = " ".join(sorted(keywords(text))[:6])
            if key in seen or not key:
                continue
            seen.add(key)
            clipped = _clip(text, 220)
            out.append({
                "text": clipped,
                "category": item_bucket,
                "kind": _classify_kind(clipped),
            })
            if len(out) >= 12:
                break

        # No placeholder. An empty list is an honest answer that the caller can
        # act on; a fabricated requirement is not.
        return {"requirements": out}

    def _analyse_match(self, payload: dict[str, Any]) -> dict:
        reqs: list[dict] = payload.get("requirements", [])
        evidence: dict[str, list[dict]] = payload.get("evidence", {})
        items: list[dict] = []

        # Weight each requirement term by how distinctive it is across the CV
        # passages, so a rare term ("graphql") outweighs a generic one ("apis").
        idf = build_idf([c["text"] for cands in evidence.values() for c in cands])

        for idx, req in enumerate(reqs):
            text = req["text"]
            cands = evidence.get(str(idx), [])
            best: dict | None = None
            best_cov = 0.0
            best_quote = ""
            pivot_present = False
            # Score on the single best sentence rather than the whole section: a
            # long section can accumulate coverage from unrelated lines, which
            # would credit the candidate for evidence no sentence actually gives.
            # Prefer a sentence carrying the decisive term over a merely wordy one.
            # Rank on evidence first, then reject bare fragments. A skills-list
            # entry and a sentence describing the work cover the requirement
            # equally, but "Spring Boot" is a weaker citation than the sentence
            # saying what was built with it. The preference is only strong
            # enough to break that tie: among real sentences, retrieval order
            # decides, so the most relevant passage still wins.
            best_rank: tuple = (False, 0.0, False)
            for c in cands:
                quote, cov, has_pivot = best_evidence(text, c["text"], idf)
                rank = (has_pivot, round(cov, 3), len(quote) >= _FRAGMENT_CHARS)
                if rank > best_rank:
                    best_rank = rank
                    best_cov, best, best_quote, pivot_present = cov, c, quote, has_pivot

            # The distinctive term must be present. Without this gate,
            # "Familiarity with GraphQL APIs" scores as partial against any CV
            # that mentions APIs at all.
            # Thresholds calibrated with evals/run.py over the full golden set,
            # not by eye on one example. A sweep showed a flat optimum between
            # 0.20 and 0.25 (0.806 exact accuracy); 0.30 — the value picked by
            # hand against the backend pair alone — scored 0.710.
            if best is not None and pivot_present and best_cov >= 0.22:
                status, conf = "strong", min(0.95, 0.45 + best_cov)
            elif best is not None and pivot_present and best_cov >= 0.10:
                status, conf = "partial", 0.3 + best_cov
            else:
                status, conf = "missing", max(0.10, best_cov / 2)

            quote = page = chunk_id = section = None
            if status != "missing" and best is not None:
                quote = best_quote
                page, chunk_id = best.get("page"), best.get("chunk_id")
                section = best.get("section")

            matched = [k for k in keywords(text) if k in set(tokens(best_quote))] if best else []
            if status == "strong":
                reasoning = (
                    f"The CV covers {int(best_cov * 100)}% of the terms in this requirement"
                    + (f" (matched: {', '.join(matched[:5])})" if matched else "")
                    + f", in the {section or 'CV'} section, and the surrounding sentence "
                      "describes concrete work rather than a keyword list."
                )
            elif status == "partial":
                missing_kw = [k for k in keywords(text) if k not in matched][:4]
                reasoning = (
                    f"There is related material in the {section or 'CV'} section "
                    f"({int(best_cov * 100)}% term overlap), but "
                    + (f"nothing addressing {', '.join(missing_kw)}. " if missing_kw else "it is thin. ")
                    + "An interviewer would probe how deep this actually goes."
                )
            else:
                reasoning = (
                    "No passage in the CV covers this requirement above the relevance floor. "
                    "Treat it as a genuine gap rather than an omission of wording."
                )

            items.append({
                "requirement": text,
                "category": req.get("category", "must_have"),
                "kind": req.get("kind", "evidenceable"),
                "status": status,
                "confidence": round(conf, 2),
                "reasoning": reasoning,
                "evidence_quote": quote,
                "evidence_page": page,
                "evidence_chunk_id": chunk_id,
                "evidence_section": section,
            })

        # Behavioural requirements are excluded: no CV can evidence them, so
        # counting them as missing would mark the candidate down for a property
        # of the medium rather than of their experience. They are surfaced as
        # interview questions instead.
        weights = {"strong": 1.0, "partial": 0.5, "missing": 0.0}
        scored = [i for i in items if i["kind"] == "evidenceable"]
        total = weight_sum = 0.0
        for it in scored:
            w = 2.0 if it["category"] == "must_have" else 1.0
            total += weights[it["status"]] * w
            weight_sum += w
        overall = int(round(100 * total / weight_sum)) if weight_sum else 0

        n_missing = sum(1 for i in scored if i["status"] == "missing")
        n_strong = sum(1 for i in scored if i["status"] == "strong")
        n_behavioural = len(items) - len(scored)
        must_missing = [i["requirement"] for i in scored
                        if i["status"] == "missing" and i["category"] == "must_have"]

        if overall >= 75:
            verdict = "Strong match"
        elif overall >= 50:
            verdict = "Credible match with gaps"
        elif overall >= 30:
            verdict = "Stretch application"
        else:
            verdict = "Weak match"

        summary = (
            f"{n_strong} of {len(scored)} requirements are backed by concrete evidence in the CV; "
            f"{n_missing} have none. "
            + (f"A further {n_behavioural} ask about how you work rather than what you "
               "have done, so they are left to the interview and excluded from the score. "
               if n_behavioural else "")
            + (f"The gaps that will cost you most are: {'; '.join(must_missing[:3])}. "
               if must_missing else "No must-have requirement is completely unevidenced. ")
            + "Every verdict below links to the exact sentence it was drawn from, so you can "
              "check the reasoning yourself."
        )
        return {"overall_score": overall, "verdict": verdict, "summary": summary, "items": items}

    def _generate_questions(self, payload: dict[str, Any]) -> dict:
        items: list[dict] = payload.get("items", [])
        n_tech: int = payload.get("n_technical", 5)
        n_behav: int = payload.get("n_behavioural", 3)
        role: str = payload.get("target_role") or "this role"

        # Technical questions come only from requirements a CV could evidence;
        # the rest are exactly what the behavioural half of the interview is for.
        evidenceable = [i for i in items if i.get("kind", "evidenceable") == "evidenceable"]
        behavioural_reqs = [i for i in items if i.get("kind") == "behavioural"]

        status_rank = {"missing": 0.0, "partial": 1.0, "strong": 2.0}
        ordered = sorted(
            evidenceable,
            key=lambda i: status_rank.get(i["status"], 3.0)
            + (0.0 if i["category"] == "must_have" else 1.5),
        )

        questions: list[dict] = []
        for item in ordered[:n_tech]:
            req, status = item["requirement"], item["status"]
            short = _clip(req, 90)
            # Spliced into the middle of a sentence, so drop the leading capital
            # unless the requirement opens with a proper noun (PostgreSQL, AWS).
            if short[:2] != short[:2].upper():
                short = short[0].lower() + short[1:]
            if status == "missing":
                text = (
                    f"The role requires {short}. I can't find it anywhere in your CV. "
                    "How would you get productive with it in your first month, and what "
                    "part do you expect to find hardest?"
                )
                difficulty, why = 4, "your CV shows no evidence for it at all"
            elif status == "partial":
                hint = _clip(item.get("evidence_quote") or "", 90)
                text = (
                    f"Your CV touches {short}"
                    + (f' — you wrote "{hint}". ' if hint else ". ")
                    + "Take that further: what would have broken first if the load had been "
                      "ten times higher, and what would you have changed?"
                )
                difficulty, why = 3, "your evidence is thin, so an interviewer will probe how deep it goes"
            else:
                hint = _clip(item.get("evidence_quote") or "", 90)
                text = (
                    f"You list {short}"
                    + (f' — specifically "{hint}". ' if hint else ". ")
                    + "Walk me through the hardest decision you made there, what you gave up "
                      "to get it, and whether you still think it was right."
                )
                difficulty, why = 3, "it is your strongest claim here, so expect it to be tested hardest"

            questions.append({
                "category": "technical",
                "text": text,
                "rationale": f"Asked because the job description lists this as a "
                             f"{item['category'].replace('_', ' ')} and {why}.",
                "difficulty": difficulty,
                "linked_requirement": req,
            })

        # A behavioural requirement the posting actually states beats a generic
        # one from the bank: the candidate is asked about what this employer
        # said they care about.
        for req in behavioural_reqs[:n_behav]:
            trait = _clip(req["requirement"], 90)
            questions.append({
                "category": "behavioural",
                "text": (
                    f"This role asks for {trait[0].lower() + trait[1:] if trait[:2] != trait[:2].upper() else trait}. "
                    "Tell me about a specific time that was tested — what happened, "
                    "what you did, and how it turned out."
                ),
                "rationale": "Asked because the job description states this and no CV can "
                             "evidence it. This is where it gets assessed.",
                "difficulty": 3,
                "linked_requirement": req["requirement"],
            })

        # Top up from the bank when the posting names fewer traits than asked for.
        offset = len(items) % max(1, len(_BEHAVIOURAL_BANK))
        for i in range(n_behav - len(behavioural_reqs[:n_behav])):
            text, competency = _BEHAVIOURAL_BANK[(offset + i) % len(_BEHAVIOURAL_BANK)]
            questions.append({
                "category": "behavioural",
                "text": text,
                "rationale": f"Probes {competency.lower()}, which {role} interviews weight "
                             "heavily and which a CV cannot evidence.",
                "difficulty": 3,
                "linked_requirement": competency,
            })

        return {"questions": questions}

    def _evaluate_answer(self, payload: dict[str, Any]) -> dict:
        answer: str = payload.get("answer_text", "")
        requirement: str = payload.get("linked_requirement", "")
        rubric: str = payload.get("rubric", "technical")

        toks = tokens(answer)
        words = len(toks)
        sents = max(1, answer.count(".") + answer.count("!") + answer.count("?"))
        low = answer.lower()
        metrics = len(_NUMBER.findall(answer))
        i_count, we_count = low.count(" i "), low.count(" we ")
        cov = coverage(requirement, answer) if requirement else 0.5
        present = {k: sum(1 for m in v if m in low) for k, v in _STAR_MARKERS.items()}

        def scale(value: float, lo: float, hi: float) -> int:
            if value <= lo:
                return 1
            if value >= hi:
                return 5
            return int(round(1 + 4 * (value - lo) / (hi - lo)))

        length_score = scale(words, 25, 170)
        trace: list[str] = [
            f"1. Shape: {words} words across {sents} sentences. "
            + ("Too short to develop an argument." if words < 60
               else "Long enough to develop an argument." if words < 320
               else "Long — an interviewer's attention will drift before the point lands.")
        ]

        if rubric == "star":
            s_sit = scale(present["situation"], 0, 2)
            s_task = scale(present["task"], 0, 2)
            s_act = min(5, scale(present["action"], 0, 3))
            s_res = scale(present["result"] + metrics, 0, 3)
            s_imp = scale(metrics, 0, 3)
            trace += [
                f"2. Situation: {present['situation']} context marker(s) found. "
                + ("The setup is concrete." if present["situation"] else
                   "No explicit setup — the listener cannot picture where this happened."),
                f"3. Task: {present['task']} ownership marker(s). "
                + ("You state what you personally owned." if present["task"] else
                   "You never say what *you* were responsible for, only what happened."),
                f"4. Action: {present['action']} first-person action verb(s); "
                f"'I' used {i_count} times against 'we' {we_count} times. "
                + ("Your individual contribution is visible." if i_count >= we_count else
                   "The answer hides behind 'we' — an interviewer cannot tell what you did."),
                f"5. Result: {present['result']} outcome phrase(s) and {metrics} number(s). "
                + ("The outcome is quantified." if metrics else
                   "No numbers — the result is asserted, not demonstrated."),
            ]
            criteria = [
                {"name": "Situation", "score": s_sit, "comment": "Context the listener can picture."},
                {"name": "Task", "score": s_task, "comment": "What you personally owned."},
                {"name": "Action", "score": s_act, "comment": "Specific steps you took."},
                {"name": "Result", "score": s_res, "comment": "What changed because of you."},
                {"name": "Impact", "score": s_imp, "comment": "Quantified, durable outcome."},
            ]
        else:
            s_corr = scale(cov * 5 + (1 if metrics else 0), 0.5, 4.0)
            s_depth = scale(words * (0.5 + cov), 40, 260)
            s_trade = scale(sum(low.count(w) for w in
                                ("trade-off", "tradeoff", "instead of", "rather than", "downside",
                                 "cost of", "we chose", "alternative", "but ")), 0, 3)
            s_comm = scale(6 - abs(sents - 7) * 0.6, 1.0, 5.5)
            s_rel = scale(cov, 0.1, 0.7)
            trace += [
                f"2. Relevance: the answer covers {int(cov * 100)}% of the terms in the "
                f"requirement it was asked against.",
                f"3. Specificity: {metrics} concrete number(s) or measurement(s). "
                + ("Claims are anchored." if metrics else "Nothing is measurable."),
                f"4. Trade-offs: {'discussed' if s_trade >= 3 else 'not discussed'} — senior "
                "answers name what was given up, not only what was chosen.",
                f"5. Structure: {sents} sentences; "
                + ("well-paced." if 4 <= sents <= 10 else "pacing works against the point."),
            ]
            criteria = [
                {"name": "Correctness", "score": s_corr, "comment": "Technically sound and on-topic."},
                {"name": "Depth", "score": s_depth, "comment": "Goes past the surface."},
                {"name": "Trade-offs", "score": s_trade, "comment": "Names what was given up."},
                {"name": "Communication", "score": s_comm, "comment": "Clear and well-paced."},
                {"name": "Relevance", "score": s_rel, "comment": "Answers what was asked."},
            ]

        for c in criteria:
            c["score"] = max(1, min(5, int(round((c["score"] * 3 + length_score) / 4))))
        overall = round(sum(c["score"] for c in criteria) / len(criteria), 1)

        ranked = sorted(criteria, key=lambda c: c["score"])
        weakest, strongest = ranked[0], ranked[-1]
        strengths = [f"{c['name']} ({c['score']}/5) — {c['comment']}"
                     for c in ranked[::-1] if c["score"] >= 4][:3]
        if not strengths:
            strengths = [f"{strongest['name']} is the most developed part of the answer, at "
                         f"{strongest['score']}/5."]
        improvements = [f"{c['name']} ({c['score']}/5) — {c['comment']}"
                        for c in ranked if c["score"] <= 3][:3]
        if not improvements:
            improvements = ["Tighten the opening: the first sentence should state the outcome."]

        if rubric == "star":
            model_answer = (
                "Situation — name the company, the team and the moment in one sentence. "
                "Task — say what you specifically owned, not what the team was doing. "
                "Action — three or four concrete steps in first person, with the decision you "
                "made at each. Result — one measured outcome and how you know it. "
                "Impact — what stayed changed after you left it."
            )
        else:
            model_answer = (
                f"Open with a one-sentence answer to {_clip(requirement, 70) or 'the question'}. "
                "Then give one concrete example from your own work, including the constraint you "
                "were under. Name the alternative you rejected and why. Close with the measurable "
                "result and what you would do differently at ten times the scale."
            )

        follow_ups = {
            "Situation": "Before we go on — where exactly was this, and when?",
            "Task": "What part of that were you personally accountable for?",
            "Action": "Take me through the first thing you actually did.",
            "Result": "How did you measure whether it worked?",
            "Impact": "Is it still in place today? What happened after you moved on?",
            "Correctness": "Let's check one detail — why that approach and not the obvious alternative?",
            "Depth": "Go one level deeper: what happens under the hood when that runs?",
            "Trade-offs": "What did you give up by choosing that?",
            "Communication": "Summarise that in two sentences for a non-technical stakeholder.",
            "Relevance": "Bring that back to the requirement — how does it apply here?",
        }

        return {
            "rubric": rubric,
            "reasoning": "\n".join(trace),
            "criteria": criteria,
            "overall_score": overall,
            "strengths": strengths,
            "improvements": improvements,
            "model_answer": model_answer,
            "follow_up_question": follow_ups.get(weakest["name"], "Tell me more about that."),
        }

    def _build_scorecard(self, payload: dict[str, Any]) -> dict:
        report: dict = payload.get("report", {})
        evals: list[dict] = payload.get("evaluations", [])
        match_score = int(report.get("overall_score", 0))

        competencies: dict[str, list[float]] = {}
        for e in evals:
            for name, score in e.get("criterion_scores", {}).items():
                competencies.setdefault(name, []).append(float(score))
        comp_avg = {k: round(sum(v) / len(v), 2) for k, v in competencies.items()}

        answer_mean = (
            sum(e.get("overall_score", 0) for e in evals) / len(evals) if evals else 0.0
        )
        answer_pct = (answer_mean / 5) * 100
        readiness = int(round(0.4 * match_score + 0.6 * answer_pct)) if evals else match_score

        if readiness >= 75:
            band = "Interview ready"
        elif readiness >= 55:
            band = "Nearly ready"
        elif readiness >= 35:
            band = "Needs work"
        else:
            band = "Not ready yet"

        items = report.get("items", [])
        strengths = [f"{i['requirement']} — evidenced in your CV"
                     for i in items if i.get("status") == "strong"][:4]
        for name, score in sorted(comp_avg.items(), key=lambda kv: -kv[1])[:2]:
            if score >= 4:
                strengths.append(f"{name} scored {score}/5 across your practice answers")

        gaps = [f"{i['requirement']} — no evidence in your CV"
                for i in items if i.get("status") == "missing"][:4]
        for name, score in sorted(comp_avg.items(), key=lambda kv: kv[1])[:2]:
            if score <= 3:
                gaps.append(f"{name} averaged {score}/5 across your practice answers")

        actions: list[dict] = []
        for i in items:
            if i.get("status") == "missing" and i.get("category") == "must_have":
                actions.append({
                    "priority": "high",
                    "title": f"Build a story for: {_clip(i['requirement'], 80)}",
                    "why": "It is a must-have on the job description and your CV shows nothing "
                           "for it. This is the question most likely to end the interview.",
                    "how": "Find the closest thing you have actually done, and prepare a STAR "
                           "answer that names the gap honestly, then bridges to adjacent evidence.",
                })
        weak_dimensions = [n for n, sc in sorted(comp_avg.items(), key=lambda kv: kv[1]) if sc <= 3]
        for rank_i, name in enumerate(weak_dimensions):
            score = comp_avg[name]
            actions.append({
                    "priority": "high" if score <= 2 else "medium",
                    "title": f"Raise {name} from {score}/5",
                    "why": (f"{name} is your weakest scoring dimension across practice answers."
                            if rank_i == 0
                            else f"{name} is among your lowest scoring dimensions."),
                    "how": {
                        "Result": "Re-record two answers, each ending with one number.",
                        "Impact": "For each story, write down what was still true six months later.",
                        "Task": "Rewrite each opening to say what you personally owned.",
                        "Trade-offs": "For each answer, add the alternative you rejected and why.",
                        "Depth": "Pick one story and add the mechanism behind the decision.",
                    }.get(name, "Rewrite two answers with this dimension as the focus."),
            })
        for i in items:
            if i.get("status") == "partial" and len(actions) < 8:
                actions.append({
                    "priority": "medium",
                    "title": f"Deepen your evidence for: {_clip(i['requirement'], 80)}",
                    "why": "Your CV mentions this but does not show depth, so expect probing.",
                    "how": "Add scale, constraint and outcome to the bullet on your CV, then "
                           "rehearse the two-level-deeper version.",
                })
        if not actions:
            actions.append({
                "priority": "low",
                "title": "Rehearse your strongest three answers out loud",
                "why": "No structural gaps were found; the remaining risk is delivery.",
                "how": "Record yourself, then cut each answer to under 90 seconds.",
            })

        summary = (
            f"Your CV covers {match_score}% of what the role asks for. "
            + (f"Across {len(evals)} practice answer{'s' if len(evals) != 1 else ''} you averaged "
               f"{answer_mean:.1f}/5. " if evals else "You have not practised any answers yet. ")
            + f"Combined, that puts you at {readiness}/100 — {band.lower()}. "
            + ("Work the high-priority items first; they are the ones that end interviews."
               if any(a["priority"] == "high" for a in actions)
               else "The remaining work is refinement rather than repair.")
        )

        return {
            "readiness_score": readiness,
            "readiness_band": band,
            "summary": summary,
            "competencies": comp_avg,
            "strengths": strengths[:6],
            "gaps": gaps[:6],
            "action_items": actions[:8],
        }
