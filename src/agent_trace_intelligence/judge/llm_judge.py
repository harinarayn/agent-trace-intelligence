import litellm
import json
import re
import os

OPENAI_MODELS = ["gpt-", "azure/gpt-"]


def _supports_json_mode(model: str) -> bool:
    """Only OpenAI/Azure OpenAI models support response_format json_object natively."""
    return any(model.startswith(prefix) for prefix in OPENAI_MODELS)


def _extract_json(text: str) -> dict:
    """Fallback JSON extractor for models that don't support json_object mode.

    Strategy:
    1. Strip markdown code fences (```json ... ```)
    2. Walk the string character-by-character tracking brace depth to find the
       outermost { ... } block — avoids the greedy-regex truncation bug where
       re.search(r'{.*}') stops at the first } it finds inside a nested object.
    3. Try json.loads on the extracted block; raise with context on failure.
    """
    # Strip ```json ... ``` fences and leading/trailing whitespace
    text = re.sub(r"```(?:json)?\s*", "", text).strip()

    # Find outermost { ... } via brace depth tracking
    start = text.find("{")
    if start == -1:
        raise ValueError(f"No JSON object found in model response: {text[:200]}")

    depth = 0
    in_string = False
    escape_next = False
    for i, ch in enumerate(text[start:], start=start):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError as e:
                    raise ValueError(
                        f"Extracted JSON block failed to parse: {e}\n"
                        f"Block (first 300 chars): {candidate[:300]}"
                    ) from e

    raise ValueError(f"Unclosed JSON object in model response: {text[:200]}")


async def call_judge(system_prompt: str, user_content: str) -> dict:
    model = os.getenv("JUDGE_MODEL", "azure_ai/claude-opus-4-6")

    kwargs = dict(
        model=model,
        messages=[
            {
                "role": "system",
                "content": system_prompt
                + "\n\nYou MUST respond with valid JSON only. No explanation, no markdown, no preamble.",
            },
            {"role": "user", "content": user_content},
        ],
        temperature=0.1,
    )

    # Only add response_format for models that support it natively
    if _supports_json_mode(model):
        kwargs["response_format"] = {"type": "json_object"}

    response = await litellm.acompletion(**kwargs)
    raw = response.choices[0].message.content

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return _extract_json(raw)
