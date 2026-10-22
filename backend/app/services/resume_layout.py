"""Owned layout v1. Imported TeX/style bytes are provenance, never executable input."""
import re
import unicodedata
from urllib.parse import urlsplit

from app.services.intake_preferences import digest

VERSION = "resume-layout-v1"
PREAMBLE = r"""\documentclass[11pt,letterpaper]{article}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{lmodern,microtype,enumitem,titlesec}
\usepackage[letterpaper,left=0.6in,right=0.6in,top=0.42in,bottom=0.42in]{geometry}
\usepackage[hidelinks]{hyperref}
\input{glyphtounicode}
\pdfgentounicode=1
\pagestyle{empty}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}
\raggedright
\urlstyle{same}
\titleformat{\section}{\normalsize\bfseries}{}{0em}{}[\titlerule]
\titlespacing*{\section}{0pt}{8pt}{5pt}
\setlist[itemize]{leftmargin=12pt,label=\textbullet,itemsep=3pt,topsep=3pt,parsep=0pt,partopsep=0pt}
\newcommand{\job}[4]{\textbf{#1}\hfill #2\\\textit{#3}\hfill #4\par}
\newcommand{\project}[2]{\textbf{#1}\\{\small #2}\par}
"""
TEMPLATE_HASH = digest(PREAMBLE)


def escape(value):
    replacements = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "$": r"\$",
                    "&": r"\&", "%": r"\%", "#": r"\#", "_": r"\_", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    value = unicodedata.normalize("NFC", str(value))
    if any(unicodedata.category(c) in {"Cc", "Cf"} and c not in "\n\r\t" for c in value):
        raise ValueError("Resume text contains unsupported control characters.")
    return "".join(replacements.get(c, " " if c in "\n\r\t" else c) for c in value)


def safe_link(value, email=False):
    # Only literal ASCII URI characters; TeX metacharacters are percent encoded.
    from urllib.parse import quote
    if not value or not value.isascii() or any(c.isspace() for c in value):
        return None
    if not email and ":" in value and not value.startswith(("https://", "http://")):
        return None
    target = "mailto:" + value if email else value if "://" in value else "https://" + value
    parsed = urlsplit(target)
    if parsed.scheme not in ({"mailto"} if email else {"https", "http"}) or (not email and (not parsed.hostname or parsed.username or parsed.password)):
        return None
    target = re.sub(r"%(?![a-fA-F0-9]{2})", "%25", target)
    return quote(target, safe=":/?#[]@!$&'()*+,;=%")


def presentation_metadata(content, snapshot, bank):
    """Add project presentation from the frozen approved bank without rewriting old drafts.

    Older generation projections omitted these fields. Tech lines only include technologies
    explicitly supported by the selected claims, never planned or excluded work.
    """
    records = {r["id"]: r for r in bank["records"]}
    selected = {cid for b in content["draft"]["bullets"] for cid in b["evidence_ids"]}
    metadata = {}
    for r in content["records"]:
        if r["kind"] != "project": continue
        approved = records[r["id"]]
        supported = {name.casefold() for c in snapshot["projection"]["claims"] if c["id"] in selected and c["record_id"] == r["id"] for name in c["technologies"]}
        metadata[r["id"]] = {"subtitle": approved.get("subtitle"), "public_url": approved.get("public_url"),
            "technologies": [name for name in approved.get("technologies", []) if name.casefold() in supported]}
    return metadata


