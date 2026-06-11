from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import re

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, prompts, schemas
from app.services import ai_service, profile_asset_service, profile_service, skill_gap_service


MAX_INSIGHT_MESSAGES = 50
WEAK_POINT_EXAMPLE_LIMIT = 3
KNOWLEDGE_TREND_TAGS = {"technical_depth", "missing_skill", "company_context"}
INTERVIEW_SKILL_TREND_TAGS = {
    "answer_structure",
    "specific_evidence",
    "role_alignment",
    "concision",
    "communication_clarity",
    "resume_positioning",
}
WHITESPACE_RE = re.compile(r"\s+")


def _normalize_question(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text.strip()).casefold()


def _job_source_text(job: models.Job) -> str:
    return job.source_content or job.summary or "\n".join(job.responsibilities)


def _active_or_requested_profile(
    db: Session,
    resume_profile_id: str | None,
) -> models.ResumeProfile | None:
    if resume_profile_id:
        profile = db.get(models.ResumeProfile, resume_profile_id)
        if not profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume profile not found")
        return profile
    return profile_service.get_active_profile(db)


def _resume_text_for_target(
    db: Session,
    job: models.Job | None,
    profile: models.ResumeProfile | None,
) -> str:
    if job and job.selected_resume_option_id:
        selected = db.get(models.ResumeOption, job.selected_resume_option_id)
        if selected and selected.parsed_text.strip():
            return selected.parsed_text
    return profile.resume_text if profile else ""


def _target_role(payload: schemas.InterviewPracticeSetCreate, job: models.Job | None) -> str | None:
    return (payload.target_role or "").strip() or (job.role_title if job else None)


def _target_category(
    payload: schemas.InterviewPracticeSetCreate,
    job: models.Job | None,
) -> models.JobCategory | None:
    return payload.target_category or (job.category if job else None)


def _question_matches_target(
    question: models.InterviewQuestion,
    *,
    job: models.Job | None,
    target_category: models.JobCategory | None,
    target_role: str | None,
) -> bool:
    if job and question.job_id == job.id:
        return True
    if question.job_id is not None:
        return False
    if target_category and question.target_category == target_category:
        return True
    if target_role and question.target_role:
        return question.target_role.strip().casefold() == target_role.strip().casefold()
    return False


def _compatible_stage(question: models.InterviewQuestion, stage: models.InterviewStage) -> bool:
    return stage == models.InterviewStage.mixed or question.stage in {stage, models.InterviewStage.mixed}


def _compatible_type(question: models.InterviewQuestion, question_type: str) -> bool:
    return question_type == "mixed" or question.question_type in {question_type, "mixed"}


def _matching_questions(
    db: Session,
    *,
    job: models.Job | None,
    target_category: models.JobCategory | None,
    target_role: str | None,
    stage: models.InterviewStage,
    question_type: str,
) -> list[models.InterviewQuestion]:
    candidates = list(
        db.scalars(
            select(models.InterviewQuestion).order_by(
                models.InterviewQuestion.asked_count.asc(),
                models.InterviewQuestion.created_at.asc(),
            )
        ).all()
    )
    return [
        question
        for question in candidates
        if _question_matches_target(
            question,
            job=job,
            target_category=target_category,
            target_role=target_role,
        )
        and _compatible_stage(question, stage)
        and _compatible_type(question, question_type)
    ]


def _find_existing_question(
    db: Session,
    *,
    content: str,
    job_id: str | None,
    target_category: models.JobCategory | None,
    target_role: str | None,
) -> models.InterviewQuestion | None:
    normalized = _normalize_question(content)
    for question in db.scalars(select(models.InterviewQuestion)).all():
        if _normalize_question(question.content) != normalized:
            continue
        if job_id and question.job_id == job_id:
            return question
        if not job_id and question.job_id is None:
            same_category = question.target_category == target_category
            same_role = (question.target_role or "").strip().casefold() == (target_role or "").strip().casefold()
            if same_category or same_role:
                return question
    return None


