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
    .badge-processing {{ background: #cce5ff; color: #004085; }}
    .badge-done {{ background: #d4edda; color: #155724; }}
    .badge-failed {{ background: #f8d7da; color: #721c24; }}
    .badge-cancelled {{ background: #b9bdba; color: #666967; }}
    a.authorize-link {{ color: #0066cc; text-decoration: none; }}
    a.authorize-link:hover {{ text-decoration: underline; }}

    .tab-bar {{ display: flex; border-bottom: 2px solid #ddd; margin-bottom: 16px; }}
    .tab {{ padding: 10px 20px; cursor: pointer; border: none; background: none;
            font-size: 0.95em; color: #666; border-bottom: 2px solid transparent;
            margin-bottom: -2px; }}
    .tab.active {{ color: #0066cc; border-bottom-color: #0066cc; font-weight: 600; }}
    .tab:hover {{ color: #0052a3; background: none; }}
    .tab-content {{ display: none; }}
    .tab-content.active {{ display: block; }}

    .steps {{ display: flex; align-items: center; padding: 12px 16px;
              background: white; border-radius: 8px; margin-bottom: 16px;
              box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
    .step {{ display: flex; align-items: center; color: #999; font-size: 0.9em; }}
    .step.active {{ color: #0066cc; font-weight: 600; }}
    .step.done {{ color: #006600; }}
    .step-num {{ display: inline-flex; align-items: center; justify-content: center;
                 width: 22px; height: 22px; border-radius: 50%;
                 background: #ddd; color: #666; font-size: 0.8em; font-weight: 700;
                 margin-right: 6px; }}
    .step.active .step-num {{ background: #0066cc; color: white; }}
    .step.done .step-num {{ background: #006600; color: white; }}
    .step-arrow {{ margin: 0 12px; color: #ccc; font-size: 1.1em; }}

    .stats-bar {{ display: flex; gap: 24px; padding: 14px 20px; background: #f0f7ff;
                  border-radius: 6px; margin-bottom: 16px; }}
    .stat {{ text-align: center; flex: 1; }}
    .stat-value {{ font-size: 1.3em; font-weight: 700; color: #0066cc; }}
    .stat-label {{ font-size: 0.8em; color: #666; margin-top: 2px; }}

    .student-header td {{ background: #e8f0fe; font-weight: 600;
                          padding: 10px 8px; border-bottom: 2px solid #c4d8f0; }}

    .results-header {{ display: flex; justify-content: space-between;
                       align-items: center; margin-bottom: 12px; }}
    .results-header h2 {{ margin: 0; }}

    .btn-small {{ padding: 4px 12px; font-size: 0.85em; }}
    .btn-link {{ background: none; border: none; color: #0066cc; cursor: pointer;
                 font-size: 0.9em; padding: 0; }}
    .btn-link:hover {{ text-decoration: underline; background: none; }}

    #results-table td:nth-child(2),
    #results-table td:nth-child(3),
    #results-table td:nth-child(6) {{
      max-width: 250px; word-break: break-word;
    }}
    #history-table tbody tr:hover {{ background: #f8f8f8; }}
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

  <div class="tab-bar">
    <button class="tab active" id="tab-btn-grade" onclick="switchTab('grade')">Grade a Quiz</button>
    <button class="tab" id="tab-btn-history" onclick="switchTab('history')">Past Jobs</button>
  </div>

  <div id="tab-grade" class="tab-content active">
    <div class="steps">
      <div class="step active" id="step-1">
        <span class="step-num">1</span> Select Quiz
      </div>
      <span class="step-arrow">&rarr;</span>
      <div class="step" id="step-2">
        <span class="step-num">2</span> Grade
      </div>
      <span class="step-arrow">&rarr;</span>
      <div class="step" id="step-3">
        <span class="step-num">3</span> Review &amp; Push
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
		<button id="btn-cancel-grading" style="display:none;">Cancel Grading</button>

<div id="grading-status"></div>
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
      <div class="results-header">
        <h2 id="results-title">Grading Results</h2>
        <button id="btn-back-history" class="btn-link hidden"
                onclick="backToHistory()">&larr; Back to Past Jobs</button>
      </div>
      <div class="stats-bar">
        <div class="stat">
          <div class="stat-value" id="stat-students">0</div>
          <div class="stat-label">Students</div>
        </div>
        <div class="stat">
          <div class="stat-value" id="stat-questions">0</div>
          <div class="stat-label">Questions</div>
        </div>
        <div class="stat">
          <div class="stat-value" id="stat-avg">&mdash;</div>
          <div class="stat-label">Avg Score</div>
        </div>
        <div class="stat">
          <div class="stat-value" id="stat-max">&mdash;</div>
          <div class="stat-label">Max Points</div>
        </div>
      </div>
      <div id="results-summary" class="status"></div>
      <br>
      <table id="results-table">
        <thead>
          <tr>
            <th>Question</th>
            <th>Question Text</th>
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
  </div>

  <div id="tab-history" class="tab-content">
    <div class="card">
      <h2>Past Grading Jobs</h2>
      <table id="history-table">
        <thead>
          <tr>
            <th>Quiz Name</th>
            <th>Date</th>
            <th>Submissions</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody id="history-tbody"></tbody>
      </table>
      <div id="history-empty" class="status hidden">No past jobs found.</div>
      <div id="history-error" class="error hidden"></div>
    </div>
  </div>

  <script>
    const SESSION_TOKEN = document.querySelector('meta[name="session-token"]').getAttribute('content');
    const BASE_URL = '{safe_base_url}';
    const LAUNCH_ID = '{safe_launch_id}';
    let currentJobId = null;
    let pollTimer = null;
    let cameFromHistory = false;

    function authHeaders() {{
      return {{
        'Authorization': 'Bearer ' + SESSION_TOKEN,
        'Content-Type': 'application/json',
      }};
    }}

    // Canvas returns question text and (sometimes) student answers wrapped in
    // HTML markup like <p><span>...</span></p>. Render that into a detached
    // element and read textContent to get the plain-text version. Using a
    // detached node means any <script> in the HTML never executes.
    function stripHtml(value) {{
      if (value == null) return '';
      const s = String(value);
      if (s.indexOf('<') === -1) return s;
      const tmp = document.createElement('div');
      tmp.innerHTML = s;
      return (tmp.textContent || tmp.innerText || '').trim();
    }}

    function showError(elementId, msg) {{
      const el = document.getElementById(elementId);
      el.textContent = msg;
      el.classList.remove('hidden');
    }}

    async function getErrorMessage(resp) {{
      try {{
        const body = await resp.clone().json();
        if (body.detail && typeof body.detail === 'string') return body.detail;
      }} catch (e) {{}}
      const messages = {{
        403: 'You do not have permission to perform this action.',
        404: 'The requested resource was not found.',
        409: 'This quiz has already been graded.',
        422: 'No gradable submissions were found in this quiz.',
        502: 'Could not reach Canvas. Please try again later.',
        503: 'Canvas API is not configured. Contact your administrator.',
      }};
      return messages[resp.status] || 'Something went wrong. Please try again.';
    }}

    function switchTab(tab) {{
      // If the user is currently viewing a past job's results (which renders
      // inside the Grade tab) and clicks "Grade a Quiz", reset the Grade tab
      // back to step 1 so they can start a fresh grading job.
      if (tab === 'grade' && cameFromHistory) {{
        resetGradeTab();
      }}
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      document.getElementById('tab-btn-' + tab).classList.add('active');
      document.getElementById('tab-' + tab).classList.add('active');
      if (tab === 'history') loadPastJobs();
    }}

    // Restore the Grade tab to its initial "select a quiz" state. Used when
    // returning from a past-job results view so the next grading run starts
    // cleanly without leftover UI from the previous job.
    function resetGradeTab() {{
      cameFromHistory = false;
      currentJobId = null;
      document.getElementById('section-quiz').classList.remove('hidden');
      document.getElementById('section-grading').classList.add('hidden');
      document.getElementById('section-results').classList.add('hidden');
      document.getElementById('btn-back-history').classList.add('hidden');
      document.getElementById('results-title').textContent = 'Grading Results';
      document.getElementById('passback-status').classList.add('hidden');
      document.getElementById('btn-passback').disabled = false;
      setStep(1);
    }}

    function setStep(n) {{
      [1, 2, 3].forEach(i => {{
        const el = document.getElementById('step-' + i);
        el.classList.remove('active', 'done');
        if (i < n) el.classList.add('done');
        if (i === n) el.classList.add('active');
      }});
    }}

    // Fetch the instructor's quizzes from Canvas via the LTI proxy endpoint.
    // If Canvas returns 401 the instructor needs to OAuth-authorize the tool;
    // we surface the authorize link instead of an error.
    async function loadQuizzes() {{
      document.getElementById('btn-load-quizzes').disabled = true;
      document.getElementById('quiz-error').classList.add('hidden');
      document.getElementById('auth-prompt').classList.add('hidden');
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
        if (!resp.ok) {{
          showError('quiz-error', await getErrorMessage(resp));
          document.getElementById('btn-load-quizzes').disabled = false;
          return;
        }}
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
        showError('quiz-error', 'Could not connect to the server. Please try again.');
        document.getElementById('btn-load-quizzes').disabled = false;
      }}
    }}

    // Three-step flow: (1) create the grading job from the chosen quiz,
    // (2) kick off the AI grading run, (3) start polling for completion.
    // The AI grading endpoint returns immediately; results land in DynamoDB
    // as Bedrock calls finish, which is why we poll the job status below.
    async function startGrading() {{
      const select = document.getElementById('quiz-select');
      const quizId = select.value;
      if (!quizId) return;
      const quizTitle = select.options[select.selectedIndex].text;

      document.getElementById('btn-start-grading').disabled = true;
      setStep(2);
      document.getElementById('section-grading').classList.remove('hidden');
      document.getElementById('grading-status').textContent = 'Creating grading job...';

      try {{
        const resp = await fetch(BASE_URL + '/lti/jobs', {{
          method: 'POST',
          headers: authHeaders(),
          body: JSON.stringify({{ launch_id: LAUNCH_ID, quiz_id: quizId, quiz_title: quizTitle }}),
        }});
        if (!resp.ok) {{
          document.getElementById('grading-status').textContent = await getErrorMessage(resp);
          document.getElementById('btn-start-grading').disabled = false;
          setStep(1);
          return;
        }}
        const job = await resp.json();
        currentJobId = job.job_id;
        
        document.getElementById('btn-cancel-grading').style.display = 'inline-block';

        document.getElementById('grading-status').textContent = 'Starting AI grading...';
        const gradeResp = await fetch(BASE_URL + '/jobs/' + currentJobId + '/grade', {{
          method: 'POST',
          headers: authHeaders(),
        }});
        if (!gradeResp.ok) {{
          document.getElementById('grading-status').textContent = await getErrorMessage(gradeResp);
          document.getElementById('btn-start-grading').disabled = false;
          document.getElementById('btn-cancel-grading').style.display = 'none';
          setStep(1);
          return;
        }}

        document.getElementById('grading-status').textContent = 'Grading in progress...';
        pollJobStatus();
      }} catch (e) {{
        document.getElementById('grading-status').textContent =
          'Could not connect to the server. Please try again.';
        document.getElementById('btn-start-grading').disabled = false;
        document.getElementById('btn-cancel-grading').style.display = 'none';
        setStep(1);
      }}
    }}

    function pollJobStatus() {{
      // Guard against overlapping pollers if startGrading is triggered twice
      // before a previous interval clears (e.g. user double-clicks).
      if (pollTimer) {{
        clearInterval(pollTimer);
        pollTimer = null;
      }}
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
            setStep(3);
            document.getElementById('btn-cancel-grading').style.display = 'none';
			document.getElementById('btn-start-grading').disabled = false;
            await showResults();
          }} else if (job.status === 'FAILED') {{
            clearInterval(pollTimer);
            document.getElementById('grading-status').textContent =
              'Grading failed: ' + (job.error_message || 'Unknown error');
              document.getElementById('btn-cancel-grading').style.display = 'none';
			  document.getElementById('btn-start-grading').disabled = false;
          }} else if (job.status === 'CANCELLED') {{
				clearInterval(pollTimer);

				document.getElementById('grading-status').textContent =
					'Grading cancelled.';

				document.getElementById('btn-cancel-grading').style.display = 'none';
				document.getElementById('btn-start-grading').disabled = false;

				setStep(1);
		  }}

        }} catch (e) {{
          // Keep polling on transient errors
        }}
      }}, 2000);
    }}

    // Fetch all submissions for the current job and render them grouped by
    // student. Computes summary stats (student count, question count, average
    // percentage, max points) and populates the results table with one
    // student-header row followed by one row per question.
    async function showResults() {{
      document.getElementById('btn-passback').disabled = false;
      document.getElementById('passback-status').classList.add('hidden');

      const resp = await fetch(BASE_URL + '/jobs/' + currentJobId + '/submissions', {{
        headers: authHeaders(),
      }});
      if (!resp.ok) return;
      const subs = await resp.json();

      const groups = {{}};
      const order = [];
      subs.forEach(sub => {{
        const uid = sub.canvas_user_id || 'unknown';
        if (!groups[uid]) {{
          groups[uid] = [];
          order.push(uid);
        }}
        groups[uid].push(sub);
      }});

      const totalStudents = order.length;
      const questionPoints = {{}};
      subs.forEach(s => {{ questionPoints[s.question_id] = s.points_possible; }});
      const uniqueQuestions = Object.keys(questionPoints).length;
      const maxPoints = Object.values(questionPoints).reduce((a, b) => a + b, 0);

      let percentSum = 0;
      let countedStudents = 0;
      order.forEach(uid => {{
        let s = 0, m = 0;
        groups[uid].forEach(sub => {{
          if (sub.ai_grade != null) s += sub.ai_grade;
          m += sub.points_possible;
        }});
        if (m > 0) {{
          percentSum += (s / m * 100);
          countedStudents++;
        }}
      }});
      const avgPercent = countedStudents > 0
        ? (percentSum / countedStudents).toFixed(1) + '%' : '\u2014';

      document.getElementById('stat-students').textContent = totalStudents;
      document.getElementById('stat-questions').textContent = uniqueQuestions;
      document.getElementById('stat-avg').textContent = avgPercent;
      document.getElementById('stat-max').textContent = maxPoints > 0
        ? maxPoints.toFixed(1) : '\u2014';

      const tbody = document.getElementById('results-tbody');
      tbody.innerHTML = '';

      order.forEach(uid => {{
        const studentSubs = groups[uid];
        let studentScore = 0;
        let studentMax = 0;
        studentSubs.forEach(s => {{
          if (s.ai_grade != null) studentScore += s.ai_grade;
          studentMax += s.points_possible;
        }});

        const headerRow = document.createElement('tr');
        headerRow.classList.add('student-header');
        const headerTd = document.createElement('td');
        headerTd.colSpan = 6;
        headerTd.textContent = 'Student ' + uid + '  \u2014  ' +
          studentScore.toFixed(1) + ' / ' + studentMax.toFixed(1) + ' points';
        headerRow.appendChild(headerTd);
        tbody.appendChild(headerRow);

        studentSubs.forEach(sub => {{
          const tr = document.createElement('tr');
          [
            stripHtml(sub.question_name) || ('Q' + sub.question_id),
            stripHtml(sub.question_text) || '\u2014',
            stripHtml(sub.student_answer),
            sub.ai_grade != null ? sub.ai_grade : '\u2014',
            sub.points_possible,
            stripHtml(sub.ai_feedback) || '\u2014',
          ].forEach(val => {{
            const td = document.createElement('td');
            td.textContent = val;
            tr.appendChild(td);
          }});
          tbody.appendChild(tr);
        }});
      }});

      const graded = subs.filter(s => s.ai_grade != null).length;
      document.getElementById('results-summary').textContent =
        graded + ' of ' + subs.length + ' answers graded.';
      document.getElementById('section-results').classList.remove('hidden');
    }}

    // Load all past grading jobs for this course and render them in the
    // history table, sorted newest-first. Only COMPLETED jobs get a
    // "View Results" button.
    async function loadPastJobs() {{
      const tbody = document.getElementById('history-tbody');
      const emptyMsg = document.getElementById('history-empty');
      const errorEl = document.getElementById('history-error');
      tbody.innerHTML = '';
      emptyMsg.classList.add('hidden');
      errorEl.classList.add('hidden');

      try {{
        const resp = await fetch(BASE_URL + '/jobs', {{ headers: authHeaders() }});
        if (!resp.ok) {{
          showError('history-error', await getErrorMessage(resp));
          return;
        }}
        const jobs = await resp.json();
        if (jobs.length === 0) {{
          emptyMsg.classList.remove('hidden');
          return;
        }}
        // Sort newest-first so the most recently graded jobs appear at the top.
        jobs.sort((a, b) => {{
          const da = new Date(a.created_at).getTime();
          const db = new Date(b.created_at).getTime();
          return db - da;
        }});
        jobs.forEach(job => {{
          const tr = document.createElement('tr');

          const tdName = document.createElement('td');
          tdName.textContent = job.job_name;
          tr.appendChild(tdName);

          const tdDate = document.createElement('td');
          tdDate.textContent = new Date(job.created_at).toLocaleDateString();
          tr.appendChild(tdDate);

          const tdSubs = document.createElement('td');
          tdSubs.textContent = job.total_submissions;
          tr.appendChild(tdSubs);

          const tdStatus = document.createElement('td');
          const badge = document.createElement('span');
          badge.classList.add('badge');
          const statusClass = {{
            'COMPLETED': 'badge-done',
            'FAILED': 'badge-failed',
            'PROCESSING': 'badge-processing',
            'PENDING': 'badge-pending',
            'CANCELED': 'badge-cancelled',
          }}[job.status] || 'badge-pending';
          badge.classList.add(statusClass);
          badge.textContent = job.status;
          tdStatus.appendChild(badge);
          tr.appendChild(tdStatus);

          
          const tdAction = document.createElement('td');
          if (job.status === 'COMPLETED') {{
            const btn = document.createElement('button');
            btn.textContent = 'View Results';
            btn.classList.add('btn-small');
            btn.addEventListener('click', () => viewJobResults(job.job_id, job.job_name));
            tdAction.appendChild(btn);
          }}
          tr.appendChild(tdAction);

          tbody.appendChild(tr);
        }});
      }} catch (e) {{
        showError('history-error', 'Could not load past jobs. Please try again.');
      }}
    }}

    // Open a past job's results in the Grade tab. Hides the quiz selector
    // and grading-progress sections, surfaces the "Back to Past Jobs" link,
    // and reuses showResults() to render the table.
    async function viewJobResults(jobId, jobName) {{
      currentJobId = jobId;
      cameFromHistory = true;

      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      document.getElementById('tab-btn-grade').classList.add('active');
      document.getElementById('tab-grade').classList.add('active');

      setStep(3);
      document.getElementById('section-quiz').classList.add('hidden');
      document.getElementById('section-grading').classList.add('hidden');
      document.getElementById('results-title').textContent = jobName;
      document.getElementById('btn-back-history').classList.remove('hidden');
      await showResults();
    }}

    function backToHistory() {{
      // Reset the Grade tab so a future visit starts fresh, then switch back
      // to the Past Jobs list view.
      resetGradeTab();
      switchTab('history');
    }}

    // Send the current job's AI grades back to Canvas. The server picks the
    // right passback path (REST per-question PUT for quizzes, AGS score
    // submission otherwise) based on whether the job has a quiz_id.
    async function pushGrades() {{
      document.getElementById('btn-passback').disabled = true;
      document.getElementById('passback-status').classList.remove('hidden');
      document.getElementById('passback-status').textContent = 'Pushing grades to Canvas...';

      try {{
        const resp = await fetch(BASE_URL + '/lti/passback/' + currentJobId, {{
          method: 'POST',
          headers: authHeaders(),
          body: JSON.stringify({{ launch_id: LAUNCH_ID }}),
        }});
        if (!resp.ok) {{
          document.getElementById('passback-status').textContent = await getErrorMessage(resp);
          document.getElementById('btn-passback').disabled = false;
          return;
        }}
        const result = await resp.json();
        document.getElementById('passback-status').textContent =
          'Done! ' + result.submitted + ' grades submitted to Canvas.' +
          (result.errors.length ? ' Errors: ' + result.errors.join(', ') : '');
      }} catch (e) {{
        document.getElementById('passback-status').textContent =
          'Could not connect to the server. Please try again.';
        document.getElementById('btn-passback').disabled = false;
      }}
    }}
    
  </script>
</body>
</html>"""
