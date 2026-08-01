"""
Multi-agent RFP analysis pipeline.

Instead of one large Gemini prompt trying to extract the summary, deliverables,
evaluation criteria, compliance checklist, and go/no-go decision all at once,
this module splits that into five independent, single-responsibility agents:

    SummaryAgent                    -> project_summary
    DeliverablesAgent               -> deliverables (with section_ref/source_file/quote)
    EvaluationCriteriaAgent         -> evaluation_criteria
    FAQAgent                        -> faqs (20 short Q&A pairs about the RFP)
    GoNoGoAgent                     -> go/no-go scoring against the company checklist

Why this shape:
  - Parallel:      all agents are dispatched together via a thread pool,
                    so wall-clock time is roughly max(agent times) instead of
                    sum(agent times).
  - Maintainable:   each agent owns its own prompt, its own JSON schema, and
                    its own fallback. Fixing/tuning "deliverables" extraction
                    never risks touching "compliance checklist" logic.
  - Isolated failure: if one agent's response fails to parse, only that
                    section falls back to a safe default — the other agents
                    still return normal results instead of the whole
                    analysis failing.

Trade-off worth knowing: since each agent sends the FULL RFP text
independently, this uses roughly 5x the input tokens of a single combined
prompt. You're trading token/cost for speed + isolation + maintainability.
"""

import json
import re
import time
import concurrent.futures
from typing import Dict, Any, List


def _extract_json(raw_text: str) -> str:
    """Strip markdown code fences (```json ... ```) that Gemini sometimes wraps JSON in."""
    raw_text = raw_text.strip()
    if "```json" in raw_text:
        raw_text = raw_text.split("```json")[1].split("```")[0].strip()
    elif "```" in raw_text:
        raw_text = raw_text.split("```")[1].split("```")[0].strip()
    return raw_text


def _loose_json_parse(raw_text: str) -> Dict[str, Any]:
    """Parse JSON, trying a couple of light repairs (trailing commas) before giving up."""
    json_str = _extract_json(raw_text)
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # try to salvage: grab the outermost {...} block and strip trailing commas
        match = re.search(r'(\{.*\})', json_str, re.DOTALL)
        if match:
            candidate = match.group(1)
            candidate = re.sub(r',\s*}', '}', candidate)
            candidate = re.sub(r',\s*]', ']', candidate)
            return json.loads(candidate)
        raise


def _describe_empty_response(response) -> str:
    """Best-effort explanation for why a model response had no text, so the
    fallback error message is diagnosable instead of a bare JSON error."""
    try:
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            prompt_feedback = getattr(response, "prompt_feedback", None)
            block_reason = getattr(prompt_feedback, "block_reason", None) if prompt_feedback else None
            if block_reason:
                return f"blocked by safety filters, block_reason={block_reason}"
            return "no candidates returned, likely blocked by safety filters or an API issue"
        finish_reason = getattr(candidates[0], "finish_reason", None)
        if finish_reason:
            return f"finish_reason={finish_reason}"
    except Exception:
        pass
    return "no further detail available"