def _save_question(
    db: Session,
    *,
    content: str,
    source: models.InterviewQuestionSource,
    job: models.Job | None,
    profile: models.ResumeProfile | None,
    target_category: models.JobCategory | None,
    target_role: str | None,
    stage: models.InterviewStage,
    question_type: str,
    why_it_matters: str | None = None,
    strong_answer_should_include: list[str] | None = None,
    prompt_metadata: dict | None = None,
    weak_point_tags: list[str] | None = None,
) -> tuple[models.InterviewQuestion, bool]:
    existing = _find_existing_question(
        db,
        content=content,
        job_id=job.id if job else None,
        target_category=target_category,
        target_role=target_role,
    )
    if existing:
        if why_it_matters and not existing.why_it_matters:
            existing.why_it_matters = why_it_matters
        if strong_answer_should_include and not existing.strong_answer_should_include:
            existing.strong_answer_should_include = strong_answer_should_include
        if weak_point_tags:
            existing.weak_point_tags = sorted({*(existing.weak_point_tags or []), *weak_point_tags})
        db.add(existing)
        return existing, False

    question = models.InterviewQuestion(
        job_id=job.id if job else None,
        resume_profile_id=profile.id if profile else None,
        target_category=target_category,
        target_role=target_role,
        stage=stage,
        question_type=question_type,
        content=content.strip(),
        why_it_matters=why_it_matters,
        strong_answer_should_include=strong_answer_should_include or [],
        source=source,
        prompt_metadata=prompt_metadata or {},
        weak_point_tags=weak_point_tags or [],
    )
    db.add(question)
    db.flush()
    return question, True


def _latest_advanced_analysis(db: Session, job: models.Job) -> models.AdvancedJobAnalysis | None:
    return db.scalars(
        select(models.AdvancedJobAnalysis)
        .where(models.AdvancedJobAnalysis.job_id == job.id)
        .order_by(models.AdvancedJobAnalysis.created_at.desc())
        .limit(1)
    ).first()


def _import_advanced_questions(
    db: Session,
    job: models.Job,
    profile: models.ResumeProfile | None,
) -> None:
    analysis = _latest_advanced_analysis(db, job)
    if not analysis:
        return
    for item in analysis.expected_questions or []:
        content = str(item.get("question") or "").strip()
        if not content:
            continue
        _save_question(
            db,
            content=content,
            source=models.InterviewQuestionSource.advanced_analysis,
            job=job,
            profile=profile,
            target_category=job.category,
            target_role=job.role_title,
            stage=models.InterviewStage.mixed,
            question_type=str(item.get("type") or "mixed"),
            why_it_matters=item.get("why_it_matters"),
            strong_answer_should_include=[],
            prompt_metadata={"advanced_analysis_id": analysis.id},
        )


def _select_existing_questions(
    questions: list[models.InterviewQuestion],
    count: int,
) -> list[models.InterviewQuestion]:
    selected: list[models.InterviewQuestion] = []
    selected_ids: set[str] = set()

    def take(items: list[models.InterviewQuestion]) -> None:
        for item in items:
            if len(selected) >= count:
                return
            if item.id in selected_ids:
                continue
            selected.append(item)
            selected_ids.add(item.id)

    take([question for question in questions if question.asked_count == 0])
    take([question for question in questions if question.weak_point_tags])
    take([question for question in questions if question.asked_count > 0])
    return selected


def _generate_questions(
    db: Session,
    *,
    job: models.Job | None,
    profile: models.ResumeProfile | None,
    target_category: models.JobCategory | None,
    target_role: str | None,
    stage: models.InterviewStage,
    question_type: str,
    count: int,
    prior_questions: list[str],
) -> tuple[list[models.InterviewQuestion], int]:
    if count <= 0:
        return [], 0

    company = job.company if job else "General role practice"
    role_title = job.role_title if job else (target_role or (target_category.value if target_category else "Software role"))
    practice_target = target_role or (target_category.value if target_category else "a software role")
    job_source = _job_source_text(job) if job else f"General interview practice for {practice_target}."
    output = ai_service.get_structured_output(
        schemas.InterviewQuestionsOutput,
        prompts.SYSTEM_PROMPT,
        prompts.interview_questions_prompt(
            company,
            role_title,
            job_source,
            _resume_text_for_target(db, job, profile),
            question_type,
            count,
            stage=stage.value,
            target_category=target_category.value if target_category else None,
            target_role=target_role,
            prior_questions=prior_questions,
        ),
    )

    generated: list[models.InterviewQuestion] = []
    created_count = 0
    seen: set[str] = set()
    for item in output.questions:
        key = _normalize_question(item.question)
        if key in seen:
            continue
        seen.add(key)
        question, created = _save_question(
            db,
            content=item.question,
            source=models.InterviewQuestionSource.generated,
            job=job,
            profile=profile,
            target_category=target_category,
            target_role=target_role,
            stage=stage,
            question_type=item.type,
            why_it_matters=item.why_it_matters,
            strong_answer_should_include=item.strong_answer_should_include,
            prompt_metadata={
                "stage": stage.value,
                "question_type": question_type,
                "target_category": target_category.value if target_category else None,
                "target_role": target_role,
            },
        )
        if question.id not in {existing.id for existing in generated}:
            generated.append(question)
        if created:
            created_count += 1
    return generated[:count], created_count


