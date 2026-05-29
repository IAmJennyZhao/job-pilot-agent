SYSTEM_PROMPT = (
    "You are CareerPilot, a precise AI career coach for software and AI job seekers. "
    "Return only data matching the requested schema. Never fabricate resume experience. "
    "If a skill is missing from the profile, suggest learning, project work, or honest positioning."
)


def job_analysis_prompt(company: str, role_title: str, job_description: str) -> str:
    return f"""
Analyze this job description for a software or AI job seeker.

Company: {company}
Role: {role_title}

Job description:
{job_description}

Extract only information supported by the job description.
""".strip()


def job_intake_prompt(source_url: str | None, source_content: str) -> str:
    return f"""
Extract tracker-ready information from this job posting.

Source URL:
{source_url or ""}

Job posting content:
{source_content}

Use one controlled category only:
- AI/ML Engineer
- Backend Engineer
- Frontend Engineer
- Full Stack Engineer
- Data Engineer
- DevOps/Infrastructure
- Product/Platform Engineer
- Other

Extract only information supported by the posting. If a field is unclear, use "Unknown" or add a warning.
Keep responsibilities and required skills concise enough for a job tracker.
Include useful links only if the posting clearly contains them.
""".strip()


def resume_suggestion_prompt(
    company: str,
    role_title: str,
    job_description: str,
    resume_text: str,
    profile_summary: str | None,
    skills: list[str],
) -> str:
    return f"""
Compare the resume/profile against this job. Suggest honest improvements only.

Company: {company}
Role: {role_title}
Job description:
{job_description}

Profile summary:
{profile_summary or ""}

Skills:
{", ".join(skills)}

Resume text:
{resume_text}

Do not invent experience. If a skill is missing, recommend project or study work.
""".strip()


def interview_questions_prompt(
    company: str,
    role_title: str,
    job_description: str,
    resume_text: str,
    question_type: str,
    count: int,
) -> str:
    return f"""
Generate {count} likely interview questions for this job.

Company: {company}
Role: {role_title}
Question type: {question_type}

Job description:
{job_description}

Candidate resume/profile:
{resume_text}
""".strip()


def interview_feedback_prompt(
    company: str,
    role_title: str,
    job_description: str,
    question: str,
    answer: str,
) -> str:
    return f"""
Evaluate this interview answer constructively.

Company: {company}
Role: {role_title}

Job description:
{job_description}

Question:
{question}

Candidate answer:
{answer}
""".strip()


def study_plan_prompt(
    timeframe: str,
    target_roles: list[str],
    gaps: list[dict],
    resume_text: str,
) -> str:
    return f"""
Create a practical study plan for a job seeker.

Timeframe: {timeframe}
Target roles: {", ".join(target_roles)}

Current skill gaps:
{gaps}

Resume/profile:
{resume_text}
""".strip()