class BaseAgent:
    """
    A single-responsibility RFP analysis agent.

    Subclasses implement build_prompt() and fallback(); postprocess() is
    optional and defaults to a no-op. run() is the same for every agent:
    build the prompt, call the model, parse JSON, postprocess, or fall back
    cleanly on any error.
    """

    name = "base"

    # Appended to every agent's prompt. The single most common cause of
    # broken JSON from the model is a literal double-quote character inside
    # a string value (e.g. quoting the RFP's exact wording verbatim,
    # quotation marks and all) — JSON has no way to tell that apart from a
    # string terminator unless it's escaped, and models frequently forget to
    # escape it. Instructing the model to avoid the character entirely is
    # far more reliable than trying to repair it after the fact.
    JSON_SAFETY_INSTRUCTIONS = """

        CRITICAL JSON SAFETY RULE: Never place a literal double-quote (")
        character inside any JSON string value (this applies to every field,
        including "reason", "evidence", "quote", "summary", "answer", etc.).
        If you need to reference wording from the source text that itself
        contains quotation marks, either paraphrase it slightly or replace the
        inner quotation marks with single quotes ('). A single unescaped
        double-quote inside a string value makes the entire JSON response
        invalid and unusable, so this rule overrides any instruction above
        that could tempt you to quote text verbatim with double quotes.
        """

    def build_prompt(self, text: str) -> str:
        raise NotImplementedError

    def fallback(self, error: str) -> Dict[str, Any]:
        raise NotImplementedError

    def postprocess(self, result: Dict[str, Any]) -> Dict[str, Any]:
        return result

    def run(self, model, text: str) -> Dict[str, Any]:
        prompt = self.build_prompt(text) + self.JSON_SAFETY_INSTRUCTIONS
        last_error = "Unknown error"
        for attempt in range(2):  # one retry in case of a transient empty/blocked response
            try:
                response = model.generate_content(
                    prompt,
                    generation_config={"max_output_tokens": 8192, "temperature": 0.4},
                )
                raw_text = getattr(response, "text", "") or ""
                if not raw_text.strip():
                    raise ValueError(
                        f"Model returned an empty response ({_describe_empty_response(response)})."
                    )
                result = _loose_json_parse(raw_text)
                return self.postprocess(result)
            except Exception as e:
                last_error = str(e)
                continue
        return self.fallback(last_error)


# ============================================================
# AGENT 1: Project Summary
# ============================================================
class SummaryAgent(BaseAgent):
    name = "summary"

    def build_prompt(self, text: str) -> str:
        return f"""
        You are an expert RFP analyst. Your ONLY job is to write a concise project summary.
        Do not extract deliverables, criteria, or anything else.

        RFP TEXT:
        {text}

        Return ONLY valid JSON, no text outside the JSON:
        {{"project_summary": "A brief 2-3 sentence summary of what the project/RFP is asking for"}}
        """

    def fallback(self, error: str) -> Dict[str, Any]:
        return {"project_summary": "Error processing document", "error": error}


