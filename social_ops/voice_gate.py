"""The orchestrator's voice check. Ollama drafts never score themselves —
Claude independently checks a draft against the brand voice profile before
anything ships. This mirrors the same pattern used in the agentic_priming_pilot
repo's quality_gate.py: cheap volume from Ollama, an independent quality bar
from a stronger model before anything reaches a customer or the public feed.
"""
import json
import logging
import os

logger = logging.getLogger(__name__)

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

DEFAULT_THRESHOLD = int(os.environ.get("VOICE_GATE_THRESHOLD", "75"))
CLAUDE_MODEL = "claude-sonnet-5"

VOICE_GATE_SYSTEM_PROMPT = """You are an independent brand-voice and safety reviewer.
You did not write the post you are reviewing.

Score the post 0-100 on:
- Voice fit: does it actually match the described brand voice, or is it generic?
- Safety: does it avoid fabricated claims, promises, guarantees, or anything that
  reads as a legal/financial commitment the brand didn't explicitly authorize?
- Platform fit: is it an appropriate length and tone for the stated platform?

A score below the caller's threshold means: hold this for a human to review
before it goes anywhere near a real audience.

Respond with JSON only, no prose, no markdown fences:
{"score": <0-100 integer>, "reasoning": "<one sentence, specific to this post>"}
"""


def gate_configured() -> bool:
    return ANTHROPIC_AVAILABLE and bool(os.environ.get("ANTHROPIC_API_KEY"))


def init_claude_client():
    if not ANTHROPIC_AVAILABLE:
        raise ImportError("anthropic package not installed. Install with: pip install anthropic")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set; the voice gate cannot run")
    return anthropic.Anthropic(api_key=api_key)


def score_post(body: str, voice_profile: str, platform: str, client=None) -> dict:
    """Independently score a draft. Fails open (score=0, forcing manual review)
    on any API error — a post that can't be scored never auto-ships.
    """
    if client is None:
        client = init_claude_client()

    user_content = f"""Brand voice profile: {voice_profile}
Platform: {platform}

Post to review:
{body}"""

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=200,
            system=VOICE_GATE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        text = "".join(block.text for block in response.content if hasattr(block, "text"))
        result = json.loads(text)
        return {"score": int(result["score"]), "reasoning": result.get("reasoning", "")}
    except Exception as e:
        logger.warning("Voice gate scoring failed, forcing manual review: %s", e)
        return {"score": 0, "reasoning": f"scoring unavailable, held for manual review ({e})"}
