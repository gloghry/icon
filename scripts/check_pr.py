"""Validate current PR metadata using trusted code and read-only GitHub access."""
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def validate(pr, repository, catalog, fetch_issue):
    labels = {label['name'] for label in pr.get('labels', [])} & set(catalog)
    if len(labels) != 1:
        raise ValueError('Apply exactly one change-type label: ' + ', '.join(catalog))
    # Accept standard closing keywords and explicit non-closing references.
    # Limit references to this repository; cross-repository references are context.
    prefix = rf'(?:#|{re.escape(repository)}#|https://github\.com/{re.escape(repository)}/issues/)'
    pattern = rf'\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?|related\s+to)\s+{prefix}(\d+)\b'
    body = re.sub(r'<!--.*?-->', '', pr.get('body') or '', flags=re.S)
    numbers = sorted({int(n) for n in re.findall(pattern, body, flags=re.I)})
    if not numbers:
        raise ValueError('Reference an existing local issue with Closes #N or Related to #N')
    for number in numbers:
        try:
            issue = fetch_issue(number)
        except HTTPError as error:
            if error.code == 404:
                error.close()
                continue
            raise
        if not issue.get('pull_request'):
            return
    raise ValueError('At least one referenced issue must exist and must not be a pull request')


def main():
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    repository = os.environ['GITHUB_REPOSITORY']
    number = event['pull_request']['number']
    token = os.environ['GH_TOKEN']

    def get(route):
        request = Request('https://api.github.com/' + route, headers={
            'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'icon-pr-policy'})
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    # Fetch current metadata so queued label/edit events validate the latest state.
    pr = get(f'repos/{repository}/issues/{number}')
    catalog = json.loads(Path(__file__).with_name('change_type_labels.json').read_text())
    validate(pr, repository, catalog, lambda n: get(f'repos/{repository}/issues/{n}'))
    print('PR references an existing local issue and has exactly one change-type label.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError) as error:
        print(f'PR policy failed: {error}', file=sys.stderr)
        sys.exit(1)