# ============================================================
# AGENT 2: Deliverables (with exact source quote for PDF highlighting)
# ============================================================
class DeliverablesAgent(BaseAgent):
    name = "deliverables"

    def build_prompt(self, text: str) -> str:
        return f"""
        You are an expert RFP analyst. Your ONLY job is to extract DELIVERABLES.
        Do not write a project summary, evaluation criteria, or compliance checklist.

        The text below may contain content from MULTIPLE FILES, each marked with:
        "========================================"
        "FILE: [filename]"
        "========================================"

        **CRITICAL: For EVERY deliverable, include the EXACT filename it came from.**

        **CRITICAL: For EVERY deliverable, include a "quote" field — an EXACT, VERBATIM
        phrase copied directly from the RFP text (5 to 15 words). Do NOT paraphrase.
        Copy the exact characters as they appear in the RFP TEXT, including original
        spelling/punctuation. This is used to programmatically locate and highlight the
        deliverable inside the source PDF.**

        **EXCEPTION for the "quote" field only: if the ideal 5-15 word span from the
        RFP text would itself contain a double-quote character ("), shift the start or
        end of the quote by a few words (staying within the same sentence/area) so the
        chosen quote contains NO double-quote character at all, while still being an
        exact verbatim substring of the RFP text. Never let a quote value include a
        literal " character — pick a nearby span that avoids it instead.**

        RFP TEXT:
        {text}

        Group deliverables into BUSINESS CATEGORIES (max 5-6 categories, max 5-6 items each).
        For EACH deliverable include:
          - "name": The deliverable name
          - "section_ref": The section number where it appears (e.g., "Section XI.B.1")
          - "reason": Why this deliverable is required (include the section reference)
          - "source_file": The EXACT filename where this deliverable was found
          - "quote": An EXACT verbatim 5-15 word snippet copied directly from the RFP text

        Return ONLY valid JSON, no text outside the JSON:
        {{
            "deliverables": [
                {{
                    "category": "Documentation & Forms",
                    "items": [
                        {{"name": "RFP Cover Sheet", "section_ref": "Section XI.B.1", "reason": "Requires the return of the RFP cover sheet", "source_file": "doc1.txt", "quote": "Offerors must return the completed RFP Cover Sheet"}}
                    ]
                }}
            ]
        }}
        """

    def postprocess(self, result: Dict[str, Any]) -> Dict[str, Any]:
        deliverables = result.get('deliverables', [])

        if isinstance(deliverables, list) and len(deliverables) > 0:
            if isinstance(deliverables[0], str):
                flat_list = [
                    {"name": item, "section_ref": "N/A", "reason": "Required by RFP", "source_file": "Unknown", "quote": ""}
                    for item in deliverables
                ]
                deliverables = [{"category": "General", "items": flat_list}]
            else:
                for cat in deliverables:
                    items = cat.get('items', [])
                    if items and isinstance(items[0], str):
                        cat['items'] = [
                            {"name": item, "section_ref": "N/A", "reason": "Required by RFP", "source_file": "Unknown", "quote": ""}
                            for item in items
                        ]
                    else:
                        for item in items:
                            item.setdefault('section_ref', 'N/A')
                            item.setdefault('reason', 'Required by RFP')
                            item.setdefault('source_file', 'Unknown')
                            item.setdefault('quote', '')

        result['deliverables'] = deliverables
        return result

    def fallback(self, error: str) -> Dict[str, Any]:
        return {"deliverables": [], "error": error}

    def run(self, model, text: str) -> Dict[str, Any]:
        prompt = self.build_prompt(text) + self.JSON_SAFETY_INSTRUCTIONS
        last_error = "Unknown error"
        for attempt in range(2):  # one retry in case of a transient empty/blocked response
            try:
                response = model.generate_content(
                    prompt,
                    generation_config={"max_output_tokens": 8192, "temperature": 0.4},
                )
                raw_text = getattr(response, "text", "") or ""
                if not raw_text.strip():
                    raise ValueError(
                        f"Model returned an empty response ({_describe_empty_response(response)})."
                    )
                try:
                    result = _loose_json_parse(raw_text)
                except Exception:
                    # If the outer JSON is broken (most often a stray unescaped
                    # quote inside one "quote" field), salvage any individual
                    # deliverable objects that are still well-formed via regex,
                    # rather than discarding every deliverable the model found.
                    salvaged = self._salvage_deliverables(raw_text)
                    if not salvaged:
                        raise
                    result = {"deliverables": [{"category": "Recovered Items", "items": salvaged}]}
                return self.postprocess(result)
            except Exception as e:
                last_error = str(e)
                continue
        return self.fallback(last_error)

    @staticmethod
    def _salvage_deliverables(raw_text: str) -> List[Dict[str, str]]:
        pattern = re.compile(
            r'"name"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*'
            r'"section_ref"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*'
            r'"reason"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*'
            r'"source_file"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*'
            r'"quote"\s*:\s*"((?:[^"\\]|\\.)*)"',
            re.DOTALL,
        )
        items = []
        for name, section_ref, reason, source_file, quote in pattern.findall(raw_text):
            unescape = lambda s: s.replace('\\"', '"').strip()
            if unescape(name):
                items.append({
                    "name": unescape(name),
                    "section_ref": unescape(section_ref) or "N/A",
                    "reason": unescape(reason) or "Required by RFP",
                    "source_file": unescape(source_file) or "Unknown",
                    "quote": unescape(quote),
                })
        return items


# ============================================================
# AGENT 3: Evaluation Criteria
# ============================================================
class EvaluationCriteriaAgent(BaseAgent):
    name = "evaluation_criteria"

    def build_prompt(self, text: str) -> str:
        return f"""
        You are an expert RFP analyst. Your ONLY job is to extract EVALUATION CRITERIA —
        the criteria the client will use to judge/score proposals. Do not extract
        deliverables or anything else.

        RFP TEXT:
        {text}

        Return ONLY valid JSON, no text outside the JSON:
        {{"evaluation_criteria": ["Experience", "Technical Capability", "Cost", "..."]}}
        """

    def fallback(self, error: str) -> Dict[str, Any]:
        return {"evaluation_criteria": ["Unable to extract evaluation criteria"], "error": error}


