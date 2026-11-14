"""Read JobPosting metadata from a local HTML snapshot. No network access."""
import argparse
import json
from pathlib import Path


def postings(value):
    if isinstance(value, list):
        for item in value:
            yield from postings(item)
    elif isinstance(value, dict):
        kinds = value.get('@type')
        if kinds == 'JobPosting' or isinstance(kinds, list) and 'JobPosting' in kinds:
            yield {key: value[key] for key in (
                'title', 'hiringOrganization', 'jobLocation', 'jobLocationType',
                'applicantLocationRequirements', 'datePosted', 'url', 'description',
            ) if key in value}
        yield from postings(value.get('@graph'))


def extract(path):
    try:
        from scrapling.parser import Selector
    except ImportError as exc:
        raise ValueError('Install the optional parser with python -m pip install scrapling.') from exc
    with path.open('rb') as source:
        raw = source.read(5_000_001)
    if len(raw) > 5_000_000:
        raise ValueError('HTML snapshot exceeds 5 MB.')
    page = Selector(raw.decode('utf-8-sig'))
    jobs = []
    for block in page.css('script[type="application/ld+json"]::text').getall():
        try:
            jobs.extend(postings(json.loads(block)))
        except (ValueError, RecursionError):
            continue
    return {'verified': False, 'candidates': jobs}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('html', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(extract(args.html)))
    except (ValueError, OSError) as exc:
        parser.exit(1, str(exc) + '\n')
