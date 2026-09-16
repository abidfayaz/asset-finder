"""
The "why did this match?" helper.

It sends the search you typed plus the matching text to the model in your model
runner (Unsloth or Ollama, on this computer), and asks for one short sentence
explaining the connection - plus a verdict on whether each result genuinely
relates, so results that do not are kept off the page.

If no token is set up, or the model runner cannot be reached, it quietly falls
back to a simple explanation built from the overlapping words. The app keeps
working either way - it just gives a plainer reason.

To switch model runner, change LLM_BASE_URL / LLM_API_KEY / LLM_MODEL in .env.
"""

import json

import requests

import config

# How long to wait for the model before giving up and using the simple
# explanation instead. Keeps a slow model from freezing the search. Set by
# LLM_TIMEOUT_SECONDS.
REQUEST_TIMEOUT_SECONDS = config.LLM_TIMEOUT_SECONDS

# If the last AI call failed, the plain-language reason is stored here so the
# app can show it on screen instead of failing quietly.
last_error: str | None = None

# The AI's verdict on each result from the last call, in order: True if it
# genuinely relates to the search, False if not, None if the model gave no
# clear answer. Used to keep results that are not real matches off the page.
last_related: list = []

# The rules we give the model. Fixed, so every explanation behaves the same.
SYSTEM_PROMPT = (
    "You explain why a search result matched someone's search. "
    "For each result, write ONE complete sentence of 10 to 20 words, in plain "
    "language a non-technical person understands. Always a full sentence, "
    "never a fragment, and always ending in a full stop. "
    "Say what the slide or page is actually about and how that relates to the "
    "search. "
    "Only describe what is in the provided text - never invent details, and "
    "never guess what else the file might contain. "
    "If the text has little to do with the search, say so honestly. "
    "Also judge, for each result, whether it genuinely relates to the search: "
    "true if it is about the searched subject or clearly covers it, false if it "
    "has nothing real to do with it. Be strict - a shared everyday word is not "
    "a relation. "
    "Good example: 'This slide shows a star schema diagram with fact and "
    "dimension tables.' "
    "Bad example: 'Mentions star schema directly.'"
)

# A different job when NOTHING matched well and we are showing the closest few.
# Here the person has already been told nothing matched, so repeating "this is
# unrelated" three times tells them nothing they do not know. What actually
# helps is knowing what each result IS about, and where the nearest connection
# to their search lies - so they can judge whether it is worth a look.
CLOSEST_SYSTEM_PROMPT = (
    "Nothing in the library matched this person's search well, and they have "
    "already been told that plainly. Your job is to help them judge each of the "
    "closest results. "
    "For each one, write ONE complete sentence of 10 to 20 words saying what "
    "the passage is actually about, and where there is one, the nearest "
    "connection to what they searched for. "
    "Do NOT say it is unrelated, does not mention, or does not relate to the "
    "search - they know, and it wastes the sentence. Stay useful and neutral. "
    "Only describe what is in the provided text - never invent details. "
    "Also judge, for each result, whether it has any genuine connection to the "
    "searched subject, even a loose one: true if it does, false if it has "
    "nothing real to do with it. Be strict - a shared everyday word is not a "
    "connection. "
    "Good example: 'Covers deploying a model to Google Cloud, the nearest thing "
    "here to a deployment pipeline.' "
    "Bad example: 'This text does not relate to Kubernetes or Docker.'"
)


def is_configured() -> bool:
    """True if an API key has been set up, so we can call the AI service."""
    return bool(config.LLM_API_KEY.strip())