# ============================================================
# AGENT 4: Frequently Asked Questions
# ============================================================
class FAQAgent(BaseAgent):
    """
    Reads the FULL RFP text and produces a set of short, practical
    question-and-answer pairs — the kind of basic questions a proposal
    team member (or someone deciding whether parts of the response process
    could be automated) would actually ask about this specific RFP.
    """

    name = "faqs"

    def build_prompt(self, text: str) -> str:
        return f"""
        You are an expert RFP analyst. Read the ENTIRE RFP text below and produce
        a Frequently Asked Questions (FAQ) list for someone who needs to quickly
        understand this specific RFP without reading the whole document.

        Include a mix of basic, practical questions such as: what is being
        requested, who is the issuing organization, what is the submission
        deadline, how should the proposal be submitted, what format is required,
        who can be contacted with questions, what is the estimated
        budget/contract value (if stated), what is the contract duration, what
        are the key eligibility requirements, and whether any parts of the
        submission/compliance process could realistically be automated.

        Base every answer STRICTLY on what is actually stated in the RFP text
        below. If the RFP does not state an answer to a reasonable question,
        either skip that question or say the RFP does not specify it — do not
        invent information.

        RFP TEXT:
        {text}

        HARD REQUIREMENTS (do not skip any of these):
        - You MUST return exactly 20 question-and-answer pairs. This is mandatory.
        - Every "answer" MUST be ONE short sentence, 20 words or fewer. This is
          mandatory — long answers are not allowed, no exceptions.
        - Output ONLY the JSON object below. No markdown fences, no commentary,
          no text before or after the JSON. The response must start with {{ and
          end with }}.
        - The JSON must be complete and syntactically valid — do not cut it off
          partway through.

        Return ONLY this JSON shape:
        {{
            "faqs": [
                {{"question": "What is this RFP asking for?", "answer": "A short, direct answer under 20 words."}}
            ]
        }}
        """

    def postprocess(self, result: Dict[str, Any]) -> Dict[str, Any]:
        faqs = result.get('faqs', [])
        cleaned = []
        for item in faqs:
            if isinstance(item, dict) and item.get('question') and item.get('answer'):
                cleaned.append({
                    "question": str(item['question']).strip(),
                    "answer": str(item['answer']).strip(),
                })
        result['faqs'] = cleaned
        return result

    def run(self, model, text: str) -> Dict[str, Any]:
        prompt = self.build_prompt(text) + self.JSON_SAFETY_INSTRUCTIONS
        last_error = "Unknown error"
        for attempt in range(2):  # one retry in case of a transient empty/blocked response
            try:
                response = model.generate_content(
                    prompt,
                    generation_config={"max_output_tokens": 8192, "temperature": 0.4},
                )
                raw_text = getattr(response, "text", "") or ""
                if not raw_text.strip():
                    raise ValueError(
                        f"Model returned an empty response ({_describe_empty_response(response)})."
                    )
                try:
                    result = _loose_json_parse(raw_text)
                except Exception:
                    # Even if the outer JSON is malformed/truncated, salvage any
                    # complete {"question": ..., "answer": ...} pairs via regex
                    # rather than returning nothing.
                    salvaged = self._salvage_qa_pairs(raw_text)
                    if not salvaged:
                        raise
                    result = {"faqs": salvaged}
                return self.postprocess(result)
            except Exception as e:
                last_error = str(e)
                continue
        return self.fallback(last_error)

    @staticmethod
    def _salvage_qa_pairs(raw_text: str) -> List[Dict[str, str]]:
        pattern = re.compile(
            r'"question"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"answer"\s*:\s*"((?:[^"\\]|\\.)*)"',
            re.DOTALL,
        )
        pairs = []
        for q, a in pattern.findall(raw_text):
            q = q.replace('\\"', '"').strip()
            a = a.replace('\\"', '"').strip()
            if q and a:
                pairs.append({"question": q, "answer": a})
        return pairs

    def fallback(self, error: str) -> Dict[str, Any]:
        return {"faqs": [], "error": error}


