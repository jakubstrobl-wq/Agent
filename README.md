# Claude ↔ Local Model Bridge

Use your **Claude subscription** together with a **free open-source model running on your own Windows 11 PC** — no API key needed.

How it works: you chat with Claude as usual inside **Claude Code** (which uses your subscription login). This project gives Claude three extra tools, served by a tiny bridge on your PC, that talk to **Ollama** (a free app that runs open-source models locally):

| Tool | What it does |
|---|---|
| `ask_local_model` | Ask the local model anything — second opinions, free generation |
| `summarize_locally` | Summarize text on your PC, so private content never leaves it |
| `list_local_models` | See which local models are installed |
| `redact_locally` | Strip emails, phone numbers, card numbers, keys, and names from text — on your PC |
| `redact_file` | Redact a file from disk so Claude never sees the original contents |

```
You ↔ Claude Code (your Claude subscription)
          │
          ▼
   bridge/server.py  (this project)
          │
          ▼
   Ollama on your PC  (free local model)
```

## Setup (Windows 11, one time, ~10 minutes)

### 1. Install Ollama and download a model

1. Download Ollama from [ollama.com/download](https://ollama.com/download) and install it (or in a terminal: `winget install Ollama.Ollama`).
2. Open **Terminal** (press Start, type "terminal") and run:
   ```
   ollama pull llama3.2
   ```
   This downloads a small, fast open-source model (~2 GB).

### 2. Install Python and this project's dependencies

1. If you don't have Python: `winget install Python.Python.3.12` (or from [python.org](https://www.python.org/downloads/)).
2. In Terminal, inside this project folder, run:
   ```
   pip install -r requirements.txt
   ```

### 3. Open the project in Claude Code

1. Install Claude Code if you haven't: [claude.com/claude-code](https://claude.com/claude-code).
2. Open this folder in Claude Code. It will detect the bridge automatically (from `.mcp.json`) and ask you to approve the **local-llm** server — say yes.

That's it. If you ever want to register the bridge manually instead, run:

```
claude mcp add local-llm -- python bridge\server.py
```

## Try it

Make sure Ollama is running (it starts with Windows by default), then ask Claude things like:

- *"List my local models"*
- *"Ask the local model what 2+2 is"*
- *"Summarize this file locally — it's private, don't read it yourself"*
- *"Get a second opinion from the local model on this paragraph"*
- *"Redact C:\Users\me\Documents\contract.txt and then explain it — don't read the original"*

**How redaction works:** emails, phone numbers, card numbers, SSNs, IP addresses, and API keys are removed by exact pattern matching (reliable, never misses the format), and the local model is used only to spot person names — the text itself is replaced by the bridge, so the model can't change your wording. If Ollama is off, you still get the pattern-based redaction plus a note that names were skipped.

If Ollama isn't running, the tools reply with a friendly reminder to start it.

## Ideas for later

- **Smart router / quota saver** — a small agent (Claude Agent SDK) that automatically sends easy or private prompts to the local model and only hard ones to Claude, stretching your subscription limits.
- **Draft locally, refine with Claude** — the local model writes free first drafts; Claude polishes them.
