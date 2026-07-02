"""
models.py — AI Interview Coach
================================
Database layer using raw sqlite3 (stdlib only — no SQLAlchemy required).

Provides the same public API that app.py expects:
  db            – dummy object with init_app() no-op (keeps app.py import clean)
  init_db()     – creates all tables
  get_or_create_candidate, get_candidate_by_email
  create_interview, get_interview, list_interviews, complete_interview
  create_question, get_question, get_questions_for_interview, get_question_by_number
  create_answer, get_answer_for_question
  create_feedback, get_feedback_for_answer
  build_report_dict

All functions return plain Python dicts / simple namespace objects whose
attributes mirror what app.py accesses (iv.id, iv.job_role, iv.status,
iv.candidate.name, question.answer, answer.feedback, etc.).
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Optional

# ---------------------------------------------------------------------------
# Database path
# ---------------------------------------------------------------------------
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH   = os.path.join(_BASE_DIR, 'database.db')


# ---------------------------------------------------------------------------
# Dummy db object so app.py's  `from models import db`  keeps working
# ---------------------------------------------------------------------------
class _DummyDB:
    """No-op stand-in so app.py can call db.init_app(application) without error."""
    def init_app(self, app):
        pass

db = _DummyDB()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def _ns(**kwargs) -> SimpleNamespace:
    """Build a SimpleNamespace from keyword args — used as lightweight row objects."""
    return SimpleNamespace(**kwargs)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS candidates (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    email      TEXT    NOT NULL UNIQUE,
    created_at TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS interviews (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id        INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    job_role            TEXT    NOT NULL,
    experience_level    TEXT    NOT NULL,
    status              TEXT    NOT NULL DEFAULT 'in_progress',
    started_at          TEXT    NOT NULL,
    completed_at        TEXT,
    total_questions     INTEGER NOT NULL DEFAULT 0,
    overall_score       REAL    NOT NULL DEFAULT 0.0,
    technical_score     REAL    NOT NULL DEFAULT 0.0,
    communication_score REAL    NOT NULL DEFAULT 0.0,
    confidence_score    REAL    NOT NULL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS questions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    interview_id    INTEGER NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    question_number INTEGER NOT NULL,
    question_text   TEXT    NOT NULL,
    question_type   TEXT    NOT NULL,
    hints_json      TEXT    NOT NULL DEFAULT '[]',
    asked_at        TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS answers (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id  INTEGER NOT NULL UNIQUE REFERENCES questions(id) ON DELETE CASCADE,
    answer_text  TEXT    NOT NULL,
    input_method TEXT    NOT NULL DEFAULT 'text',
    answered_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS feedback (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    answer_id           INTEGER NOT NULL UNIQUE REFERENCES answers(id) ON DELETE CASCADE,
    relevance_score     REAL NOT NULL DEFAULT 5.0,
    technical_score     REAL NOT NULL DEFAULT 5.0,
    communication_score REAL NOT NULL DEFAULT 5.0,
    confidence_score    REAL NOT NULL DEFAULT 5.0,
    completeness_score  REAL NOT NULL DEFAULT 5.0,
    strengths_json      TEXT NOT NULL DEFAULT '[]',
    weaknesses_json     TEXT NOT NULL DEFAULT '[]',
    suggestions_json    TEXT NOT NULL DEFAULT '[]',
    brief_feedback      TEXT,
    evaluated_at        TEXT NOT NULL
);
"""


def init_db(app=None) -> None:
    """Create all tables if they don't already exist."""
    conn = _conn()
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Row → namespace converters
# ---------------------------------------------------------------------------

def _candidate_ns(row: sqlite3.Row) -> SimpleNamespace:
    return _ns(
        id=row['id'],
        name=row['name'],
        email=row['email'],
        created_at=row['created_at'],
    )


def _feedback_ns(row: sqlite3.Row) -> Optional[SimpleNamespace]:
    if row is None:
        return None
    return _ns(
        id=row['id'],
        answer_id=row['answer_id'],
        relevance_score=row['relevance_score'],
        technical_score=row['technical_score'],
        communication_score=row['communication_score'],
        confidence_score=row['confidence_score'],
        completeness_score=row['completeness_score'],
        strengths=json.loads(row['strengths_json'] or '[]'),
        weaknesses=json.loads(row['weaknesses_json'] or '[]'),
        suggestions=json.loads(row['suggestions_json'] or '[]'),
        brief_feedback=row['brief_feedback'],
        evaluated_at=row['evaluated_at'],
        average_score=(
            row['relevance_score'] + row['technical_score'] +
            row['communication_score'] + row['confidence_score'] +
            row['completeness_score']
        ) / 5.0,
    )


