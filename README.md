# 🎯 AI Interview Coach Version 1.1

An AI-powered interview preparation platform built with **Flask**, **SQLite**. Practice technical, HR, and behavioral interviews with adaptive AI-generated questions, voice interaction, detailed feedback, and performance analytics.

---

## ✨ Features

- 🤖 AI-generated interview questions
- 🎤 Voice input using Web Speech Recognition
- 🔊 Text-to-Speech for interview questions
- 📊 AI-based answer evaluation
- 📈 Performance analytics and dashboard
- 📄 Detailed interview reports
- 🏆 Printable completion certificates
- 🌙 Dark & Light mode
- 💾 SQLite database for interview history
- 📱 Responsive user interface

---

## 📂 Project Structure

```text
AI_Interview_Coach/
├── app.py
├── ai_service.py
├── report_generator.py
├── certificate_generator.py
├── email_service.py
├── requirements.txt
├── database.db
├── models/
│   └── __init__.py
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       ├── main.js
│       ├── interview.js
│       └── avatar.js
└── templates/
    ├── index.html
    ├── interview.html
    ├── dashboard.html
    └── report.html
```

---

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/vishalvivek14332-source/AI-Interview-Coach-.git
cd AI-Interview-Coach-
```

### 2. Create a virtual environment

**Windows**

```bash
python -m venv .venv
.venv\Scripts\activate
```

**macOS/Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the application

```bash
python app.py
```

### 5. Open in your browser

```
http://localhost:5000
```

---

## 📸 Application Features

| Feature | Description |
|---------|-------------|
| AI Interview | Adaptive interview questions generated using Claude AI |
| Voice Input | Answer questions using speech recognition |
| Text-to-Speech | Questions are read aloud |
| Real-Time Evaluation | AI scores every answer |
| Performance Dashboard | View interview history and analytics |
| Reports | Detailed interview reports with charts |
| Certificates | Generate interview completion certificates |
| Dark Mode | Toggle between light and dark themes |

---

## 🌐 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/start_interview` | Start a new interview |
| POST | `/api/generate_question` | Generate the next question |
| POST | `/api/evaluate_answer` | Evaluate an answer |
| POST | `/api/complete_interview` | Finish the interview |
| GET | `/api/report/<id>` | Retrieve interview report |
| GET | `/api/interviews` | Retrieve interview history |
| GET | `/api/certificate/<id>` | Generate certificate |

---

## 🛠️ Technologies Used

- Python
- Flask
- SQLite
- HTML5
- CSS3
- JavaScript
- Web Speech API
- Chart.js

---

## 📋 Requirements

- Python 3.10+
- Modern web browser (Chrome or Microsoft Edge recommended)

---

## 🔧 Troubleshooting

### Server not starting

Make sure all dependencies are installed:

```bash
pip install -r requirements.txt
```

### Voice recognition not working

- Use Google Chrome or Microsoft Edge.
- Allow microphone permissions.
- Refresh the page after granting access.

### Text-to-Speech not working

Click anywhere on the page before starting the interview to enable browser audio.

---

## 📜 License

This project is intended for educational and learning purposes.

---

## 👨‍💻 Author

**Vishal Vivek**

GitHub: https://github.com/vishalvivek14332-source
