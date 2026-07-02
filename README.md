# AI Interview Coach

A full-stack AI-powered interview preparation platform built with Flask, SQLite, and the Anthropic Claude API.

## Project Structure

```
AI_Interview_Coach/
├── app.py                  ← Flask backend + all API routes
├── requirements.txt        ← Python dependencies
├── database.db             ← SQLite database (auto-created)
├── static/
│   └── css/
│       └── style.css       ← All styles (dark/light mode, responsive)
└── templates/
    ├── index.html          ← Landing page
    ├── interview.html      ← Live interview page (avatar, Q&A, timer)
    ├── report.html         ← Detailed score report + radar chart
    └── dashboard.html      ← Interview history + analytics
```

## Quick Start

### 1. Install dependencies
```bash
cd AI_Interview_Coach
pip install -r requirements.txt
```

### 2. Set your Anthropic API key
```bash
# macOS / Linux
export ANTHROPIC_API_KEY="sk-ant-..."

# Windows (Command Prompt)
set ANTHROPIC_API_KEY=sk-ant-...

# Windows (PowerShell)
$env:ANTHROPIC_API_KEY="sk-ant-..."
```

### 3. Run the server
```bash
python app.py
```

### 4. Open in browser
```
http://localhost:5000
```

---

## Features at a Glance

| Feature | Details |
|---|---|
| AI Avatar | Animated SVG avatar with talking animation and blinking eyes |
| Text-to-Speech | Browser Web Speech API reads each question aloud |
| Voice Input | Web Speech Recognition — speak your answers |
| Question Generation | 10 questions per session: Technical / HR / Behavioral |
| AI Evaluation | 5-dimension scoring via Claude API (relevance, accuracy, communication, confidence, completeness) |
| Real-time Feedback | Strengths, weaknesses, improvement suggestions after every answer |
| Adaptive Questions | Claude adjusts difficulty based on previous answers |
| Timer | Per-question timer + full session timer |
| Dark/Light Mode | Persisted in localStorage |
| Report | Radar chart + score bars + full Q&A breakdown |
| PDF Export | Print-to-PDF via browser |
| Certificates | Printable completion certificate with scores |
| Dashboard | Search, filter, trend charts, all past sessions |
| SQLite Storage | All interviews and responses stored locally |

## API Endpoints

| Method | Route | Purpose |
|---|---|---|
| POST | `/api/start_interview` | Create a new interview session |
| POST | `/api/generate_question` | Generate next adaptive question |
| POST | `/api/evaluate_answer` | AI-score a submitted answer |
| POST | `/api/complete_interview` | Finalize and aggregate scores |
| GET  | `/api/report/<id>` | Fetch full report data |
| GET  | `/api/interviews` | List all interviews (with optional `?search=`) |
| GET  | `/api/certificate/<id>` | Get certificate data |

## Browser Compatibility

- Chrome / Edge (recommended — best Speech API support)
- Firefox (text input works; speech recognition limited)
- Safari 15+ (partial speech support)

## Troubleshooting

**"Network error. Is the server running?"**  
Make sure `python app.py` is running and you're visiting `http://localhost:5000`.

**Voice recognition not working**  
Use Chrome/Edge. Allow microphone permission when prompted. HTTPS is required on some systems — run locally (HTTP is fine for localhost).

**TTS not speaking**  
Click anywhere on the page first (browser autoplay policy). Use the "🔊 Replay question" button.

**API errors**  
Verify `ANTHROPIC_API_KEY` is set correctly in your shell environment before running `python app.py`.
