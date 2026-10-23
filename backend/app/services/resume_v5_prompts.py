"""Coverage and content policy v5; historical v4 prompt bytes remain frozen."""
from app.services.resume_v4_prompts import system_for as previous

RULES = """
V5 REQUIREMENT ACCURACY AND CONTENT BUDGET:
Split independently assessable capabilities into separate entries. In particular, 'AI agents, backend services, APIs and web UIs' is FOUR requirements, not one. Python and SQL proficiency are distinct. A requirement may retain the same grounded posting sentence as another while its description names only its own qualification. Retain duration, ownership and production qualifiers for the capability they modify. Do not invent additional production, autonomous-agent or named-framework demands where the posting asks for basic understanding or general tool workflows.
Full support must establish the whole qualification, not one element of a compound sentence. Distinguish evaluation/benchmark pipelines from checking output schemas or testing extraction repeatability. Public demos, portfolios and locally used tools do not establish production ownership. Employment date ranges alone do not establish years of professional full-stack work. Classify adjacent evidence as partial, and absent evidence as unsupported. Use the strongest few direct claim links; do not scatter links across merely related projects.
The application applies conservative source checks to these known overstatement categories. Its checks can downgrade full to partial; explanations and all approved evidence remain visible for review. Do not fight these checks in critique or revision without genuinely stronger approved evidence.
Choose the strongest 6-10 complete accomplishments, accounting for record headings, project technology/URL lines, education and skills. Rank direct relevant evidence first; keep metrics when useful and avoid repeating the same project overview. The application enforces contract.content_budget across independent selections AND overlap choices, using complete source text and estimated space. It may omit lower-value selections; omitted evidence remains in bank coverage. Do not shorten a claim by deleting qualifiers or change the template/font to make it fit. Actual page fit is verified by PDF rendering before final approval.
"""


def system_for(stage):
    return previous(stage) + '\n' + RULES