def _call_llm(user_prompt: str, system_prompt: str = None) -> str:
    """
    Send one request to the AI service and return its text reply.
    Raises an ordinary exception if anything goes wrong - the caller decides
    what to do about it.
    """
    url = f"{config.LLM_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": config.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt or SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        # Low temperature = steady, repeatable answers.
        "temperature": 0.2,
        "max_tokens": 400,
        # Ask for a machine-readable reply so we can split it reliably.
        "response_format": {"type": "json_object"},
    }
    if _is_local_server():
        # Models such as Qwen3-VL can "think out loud" before answering, and on
        # some runners (Ollama) that thinking uses up the reply budget, leaving
        # an empty answer. Short explanations need no thinking, so switch it off.
        body["reasoning_effort"] = "none"

    response = requests.post(url, headers=headers, json=body,
                             timeout=REQUEST_TIMEOUT_SECONDS)

    # Not every server understands the "reply in JSON" or "no thinking"
    # switches, and some reject the whole request because of one. The
    # instructions already ask for JSON in plain words, so try once more
    # without them.
    if response.status_code == 400:
        body.pop("response_format", None)
        body.pop("reasoning_effort", None)
        response = requests.post(url, headers=headers, json=body,
                                 timeout=REQUEST_TIMEOUT_SECONDS)

    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def simple_reason(query: str, text: str, weak: bool = False) -> str:
    """
    The no-AI-needed explanation: which of your search words appear in the
    text. Used when there is no API key, or the service is unavailable.

    `weak` is for the "closest few" case, where saying what is missing is not
    useful - the person has already been told nothing matched well.
    """
    from search import matching_terms  # imported here to avoid a circular import

    found = matching_terms(query, text)
    if found:
        words = ", ".join(f'"{w}"' for w in found)
        return f"This text contains {words} from your search."
    if weak:
        return "One of the nearest things in your library, by overall meaning."
    return "Close in meaning to your search, though it uses different words."


def why_it_matched(query: str, results: list[dict], weak: bool = False) -> list[str]:
    """
    Produce one explanation per result, in the same order as `results`.

    All results are explained in a SINGLE request rather than one request each,
    which keeps the search fast and the cost low.

    This never raises. If anything at all goes wrong it returns the simple
    word-overlap explanations instead.
    """
    global last_error, last_related
    last_error = None
    last_related = [None] * len(results)

    if not results:
        return []

    # No key configured - use the simple explanation, no network call.
    if not is_configured():
        return [simple_reason(query, r["text"], weak) for r in results]

    # Build one numbered list of the matches for the model to work through.
    blocks = []
    for number, result in enumerate(results, start=1):
        where = result.get("location_label") or ""
        blocks.append(
            f"RESULT {number}\n"
            f"File: {result['file_name']} {where}\n"
            f"Text: {result['snippet']}"
        )

    # Every reply carries a verdict per result, so nothing unrelated is shown -
    # whether these are matches or only the closest few.
    connection = ("has any genuine connection to the search, even a loose one"
                  if weak else "genuinely relates to the search")
    shape = (
        '{"reasons": ["reason for result 1", "reason for result 2", ...], '
        '"related": [true, false, ...]}\n'
        f'In "related", put true if that result {connection}, or false if it '
        'has nothing real to do with it.\n'
    )

    user_prompt = (
        f'The person searched for: "{query}"\n\n'
        + "\n\n".join(blocks)
        + "\n\nReply with JSON in exactly this shape, one entry per result, "
        "in order:\n"
        + shape
        + f"There must be exactly {len(results)} reasons."
    )

    try:
        raw = _call_llm(user_prompt,
                        CLOSEST_SYSTEM_PROMPT if weak else SYSTEM_PROMPT)
        reply = _parse_reply(raw)
        reasons = reply.get("reasons", [])
        if not isinstance(reasons, list):
            reasons = []
        verdicts = reply.get("related", [])
        if isinstance(verdicts, list):
            last_related = [_as_verdict(verdicts[i]) if i < len(verdicts) else None
                            for i in range(len(results))]

        # Make sure we got a usable list of the right length. If the model
        # returned too few, pad with the simple explanation.
        cleaned = []
        for index, result in enumerate(results):
            if index < len(reasons) and isinstance(reasons[index], str) and reasons[index].strip():
                cleaned.append(reasons[index].strip())
            else:
                cleaned.append(simple_reason(query, result["text"], weak))
        return cleaned

    except Exception as error:
        # Network down, bad key, rate limit, odd reply - none of these should
        # break the search. Fall back, but record why so the app can say so.
        last_error = _friendly_error(error)
        print(f"Could not get AI explanations ({error}). Using simple reasons.")
        return [simple_reason(query, r["text"], weak) for r in results]