def _answer_ns(row: sqlite3.Row, feedback=None) -> Optional[SimpleNamespace]:
    if row is None:
        return None
    return _ns(
        id=row['id'],
        question_id=row['question_id'],
        answer_text=row['answer_text'],
        input_method=row['input_method'],
        answered_at=row['answered_at'],
        feedback=feedback,
    )


def _question_ns(row: sqlite3.Row, answer=None) -> SimpleNamespace:
    return _ns(
        id=row['id'],
        interview_id=row['interview_id'],
        question_number=row['question_number'],
        question_text=row['question_text'],
        question_type=row['question_type'],
        hints=json.loads(row['hints_json'] or '[]'),
        asked_at=row['asked_at'],
        answer=answer,
    )


def _interview_ns(row: sqlite3.Row, candidate=None) -> SimpleNamespace:
    return _ns(
        id=row['id'],
        candidate_id=row['candidate_id'],
        job_role=row['job_role'],
        experience_level=row['experience_level'],
        status=row['status'],
        started_at=row['started_at'],
        completed_at=row['completed_at'],
        total_questions=row['total_questions'],
        overall_score=row['overall_score'],
        technical_score=row['technical_score'],
        communication_score=row['communication_score'],
        confidence_score=row['confidence_score'],
        candidate=candidate,
        # to_dict mirrors the old ORM shape used by dashboard + report templates
        to_dict=lambda: {
            'id':                  row['id'],
            'candidate_id':        row['candidate_id'],
            'name':                candidate.name  if candidate else '',
            'email':               candidate.email if candidate else '',
            'job_role':            row['job_role'],
            'experience_level':    row['experience_level'],
            'status':              row['status'],
            'started_at':          row['started_at'],
            'completed_at':        row['completed_at'],
            'total_questions':     row['total_questions'],
            'overall_score':       row['overall_score'],
            'technical_score':     row['technical_score'],
            'communication_score': row['communication_score'],
            'confidence_score':    row['confidence_score'],
        },
    )


def _load_interview(conn: sqlite3.Connection, interview_id: int) -> Optional[SimpleNamespace]:
    """Load an Interview plus its Candidate from the DB."""
    iv_row = conn.execute(
        'SELECT * FROM interviews WHERE id=?', (interview_id,)
    ).fetchone()
    if not iv_row:
        return None
    cand_row = conn.execute(
        'SELECT * FROM candidates WHERE id=?', (iv_row['candidate_id'],)
    ).fetchone()
    candidate = _candidate_ns(cand_row) if cand_row else None
    return _interview_ns(iv_row, candidate)


def _load_question_with_chain(conn: sqlite3.Connection,
                               question_id: int) -> Optional[SimpleNamespace]:
    """Load Question + Answer + Feedback chain."""
    q_row = conn.execute('SELECT * FROM questions WHERE id=?', (question_id,)).fetchone()
    if not q_row:
        return None
    a_row = conn.execute(
        'SELECT * FROM answers WHERE question_id=?', (q_row['id'],)
    ).fetchone()
    answer = None
    if a_row:
        fb_row = conn.execute(
            'SELECT * FROM feedback WHERE answer_id=?', (a_row['id'],)
        ).fetchone()
        answer = _answer_ns(a_row, _feedback_ns(fb_row))
    return _question_ns(q_row, answer)


# ===========================================================================
# CRUD — Candidate
# ===========================================================================

def get_candidate_by_email(email: str) -> Optional[SimpleNamespace]:
    email = email.lower().strip()
    conn = _conn()
    try:
        row = conn.execute(
            'SELECT * FROM candidates WHERE email=?', (email,)
        ).fetchone()
        return _candidate_ns(row) if row else None
    finally:
        conn.close()


def get_or_create_candidate(name: str, email: str) -> SimpleNamespace:
    email = email.lower().strip()
    conn  = _conn()
    try:
        row = conn.execute(
            'SELECT * FROM candidates WHERE email=?', (email,)
        ).fetchone()
        if row:
            if row['name'] != name:
                conn.execute(
                    'UPDATE candidates SET name=? WHERE id=?', (name, row['id'])
                )
                conn.commit()
            return _candidate_ns(conn.execute(
                'SELECT * FROM candidates WHERE id=?', (row['id'],)
            ).fetchone())
        cur = conn.execute(
            'INSERT INTO candidates (name, email, created_at) VALUES (?,?,?)',
            (name, email, _now_iso())
        )
        conn.commit()
        row = conn.execute(
            'SELECT * FROM candidates WHERE id=?', (cur.lastrowid,)
        ).fetchone()
        return _candidate_ns(row)
    finally:
        conn.close()


# ===========================================================================
# CRUD — Interview
# ===========================================================================

