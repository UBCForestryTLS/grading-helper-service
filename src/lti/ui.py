"""Instructor SPA rendered as HTML from the LTI launch endpoint."""

from html import escape


def render_instructor_ui(
    launch_id: str,
    session_token: str,
    base_url: str,
    user_name: str = "",
    course_title: str = "",
    roles: list[str] | None = None,
) -> str:
    """Render the instructor single-page application as an HTML string."""
    roles = roles or []
    safe_name = escape(user_name)
    safe_course = escape(course_title)
    safe_roles = ", ".join(escape(r) for r in roles)
    safe_token = escape(session_token)
    safe_base_url = escape(base_url)
    safe_launch_id = escape(launch_id)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="session-token" content="{safe_token}">
  <title>Grading Helper</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           margin: 0; padding: 16px; background: #f5f5f5; color: #333; }}
    .card {{ background: white; border-radius: 8px; padding: 16px; margin-bottom: 16px;
             box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
    .user-info {{ font-size: 0.9em; color: #666; }}
    h1 {{ margin: 0 0 4px 0; font-size: 1.4em; color: #1a1a1a; }}
    h2 {{ margin: 0 0 12px 0; font-size: 1.1em; }}
    button {{ background: #0066cc; color: white; border: none; border-radius: 4px;
              padding: 8px 16px; cursor: pointer; font-size: 0.95em; }}
    button:hover {{ background: #0052a3; }}
    button:disabled {{ background: #999; cursor: not-allowed; }}
    select {{ width: 100%; padding: 8px; font-size: 0.95em; border: 1px solid #ccc;
              border-radius: 4px; margin-bottom: 12px; }}
    .hidden {{ display: none; }}
    .error {{ color: #cc0000; font-size: 0.9em; margin-top: 8px; }}
    .success {{ color: #006600; font-size: 0.9em; margin-top: 8px; }}
    .status {{ font-size: 0.9em; color: #555; margin-top: 8px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.9em; }}
    th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #eee; }}
    th {{ background: #f0f0f0; font-weight: 600; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px;
              font-size: 0.8em; font-weight: 600; }}
    .badge-pending {{ background: #fff3cd; color: #856404; }}
    .badge-done {{ background: #d4edda; color: #155724; }}
    a.authorize-link {{ color: #0066cc; text-decoration: none; }}
    a.authorize-link:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>UBC Forestry Grading Helper</h1>
    <div class="user-info">
      <span>User: {safe_name}</span> &nbsp;|&nbsp;
      <span>Course: {safe_course}</span> &nbsp;|&nbsp;
      <span>Roles: {safe_roles}</span>
    </div>
  </div>

  <div id="section-quiz" class="card">
    <h2>Select Quiz to Grade</h2>
    <button id="btn-load-quizzes" onclick="loadQuizzes()">Load Quizzes</button>
    <div id="quiz-list-container" class="hidden">
      <br>
      <select id="quiz-select">
        <option value="">-- Select a quiz --</option>
      </select>
      <button id="btn-start-grading" onclick="startGrading()" disabled>
        Start AI Grading
      </button>
    </div>
    <div id="auth-prompt" class="hidden">
      <p>Canvas access not authorized yet.</p>
      <a class="authorize-link" id="authorize-link" href="#">
        Click here to authorize Canvas access
      </a>
    </div>
    <div id="quiz-error" class="error hidden"></div>
  </div>

  <div id="section-grading" class="card hidden">
    <h2>Grading in Progress</h2>
    <div id="grading-status" class="status">Starting...</div>
  </div>

  <div id="section-results" class="card hidden">
    <h2>Grading Results</h2>
    <div id="results-summary" class="status"></div>
    <br>
    <table id="results-table">
      <thead>
        <tr>
          <th>Question</th>
          <th>Student Answer</th>
          <th>AI Grade</th>
          <th>Max</th>
          <th>Feedback</th>
        </tr>
      </thead>
      <tbody id="results-tbody"></tbody>
    </table>
    <br>
    <button id="btn-passback" onclick="pushGrades()">Push Grades to Canvas</button>
    <div id="passback-status" class="status hidden"></div>
  </div>

  <script>
    const SESSION_TOKEN = document.querySelector('meta[name="session-token"]').getAttribute('content');
    const BASE_URL = '{safe_base_url}';
    const LAUNCH_ID = '{safe_launch_id}';
    let currentJobId = null;
    let pollTimer = null;

    function authHeaders() {{
      return {{
        'Authorization': 'Bearer ' + SESSION_TOKEN,
        'Content-Type': 'application/json',
      }};
    }}

    function showError(elementId, msg) {{
      const el = document.getElementById(elementId);
      el.textContent = msg;
      el.classList.remove('hidden');
    }}

    async function loadQuizzes() {{
      document.getElementById('btn-load-quizzes').disabled = true;
      document.getElementById('quiz-error').classList.add('hidden');
      try {{
        const resp = await fetch(BASE_URL + '/lti/quizzes?launch_id=' + LAUNCH_ID, {{
          headers: authHeaders(),
        }});
        if (resp.status === 401) {{
          const authLink = BASE_URL + '/lti/oauth/authorize?launch_id=' + LAUNCH_ID;
          document.getElementById('authorize-link').href = authLink;
          document.getElementById('auth-prompt').classList.remove('hidden');
          document.getElementById('btn-load-quizzes').disabled = false;
          return;
        }}
        if (!resp.ok) throw new Error('Failed to load quizzes: ' + resp.status);
        const quizzes = await resp.json();
        const select = document.getElementById('quiz-select');
        quizzes.forEach(q => {{
          const opt = document.createElement('option');
          opt.value = q.id;
          opt.textContent = q.title || ('Quiz ' + q.id);
          select.appendChild(opt);
        }});
        document.getElementById('quiz-list-container').classList.remove('hidden');
        select.addEventListener('change', () => {{
          document.getElementById('btn-start-grading').disabled = !select.value;
        }});
      }} catch (e) {{
        showError('quiz-error', e.message);
        document.getElementById('btn-load-quizzes').disabled = false;
      }}
    }}

    async function startGrading() {{
      const quizId = document.getElementById('quiz-select').value;
      if (!quizId) return;
      document.getElementById('btn-start-grading').disabled = true;
      document.getElementById('section-grading').classList.remove('hidden');
      document.getElementById('grading-status').textContent = 'Creating grading job...';

      try {{
        const resp = await fetch(BASE_URL + '/lti/jobs', {{
          method: 'POST',
          headers: authHeaders(),
          body: JSON.stringify({{ launch_id: LAUNCH_ID, quiz_id: quizId }}),
        }});
        if (!resp.ok) throw new Error('Failed to create job: ' + resp.status);
        const job = await resp.json();
        currentJobId = job.job_id;

        // Start grading
        const gradeResp = await fetch(BASE_URL + '/jobs/' + currentJobId + '/grade', {{
          method: 'POST',
          headers: authHeaders(),
        }});
        if (!gradeResp.ok) throw new Error('Failed to start grading: ' + gradeResp.status);

        pollJobStatus();
      }} catch (e) {{
        document.getElementById('grading-status').textContent = 'Error: ' + e.message;
        document.getElementById('btn-start-grading').disabled = false;
      }}
    }}

    function pollJobStatus() {{
      pollTimer = setInterval(async () => {{
        try {{
          const resp = await fetch(BASE_URL + '/jobs/' + currentJobId, {{
            headers: authHeaders(),
          }});
          if (!resp.ok) return;
          const job = await resp.json();
          document.getElementById('grading-status').textContent =
            'Status: ' + job.status + ' (' + job.total_submissions + ' submissions)';

          if (job.status === 'COMPLETED') {{
            clearInterval(pollTimer);
            await showResults();
          }} else if (job.status === 'FAILED') {{
            clearInterval(pollTimer);
            document.getElementById('grading-status').textContent =
              'Grading failed: ' + (job.error_message || 'Unknown error');
          }}
        }} catch (e) {{
          // Keep polling on transient errors
        }}
      }}, 2000);
    }}

    async function showResults() {{
      const resp = await fetch(BASE_URL + '/jobs/' + currentJobId + '/submissions', {{
        headers: authHeaders(),
      }});
      if (!resp.ok) return;
      const subs = await resp.json();

      const tbody = document.getElementById('results-tbody');
      tbody.innerHTML = '';
      subs.forEach(sub => {{
        const tr = document.createElement('tr');
        [
          sub.question_name || ('Q' + sub.question_id),
          sub.student_answer,
          sub.ai_grade != null ? sub.ai_grade : '—',
          sub.points_possible,
          sub.ai_feedback || '—',
        ].forEach(val => {{
          const td = document.createElement('td');
          td.textContent = val;
          tr.appendChild(td);
        }});
        tbody.appendChild(tr);
      }});

      const graded = subs.filter(s => s.ai_grade != null).length;
      document.getElementById('results-summary').textContent =
        graded + ' of ' + subs.length + ' submissions graded.';
      document.getElementById('section-results').classList.remove('hidden');
    }}

    async function pushGrades() {{
      document.getElementById('btn-passback').disabled = true;
      document.getElementById('passback-status').classList.remove('hidden');
      document.getElementById('passback-status').textContent = 'Pushing grades...';

      try {{
        const resp = await fetch(BASE_URL + '/lti/passback/' + currentJobId, {{
          method: 'POST',
          headers: authHeaders(),
          body: JSON.stringify({{ launch_id: LAUNCH_ID }}),
        }});
        if (!resp.ok) throw new Error('Passback failed: ' + resp.status);
        const result = await resp.json();
        document.getElementById('passback-status').textContent =
          'Done! ' + result.submitted + ' grades submitted to Canvas.' +
          (result.errors.length ? ' Errors: ' + result.errors.join(', ') : '');
      }} catch (e) {{
        document.getElementById('passback-status').textContent = 'Error: ' + e.message;
        document.getElementById('btn-passback').disabled = false;
      }}
    }}
  </script>
</body>
</html>"""
