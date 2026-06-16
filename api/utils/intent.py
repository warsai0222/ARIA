"""
Intent classifier — zero-latency, zero-cost regex routing.

Returns one of three buckets:
  'conversational' — greetings, small talk, self-introductions, thanks
  'off_topic'      — code requests, weather, generic AI tasks, PII fishing
  'portfolio'      — anything that should hit RAG and be answered

Called BEFORE retrieval so we can skip the vector DB entirely for the
first two buckets.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Conversational patterns — respond warmly, no RAG needed
# ---------------------------------------------------------------------------
_CONVERSATIONAL = [
    r"^(hi|hello|hey|howdy|sup|yo)[\s!,.]",
    r"^(hi|hello|hey|howdy|sup|yo)$",
    r"^(good\s?(morning|afternoon|evening|night|day))",
    r"^(thanks|thank you|thx|ty|cheers|appreciated)",
    r"^(bye|goodbye|see\s?you|cya|later|take care)",
    r"who are you\??$",
    r"what (are|can) you do\??$",
    r"what('s| is) (your name|this chatbot|this)\??",
    r"^(ok|okay|cool|great|nice|awesome|got it|i see|makes sense|sure|sounds good|alright|perfect)[\s!.,]?$",
    r"^(lol|haha|hehe|😄|😊|👍)$",
    r"(how are you|how's it going|how do you do)",
    r"(i'?m|i am) [a-z]+[\s.,!]",           # "I'm John", "I am a recruiter"
    r"my name is [a-z]+",
    r"(nice|pleasure|great) to meet you",
    r"^(interesting|cool|nice|wow|amazing|impressive)[\s!.]?$",
    r"^(yes|no|nope|yep|yup|sure|definitely|absolutely|of course)[\s!.]?$",
    r"^(what|tell me more|go on|continue|elaborate)[\s?!.]?$",
    r"can you help me\??$",
    r"^(i have a question|quick question)",
]

# ---------------------------------------------------------------------------
# Off-topic patterns — deflect immediately, no RAG, no LLM call
# ---------------------------------------------------------------------------
_OFF_TOPIC = [
    # Generic coding requests (not asking about Varshith's code)
    r"(write|create|generate|code|implement|debug|fix)\s+(me\s+)?(a\s+|an\s+|the\s+)?(code|script|function|program|class|snippet|algorithm)",
    r"how (do i|to|can i) (code|program|implement|write) ",
    r"(python|javascript|typescript|java|c\+\+|rust|golang|php|ruby)\s+(code|script|snippet|example|tutorial|boilerplate)",
    r"give me (a |an )?(code|example|snippet|template) (for|to|that)",
    # Weather / news / stock / time
    r"(what('s| is) the weather|weather (today|tomorrow|forecast|in ))",
    r"(today'?s?|latest|current)\s+(news|headlines|events)",
    r"(stock|share) price (of|for)",
    r"what (time|day) is it",
    # Generic creative / writing tasks
    r"write (me )?(a |an )?(joke|poem|story|essay|blog post|song|letter|email to)",
    r"tell me (a |an )?(joke|story|fun fact about (?!varshith))",
    r"(translate|summarize|summarise) (this|the following|from)",
    # Math / calculations
    r"(calculate|compute|solve|what is)\s+[\d\s\+\-\*\/\^]+[\=\?]?$",
    r"\d+\s*[\+\-\*\/]\s*\d+",
    # Recipe / how-to (non-tech)
    r"how (do i|to) (cook|bake|make|clean|lose weight|get fit|learn to)",
    # Personal info fishing
    r"(varshith'?s?|his)\s+(password|ssn|social security|bank|credit card|address|phone number)",
    r"(reveal|expose|show|print|output)\s+(your\s+)?(system prompt|instructions|api key|secret key|env)",
    # Generic world-knowledge questions not about Varshith
    r"who (is|was) (the )?(president|prime minister|ceo|founder|king|queen) of (?!varshith)",
    r"what('s| is) the (capital|population|currency|gdp) of ",
    r"(history|biography) of (?!varshith)",
    r"explain (quantum|relativity|blockchain|nft|crypto|forex) (to me|in simple|like i)",
    # Other people / companies
    r"(tell me about|who is|what is) (google|openai|anthropic|tesla|apple|meta|amazon|netflix|uber)(?!'?s?\s+(?:api|model|tool|used in))",
    r"compare (gpt|gemini|claude|llama) (to|vs|with) (?!varshith)",
]


def classify_intent(query: str) -> str:
    """
    Classify query intent without any API call.

    Returns:
        'conversational' — small talk, greetings, intros → respond warmly, skip RAG
        'off_topic'      — unrelated requests → deflect immediately
        'portfolio'      — about Varshith → full RAG pipeline
    """
    q = query.strip().lower()

    for pattern in _CONVERSATIONAL:
        if re.search(pattern, q):
            return "conversational"

    for pattern in _OFF_TOPIC:
        if re.search(pattern, q):
            return "off_topic"

    return "portfolio"
