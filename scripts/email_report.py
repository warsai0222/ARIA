"""
ARIA Weekly Analytics Report

Queries aria_query_log for the past 7 days and sends an HTML email to Varshith.

Usage:
    python scripts/email_report.py

Required env vars:
    DATABASE_URL         — Neon PostgreSQL connection string
    GMAIL_USER           — Gmail address used to send (e.g. yourname@gmail.com)
    GMAIL_APP_PASSWORD   — 16-char App Password from Google Account → Security → App Passwords
    REPORT_RECIPIENT     — defaults to varshith.tipirneni@gmail.com
"""

from __future__ import annotations

import os
import smtplib
import sys
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv()

import asyncpg
import asyncio


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

async def fetch_report_data(days: int = 7) -> dict:
    """Pull last N days of analytics from Neon."""
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    since = datetime.now(timezone.utc) - timedelta(days=days)

    try:
        rows = await conn.fetch(
            """
            SELECT query, session_id, cache_hit, couldnt_answer,
                   response_snippet, response_time_ms, created_at
            FROM aria_query_log
            WHERE created_at >= $1
            ORDER BY created_at DESC
            """,
            since,
        )
    finally:
        await conn.close()

    records = [dict(r) for r in rows]
    total = len(records)
    cache_hits = sum(1 for r in records if r.get("cache_hit"))
    couldnt_answer = [r for r in records if r.get("couldnt_answer")]
    unique_sessions = len({r["session_id"] for r in records if r.get("session_id")})
    avg_rt = (
        int(sum(r["response_time_ms"] for r in records if r.get("response_time_ms")) / total)
        if total else 0
    )

    # Top questions by frequency
    query_counts = Counter(r["query"].strip().lower() for r in records if r.get("query"))
    top_questions = query_counts.most_common(10)

    # Top questions with response snippets (first occurrence per question)
    seen: set[str] = set()
    top_with_response: list[dict] = []
    for r in reversed(records):  # oldest first so we get the first response
        q = r["query"].strip().lower()
        if q not in seen and r.get("response_snippet"):
            seen.add(q)
            top_with_response.append({
                "query": r["query"].strip(),
                "snippet": r["response_snippet"],
                "count": query_counts.get(q, 1),
            })
        if len(top_with_response) >= 10:
            break
    top_with_response.sort(key=lambda x: x["count"], reverse=True)

    # Unanswered questions (couldnt_answer, unique)
    seen_unanswered: set[str] = set()
    unanswered_unique: list[str] = []
    for r in couldnt_answer:
        q = r["query"].strip()
        if q.lower() not in seen_unanswered:
            seen_unanswered.add(q.lower())
            unanswered_unique.append(q)

    return {
        "total": total,
        "unique_sessions": unique_sessions,
        "cache_hits": cache_hits,
        "cache_hit_rate": round(100 * cache_hits / total, 1) if total else 0,
        "couldnt_answer_count": len(couldnt_answer),
        "couldnt_answer_rate": round(100 * len(couldnt_answer) / total, 1) if total else 0,
        "avg_response_ms": avg_rt,
        "top_questions": top_questions,
        "top_with_response": top_with_response,
        "unanswered": unanswered_unique[:15],
        "period_start": since.strftime("%b %d, %Y"),
        "period_end": datetime.now(timezone.utc).strftime("%b %d, %Y"),
    }


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def build_html(data: dict) -> str:
    def stat_card(label: str, value: str, sub: str = "") -> str:
        return f"""
        <td style="width:25%;padding:0 8px 0 0;vertical-align:top">
          <div style="background:#1a1812;border:1px solid #262119;border-radius:10px;padding:20px 18px">
            <div style="font-size:26px;font-weight:700;color:#f5a623;font-family:Arial,sans-serif">{value}</div>
            <div style="font-size:12px;color:#a39577;margin-top:4px">{label}</div>
            {f'<div style="font-size:11px;color:#6b6050;margin-top:2px">{sub}</div>' if sub else ''}
          </div>
        </td>"""

    def section(title: str, content: str) -> str:
        return f"""
        <div style="margin-bottom:32px">
          <h2 style="font-size:15px;font-weight:600;color:#f5a623;margin:0 0 14px;
                     text-transform:uppercase;letter-spacing:0.08em;font-family:Arial,sans-serif">
            {title}
          </h2>
          {content}
        </div>"""

    # Top questions table
    top_q_rows = ""
    for i, (q, count) in enumerate(data["top_questions"], 1):
        bg = "#1a1812" if i % 2 == 0 else "#13110d"
        top_q_rows += f"""
        <tr style="background:{bg}">
          <td style="padding:10px 14px;color:#6b6050;font-size:12px;width:32px">{i}</td>
          <td style="padding:10px 14px;color:#ede9db;font-size:13px">{q}</td>
          <td style="padding:10px 14px;color:#f5a623;font-size:13px;text-align:right;
                     font-weight:600;width:60px">{count}×</td>
        </tr>"""

    top_q_table = f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;
           border:1px solid #262119;border-radius:8px;overflow:hidden">
      <thead>
        <tr style="background:#221e15">
          <th style="padding:10px 14px;color:#6b6050;font-size:11px;text-align:left">#</th>
          <th style="padding:10px 14px;color:#6b6050;font-size:11px;text-align:left">Question</th>
          <th style="padding:10px 14px;color:#6b6050;font-size:11px;text-align:right">Asked</th>
        </tr>
      </thead>
      <tbody>{top_q_rows}</tbody>
    </table>""" if data["top_questions"] else "<p style='color:#6b6050;font-size:13px'>No questions this week.</p>"

    # Response preview cards
    response_cards = ""
    for item in data["top_with_response"][:5]:
        snippet = item["snippet"][:280].rstrip() + ("…" if len(item["snippet"]) > 280 else "")
        response_cards += f"""
        <div style="background:#1a1812;border:1px solid #262119;border-radius:8px;
                    padding:16px;margin-bottom:10px">
          <div style="font-size:13px;font-weight:600;color:#ede9db;margin-bottom:8px">
            Q: {item['query']}
            <span style="font-size:11px;color:#f5a623;margin-left:8px">
              asked {item['count']}×
            </span>
          </div>
          <div style="font-size:12px;color:#a39577;line-height:1.6;border-left:2px solid #38311f;
                      padding-left:12px">
            {snippet}
          </div>
        </div>"""

    # Unanswered questions
    if data["unanswered"]:
        unanswered_items = "".join(
            f'<li style="margin-bottom:6px;color:#ede9db;font-size:13px">{q}</li>'
            for q in data["unanswered"]
        )
        unanswered_content = f"""
        <div style="background:#1a1812;border:1px solid #262119;border-radius:8px;padding:16px">
          <ul style="margin:0;padding-left:18px">{unanswered_items}</ul>
        </div>
        <p style="font-size:12px;color:#6b6050;margin-top:10px">
          💡 Consider adding these to <code>data/varshith.json</code> FAQ section.
        </p>"""
    else:
        unanswered_content = "<p style='color:#10b981;font-size:13px'>✓ ARIA answered everything this week.</p>"

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0a0908;font-family:Arial,Helvetica,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0908">
    <tr><td align="center" style="padding:40px 20px">
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%">

        <!-- Header -->
        <tr><td style="padding-bottom:28px">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td>
                <div style="display:inline-block;background:linear-gradient(135deg,#f5a623,#b45309);
                            border-radius:50%;width:40px;height:40px;text-align:center;
                            line-height:40px;font-size:18px;font-weight:700;color:#000">A</div>
              </td>
              <td style="padding-left:12px;vertical-align:middle">
                <div style="font-size:18px;font-weight:700;color:#ede9db">ARIA Weekly Report</div>
                <div style="font-size:12px;color:#a39577">{data['period_start']} — {data['period_end']}</div>
              </td>
            </tr>
          </table>
        </td></tr>

        <!-- Stats row -->
        <tr><td style="padding-bottom:28px">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              {stat_card("Total Queries", str(data['total']), f"{data['unique_sessions']} unique visitors")}
              {stat_card("Cache Hit Rate", f"{data['cache_hit_rate']}%", f"{data['cache_hits']} cached")}
              {stat_card("Couldn't Answer", f"{data['couldnt_answer_rate']}%", f"{data['couldnt_answer_count']} queries")}
              {stat_card("Avg Response", f"{data['avg_response_ms']}ms", "streaming latency")}
            </tr>
          </table>
        </td></tr>

        <!-- Divider -->
        <tr><td style="border-top:1px solid #262119;padding-bottom:28px"></td></tr>

        <!-- Top questions -->
        <tr><td style="padding-bottom:28px">
          {section("🔥 Most Asked Questions", top_q_table)}
        </td></tr>

        <!-- Response previews -->
        <tr><td style="padding-bottom:28px">
          {section("💬 What ARIA Said (Top 5)", response_cards or "<p style='color:#6b6050;font-size:13px'>No responses logged this week.</p>")}
        </td></tr>

        <!-- Unanswered -->
        <tr><td style="padding-bottom:28px">
          {section("❓ Questions ARIA Couldn't Answer", unanswered_content)}
        </td></tr>

        <!-- Footer -->
        <tr><td style="border-top:1px solid #262119;padding-top:20px">
          <p style="font-size:11px;color:#544a36;margin:0">
            ARIA — Varshith Tipirneni's portfolio AI assistant •
            Report generated automatically every Monday
          </p>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Send email
# ---------------------------------------------------------------------------

def send_email(html: str, subject: str) -> None:
    gmail_user = os.environ["GMAIL_USER"]
    gmail_password = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ.get("REPORT_RECIPIENT", "varshith.tipirneni@gmail.com")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"ARIA Report <{gmail_user}>"
    msg["To"] = recipient

    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_password)
        server.sendmail(gmail_user, recipient, msg.as_string())

    print(f"✓ Report sent to {recipient}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def _main() -> None:
    for var in ["DATABASE_URL", "GMAIL_USER", "GMAIL_APP_PASSWORD"]:
        if not os.environ.get(var):
            raise EnvironmentError(f"Missing required env var: {var}")

    print("Fetching analytics data...")
    data = await fetch_report_data(days=7)

    print(f"  Total queries: {data['total']}")
    print(f"  Unique visitors: {data['unique_sessions']}")
    print(f"  Couldn't answer: {data['couldnt_answer_count']} ({data['couldnt_answer_rate']}%)")
    print(f"  Top question: {data['top_questions'][0][0] if data['top_questions'] else 'N/A'}")

    html = build_html(data)
    subject = f"ARIA Weekly Report — {data['period_start']} to {data['period_end']}"

    print("Sending email...")
    send_email(html, subject)


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