def create_interview(candidate: SimpleNamespace, job_role: str,
                     experience_level: str) -> SimpleNamespace:
    conn = _conn()
    try:
        cur = conn.execute(
            '''INSERT INTO interviews
               (candidate_id, job_role, experience_level, status, started_at)
               VALUES (?,?,?,?,?)''',
            (candidate.id, job_role, experience_level, 'in_progress', _now_iso())
        )
        conn.commit()
        return _load_interview(conn, cur.lastrowid)
    finally:
        conn.close()


def get_interview(interview_id) -> Optional[SimpleNamespace]:
    if interview_id is None:
        return None
    conn = _conn()
    try:
        return _load_interview(conn, int(interview_id))
    finally:
        conn.close()


def list_interviews(search: str = '', limit: int = 50) -> list:
    conn = _conn()
    try:
        if search:
            pattern = '%' + search + '%'
            rows = conn.execute(
                '''SELECT i.*, c.name as cname, c.email as cemail
                   FROM interviews i JOIN candidates c ON i.candidate_id=c.id
                   WHERE c.name LIKE ? OR c.email LIKE ?
                   ORDER BY i.started_at DESC LIMIT ?''',
                (pattern, pattern, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                '''SELECT i.*, c.name as cname, c.email as cemail
                   FROM interviews i JOIN candidates c ON i.candidate_id=c.id
                   ORDER BY i.started_at DESC LIMIT ?''',
                (limit,)
            ).fetchall()
        result = []
        for r in rows:
            result.append({
                'id':                  r['id'],
                'candidate_id':        r['candidate_id'],
                'name':                r['cname'],
                'email':               r['cemail'],
                'job_role':            r['job_role'],
                'experience_level':    r['experience_level'],
                'status':              r['status'],
                'started_at':          r['started_at'],
                'completed_at':        r['completed_at'],
                'total_questions':     r['total_questions'],
                'overall_score':       r['overall_score'],
                'technical_score':     r['technical_score'],
                'communication_score': r['communication_score'],
                'confidence_score':    r['confidence_score'],
            })
        return result
    finally:
        conn.close()


def complete_interview(iv: SimpleNamespace) -> dict:
    """Aggregate feedback scores and update the Interview row."""
    conn = _conn()
    try:
        q_rows = conn.execute(
            'SELECT id FROM questions WHERE interview_id=?', (iv.id,)
        ).fetchall()

        feedback_rows = []
        for q_row in q_rows:
            a_row = conn.execute(
                'SELECT id FROM answers WHERE question_id=?', (q_row['id'],)
            ).fetchone()
            if a_row:
                fb_row = conn.execute(
                    'SELECT * FROM feedback WHERE answer_id=?', (a_row['id'],)
                ).fetchone()
                if fb_row:
                    feedback_rows.append(fb_row)

        if not feedback_rows:
            raise ValueError('No scored answers found for this interview.')

        n = len(feedback_rows)

        def avg(col):
            return round(sum(r[col] for r in feedback_rows) / n, 2)

        overall = round(
            (avg('relevance_score') + avg('technical_score') +
             avg('communication_score') + avg('confidence_score') +
             avg('completeness_score')) / 5, 2
        )
        tech   = avg('technical_score')
        comm   = avg('communication_score')
        conf   = avg('confidence_score')

        conn.execute(
            '''UPDATE interviews SET
               status='completed', completed_at=?, total_questions=?,
               overall_score=?, technical_score=?,
               communication_score=?, confidence_score=?
               WHERE id=?''',
            (_now_iso(), n, overall, tech, comm, conf, iv.id)
        )
        conn.commit()

        return {
            'interview_id':        iv.id,
            'overall_score':       overall,
            'technical_score':     tech,
            'communication_score': comm,
            'confidence_score':    conf,
            'total_questions':     n,
        }
    finally:
        conn.close()


def search_interviews(query: str) -> list:
    return list_interviews(search=query)


# ===========================================================================
# CRUD — Question
# ===========================================================================

def create_question(interview: SimpleNamespace, question_number: int,
                    question_text: str, question_type: str,
                    hints: Optional[list] = None) -> SimpleNamespace:
    conn = _conn()
    try:
        # Avoid duplicate question_number for same interview (idempotent retry)
        existing = conn.execute(
            'SELECT id FROM questions WHERE interview_id=? AND question_number=?',
            (interview.id, question_number)
        ).fetchone()
        if existing:
            return _load_question_with_chain(conn, existing['id'])

        cur = conn.execute(
            '''INSERT INTO questions
               (interview_id, question_number, question_text, question_type,
                hints_json, asked_at)
               VALUES (?,?,?,?,?,?)''',
            (interview.id, question_number, question_text, question_type,
             json.dumps(hints or []), _now_iso())
        )
        conn.commit()
        return _load_question_with_chain(conn, cur.lastrowid)
    finally:
        conn.close()


def get_question(question_id: int) -> Optional[SimpleNamespace]:
    conn = _conn()
    try:
        return _load_question_with_chain(conn, question_id)
    finally:
        conn.close()


def get_questions_for_interview(interview_id: int) -> list:
    conn = _conn()
    try:
        rows = conn.execute(
            'SELECT id FROM questions WHERE interview_id=? ORDER BY question_number',
            (interview_id,)
        ).fetchall()
        return [_load_question_with_chain(conn, r['id']) for r in rows]
    finally:
        conn.close()


def get_question_by_number(interview_id: int,
                            question_number: int) -> Optional[SimpleNamespace]:
    conn = _conn()
    try:
        row = conn.execute(
            'SELECT id FROM questions WHERE interview_id=? AND question_number=?',
            (interview_id, question_number)
        ).fetchone()
        if not row:
            return None
        return _load_question_with_chain(conn, row['id'])
    finally:
        conn.close()


# ===========================================================================
# CRUD — Answer
# ===========================================================================

def create_answer(question: SimpleNamespace, answer_text: str,
                  input_method: str = 'text') -> SimpleNamespace:
    conn = _conn()
    try:
        cur = conn.execute(
            '''INSERT OR IGNORE INTO answers
               (question_id, answer_text, input_method, answered_at)
               VALUES (?,?,?,?)''',
            (question.id, answer_text, input_method, _now_iso())
        )
        conn.commit()
        a_row = conn.execute(
            'SELECT * FROM answers WHERE question_id=?', (question.id,)
        ).fetchone()
        return _answer_ns(a_row)
    finally:
        conn.close()


def get_answer_for_question(question_id: int) -> Optional[SimpleNamespace]:
    conn = _conn()
    try:
        a_row = conn.execute(
            'SELECT * FROM answers WHERE question_id=?', (question_id,)
        ).fetchone()
        if not a_row:
            return None
        fb_row = conn.execute(
            'SELECT * FROM feedback WHERE answer_id=?', (a_row['id'],)
        ).fetchone()
        return _answer_ns(a_row, _feedback_ns(fb_row))
    finally:
        conn.close()


# ===========================================================================
# CRUD — Feedback
# ===========================================================================

def create_feedback(answer: SimpleNamespace, scores: dict,
                    strengths: Optional[list] = None,
                    weaknesses: Optional[list] = None,
                    suggestions: Optional[list] = None,
                    brief_feedback: Optional[str] = None) -> SimpleNamespace:
    conn = _conn()
    try:
        cur = conn.execute(
            '''INSERT OR IGNORE INTO feedback
               (answer_id, relevance_score, technical_score,
                communication_score, confidence_score, completeness_score,
                strengths_json, weaknesses_json, suggestions_json,
                brief_feedback, evaluated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            (
                answer.id,
                float(scores.get('relevance', 5)),
                float(scores.get('technical', 5)),
                float(scores.get('communication', 5)),
                float(scores.get('confidence', 5)),
                float(scores.get('completeness', 5)),
                json.dumps(strengths   or []),
                json.dumps(weaknesses  or []),
                json.dumps(suggestions or []),
                brief_feedback,
                _now_iso(),
            )
        )
        conn.commit()
        fb_row = conn.execute(
            'SELECT * FROM feedback WHERE answer_id=?', (answer.id,)
        ).fetchone()
        return _feedback_ns(fb_row)
    finally:
        conn.close()


def get_feedback_for_answer(answer_id: int) -> Optional[SimpleNamespace]:
    conn = _conn()
    try:
        fb_row = conn.execute(
            'SELECT * FROM feedback WHERE answer_id=?', (answer_id,)
        ).fetchone()
        return _feedback_ns(fb_row)
    finally:
        conn.close()


# ===========================================================================
# REPORT BUILDER
# ===========================================================================

def build_report_dict(iv: SimpleNamespace) -> dict:
    """
    Assemble the full report payload that /api/report/<id> returns.
    Shape: { interview: {...}, responses: [{...}, ...] }
    """
    questions = get_questions_for_interview(iv.id)
    responses = []
    for question in questions:
        answer   = question.answer
        feedback = answer.feedback if answer else None
        responses.append({
            'question_number': question.question_number,
            'question_text':   question.question_text,
            'question_type':   question.question_type,
            'answer_text':     answer.answer_text if answer else None,
            'scores': {
                'relevance':     feedback.relevance_score     if feedback else 0.0,
                'technical':     feedback.technical_score     if feedback else 0.0,
                'communication': feedback.communication_score if feedback else 0.0,
                'confidence':    feedback.confidence_score    if feedback else 0.0,
                'completeness':  feedback.completeness_score  if feedback else 0.0,
            },
            'strengths':   feedback.strengths   if feedback else [],
            'weaknesses':  feedback.weaknesses  if feedback else [],
            'suggestions': feedback.suggestions if feedback else [],
        })

    return {
        'interview': iv.to_dict(),
        'responses': responses,
    }
