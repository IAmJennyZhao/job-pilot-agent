"""Job-side facts only: evidence is never candidate experience."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Fact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str | float | None = None
    quote: str = Field(default="", max_length=2000)
    origin: Literal["posting", "user", "unknown"] = "unknown"


class IntakeFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role_family: Fact = Field(default_factory=Fact)
    employment_type: Fact = Field(default_factory=Fact)
    salary_component: Fact = Field(default_factory=Fact)
    salary_band: Fact = Field(default_factory=Fact)
    nyc_compatible: Fact = Field(default_factory=Fact)
    employer_source: Fact = Field(default_factory=Fact)
    required_years: Fact = Field(default_factory=Fact)
    preferred_years: Fact = Field(default_factory=Fact)
    company_stage: Fact = Field(default_factory=Fact)
    employee_count: Fact = Field(default_factory=Fact)
    hours_week: Fact = Field(default_factory=Fact)


CHOICES = {
    "role_family": {"software_engineer", "ai_engineer", "applied_ai_developer", "full_stack_engineer", "backend_engineer", "other"},
    "employment_type": {"full_time", "part_time", "contract", "internship", "other"},
    "salary_component": {"base", "total"},
    "salary_band": {"applicable", "unclear"},
    "nyc_compatible": {"yes", "no"},
    "employer_source": {"direct", "agency"},
    "company_stage": {"startup", "established"},
}


def verified_facts(facts: IntakeFacts, text: str, *, extraction=False) -> IntakeFacts:
    result = IntakeFacts()
    for name in IntakeFacts.model_fields:
        fact = getattr(facts, name)
        valid = fact.origin == "user" and not extraction
        valid |= fact.origin == "posting" and bool(fact.quote.strip()) and fact.quote in text
        if name in CHOICES:
            valid &= fact.value in CHOICES[name]
        else:
            valid &= isinstance(fact.value, (float, int)) and 0 <= fact.value <= (10_000_000 if name == "employee_count" else 168 if name == "hours_week" else 80)
        if valid:
            setattr(result, name, fact)
    return result