def _parse_reply(raw: str) -> dict:
    """
    Pull the JSON object out of the model's reply.

    Large hosted models return clean JSON when asked. Small local models often
    wrap it in a ```json block, or add a sentence before or after it. That is
    not a real failure, so look for the JSON object inside the reply before
    giving up on it.
    """
    text = (raw or "").strip()
    try:
        reply = json.loads(text)
        if isinstance(reply, dict):
            return reply
    except json.JSONDecodeError:
        pass

    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            reply = json.loads(text[start:end + 1])
            if isinstance(reply, dict):
                return reply
        except json.JSONDecodeError:
            pass

    raise ValueError("the AI reply was not in the expected format")


def _parse_reasons(raw: str) -> list:
    """Just the list of reasons from the model's reply."""
    return _parse_reply(raw).get("reasons", [])


def _as_verdict(value):
    """The model's true/false answer, allowing for "yes"/"no" and the like."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        word = value.strip().lower()
        if word in ("true", "yes", "related"):
            return True
        if word in ("false", "no", "unrelated", "not related"):
            return False
    return None


# Ways a sentence says the result has no connection at all. A backstop for when
# a model writes "this has no relation to the query" but forgets to mark it
# false. Only unambiguous phrases: "doesn't mention Airflow" is NOT here, because
# a genuinely near result can say that honestly ("covers Python and Pandas,
# though it doesn't mention Airflow") - the model's own verdict judges those.
_UNRELATED_PATTERNS = [
    r"\bno (real |clear |direct |obvious |apparent )?(relation|relevance|connection|link)\b",
    r"\bunrelated\b",
    r"\birrelevant\b",
    r"\bnothing to do with\b",
    r"\b(is|are|does|do|has|have)\s*(not|n't)\s+(\w+\s+)?"
    r"(relate|related|relevant|connected)\b",
]


def says_unrelated(sentence: str) -> bool:
    """Does this explanation say the result has no connection to the search?"""
    import re
    # Models write both ' and the curly ’ - treat them the same.
    text = (sentence or "").lower().replace("’", "'")
    return any(re.search(pattern, text) for pattern in _UNRELATED_PATTERNS)


def _is_local_server() -> bool:
    """True when the text model runs on this machine rather than online."""
    address = config.LLM_BASE_URL.lower()
    return "127.0.0.1" in address or "localhost" in address


def _friendly_error(error: Exception) -> str:
    """Turn a technical error into something worth showing on screen."""
    text = str(error)
    local = _is_local_server()

    if isinstance(error, requests.exceptions.Timeout):
        if local:
            return ("the local model did not reply in time - small models on a "
                    "laptop are slow, so raise LLM_TIMEOUT_SECONDS in your .env")
        return "the AI service did not reply in time"

    if isinstance(error, requests.exceptions.ConnectionError):
        if local:
            return (f"could not reach the local model server at "
                    f"{config.LLM_BASE_URL} - is your model runner (Unsloth "
                    f"Studio or Ollama) open, and is that address right?")
        return "could not reach the AI service - check your internet connection"

    if "401" in text or "invalid_api_key" in text:
        if local:
            return ("the local model runner rejected the token in LLM_API_KEY. "
                    "Unsloth needs a real key starting sk-unsloth- (Settings -> "
                    "API -> Create); Ollama accepts any word, such as ollama")
        return "the API key was rejected - check LLM_API_KEY in your .env"

    if "404" in text or "model_not_found" in text or "decommissioned" in text:
        if local:
            return (f"the model '{config.LLM_MODEL}' was not found - check "
                    f"LLM_MODEL in your .env matches the name exactly as your "
                    f"model runner shows it (Ollama: type 'ollama list'; "
                    f"Unsloth: check the model is downloaded and loaded)")
        return (f"the model '{config.LLM_MODEL}' was not found - check "
                f"LLM_MODEL in your .env against your provider's model list")

    if "429" in text:
        return "the model is busy - wait a moment and search again"
    return text