# ============================================================
# AGENT 5: Go/No-Go Decision (company checklist scoring)
# ============================================================
class GoNoGoAgent(BaseAgent):
    name = "go_no_go"

    def build_prompt(self, text: str) -> str:
        return f"""
        You are a Bid/No-Bid decision expert. Analyze this RFP against our company checklist.

        **CRITICAL: You MUST read and extract ALL numeric values (payment terms, dollar amounts, dates, deadlines) from the RFP text.**

        RFP TEXT (FULL DOCUMENT):
        {text}

        ========================================
        COMPANY CHECKLIST - Evaluate Each Item
        ========================================

        FINANCIAL CHECKLIST (Score each 0-10):
        1. "Payment Terms" - NET30 or better = 10, NET45 = 7, NET60 = 4, Not mentioned = 3
        2. "Insurance Requirements" - $5M or less = 10, $10M = 5, More = 0, Not mentioned = 3
        3. "Financial Stability" - We meet = 10, Partial = 7, Don't meet = 0
        4. "Profitability" - Budget known = 10, Vague = 5, Not mentioned = 3
        5. "Bid Bond" - Not required = 10, Can provide = 7, Can't = 0

        LEGAL CHECKLIST (Score each 0-10):
        6. "Eligibility Criteria" - Meet all = 10, Meet most = 7, Don't meet = 0
        7. "State Registration" - Not required = 10, Have it = 7, Don't have = 0
        8. "E-Verify" - Not required = 10, Have it = 7, Don't have = 0
        9. "Contract Terms" - Acceptable = 10, Review needed = 7, Major issues = 3
        10. "Legal Compliance" - Comply = 10, Mostly = 7, Don't = 0

        OPERATIONS CHECKLIST (Score each 0-10):
        11. "Required Forms" - All standard = 10, Some effort = 7, Extensive = 4
        12. "Submission Deadlines" - Feasible (30+ days) = 10, Tight (15-29 days) = 7, Very tight (<15 days) = 4
        13. "Signatory Authority" - Available = 10, Need approval = 7, Not available = 0
        14. "Vendor Registration" - Not required = 10, Have it = 7, Need to register = 3

        TECHNICAL CHECKLIST (Score each 0-10):
        15. "Scope Alignment" - Perfect = 10, Good fit = 7, Partial = 4
        16. "Technical Requirements" - Meet all = 10, Meet most = 7, Don't meet = 0
        17. "Industry Standards" - Comply = 10, Mostly = 7, Don't = 0
        18. "Security Requirements" - Meet = 10, Mostly = 7, Don't = 0
        19. "Integration Needs" - Can do = 10, With effort = 7, Can't = 0

        ========================================

        STATUS DEFINITIONS:
        - "GO" = Score 7-10 (We fully meet this)
        - "ESCALATE" = Score 3-6 (Missing info or needs management review)
        - "NO-GO" = Score 0-2 (Cannot meet this)

        Return JSON ONLY in this format:
        {{
            "checklist": [
                {{"category": "Financial", "item": "Payment Terms", "score": 10, "status": "GO", "reason": "NET30 terms found", "evidence": "Section 1: NET30"}}
            ],
            "go_count": 10,
            "no_go_count": 0,
            "escalate_count": 2,
            "summary": "2-3 sentences explaining WHY this decision was reached, citing the specific strongest factors and, if any exist, naming the specific escalation/no-go items that need attention. Do not write generic filler like 'this is a strong opportunity' without saying what makes it strong."
        }}

        IMPORTANT: DO NOT include "overall_score" in your JSON. It is calculated automatically.
        """

    def postprocess(self, result: Dict[str, Any]) -> Dict[str, Any]:
        if 'checklist' not in result:
            result['checklist'] = []

        checklist = result.get('checklist', [])
        total_score = sum(item.get('score', 0) for item in checklist)
        max_score = len(checklist) * 10

        result['overall_score'] = round(min(100, (total_score / max_score) * 100)) if max_score > 0 else 50

        score = result['overall_score']
        if score >= 71:
            result['overall_decision'] = 'GO'
        elif 51 <= score <= 70:
            result['overall_decision'] = 'ESCALATE'
        else:
            result['overall_decision'] = 'NO-GO'

        result['go_count'] = sum(1 for i in checklist if i.get('status') == 'GO')
        result['no_go_count'] = sum(1 for i in checklist if i.get('status') == 'NO-GO')
        result['escalate_count'] = sum(1 for i in checklist if i.get('status') == 'ESCALATE')
        result['conditional_count'] = result['escalate_count']

        return result

    def fallback(self, error: str) -> Dict[str, Any]:
        return {
            "overall_decision": "NEEDS REVIEW",
            "overall_score": 50,
            "checklist": [
                {"category": "Financial", "item": "Payment Terms", "score": 5, "status": "ESCALATE", "reason": "Could not analyze", "evidence": "Check RFP manually"},
                {"category": "Legal", "item": "Eligibility", "score": 5, "status": "ESCALATE", "reason": "Could not analyze", "evidence": "Check RFP manually"},
                {"category": "Operations", "item": "Deadlines", "score": 5, "status": "ESCALATE", "reason": "Could not analyze", "evidence": "Check RFP manually"},
                {"category": "Technical", "item": "Scope", "score": 5, "status": "ESCALATE", "reason": "Could not analyze", "evidence": "Check RFP manually"},
            ],
            "go_count": 0,
            "no_go_count": 0,
            "escalate_count": 4,
            "conditional_count": 4,
            "summary": f"AI analysis encountered an error: {error}. Please review the RFP manually.",
        }


