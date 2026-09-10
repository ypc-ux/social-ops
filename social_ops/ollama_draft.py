"""Cheap first-draft generation via local Ollama. Never posted without a
voice_gate pass (see voice_gate.py) — this module's job is volume, not
final quality.
"""
import logging
import os

logger = logging.getLogger(__name__)

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "mistral")


def init_ollama_client():
    if not OLLAMA_AVAILABLE:
        raise ImportError("ollama package not installed. Install with: pip install ollama")
    client = ollama.Client(host=OLLAMA_BASE_URL)
    client.list()  # raises if unreachable
    return client


SYSTEM_PROMPT_TEMPLATE = """You are a social media copywriter drafting a short post for one brand.

Brand voice profile (follow this exactly):
{voice_profile}

Hard boundaries:
- Never invent a statistic, customer name, or result you weren't given.
- Never promise a discount, guarantee, or price unless explicitly given in the prompt.
- Stay under platform length limits: Twitter/X ~260 characters, LinkedIn ~600 characters.

Output format: return only the post body. No hashtag spam (max 2 hashtags), no
preamble like "Here's a post:", no markdown.
"""


def draft_post(
    voice_profile: str,
    platform: str,
    topic: str,
    context: str = "",
    client=None,
) -> str:
    """Generate one draft post body for a topic, in the client's voice."""
    if client is None:
        client = init_ollama_client()

    prompt = f"""Platform: {platform}
Topic: {topic}
{('Extra context: ' + context) if context else ''}

Write the post now."""

    response = client.generate(
        model=OLLAMA_MODEL,
        prompt=prompt,
        system=SYSTEM_PROMPT_TEMPLATE.format(voice_profile=voice_profile),
        stream=False,
        options={"temperature": 0.7, "num_predict": 300},
    )
    body = response.get("response", "").strip()
    if not body:
        raise RuntimeError("Ollama returned an empty draft")
    return body


def draft_reply(
    voice_profile: str,
    platform: str,
    original_text: str,
    reply_kind: str,
    client=None,
) -> str:
    """Generate a reply to a mention/review/competitor post.

    reply_kind: 'reputation' (replying to a mention/review of your own brand)
                or 'market_radar' (responding to a competitor/trend angle).
    """
    if client is None:
        client = init_ollama_client()

    if reply_kind == "reputation":
        instruction = (
            "Someone mentioned or reviewed the brand. Write a short, genuine reply — "
            "thank them if positive, address the concern directly if negative. "
            "Never sound defensive or scripted."
        )
    else:
        instruction = (
            "A competitor or trending angle in the market needs a response. Write a "
            "short post that stakes out the brand's position without naming or "
            "attacking the competitor directly."
        )

    prompt = f"""Platform: {platform}
What you're responding to: {original_text}

{instruction}

Write the reply now."""

    response = client.generate(
        model=OLLAMA_MODEL,
        prompt=prompt,
        system=SYSTEM_PROMPT_TEMPLATE.format(voice_profile=voice_profile),
        stream=False,
        options={"temperature": 0.6, "num_predict": 300},
    )
    body = response.get("response", "").strip()
    if not body:
        raise RuntimeError("Ollama returned an empty draft")
    return body
