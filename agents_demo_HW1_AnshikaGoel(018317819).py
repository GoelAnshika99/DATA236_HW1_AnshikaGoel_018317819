import argparse
import json
import re
import time
from typing import List
from pydantic import BaseModel, Field, field_validator
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
def summaryValidation(s):
    return len(re.findall(r"\b\w[\w'-]*\b", s or ""))
class DataBlock(BaseModel):
    tags: List[str] = Field(..., description="Exactly 3 concise, lowercase topical tags (no meta).")
    summary: str = Field(..., description="One sentence, <= 25 words, no filler.")
    issues: List[str] = Field(default_factory=list)
    @field_validator("tags")
    @classmethod
    def _three_tags(cls, v):
        meta_ban = {"json", "planner", "reviewer", "finalizer", "agent", "llm", "model", "prompt"}
        clean, seen = [], set()
        for i in v or []:
            i = (i or "").strip().lower()
            if not i or i in meta_ban:
                continue
            i = re.sub(r"\b(post|here|topic|the|article|and|an|a|of|about|content)\b", "", i).strip()
            if i and i not in seen:
                clean.append(i)
                seen.add(i)
            if len(clean) == 3:
                break
        return clean[:3]
    @field_validator("summary")
    @classmethod
    def _limit_25(cls, v):
        v = re.sub(r"^\s*here\s+is\s+the\s+paraphrased.*?:\s*", "", v, flags=re.I)
        v = re.sub(r"^\s*(this|the)\s+(post|content|article)\s+.*?:\s*", "", v, flags=re.I)
        words = re.findall(r"\b\w[\w'-]*\b", (v or "").strip())
        return " ".join(words[:25])
class AgentJSON(BaseModel):
    thought: str
    message: str
    data: DataBlock
    @field_validator("message")
    @classmethod
    def _ensure_message(cls, v):
        v = (v or "").strip()
        return v if v else "Draft analyzed and improved; provided concise tags and a <=25-word summary."
def build_llm(model, base_url, temperature= 0.2, json_mode= True):
    kwargs = dict(model=model, base_url=base_url, temperature=temperature, num_ctx=2048)
    if json_mode:
        kwargs["format"] = "json"
    return ChatOllama(**kwargs)
def extract_json(text):
    text = (text or "").strip()
    try:
        json.loads(text)
        return text
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text
def call_agent(llm, system_prompt, human_prompt, max_repairs = 2):
    def _invoke(sys_msg, hum_msg):
        resp = llm.invoke([SystemMessage(content=sys_msg), HumanMessage(content=hum_msg)])
        return resp.content
    raw = _invoke(system_prompt, human_prompt)
    candidate = extract_json(raw)
    for k in range(max_repairs + 1):
        try:
            return AgentJSON(**json.loads(candidate))
        except Exception:
            if k == max_repairs:
                return AgentJSON(
                    thought="Fallback",
                    message="Draft analyzed and improved; provided concise tags and a <=25-word summary.",
                    data=DataBlock(tags=[],
                                   summary="Concise summary not provided by the model",
                                   issues=["autofix"])
                )
            repair = (
                "Previous response was invalid JSON for the required schema. "
                "Return STRICT JSON ONLY with shape:\n"
                '{ "thought": str, "message": str, "data": { "tags":[str,str,str], "summary": str, "issues":[str,...] } }\n'
                "Constraints:\n"
                "- Exactly 3 concise, lowercase, topic-derived tags (no meta: json/planner/reviewer/finalizer/agent/llm)\n"
                "- Summary <= 25 words, no filler\n"
                "Fix this JSON:\n"
                f"{candidate}"
            )
            raw = _invoke(system_prompt, repair)
            candidate = extract_json(raw)
def print_block(title, payload):
    print(f"--- {title} ---")
    if isinstance(payload, (dict, list)):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(payload)
