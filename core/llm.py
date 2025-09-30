import json
from huggingface_hub import InferenceClient
from tenacity import retry, stop_after_attempt, wait_fixed

SYSTEM = (
    #Hard Instructions
    #"You are a technical editor. Rewrite the justification for refinery RBI components. "
    #"Rules: Do not invent facts. Do not change numbers, category letters, or the risk category. "
    #"Mention PoF and corrosion-rate stance, inspection-priority phrasing tied to risk profile, "
    #"all three consequence categories, which category governs CoF or if a tie, and the inventory and flammable-area levels. "
    #"Use the word 'component'. One concise paragraph. Return only the paragraph text."

    #Soft Instructions
    "You are a technical editor. Rewrite the justification to improve flow, sentence variety, and readability."
    "Rules: Do not invent facts. Do not change numbers, category letters, or the risk category. "
    "Keep all factual details (PoF number, corrosion rates, category letters, risk category)."
    "You may change wording, sentence order, and phrasing, but not the facts."

)

def build_prompt(payload: dict, draft_text: str):
    return (
        f"{SYSTEM}\n\n"
        f"Data JSON:\n{json.dumps(payload, ensure_ascii=False)}\n\n"
        f"Draft paragraph:\n{draft_text}\n\n"
        f"Rewrite now. Keep all facts and categories unchanged."
    )

@retry(stop=stop_after_attempt(2), wait=wait_fixed(1))
def polish_with_hf(model_id: str, hf_token: str, payload: dict, draft_text: str) -> str:
    client = InferenceClient(model=model_id, token=hf_token, timeout=45)
    prompt = build_prompt(payload, draft_text)
    # Use generic text-generation so it works with TGI or serverless Inference API
    text = client.text_generation(
        prompt=prompt,
        max_new_tokens=220,
        temperature=0.2,
        top_p=0.9,
        repetition_penalty=1.05,
        stop_sequences=["\n\n"]
    )
    return text.strip()
