"""Generate the sample CV and job description PDFs used by the demo and evals.

Synthetic on purpose: no real personal data goes into the repository.
Run:  python scripts/make_fixtures.py
"""

from pathlib import Path

from fpdf import FPDF

OUT = Path(__file__).resolve().parent.parent / "evals" / "data"

CV = """ELENA ROUSSOU
Senior Backend Engineer - Athens, Greece
elena.roussou@example.com | github.com/example

SUMMARY
Backend engineer with 7 years building and operating Python services for
high-traffic consumer products. Comfortable owning a service end to end, from
schema design through to on-call. Most recent work has been on payments and
order processing.

EXPERIENCE

Senior Backend Engineer, Nexora Commerce (2021 - 2024)
Owned the order processing service handling 1.2M orders per month.
Rebuilt the checkout API in Python and FastAPI, replacing a legacy Flask
service; reduced p99 latency from 840ms to 210ms by moving to async I/O and
adding connection pooling.
Designed the PostgreSQL schema for the orders domain, including partitioning by
month once the table passed 400M rows, and wrote the migration playbook the team
still uses.
Introduced RabbitMQ for order events so that fulfilment and invoicing could be
decoupled from checkout; this cut checkout timeouts by 90 percent.
Mentored two junior engineers through their first year, running weekly code
review sessions and pairing on their first production changes.
Raised test coverage on the payments module from 34 percent to 81 percent using
pytest, and made the suite a required check before merge.

Backend Engineer, Delphi Analytics (2018 - 2021)
Built REST APIs in Python and Django for a B2B analytics dashboard used by
around 300 customer accounts.
Containerised the application with Docker and wrote the first CI pipeline in
GitHub Actions, taking deploys from a manual weekly release to daily automated
deploys.
Deployed and maintained services on AWS using EC2, S3 and RDS. Set up CloudWatch
dashboards and alerts for the ingestion pipeline.
Wrote the internal API style guide adopted across three teams.

Junior Developer, Ionian Software (2017 - 2018)
Maintained a PHP monolith and wrote the reporting module that replaced a set of
manual spreadsheets.

EDUCATION
MSc Computer Science, Athens University of Economics and Business, 2017
BSc Informatics, University of Piraeus, 2015

TECHNICAL SKILLS
Languages: Python, SQL, JavaScript, PHP
Frameworks: FastAPI, Django, Flask, pytest
Data: PostgreSQL, Redis, RabbitMQ
Infrastructure: Docker, AWS (EC2, S3, RDS), GitHub Actions, Linux
Practices: REST API design, code review, pair programming, agile delivery
"""

JD = """SENIOR BACKEND ENGINEER (PYTHON)
Meridian Labs - Athens or remote within EU

ABOUT THE ROLE
We are building the platform that powers logistics for mid-sized European
retailers. You will join a team of six engineers and own services that move real
money and real parcels.

REQUIREMENTS
Strong commercial experience with Python, ideally with FastAPI or a comparable
async framework.
Proven experience designing and operating PostgreSQL databases at scale,
including query optimisation and schema migration.
Production experience with Kubernetes for container orchestration and workload
scheduling.
Solid understanding of event-driven architecture and message brokers.
Experience building and maintaining CI/CD pipelines.
Hands-on experience running services on a major cloud provider, preferably AWS.
Experience with observability: structured logging, metrics and distributed tracing.
Demonstrated experience mentoring engineers and raising the standard of code
review within a team.

NICE TO HAVE
Experience with Terraform or another infrastructure-as-code tool.
Familiarity with GraphQL APIs.
Exposure to the logistics or payments domain.

WHAT WE OFFER
Competitive salary, equity, and a genuine four-day-week pilot starting this year.
Meridian Labs is an equal opportunity employer.
"""


CV_FRONTEND = """NIKOS PALAIOLOGOS
Frontend Developer - Thessaloniki, Greece
nikos.p@example.com

SUMMARY
Frontend developer with 2 years of experience building single-page applications.
Comfortable owning a feature from Figma handoff through to release. Strongest on
React and TypeScript; keen to grow into accessibility and design systems work.

EXPERIENCE

Frontend Developer, Kalliste Digital (2023 - 2025)
Built the customer dashboard in React and TypeScript, replacing a jQuery page
that had grown to 4000 lines.
Introduced a component library with Storybook so the three product squads stopped
rebuilding the same date picker.
Cut the initial bundle from 1.4MB to 480KB by code-splitting routes and moving
charting to a lazily loaded module.
Added Playwright end-to-end tests covering the checkout journey, which caught two
regressions before release in the first month.
Worked with the designer to bring the dashboard to WCAG 2.1 AA, fixing focus
order, contrast and screen-reader labels.

Junior Developer, Aegean Web (2022 - 2023)
Maintained WordPress and vanilla JavaScript sites for local businesses.
Built a booking widget in plain JavaScript that is still in use.

EDUCATION
BSc Computer Science, Aristotle University of Thessaloniki, 2022

TECHNICAL SKILLS
Languages: TypeScript, JavaScript, HTML, CSS
Frameworks: React, Next.js, Storybook, Playwright, Vitest
Styling: Tailwind, CSS Modules, responsive design
Practices: accessibility (WCAG 2.1), code review, Figma handoff, Git
"""

JD_FRONTEND = """SENIOR FRONTEND ENGINEER
Kyma Interactive - Athens, hybrid

ABOUT THE ROLE
We build the booking experience used by several thousand travellers a day. You
will own the front end of that journey.

REQUIREMENTS
Strong commercial experience with React and TypeScript in production applications.
Experience building and maintaining a shared component library or design system.
Demonstrated attention to web performance, including bundle size and load time.
Practical knowledge of web accessibility standards such as WCAG.
Experience writing end-to-end or integration tests for user journeys.
Comfortable collaborating directly with designers.

NICE TO HAVE
Experience with server-side rendering, for example Next.js.
Familiarity with WebGL or canvas-based visualisation.
Experience mentoring junior engineers.

WHAT WE OFFER
Hybrid working, a learning budget, and a genuinely good coffee machine.
"""


def write_pdf(text: str, path: Path, title: str) -> None:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_title(title)
    for line in text.strip().splitlines():
        stripped = line.strip()
        if not stripped:
            pdf.ln(3)
            continue
        letters = [c for c in stripped if c.isalpha()]
        is_heading = letters and all(c.isupper() for c in letters) and len(stripped) < 60
        pdf.set_font("Helvetica", "B" if is_heading else "", 11 if is_heading else 10)
        pdf.multi_cell(0, 5, stripped, new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(path))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pairs = [
        (CV, "sample_cv", "Elena Roussou - CV"),
        (JD, "sample_jd", "Senior Backend Engineer - Meridian Labs"),
        (CV_FRONTEND, "frontend_cv", "Nikos Palaiologos - CV"),
        (JD_FRONTEND, "frontend_jd", "Senior Frontend Engineer - Kyma Interactive"),
    ]
    for text, stem, title in pairs:
        write_pdf(text, OUT / f"{stem}.pdf", title)
        (OUT / f"{stem}.txt").write_text(text)
    print(f"Wrote {len(pairs)} fixtures to {OUT}")


if __name__ == "__main__":
    main()