def _session_title(
    *,
    job: models.Job | None,
    target_category: models.JobCategory | None,
    target_role: str | None,
    stage: models.InterviewStage,
) -> str:
    target = job.role_title if job else (target_role or (target_category.value if target_category else "Interview"))
    stage_label = stage.value.replace("_", " ")
    return f"{target} {stage_label} practice"


def create_practice_set(
    db: Session,
    payload: schemas.InterviewPracticeSetCreate,
) -> schemas.InterviewPracticeSetResponse:
    job = db.get(models.Job, payload.job_id) if payload.job_id else None
    if payload.job_id and not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    profile = _active_or_requested_profile(db, payload.resume_profile_id)
    target_category = _target_category(payload, job)
    target_role = _target_role(payload, job)
    if not job and not target_category and not target_role:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Choose a saved job or target role.")

    if job:
        _import_advanced_questions(db, job, profile)

    matching = _matching_questions(
        db,
        job=job,
        target_category=target_category,
        target_role=target_role,
        stage=payload.stage,
        question_type=payload.question_type,
    )
    selected = _select_existing_questions(matching, payload.count)
    remaining = payload.count - len(selected)
    generated, generated_count = _generate_questions(
        db,
        job=job,
        profile=profile,
        target_category=target_category,
        target_role=target_role,
        stage=payload.stage,
        question_type=payload.question_type,
        count=remaining,
        prior_questions=[question.content for question in matching],
    )
    selected_ids = {question.id for question in selected}
    selected.extend(question for question in generated if question.id not in selected_ids)
    selected = selected[: payload.count]

    session = models.InterviewSession(
        job_id=job.id if job else None,
        resume_profile_id=profile.id if profile else None,
        mode=models.InterviewMode.live_practice,
        title=_session_title(
            job=job,
            target_category=target_category,
            target_role=target_role,
            stage=payload.stage,
        ),
        target_category=target_category,
        target_role=target_role,
        stage=payload.stage,
        question_type=payload.question_type,
    )
    db.add(session)
    db.flush()

    now = datetime.now(timezone.utc)
    for question in selected:
        question.asked_count += 1
        question.last_asked_at = now
        db.add(question)
        db.add(
            models.InterviewMessage(
                session_id=session.id,
                question_id=question.id,
                role=models.MessageRole.ai,
                content=question.content,
                question_type=question.question_type,
                feedback={
                    "why_it_matters": question.why_it_matters,
                    "strong_answer_should_include": question.strong_answer_should_include,
                    "source": question.source.value,
                    "weak_point_tags": question.weak_point_tags,
                },
            )
        )

    db.commit()
    for question in selected:
        db.refresh(question)

    return schemas.InterviewPracticeSetResponse(
        session_id=session.id,
        questions=[schemas.InterviewPracticeQuestionRead.model_validate(question) for question in selected],
        reused_count=max(0, len(selected) - generated_count),
        generated_count=generated_count,
        job_id=job.id if job else None,
        target_category=target_category,
        target_role=target_role,
        stage=payload.stage,
        question_type=payload.question_type,
    )


def _practice_target_for_session(
    db: Session,
    session: models.InterviewSession,
) -> tuple[models.Job | None, models.ResumeProfile | None, str, str, str]:
    job = db.get(models.Job, session.job_id) if session.job_id else None
    profile = db.get(models.ResumeProfile, session.resume_profile_id) if session.resume_profile_id else profile_service.get_active_profile(db)
    if job:
        return job, profile, job.company, job.role_title, _job_source_text(job)
    role = session.target_role or (session.target_category.value if session.target_category else "Software role")
    source = f"General interview practice for {role}."
    if session.target_category:
        source += f"\nTarget category: {session.target_category.value}."
    return None, profile, "General role practice", role, source