def demeta_tags(tags, title, content):
    meta_ban = {"json", "planner", "reviewer", "finalizer", "agent", "llm", "model", "prompt"}
    keep = [t for t in (tags or []) if t not in meta_ban]
    if len(keep) < 3:
        import collections
        text = f"{title} {content}".lower()
        words = re.findall(r"[a-z][a-z\-']{3,}", text)
        stop = {
            "the", "and", "with", "from", "that", "this", "into", "over", "under",
            "long", "term", "about", "your", "their", "very", "much", "more",
            "health", "wellness"
        }
        freq = collections.Counter(w for w in words if w not in stop)
        for w, _ in freq.most_common():
            if len(keep) == 3:
                break
            if w not in keep:
                keep.append(w)
    return keep[:3]
PLANNER_SYS = (
    "You are the Planner. Output STRICT JSON ONLY with keys thought,message,data.\n"
    "- data.tags = EXACTLY three concise, lowercase topical tags derived from TITLE/CONTENT (never meta like json/planner/reviewer).\n"
    "- data.summary = one sentence <= 25 words, no filler like 'Here is the paraphrased...'.\n"
    "- If unclear, add a short note to data.issues, but DO NOT ask the user for more input."
)
REVIEWER_SYS = (
    "You are the Reviewer. Improve the Planner JSON without asking for additional input.\n"
    "- Keep the same JSON shape (thought,message,data).\n"
    "- Fix grammar, strengthen topic-specific tags (never meta tags), ensure exactly 3 tags.\n"
    "- Ensure summary <= 25 words and clear.\n"
    "- STRICT JSON ONLY. Never request more information."
)
FINALIZER_SYS = (
    "You are the Finalizer. Merge Planner and Reviewer to produce the final JSON.\n"
    "- Exactly 3 concise, lowercase, topic-derived tags (no meta tags).\n"
    "- Summary <= 25 words, faithful to TITLE/CONTENT.\n"
    "- STRICT JSON ONLY. Never ask questions."
)
def main():
    ap = argparse.ArgumentParser(description="HW1 Part 2 - Assignment")
    ap.add_argument("--model", default="phi3:mini", help="e.g., phi3:mini or smollm:1.7b")
    ap.add_argument("--base_url", default="http://localhost:11434", help="Ollama base URL")
    ap.add_argument("--title", required=True, help="Blog title")
    ap.add_argument("--content", required=True, help="Blog content")
    ap.add_argument("--email", default="you@sjsu.edu", help="Author email for Publish Package")
    ap.add_argument("--strict", action="store_true", help="Keep outputs minimal/strict like the sample")
    args = ap.parse_args()
    llm = build_llm(args.model, args.base_url, json_mode=True)
    planner_h = (
        f"TITLE: {args.title}\n"
        f"CONTENT: {args.content}\n"
        "Return JSON now."
    )
    planner_obj = call_agent(llm, PLANNER_SYS, planner_h)
    print_block("Planner", planner_obj.model_dump())
    reviewer_h = json.dumps(planner_obj.model_dump(), ensure_ascii=False)
    reviewer_obj = call_agent(llm, REVIEWER_SYS, reviewer_h)
    print_block("Reviewer", reviewer_obj.model_dump())
    final_h = (
        "<<PLANNER JSON>>\n\n<<REVIEWER JSON>>"
        .replace("<<PLANNER JSON>>", json.dumps(planner_obj.model_dump(), ensure_ascii=False))
        .replace("<<REVIEWER JSON>>", json.dumps(reviewer_obj.model_dump(), ensure_ascii=False))
    )
    final_obj = call_agent(llm, FINALIZER_SYS, final_h)
    final_obj.data.tags = demeta_tags(final_obj.data.tags, args.title, args.content)
    finalized_output = final_obj.model_dump()
    finalized_output["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    print_block("Finalized Output with Timestamp", finalized_output)
    publish = {
        "title": args.title,
        "email": args.email,
        "content": args.content,
        "agents": [
            {"role": "Planner", "content": planner_obj.message},
            {"role": "Reviewer", "content": reviewer_obj.message},
        ],
        "final": finalized_output,
        "submissionDate": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    print_block("Publish Package", publish)
    return json.dumps(publish, ensure_ascii=False, indent=2)
if __name__ == "__main__":
    output_json = main()