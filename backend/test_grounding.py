import json
import re
from app.reconciliation import compute_reconciliation
from app.analytics import compute_analytics
from app.narrative import _build_report_context, _parse_llm_response, _auto_trace_figures
from app.validators import validate_billing_log
from pathlib import Path

SAMPLE_DIR = Path("c:/Users/Dell/Downloads/internr2/sample_data")
with open(SAMPLE_DIR / "billing_log_2026-07-27.json", "r", encoding="utf-8") as f:
    raw = json.load(f)

valid, errors = validate_billing_log(raw)
recon = compute_reconciliation(valid, "CLN-KNP-014", "2026-07-27", errors)
analytics = compute_analytics(valid, "CLN-KNP-014", "2026-07-27")
facts = _build_report_context(recon, analytics)

# Test 1: Grounding check script (extract numbers and verify against facts)
def check_grounding(narrative: str, facts: dict) -> list:
    # Extract all numeric tokens (including currency, commas, percentages)
    # Match things like 3,260 or 3260 or 18 or 75,500 or ₹3,260
    numbers = re.findall(r'\b\d+(?:,\d+)*(?:\.\d+)?\b', narrative)
    
    fact_values = set()
    for v in facts.values():
        if isinstance(v, str):
            # Strip non-numeric like ₹ and % for easier comparison
            clean = re.sub(r'[^\d,.]', '', v)
            if clean: fact_values.add(clean)
        elif isinstance(v, (int, float)):
            fact_values.add(str(v))

    unsupported = []
    for num in numbers:
        if num not in fact_values:
            unsupported.append(num)
            
    return unsupported

print("Testing Grounding...")
mock_narrative_good = "Today we collected ₹3,172 out of ₹3,260 billed across 18 visits."
print("Good narrative unsupported numbers:", check_grounding(mock_narrative_good, facts))

mock_narrative_hallucinated = "Today we collected ₹3,172 out of ₹3,260. Our profit was 50000. Peak was 9am."
print("Hallucinated narrative unsupported numbers:", check_grounding(mock_narrative_hallucinated, facts))

# Test 2: Malformed/garbage LLM response handling
print("\nTesting Malformed Responses...")

garbage_response = "I am a language model. I cannot help with this."
narrative, traced = _parse_llm_response(garbage_response, facts)
print("Garbage Response Narrative:", narrative)
print("Garbage Response Traced:", traced)

bad_json_response = '''
---NARRATIVE---
Here is the summary.
---TRACED---
[{"display_value": "₹3,172", field_name: missing_quotes}]
---END---
'''
narrative, traced = _parse_llm_response(bad_json_response, facts)
print("Bad JSON Response Narrative:", narrative)
print("Bad JSON Response Traced:", traced)

empty_response = ""
narrative, traced = _parse_llm_response(empty_response, facts)
print("Empty Response Narrative:", repr(narrative))
print("Empty Response Traced:", traced)

hallucinated_field = '''
---NARRATIVE---
We billed ₹3,260. Profit is ₹1,000.
---TRACED---
[{"display_value": "₹3,260", "field_name": "total_billed"}, {"display_value": "₹1,000", "field_name": "profit"}]
---END---
'''
narrative, traced = _parse_llm_response(hallucinated_field, facts)
print("Hallucinated Field Response Traced:", [t.dict() for t in traced])