def evaluate_practice_answer(
    db: Session,
    payload: schemas.InterviewPracticeAnswerCreate,
) -> schemas.InterviewPracticeAnswerFeedback:
    session = db.get(models.InterviewSession, payload.session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    question = db.get(models.InterviewQuestion, payload.question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    job, profile, company, role_title, job_source = _practice_target_for_session(db, session)
    output = ai_service.get_structured_output(
        schemas.InterviewAnswerFeedbackOutput,
        prompts.SYSTEM_PROMPT,
        prompts.interview_feedback_prompt(
            company,
            role_title,
            job_source,
            _resume_text_for_target(db, job, profile),
            question.content,
            payload.answer,
            stage=session.stage.value,
            target_category=session.target_category.value if session.target_category else None,
            target_role=session.target_role,
        ),
    )

    follow_up: models.InterviewQuestion | None = None
    if output.follow_up_question.strip():
        follow_up, _ = _save_question(
            db,
            content=output.follow_up_question,
            source=models.InterviewQuestionSource.follow_up,
            job=job,
            profile=profile,
            target_category=session.target_category or (job.category if job else None),
            target_role=session.target_role or (job.role_title if job else None),
            stage=session.stage,
            question_type=question.question_type,
            why_it_matters="Targets weak points from the previous answer.",
            strong_answer_should_include=output.evidence_to_add or output.what_was_missing,
            prompt_metadata={"source_question_id": question.id, "session_id": session.id},
            weak_point_tags=list(output.weak_point_tags),
        )
        follow_up.asked_count += 1
        follow_up.last_asked_at = datetime.now(timezone.utc)
        db.add(follow_up)

    feedback_payload = output.model_dump()
    feedback_payload["follow_up_question_id"] = follow_up.id if follow_up else None
    messages = [
        models.InterviewMessage(
            session_id=session.id,
            question_id=question.id,
            role=models.MessageRole.user,
            content=payload.answer,
            question_type=question.question_type,
        ),
        models.InterviewMessage(
            session_id=session.id,
            question_id=question.id,
            role=models.MessageRole.ai,
            content=output.suggested_better_answer,
            question_type=question.question_type,
            score=output.score,
            feedback=feedback_payload,
        ),
    ]
    if follow_up:
        messages.append(
            models.InterviewMessage(
                session_id=session.id,
                question_id=follow_up.id,
                role=models.MessageRole.ai,
                content=follow_up.content,
                question_type=follow_up.question_type,
                feedback={
                    "why_it_matters": follow_up.why_it_matters,
                    "strong_answer_should_include": follow_up.strong_answer_should_include,
                    "source": follow_up.source.value,
                    "weak_point_tags": follow_up.weak_point_tags,
                },
            )
        )
    db.add_all(messages)
    db.commit()

    if session.resume_profile_id and output.missing_skill_names:
        skill_gap_service.upsert_skill_gaps(
            db,
            session.resume_profile_id,
            output.missing_skill_names,
            models.SkillGapSource.interview_feedback,
            "Practice interview answer for",
        )

    if follow_up:
        db.refresh(follow_up)
    return schemas.InterviewPracticeAnswerFeedback(
        **output.model_dump(),
        session_id=session.id,
        question_id=question.id,
        follow_up_question_id=follow_up.id if follow_up else None,
        follow_up=schemas.InterviewPracticeQuestionRead.model_validate(follow_up) if follow_up else None,
    )


def _answer_for_score_message(message: models.InterviewMessage) -> str | None:
    if not message.question_id:
        return None

    matching_answers = [
        candidate
        for candidate in message.session.messages
        if candidate.role == models.MessageRole.user and candidate.question_id == message.question_id
    ]
    if not matching_answers:
        return None

    answers_before_score = [candidate for candidate in matching_answers if candidate.created_at <= message.created_at]
    return (answers_before_score or matching_answers)[-1].content


def _score_entry(message: models.InterviewMessage) -> schemas.InterviewRecentScore:
    feedback = message.feedback or {}
    tags = [str(tag) for tag in feedback.get("weak_point_tags", [])]
    return schemas.InterviewRecentScore(
        message_id=message.id,
        session_id=message.session_id,
        question_id=message.question_id,
        question=message.question.content if message.question else message.content,
        answer=_answer_for_score_message(message),
        score=message.score or 0,
        feedback=feedback,
        created_at=message.created_at,
        weak_point_tags=tags,
    )


def _trend_point(score: schemas.InterviewRecentScore) -> schemas.InterviewTrendPoint:
    return schemas.InterviewTrendPoint(created_at=score.created_at, score=score.score)


def interview_insights(db: Session) -> schemas.InterviewInsights:
    messages = list(
        db.scalars(
            select(models.InterviewMessage)
            .where(models.InterviewMessage.score.is_not(None))
            .order_by(models.InterviewMessage.created_at.desc())
            .limit(MAX_INSIGHT_MESSAGES)
        ).all()
    )
    if not messages:
        return schemas.InterviewInsights(average_score=None)

    scores = [message.score for message in messages if message.score is not None]
    tag_counts: Counter[str] = Counter()
    latest_notes: dict[str, str] = {}
    coaching_themes: list[str] = []
    recent_scores: list[schemas.InterviewRecentScore] = []
    examples_by_tag: dict[str, list[schemas.InterviewRecentScore]] = {}

    for message in messages:
        score = _score_entry(message)
        feedback = score.feedback or {}
        tags = score.weak_point_tags
        tag_counts.update(tags)
        note_candidates = [
            *[str(item) for item in feedback.get("what_was_missing", [])],
            *[str(item) for item in feedback.get("coaching_notes", [])],
        ]
        for tag in tags:
            if tag not in latest_notes and note_candidates:
                latest_notes[tag] = note_candidates[0]
        for note in [str(item) for item in feedback.get("coaching_notes", [])]:
            if note and note not in coaching_themes:
                coaching_themes.append(note)
        for tag in tags:
            examples = examples_by_tag.setdefault(tag, [])
            if len(examples) < WEAK_POINT_EXAMPLE_LIMIT:
                examples.append(score)
        recent_scores.append(score)

    chronological_scores = list(reversed(recent_scores))
    trends = schemas.InterviewTrendSeries(
        overall=[_trend_point(score) for score in chronological_scores],
        knowledge=[
            _trend_point(score)
            for score in chronological_scores
            if set(score.weak_point_tags).intersection(KNOWLEDGE_TREND_TAGS)
        ],
        interview_skills=[
            _trend_point(score)
            for score in chronological_scores
            if set(score.weak_point_tags).intersection(INTERVIEW_SKILL_TREND_TAGS)
        ],
    )

    weak_points = [
        schemas.InterviewWeakPointInsight(
            tag=tag,
            count=count,
            latest_note=latest_notes.get(tag),
            examples=examples_by_tag.get(tag, []),
        )
        for tag, count in tag_counts.most_common()
    ]
    return schemas.InterviewInsights(
        average_score=round(sum(scores) / len(scores)) if scores else None,
        recent_scores=recent_scores[:10],
        weak_points=weak_points,
        coaching_themes=coaching_themes[:6],
        trends=trends,
    )


def resume_session(db: Session, session_id: str) -> schemas.InterviewPracticeSetResponse:
    session = db.get(models.InterviewSession, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    asked_question_ids: list[str] = []
    answered_question_ids: set[str] = set()
    for message in session.messages:
        if message.question_id is None:
            continue
        if message.role == models.MessageRole.ai and message.score is None:
            if message.question_id not in asked_question_ids:
                asked_question_ids.append(message.question_id)
        elif message.role == models.MessageRole.user:
            answered_question_ids.add(message.question_id)

    unanswered_ids = [question_id for question_id in asked_question_ids if question_id not in answered_question_ids]

    questions: list[schemas.InterviewPracticeQuestionRead] = []
    for question_id in unanswered_ids:
        question = db.get(models.InterviewQuestion, question_id)
        if question:
            questions.append(schemas.InterviewPracticeQuestionRead.model_validate(question))

    return schemas.InterviewPracticeSetResponse(
        session_id=session.id,
        questions=questions,
        reused_count=len(questions),
        generated_count=0,
        job_id=session.job_id,
        target_category=session.target_category,
        target_role=session.target_role,
        stage=session.stage,
        question_type=session.question_type,
    )
