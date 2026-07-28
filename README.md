<div align="center">

```
██╗██████╗ ██╗███████╗     █████╗ ██╗
██║██╔══██╗██║██╔════╝    ██╔══██╗██║
██║██████╔╝██║███████╗    ███████║██║
██║██╔══██╗██║╚════██║    ██╔══██║██║
██║██║  ██║██║███████║    ██║  ██║██║
╚═╝╚═╝  ╚═╝╚═╝╚══════╝    ╚═╝  ╚═╝╚═╝
```

**IRIS AI — Intelligent Responsive Interface System**

*A futuristic, Jarvis-style AI assistant for Windows — built entirely in Python.*

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D4?style=flat-square&logo=windows&logoColor=white)](https://microsoft.com/windows)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Groq](https://img.shields.io/badge/Powered%20by-Groq%20LLM-orange?style=flat-square)](https://console.groq.com)
[![Version](https://img.shields.io/badge/Version-v3.8.4--RELEASE-blueviolet?style=flat-square)](https://github.com/YOUR_USERNAME/IRIS-AI/releases)

</div>

---

## What is IRIS?

IRIS is a **futuristic, voice-enabled, AI-powered desktop assistant** for Windows inspired by JARVIS and FRIDAY from the Iron Man universe. It combines a stunning sci-fi terminal interface with real AI reasoning, custom voice cloning, full Windows automation, browser control, and a powerful task scheduling engine — all accessible from a single terminal command.

IRIS does not run in a browser tab. It runs natively on your Windows desktop, speaks in your voice, controls your apps, automates your workflows, and responds to natural language — all in real time.

---

## Features

### 🤖 AI Chat & Reasoning
- Powered by **Groq's ultra-fast LLM inference** (`llama-3.3-70b-versatile`)
- Streams responses token-by-token in real time
- Maintains session history for contextual multi-turn conversation
- Structured JSON action routing for automation commands
- Configurable system prompt and model selection

### 🎙️ Voice Assistant
- Three-tier speech synthesis pipeline:
  1. **XTTS v2 Voice Cloning** — synthesizes speech in your own cloned voice
  2. **Edge TTS** — Microsoft's neural high-definition voice (`en-US-ChristopherNeural`) as fallback
  3. **SAPI5 / pyttsx3** — system voice as final fallback
- Non-blocking background audio queue — speech never freezes the interface
- Auto-interrupts previous speech when a new command is submitted
- Natural language text pre-processing (strips markdown, code blocks, URLs)

### 🧬 Custom Voice Cloning
- Drop any `.wav`, `.mp3`, or `.flac` reference file into the `voice/` folder
- IRIS automatically detects, loads, and clones it using **XTTS v2**
- Hot-reload — replace the file at any time and IRIS picks it up automatically
- No GPU required — runs on CPU

### ⚙️ Windows Automation
- Open, close, and switch between any application
- Lock screen, sleep, restart, shutdown the PC
- Control system volume
- Take screenshots
- Move and manage files and folders
- Run terminal commands and PowerShell scripts
- Set environment variables

### 🌐 Browser Automation
- Open multiple websites simultaneously
- Search Google, YouTube, and Spotify from voice
- Tab switching and tab closing
- Form filling via `pyautogui`
- Auto-focus browser window

### 🔍 Application Control — 7-Tier Discovery Engine
IRIS uses a sophisticated application discovery service that searches in strict order:
1. Built-in Windows applications (guaranteed: Explorer, Edge, Notepad, Calculator, Paint, Task Manager, Settings, CMD, PowerShell, Terminal)
2. Windows App Execution Aliases
3. Start Menu shortcuts (User + All Users)
4. Desktop shortcuts (User + Public)
5. Windows Registry (Uninstall keys + App Paths)
6. System PATH executables
7. Common installation folders (Program Files, AppData, Steam libraries)

Features:
- Brings already-running app windows to foreground instead of opening duplicates
- 7-tier persistent index cache — repeat launches are near-instant (~1ms)
- Smart disambiguation for multiple installations of the same app
- Natural language normalization ("open edge", "launch chrome", "start vs code")

### 📁 File Management
- Open files and folders by name
- Navigate directories
- Create, copy, move, and delete files
- Search for files by name or type

### 💬 WhatsApp Automation
- Open WhatsApp Desktop or Web
- Search for contacts by name
- Type and send messages automatically
- Message delivery verification

### 🎵 Spotify Automation
- Launch Spotify and bring it to the foreground
- Search and play songs, artists, albums, and playlists
- Control playback (play, pause, skip, volume)
- Deep automation via URI and keyboard shortcuts

### 📺 YouTube Automation
- Search YouTube from voice
- Open specific videos by query
- Play/pause via browser keyboard shortcuts

### ⏱️ Timers & Task Scheduling
- Natural language time parsing: "2 minutes", "30 seconds", "1.5 hours", "tomorrow at 9 AM"
- **Timers** — set, pause, resume, cancel, and query remaining time
- **Delayed actions** — "Open Spotify after 5 minutes"
- **Recurring tasks** — "Remind me every hour"
- Voice announcement on timer completion: *"Boss, your 5-minute timer has finished."*
- Slash commands: `/timers`, `/tasks`, `/schedule`, `/canceltimer`

### 💻 Terminal Automation
- Execute shell commands from natural language
- Run Python scripts and PowerShell commands
- Open new terminal windows (CMD, PowerShell, Windows Terminal)

### 📡 Live Information
- Real-time **weather** lookup by city
- **News headlines** from RSS feeds
- Current **time and date** in any timezone
- Live **system telemetry** (CPU, RAM, disk, uptime)
- IP and network information

### 🎨 Modern Sci-Fi Terminal UI
- 5 built-in color themes switchable at runtime:

| Theme | Style |
|---|---|
| `emerald` | Neon Electric Green (default) |
| `jarvis` | Electric Cyan / Blue |
| `cyberpunk` | Neon Magenta / Gold |
| `matrix` | Code Rain Green |
| `solar` | Solar Flare Amber |

- Futuristic ASCII art banner on startup
- Live HUD displaying CPU %, RAM %, OS, uptime, and time
- Matrix digital rain animation (`/matrix`)
- Smooth Rich-rendered streaming output
- Tab autocompletion and persistent session history

---

## Screenshots

> *Screenshots will be added after the first stable public release.*

| View | Preview |
|---|---|
| 🖥️ Main Terminal Interface | *(coming soon)* |
| 🎨 Cyberpunk Theme | *(coming soon)* |
| ⏱️ Timer & Scheduler Panel | *(coming soon)* |
| 🔍 App Discovery in Debug Mode | *(coming soon)* |
| 🎵 Spotify Automation | *(coming soon)* |

---

## Requirements

### System Requirements

| Requirement | Minimum | Notes |
|---|---|---|
| **OS** | Windows 10 (64-bit) | Windows 11 recommended |
| **Python** | 3.9+ | 3.11 or 3.12 recommended |
| **RAM** | 4 GB | 8 GB recommended for XTTS v2 voice cloning |
| **Storage** | 500 MB | ~3 GB with XTTS v2 model downloaded |
| **Internet** | Required | For Groq API, Edge TTS, live info |

### Software Prerequisites

| Software | Required | Purpose | Get it |
|---|---|---|---|
| **Python 3.9+** | ✅ Required | Runtime | [python.org](https://www.python.org/downloads/) |
| **Git** | Recommended | Cloning repo / updates | [git-scm.com](https://git-scm.com/download/win) |
| **Groq API Key** | ✅ Required | Core AI — chat, voice, automation | [console.groq.com](https://console.groq.com) (free) |
| **Gemini API Key** | Optional | Coding Mode only | [aistudio.google.com](https://aistudio.google.com/app/apikey) (free) |
| **FFmpeg** | Optional | Extended audio format support | [ffmpeg.org](https://ffmpeg.org/download.html) |
| **Spotify Desktop** | Optional | Spotify automation | [spotify.com](https://www.spotify.com/download) |
| **WhatsApp Desktop** | Optional | WhatsApp automation | [whatsapp.com](https://www.whatsapp.com/download) |

> **API Key Policy:**
> - **Groq** is required. IRIS cannot function without it. Get a free key at [console.groq.com](https://console.groq.com) — no credit card needed.
> - **Gemini** is optional. It enables Coding Mode only. Get a free key at [aistudio.google.com](https://aistudio.google.com/app/apikey).
> - Keys are stored **locally only** in `config/config.json`. They are **never** hardcoded, never logged, and never uploaded to GitHub.
> - IRIS will guide you through entering your keys on first launch — you never need to edit any file manually.

### Python Dependencies

All Python packages are installed automatically by the installer.

| Package | Version | Purpose |
|---|---|---|
| `rich` | ≥13.0.0 | Terminal UI rendering |
| `prompt-toolkit` | ≥3.0.0 | REPL input, autocomplete, history |
| `pyfiglet` | ≥1.0.0 | ASCII art banner |
| `psutil` | ≥5.9.0 | System telemetry, process management |
| `groq` | ≥0.4.0 | Groq LLM API client (Normal Mode) |
| `google-generativeai` | ≥0.7.0 | Gemini API client (Coding Mode) |
| `python-dotenv` | ≥1.0.0 | `.env` environment variable loading |
| `edge-tts` | ≥6.1.9 | Microsoft neural TTS (fallback voice) |
| `pyttsx3` | ≥2.90 | SAPI5 system TTS (second fallback) |
| `soundfile` | ≥0.12.0 | Audio file reading/writing |
| `sounddevice` | ≥0.4.0 | Audio playback for XTTS |
| `pyautogui` | ≥0.9.54 | GUI automation, keyboard/mouse |
| `requests` | ≥2.31.0 | HTTP requests for live info |

> **Optional:** Install `TTS` (Coqui TTS) separately for XTTS v2 voice cloning:
> ```bash
> pip install TTS
> ```

---

## Installation

### Step 1 — Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/IRIS-AI.git
cd IRIS-AI
```

Or download and extract the ZIP from the [Releases](https://github.com/YOUR_USERNAME/IRIS-AI/releases) page.

---

### Step 2 — Run the One-Step Installer

#### Option A: PowerShell (Recommended)

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

Or right-click `install.ps1` → **Run with PowerShell**.

#### Option B: Python

```bash
python install.py
```

The installer will automatically:

- ✅ Verify Python 3.9+ is installed
- ✅ Check for Git and FFmpeg
- ✅ Create a `.venv` virtual environment
- ✅ Upgrade pip
- ✅ Install all dependencies from `requirements.txt`
- ✅ Create all required folders (`voice/`, `logs/`, `cache/`, `temp/`, `config/`)
- ✅ Verify TTS engines (edge-tts, pyttsx3, sounddevice, soundfile)
- ✅ Verify automation dependencies
- ✅ Create `iris_run.bat` launcher shortcut
- ✅ Run a full module smoke test
- ✅ Write a detailed `iris_install.log`

> **Idempotent** — safe to run multiple times. Already-installed items are skipped automatically.

---

### Step 3 — Start IRIS

```bash
python iris.py
```

**On first launch**, IRIS will automatically detect that no API key is configured and display a friendly setup wizard for both providers:

```
╭──────────────────────────────────────────────────────────╮
│           IRIS AI  --  API Configuration                 │
│                                                          │
│  IRIS uses two independent AI providers:                 │
│                                                          │
│  [1] Groq API Key     — required for all core features   │
│      (chat, voice, automation, timers, general knowledge)│
│                                                          │
│  [2] Gemini API Key   — optional, enables Coding Mode    │
│      (code generation, bug fixing, refactoring)          │
│                                                          │
│  Keys are stored in  config/config.json  locally only.   │
│  They are NEVER uploaded to GitHub.                      │
╰──────────────────────────────────────────────────────────╯

  -- Groq API Key (console.groq.com) --

  Groq API Key >

  -- Gemini API Key (aistudio.google.com) --

  Gemini API Key (press Enter to skip) >
```

**Validation:** IRIS validates each key live against its API. Invalid keys show a clear error and allow retry. Valid keys are saved to `config/config.json` (excluded from Git). You will **never be asked again** after successful setup.

Or double-click `iris_run.bat`.



---

## Usage

### Launching with Options

```bash
# Default launch (Emerald Neon Green theme)
python iris.py

# Launch with a different theme
python iris.py --theme jarvis
python iris.py --theme cyberpunk
python iris.py --theme matrix
python iris.py --theme solar

# Skip the startup boot animation
python iris.py --no-boot

# Enable developer debug mode with live telemetry logs
python iris.py --debug
```

### Slash Commands

| Command | Description |
|---|---|
| `/help` | Show the full command reference |
| `/status` or `/sys` | Live system telemetry dashboard |
| `/matrix` | Digital rain terminal animation |
| `/calc <expr>` | Mathematical expression evaluator |
| `/time` | UTC and local time display |
| `/history` | Session query history |
| `/theme <name>` | Switch color theme at runtime |
| `/timers` | Show all active timers |
| `/tasks` | Show all scheduled tasks |
| `/schedule` | View the task scheduler |
| `/canceltimer` | Cancel the active timer |
| `/clear` | Clear screen and refresh HUD |
| `/about` | System architecture info |
| `/exit` or `quit` | Exit IRIS gracefully |

### Example Commands

```
Boss > Set a timer for 5 minutes
Boss > Open Spotify and play lo-fi hip hop
Boss > Open Chrome
Boss > Open File Explorer
Boss > Search YouTube for ocean wave sounds
Boss > Send a WhatsApp message to John saying I'll be 10 minutes late
Boss > Open my project in VS Code
Boss > Shut down the PC in 30 minutes
Boss > Remind me to drink water every hour
Boss > What's the weather in London?
Boss > What time is it in Tokyo?
Boss > Lock my computer
Boss > Take a screenshot
Boss > Open Discord after 2 minutes
Boss > Play the next song on Spotify
Boss > /theme cyberpunk
Boss > /timers
Boss > /matrix
```

---

## Voice Setup (Optional)

To use custom voice cloning, place a reference audio file in the `voice/` folder:

```
voice/
└── your-voice.wav    ← any .wav, .mp3, or .flac file
```

IRIS will automatically detect and clone it using XTTS v2.  
If no voice file is provided, IRIS falls back to Microsoft Edge TTS neural voice.

> **Tip:** A 5–30 second clean speech recording works best for cloning.

---

## Project Structure

```
IRIS-AI/
├── iris.py                  # Main entry point — launch IRIS here
├── config.py                # Themes, boot messages, global settings
├── banner.py                # ASCII art HUD dashboard generator
├── ui.py                    # Animations, Rich formatting, sound effects
├── commands.py              # Command processor & intent classification
├── llm_engine.py            # Groq LLM streaming engine
├── voice_engine.py          # XTTS v2 + Edge TTS + pyttsx3 voice pipeline
├── automation_engine.py     # Windows automation orchestration layer
├── app_discovery.py         # 7-tier application discovery service
├── task_scheduler.py        # Timer & task scheduling engine
├── browser_automation.py    # Web & browser control
├── spotify_automation.py    # Spotify deep automation
├── whatsapp_automation.py   # WhatsApp messaging automation
├── debug_logger.py          # Structured debug logging
├── live_info.py             # Live system & web telemetry
├── requirements.txt         # Python dependencies
├── install.py               # Python one-step installer
├── install.ps1              # PowerShell one-step installer
├── .env.example             # Environment variables template
├── .gitignore               # Git ignore rules
└── voice/                   # Place reference voice audio files here
    └── README.txt
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `python not found` | Install Python 3.9+ and check **Add to PATH** during setup |
| `GROQ_API_KEY missing` | Create `.env` from `.env.example` and set your key |
| `ModuleNotFoundError` | Run `python install.py` again to reinstall missing packages |
| `No audio output` | Check your audio device; install FFmpeg for extra format support |
| Voice cloning fails | IRIS falls back to Edge TTS automatically — this is normal without `TTS` installed |
| App not found | Try the full name: "open Microsoft Edge" instead of "open edge" |
| `[APP]` debug logs | Run with `--debug` flag to see the 7-tier discovery process live |
| Slow first launch | XTTS v2 model downloads on first run (~1.8 GB) — subsequent launches are fast |

---

## Debug Mode

Run IRIS with `--debug` to enable live telemetry logs:

```bash
python iris.py --debug
```

Debug tags:
- `[APP]` — Application discovery & launch pipeline
- `[VOICE]` — Voice engine initialization and synthesis
- `[TTS]` — Text-to-speech rendering
- `[AUDIO]` — Audio playback status
- `[LLM]` — LLM engine communication
- `[TASK]` — Task scheduler tick events

---

## Roadmap

- [ ] Web dashboard UI (React/Next.js)
- [ ] Plugin system for custom skills
- [ ] Multi-language voice support
- [ ] Wake word detection ("Hey IRIS")
- [ ] Calendar & Google integration
- [ ] Email automation
- [ ] Custom hotkey binding
- [ ] Mobile companion app

---

## Contributing

Contributions, issues, and feature requests are welcome.

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m "Add my feature"`
4. Push to the branch: `git push origin feature/my-feature`
5. Open a Pull Request

---

## License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) for details.

---

<div align="center">

*Built with Python · Powered by Groq · Inspired by JARVIS*

**IRIS AI — v3.8.4-RELEASE · QUANTUM NEXUS**

</div>
