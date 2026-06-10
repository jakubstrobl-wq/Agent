"""MCP server that bridges Claude Code to a local Ollama model.

Claude (running on your Claude subscription inside Claude Code) calls these
tools over MCP stdio; the tools talk to Ollama's local HTTP API. Nothing here
needs an Anthropic API key, and prompts sent to the local model never leave
your PC.
"""

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


def _chat(prompt: str, model: str, system: str | None = None) -> str:
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
        return OLLAMA_DOWN_MESSAGE.format(url=OLLAMA_URL)
    if response.status_code == 404:
        return (
            f"Model '{model}' is not installed. Run 'ollama pull {model}' "
            "in a terminal, or use list_local_models to see what is available."
        )
    response.raise_for_status()
    return response.json()["message"]["content"]


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


if __name__ == "__main__":
    mcp.run()