# ============================================================
# ORCHESTRATOR: dispatch all agents concurrently, merge results
# ============================================================

# Registry — add a new agent here and it automatically joins the parallel run.
AGENT_REGISTRY = {
    "summary": SummaryAgent,
    "deliverables": DeliverablesAgent,
    "evaluation_criteria": EvaluationCriteriaAgent,
    "faqs": FAQAgent,
    "go_no_go": GoNoGoAgent,
}


def run_agents_parallel(model, text: str) -> Dict[str, Any]:
    """
    Run every registered agent concurrently against the same RFP text using a
    thread pool (Gemini calls are I/O-bound, so threads — not processes — are
    the right tool here). Returns a single merged dict shaped exactly like the
    old single-call analyze_rfp()/go_no_go_analysis() output, so the rest of
    the app doesn't need to change.

    Also returns "_agent_meta" with timing and any per-agent errors, so the UI
    can show the user how the parallel run went.
    """
    start_time = time.time()
    agent_instances = {name: cls() for name, cls in AGENT_REGISTRY.items()}
    raw_results: Dict[str, Any] = {}
    agent_timings: Dict[str, float] = {}
    agent_errors: Dict[str, str] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(agent_instances)) as executor:
        future_to_name = {}
        for name, agent in agent_instances.items():
            future = executor.submit(_timed_run, agent, model, text)
            future_to_name[future] = name

        for future in concurrent.futures.as_completed(future_to_name):
            name = future_to_name[future]
            try:
                result, elapsed = future.result()
                raw_results[name] = result
                agent_timings[name] = round(elapsed, 2)
                if isinstance(result, dict) and 'error' in result:
                    agent_errors[name] = result['error']
            except Exception as e:
                # Should be rare — run()/fallback() already catch agent-level errors —
                # but guard against anything unexpected (e.g. thread pool issues).
                raw_results[name] = agent_instances[name].fallback(str(e))
                agent_timings[name] = 0.0
                agent_errors[name] = str(e)

    total_elapsed = time.time() - start_time

    combined: Dict[str, Any] = {
        "project_summary": raw_results.get("summary", {}).get("project_summary", "No summary available"),
        "deliverables": raw_results.get("deliverables", {}).get("deliverables", []),
        "evaluation_criteria": raw_results.get("evaluation_criteria", {}).get("evaluation_criteria", []),
        "faqs": raw_results.get("faqs", {}).get("faqs", []),
        "go_no_go": raw_results.get("go_no_go", {}),
        "_agent_meta": {
            "total_elapsed_seconds": round(total_elapsed, 2),
            "per_agent_seconds": agent_timings,
            "errors": agent_errors,
        },
    }
    return combined


def _timed_run(agent: BaseAgent, model, text: str):
    start = time.time()
    result = agent.run(model, text)
    return result, time.time() - start
