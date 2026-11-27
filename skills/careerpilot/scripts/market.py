"""Read-only market view from saved postings: skill demand and published pay."""
import re
from collections import defaultdict
from statistics import median

from document_quality import contains_keyword

# shortcut: fixed vocabulary for "skills you don't list"; extend it when target roles change.
COMMON = ['Python', 'SQL', 'Java', 'JavaScript', 'TypeScript', 'C++', 'C#', 'Scala', 'Bash', 'Spark', 'PySpark',
          'Hadoop', 'Kafka', 'Airflow', 'dbt', 'Snowflake', 'Databricks', 'BigQuery', 'Redshift', 'Azure', 'AWS',
          'GCP', 'Docker', 'Kubernetes', 'Terraform', 'Git', 'CI/CD', 'Linux', 'REST', 'GraphQL', 'PostgreSQL',
          'MySQL', 'MongoDB', 'NoSQL', 'ETL', 'ELT', 'Data Modeling', 'Data Warehouse', 'Power BI', 'Tableau',
          'Looker', 'Excel', 'DAX', 'SSIS', 'SSRS', 'Statistics', 'A/B Testing', 'Machine Learning',
          'Deep Learning', 'NLP', 'LLM', 'Generative AI', 'RAG', 'LangChain', 'PyTorch', 'TensorFlow',
          'Scikit-learn', 'MLOps', 'MLflow', 'Pandas', 'NumPy', 'React', 'Node.js', 'Django', 'Flask', 'FastAPI',
          'Agile', 'Jira', 'SIEM', 'Splunk', 'Microsoft Sentinel', 'Incident Response', 'Threat Intelligence',
          'OSINT', 'Salesforce', 'SAP', 'Google Analytics']
NUM = r'(\d[\d,]*(?:\.\d+)?)\s*([kK])?'
PAY = re.compile(r'\$\s*' + NUM + r'(?:\s*(?:-|–|—|�|to)\s*\$?\s*' + NUM + r')?'
                 r'(?:\s*(?:/|per|an?)\s*(hour|hr|year|yr|annum))?', re.I)
LIMITS = {'hour': (12, 250), 'year': (20000, 400000)}


def pay(text):
    """First plausible published pay in a posting, as (low, high, period, quote), or None."""
    for m in PAY.finditer(text or ''):
        low, low_k, high, high_k, unit = m.groups()
        values = [float(v.replace(',', '')) for v in (low, high or low)]
        if low_k or high_k:  # "$70-80K" puts the K on one bound only
            values = [v * 1000 if v < 1000 else v for v in values]
        period = ('hour' if unit.lower() in {'hour', 'hr'} else 'year') if unit else ('hour' if values[1] < 300 else 'year')
        lo, hi = LIMITS[period]
        if lo <= values[0] <= values[1] <= hi:
            return values[0], values[1], period, m.group(0).strip()
    return None


def skill_parts(skill):
    # "HTML/CSS" also counts "HTML" or "CSS"; one-letter parts ("A/B Testing") would match everything.
    return {skill} | {p.strip() for p in skill.split('/') if len(p.strip()) > 1}


def view(state, role=None):
    jobs = [j for j in state['jobs'].values() if not role or contains_keyword(j['title'], role)]
    profile = state.get('profile', {})
    yours = list(dict.fromkeys(list(profile.get('skills', [])) +
                               [s for group in profile.get('skill_groups', {}).values() for s in group]))
    known = {p.casefold() for s in yours for p in skill_parts(s)}
    total = len(jobs)

    def demand(skills, split=True):
        rows = []
        for skill in skills:
            parts = skill_parts(skill) if split else {skill}
            hits = [j['id'] for j in jobs if any(contains_keyword(j['description'], p) for p in parts)]
            rows.append(dict(skill=skill, jobs=len(hits), share=round(len(hits) / total, 2) if total else None))
        return sorted(rows, key=lambda r: -r['jobs'])

    missing = [r for r in demand([s for s in COMMON if s.casefold() not in known], split=False) if r['jobs'] >= 2][:15]
    targets = [r for r in profile.get('target_roles', []) if not role or contains_keyword(r, role) or contains_keyword(role, r)]
    groups = defaultdict(list)
    parsed = 0
    for job in jobs:
        found = pay(job['description'])
        if not found:
            continue
        parsed += 1
        roles = [r for r in targets if contains_keyword(job['title'], r)] or [role or 'Other titles']
        for r in roles:
            groups[(r, found[2])].append((job['id'], *found))
    salary = []
    for (r, period), rows in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        salary.append(dict(role=r, period=period, n=len(rows), low_median=median(x[1] for x in rows),
                           high_median=median(x[2] for x in rows), lowest=min(x[1] for x in rows),
                           highest=max(x[2] for x in rows), job_ids=[x[0] for x in rows],
                           reliability='Small sample' if len(rows) < 5 else 'Descriptive only'))
    return dict(jobs_scanned=total, role_filter=role,
                skills=dict(yours=demand(yours), missing=missing,
                            note='Literal phrase matches in saved postings; a missing skill is a learning idea, never a resume claim.'),
                salary=dict(by_role=salary, parsed_jobs=parsed,
                            note='Parsed from posting text in the currency posted (not converted); verify before relying on it.'))
