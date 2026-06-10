"""MCP server that bridges Claude Code to a local Ollama model.

Claude (running on your Claude subscription inside Claude Code) calls these
tools over MCP stdio; the tools talk to Ollama's local HTTP API. Nothing here
needs an Anthropic API key, and prompts sent to the local model never leave
your PC.
"""

import json
import re
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"
# Local generation on CPU/consumer GPUs can be slow; don't time out early.
TIMEOUT = httpx.Timeout(300.0, connect=5.0)

OLLAMA_DOWN_MESSAGE = (
    "Could not reach Ollama at {url}. Start Ollama from the Windows Start menu "
    "(or run 'ollama serve' in a terminal), then try again."
)

mcp = FastMCP("local-llm")


class OllamaUnavailable(Exception):
    """Ollama could not serve the request; str(exc) is a user-facing message."""


def _chat_raw(prompt: str, model: str, system: str | None = None) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    try:
        response = httpx.post(
            f"{OLLAMA_URL}/api/chat",
            json={"model": model, "messages": messages, "stream": False},
            timeout=TIMEOUT,
        )
    except httpx.ConnectError:
        raise OllamaUnavailable(OLLAMA_DOWN_MESSAGE.format(url=OLLAMA_URL))
    if response.status_code == 404:
        raise OllamaUnavailable(
            f"Model '{model}' is not installed. Run 'ollama pull {model}' "
            "in a terminal, or use list_local_models to see what is available."
        )
    response.raise_for_status()
    return response.json()["message"]["content"]


def _chat(prompt: str, model: str, system: str | None = None) -> str:
    try:
        return _chat_raw(prompt, model, system)
    except OllamaUnavailable as exc:
        return str(exc)


@mcp.tool()
def ask_local_model(prompt: str, model: str = DEFAULT_MODEL) -> str:
    """Send a prompt to the local open-source model running in Ollama and
    return its reply. Call this for second opinions, free/offline generation,
    or anything the user wants handled by their own machine instead of Claude.
    """
    return _chat(prompt, model)


@mcp.tool()
def summarize_locally(text: str, model: str = DEFAULT_MODEL) -> str:
    """Summarize text using the local model so the content never leaves this
    PC. Call this when the user wants private or sensitive material condensed
    before (or instead of) discussing it with Claude.
    """
    return _chat(
        text,
        model,
        system=(
            "Summarize the user's text concisely. Capture the key points and "
            "any action items. Reply with the summary only."
        ),
    )


@mcp.tool()
def list_local_models() -> str:
    """List the models currently installed in Ollama on this PC. Call this
    before ask_local_model if you are unsure which model names are available.
    """
    try:
        response = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=TIMEOUT)
    except httpx.ConnectError:
        return OLLAMA_DOWN_MESSAGE.format(url=OLLAMA_URL)
    response.raise_for_status()
    models = response.json().get("models", [])
    if not models:
        return "No models installed yet. Run 'ollama pull llama3.2' to get one."
    return "\n".join(m["name"] for m in models)


# --- Privacy gateway ---------------------------------------------------------
#
# Structured identifiers are redacted with deterministic regexes. The local
# model is only asked to *find* person names; the replacement itself happens
# in Python, so the model can never alter the surrounding text.

# Order matters: longer/stricter patterns (cards, keys) before phone numbers.
PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("[EMAIL]", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("[API_KEY]", re.compile(r"\b(?:sk|pk|rk|ghp|gho|ghs|xox[a-z])-[A-Za-z0-9_-]{10,}\b")),
    ("[API_KEY]", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("[CARD_NUMBER]", re.compile(r"\b(?:\d[ -]?){12,18}\d\b")),
    ("[SSN]", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("[IP_ADDRESS]", re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")),
    ("[PHONE]", re.compile(r"(?<![\w.])\+?\d[\d ().-]{7,14}\d\b")),
]


def _regex_redact(text: str) -> str:
    for placeholder, pattern in PII_PATTERNS:
        text = pattern.sub(placeholder, text)
    return text


def _llm_find_names(text: str, model: str) -> list[str]:
    """Ask the local model to list person names in the text. Returns [] if the
    reply isn't parseable — never raises on bad model output."""
    reply = _chat_raw(
        "List every person name that appears in the text below. Reply with a "
        'JSON array of strings only, e.g. ["Jane Doe"]. Reply [] if there are '
        "none. Do not include anything else in your reply.\n\nTEXT:\n" + text,
        model,
    )
    match = re.search(r"\[.*?\]", reply, re.S)
    if not match:
        return []
    try:
        names = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    return [n for n in names if isinstance(n, str) and len(n.strip()) > 1]


def _redact(text: str, model: str) -> str:
    redacted = _regex_redact(text)
    note = ""
    try:
        for name in _llm_find_names(redacted, model):
            redacted = re.sub(re.escape(name), "[NAME]", redacted, flags=re.I)
    except OllamaUnavailable as exc:
        note = (
            "\n\n[Note: emails, phone numbers, card numbers, and keys were "
            f"redacted, but the name-redaction step was skipped — {exc}]"
        )
    return redacted + note


@mcp.tool()
def redact_locally(text: str, model: str = DEFAULT_MODEL) -> str:
    """Redact private information from text entirely on this PC and return the
    redacted version. Emails, phone numbers, card numbers, SSNs, IP addresses,
    and API keys are replaced with placeholders deterministically; person names
    are found by the local model and replaced too. Call this BEFORE quoting or
    analyzing sensitive user text so the private details never reach Claude.
    """
    return _redact(text, model)


@mcp.tool()
def redact_file(path: str, model: str = DEFAULT_MODEL) -> str:
    """Read a text file from this PC and return a redacted copy of its
    contents. Use this when the user wants a private file summarized or
    discussed WITHOUT Claude seeing the original — pass the file path and do
    NOT read the file with your own tools first.
    """
    file = Path(path).expanduser()
    if not file.is_file():
        return f"No file found at {path}."
    if file.stat().st_size > 2_000_000:
        return f"{path} is larger than 2 MB — split it before redacting."
    text = file.read_text(encoding="utf-8", errors="replace")
    return _redact(text, model)


if __name__ == "__main__":
    mcp.run()
