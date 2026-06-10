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
Keep every user-facing field terse: summary is one short sentence; lists are 3-5 short phrases.
Responsibilities must be actions/outcomes, not tools. Start them with verbs when possible.
Do not end summaries or list items with ellipses; write the complete phrase or sentence.
Required skills must be technical only: languages, frameworks, tools, platforms, technical domains.
Do not put collaboration, communication, stakeholder management, ownership, or teamwork in required skills.
Avoid repeating the same concept across summary, responsibilities, skills, and benefits.
Extract pay and benefits only when the posting states them. Use pay_raw when the pay is not parseable as a clean range.
Do not include links except links clearly present in the posting.
""".strip()


def advanced_posting_analysis_prompt(company: str, role_title: str, job_source: str) -> str:
    return f"""
Analyze this job posting for deeper application prep.

Company: {company}
Role: {role_title}

Job posting:
{job_source}

Return a terse snapshot, not a report.
Hard rules:
- summary: one short phrase or sentence.
- role_focus: 2-3 short phrases about the role's real emphasis.
- responsibilities: 3-5 actions/outcomes only; no tool lists.
- responsibility_highlights: 1-3 word exact phrases copied from responsibilities, about one phrase per two responsibility bullets, max one per bullet.
- must_have_skills and nice_to_have_skills: technical tools, languages, frameworks, platforms, or technical domains only.
- Put collaboration, communication, stakeholder work, and ownership signals in role_focus only if they are central.
- Do not repeat the same concept across role_focus, responsibilities, must-have skills, and nice-to-have skills.
- Omit generic filler.
- Do not use markdown or trailing ellipses in any text field.
Keep it grounded in the posting. Do not invent company facts.
""".strip()


def company_research_prompt(
    company: str,
    role_title: str,
    research_context: str,
    retrieval_warnings: list[str],
) -> str:
    return f"""
Summarize public company research for this employer.

Company: {company}
Role context: {role_title}

Retrieved public source snippets:
{research_context}

Retrieval warnings:
{retrieval_warnings}

Use only the retrieved snippets and the provided warnings. Include source links for snippets used.
Keep summary to one short sentence. Put the useful takeaways in themes as 3-5 compact bullets.
Themes should be scan-friendly employee/company signals, not paragraphs.
highlight_phrases should contain 1-3 word exact phrases copied from summary or themes, about one phrase per two company signal bullets, max one per bullet.
Do not use markdown or trailing ellipses in any text field.
If public employee review data is thin, unavailable, or retrieval failed, say that clearly in the coverage note and use "unknown" sentiment when needed.
Do not invent reviews, ratings, or employee claims.
""".strip()


def resume_fit_prompt(
    company: str,
    role_title: str,
    job_source: str,
    profile_summary: str | None,
    resume_text: str,
    skills: list[str],
) -> str:
    return f"""
Compare this candidate profile against the job and company.

Company: {company}
Role: {role_title}

Job posting:
{job_source}

Profile summary:
{profile_summary or ""}

Skills:
{", ".join(skills)}

Resume text:
{resume_text}

Return practical fit signals, resume keywords, and honest risks/gaps. Keep every item short.
fit_highlights should contain 1-3 word exact phrases copied from top_company_fit, about one phrase per two fit bullets, max one per bullet.
gap_highlights should contain 1-3 word exact phrases copied from risks_gaps, about one phrase per two gap bullets, max one per bullet.
Resume keywords should be technical keywords or role-specific keywords, not soft-skill phrases.
Do not use markdown or trailing ellipses in any text field.
Do not repeat items already covered by obvious responsibilities unless they matter for resume targeting.
Do not invent experience.
""".strip()


def advanced_interview_prep_prompt(
    company: str,
    role_title: str,
    job_source: str,
    resume_text: str,
) -> str:
    return f"""
Generate likely interview questions and topics for this application.

Company: {company}
Role: {role_title}

Job posting:
{job_source}

Candidate resume/profile:
{resume_text}

Cover technical, role-specific, company/context, resume, and behavioral signals where relevant.
Keep questions direct and why_it_matters to one short phrase.
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


def resume_parse_prompt(resume_text: str) -> str:
    return f"""
Parse this resume into editable job-application profile sections.

Resume text:
{resume_text}

Return only information supported by the resume.
Rules:
- Preserve factual claims and do not invent experience, employers, dates, schools, or skills.
- experience bullets should be concise achievement/responsibility bullets.
- skills should be a flat deduplicated list.
- skill_groups should group skills into practical categories such as Languages, Frameworks, Tools, AI/ML, Cloud, Data, or Domain.
- target_keywords should be concise role-relevant keywords found or strongly implied by the resume text.
- If a section is not present, return an empty list or null.
""".strip()


def asset_ranking_prompt(
    company: str,
    role_title: str,
    job_description: str,
    resume_options: list[dict],
    cover_letter_templates: list[dict],
) -> str:
    return f"""
Rank existing application assets for this job. Do not generate new resume or cover letter content.

Company: {company}
Role: {role_title}

Job description:
{job_description}

Resume options:
{resume_options}

Cover letter templates:
{cover_letter_templates}

Rules:
- Only rank assets that are provided.
- Base recommendations on target roles, target keywords, skills, summaries, and template text.
- Do not invent candidate experience.
- Keep reasons short and practical.
""".strip()


def interview_questions_prompt(
    company: str,
    role_title: str,
    job_description: str,
    resume_text: str,
    question_type: str,
    count: int,
    stage: str = "mixed",
    target_category: str | None = None,
    target_role: str | None = None,
    prior_questions: list[str] | None = None,
) -> str:
    return f"""
Generate {count} likely interview questions for this job.

Company: {company}
Role: {role_title}
Target category: {target_category or ""}
Target role/focus: {target_role or ""}
Interview stage: {stage}
Question type: {question_type}

Job description:
{job_description}

Candidate resume/profile:
{resume_text}

Already-used questions to avoid unless they are useful weak-point drills:
{prior_questions or []}

Generate direct, realistic questions for the requested stage and question type. Use the resume/profile for honest personalization, but do not invent experience.
""".strip()


def interview_feedback_prompt(
    company: str,
    role_title: str,
    job_description: str,
    resume_text: str,
    question: str,
    answer: str,
    stage: str = "mixed",
    target_category: str | None = None,
    target_role: str | None = None,
) -> str:
    return f"""
Evaluate this interview answer constructively.

Company: {company}
Role: {role_title}
Target category: {target_category or ""}
Target role/focus: {target_role or ""}
Interview stage: {stage}

Job description:
{job_description}

Candidate resume/profile:
{resume_text}

Question:
{question}

Candidate answer:
{answer}

Return concise, actionable coaching. The stronger answer must stay grounded in the candidate profile and must not invent experience.
Use weak_point_tags only from: technical_depth, answer_structure, specific_evidence, role_alignment, concision, communication_clarity, missing_skill, company_context, resume_positioning.
Put only concrete missing technical/domain skills in missing_skill_names; do not include answer structure, clarity, confidence, or storytelling issues there.
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