def document(content, snapshot, metadata=None):
    """Allowlisted public presentation; IDs, provenance, gaps and notes never escape."""
    identity = content["identity"]
    def cell(value, link=None):
        return {"text": str(value), "link": link}
    header = [[cell(identity["name"])]]
    relocation = (identity.get("relocation_preference") or {}).get("display")
    header.append([cell(x) for x in (identity.get("location"), relocation) if x])
    header.append([cell(identity[k], safe_link(identity[k], True) if k == "email" else None) for k in ("phone", "email") if identity.get(k)])
    header.append([cell(identity[k], safe_link(identity[k])) for k in ("website", "github", "linkedin") if identity.get(k)])
    education = []
    for e in content["education"]:
        detail = [e["degree"]]
        if e.get("gpa"): detail.append("GPA: " + e["gpa"])
        if e.get("minors"): detail.append("Minors: " + ", ".join(e["minors"]))
        education.append([e["institution"], e.get("graduation_display") or e.get("graduation") or "", " | ".join(detail)])
    remaining = {s["name"].casefold(): s["name"] for s in content["draft"]["skills"]}
    categories = {"Languages": [], "Frameworks & Libraries": [], "Data & Tools": []}
    for group in snapshot["projection"]["skill_groups"]:
        names = [remaining.pop(v.casefold()) for v in group["values"] if v.casefold() in remaining]
        # Source labels can include editorial instructions. Only public, owned labels export.
        label = group["label"].casefold()
        category = "Languages" if label.startswith("languages") else "Frameworks & Libraries" if label.startswith("frameworks") else "Data & Tools"
        categories[category].extend(names)
    categories["Data & Tools"].extend(remaining.values())
    skills = [[label, ", ".join(names)] for label, names in categories.items() if names]
    entries = []
    for r in content["records"]:
        r = {**r, **(metadata or {}).get(r["id"], {})}
        bullets = [b["text"] for b in content["draft"]["bullets"] if b["record_id"] == r["id"]]
        if r["kind"] == "employment":
            entries.append({"kind": "employment", "heading": r.get("employer") or "", "dates": r.get("dates_display") or " - ".join(r[k] for k in ("start", "end") if r.get(k)),
                            "title": r.get("title_display") or "", "location": r.get("location") or "", "bullets": bullets})
        else:
            entries.append({"kind": "project", "heading": " -- ".join(r[k] for k in ("name", "subtitle") if r.get(k)),
                            "technologies": ", ".join(r.get("technologies", [])), "url": r.get("public_url") or "", "bullets": bullets})
    return {"header": header, "education": education, "skills": skills, "entries": entries}


def exports(doc):
    name = escape(doc["header"][0][0]["text"])
    tex = [PREAMBLE, r"\hypersetup{pdftitle={" + name + r" -- Resume},pdfauthor={" + name + "}}", r"\begin{document}", r"\begin{center}"]
    lines = []
    def link(c):
        label = escape(c["text"])
        return r"\href{" + escape(c["link"]) + "}{" + label + "}" if c["link"] else label
    for i, cells in enumerate(doc["header"]):
        if not cells: continue
        text = " | ".join(c["text"] for c in cells)
        lines.append(text)
        value = r" $|$ ".join(link(c) for c in cells)
        tex.append((r"{\fontsize{23}{26}\selectfont\bfseries " + value + "}" if i == 0 else value) + (r"\\[3pt]" if i == 0 else r"\\[2pt]"))
    tex.extend([r"\end{center}", r"\vspace{-5pt}", r"\section{Education}"])
    lines.append("Education")
    for school, date, detail in doc["education"]:
        tex.extend([r"\textbf{" + escape(school) + r"}\hfill " + escape(date) + r"\\", escape(detail) + r"\par"])
        lines.extend([" | ".join(x for x in (school, date) if x), detail])
    tex.append(r"\section{Technical Skills}"); lines.append("Technical Skills")
    for label, names in doc["skills"]:
        tex.append(r"\textbf{" + escape(label) + ":} " + escape(names) + r"\par")
        lines.append(label + ": " + names)
    for kind, section in (("employment", "Experience"), ("project", "Projects")):
        entries = [e for e in doc["entries"] if e["kind"] == kind]
        if not entries: continue
        tex.append(r"\section{" + section + "}"); lines.append(section)
        for e in entries:
            if kind == "employment":
                tex.append(r"\job" + "".join("{" + escape(e[k]) + "}" for k in ("heading", "dates", "title", "location")))
                lines.extend([" | ".join(x for x in (e["heading"], e["dates"]) if x), " | ".join(x for x in (e["title"], e["location"]) if x)])
            else:
                tex.append(r"\project{" + escape(e["heading"]) + "}{" + escape(e["technologies"]) + "}")
                lines.extend([e["heading"], e["technologies"]])
                if e["url"]:
                    tex.append(link({"text": e["url"], "link": safe_link(e["url"])}) + r"\par")
                    lines.append(e["url"])
            tex.append(r"\begin{itemize}")
            for bullet in e["bullets"]:
                tex.append(r"\item " + escape(bullet)); lines.append("- " + bullet)
            tex.append(r"\end{itemize}")
    tex.append(r"\end{document}")
    return "\n".join(tex) + "\n", "\n".join(lines) + "\n"
