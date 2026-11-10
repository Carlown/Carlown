"""Collect public GitHub data for the profile images (stdlib only).

Contribution calendar: scraped from the public profile fragment first (it is exactly what
visitors see, private contributions included when the user shows them), GraphQL as a
fallback when a token is available. Everything is cached in data/github.json so a build
still works offline.
"""
import datetime as dt
import json
import os
import re
import urllib.request

from kit import ROOT

CACHE = os.path.join(ROOT, 'data', 'github.json')
UA = 'Carlown-profile-readme-builder'


def _get(url, token=None, raw=False, data=None):
    headers = {'User-Agent': UA}
    if not raw:
        headers['Accept'] = 'application/vnd.github+json'
    if token and 'api.github.com' in url:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=40) as r:
        body = r.read().decode('utf-8')
    return body if raw else json.loads(body)


def calendar_from_html(user):
    html = _get(f'https://github.com/users/{user}/contributions', raw=True)
    tips = {}
    for tid, txt in re.findall(r'<tool-tip[^>]*\bfor="([^"]+)"[^>]*>([^<]*)</tool-tip>', html):
        m = re.match(r'\s*([\d,]+)\s+contribution', txt)
        tips[tid] = int(m.group(1).replace(',', '')) if m else 0
    days = []
    for tag in re.findall(r'<td\b[^>]*ContributionCalendar-day[^>]*>', html):
        a = dict(re.findall(r'([\w-]+)="([^"]*)"', tag))
        if 'data-date' not in a:
            continue
        lvl = int(a.get('data-level', 0))
        days.append({'date': a['data-date'], 'level': lvl, 'count': tips.get(a.get('id'), 1 if lvl else 0)})
    if len(days) < 300:
        raise RuntimeError(f'calendar scrape found only {len(days)} days')
    days.sort(key=lambda d: d['date'])
    m = re.search(r'([\d,]+)\s+contributions?\s+in the last year', html, re.S)
    total = int(m.group(1).replace(',', '')) if m else sum(d['count'] for d in days)
    return {'total': total, 'days': days}


def calendar_from_graphql(user, token):
    q = ('query($login:String!){user(login:$login){contributionsCollection{contributionCalendar{'
         'totalContributions weeks{contributionDays{date contributionCount contributionLevel}}}}}}')
    body = json.dumps({'query': q, 'variables': {'login': user}}).encode()
    r = _get('https://api.github.com/graphql', token, data=body)
    cal = r['data']['user']['contributionsCollection']['contributionCalendar']
    lv = {'NONE': 0, 'FIRST_QUARTILE': 1, 'SECOND_QUARTILE': 2, 'THIRD_QUARTILE': 3, 'FOURTH_QUARTILE': 4}
    days = [{'date': d['date'], 'count': d['contributionCount'], 'level': lv.get(d['contributionLevel'], 0)}
            for w in cal['weeks'] for d in w['contributionDays']]
    return {'total': cal['totalContributions'], 'days': sorted(days, key=lambda d: d['date'])}


def _repo_row(r):
    return {
        'stars': r['stargazers_count'], 'forks': r['forks_count'], 'language': r['language'],
        'description': r.get('description') or '', 'homepage': r.get('homepage') or '',
        'fork': r.get('fork', False), 'archived': r.get('archived', False),
    }


def fetch(user, token=None, extra=()):
    u = _get(f'https://api.github.com/users/{user}', token)
    repos = _get(f'https://api.github.com/users/{user}/repos?per_page=100&type=owner&sort=pushed', token)
    out_repos, langs = {}, {}
    for r in repos:
        out_repos[r['name']] = _repo_row(r)
        if not r['fork'] and not r['archived']:
            for k, v in _get(r['languages_url'], token).items():
                langs[k] = langs.get(k, 0) + v
    # repos hosted elsewhere (e.g. moved to an org) that still belong on a project card;
    # fetched live for their star/fork/language, but kept out of the personal language donut.
    for full in extra:
        try:
            out_repos[full] = _repo_row(_get(f'https://api.github.com/repos/{full}', token))
        except Exception as e:  # noqa: BLE001
            print('extra repo fetch failed:', full, e)
    cal = None
    try:
        cal = calendar_from_html(user)
    except Exception as e:  # noqa: BLE001
        print('calendar scrape failed:', e)
        if token:
            cal = calendar_from_graphql(user, token)
    if cal is None:
        raise RuntimeError('no contribution calendar')
    return {
        'user': {k: u.get(k) for k in ('login', 'name', 'bio', 'public_repos', 'followers', 'created_at')},
        'repos': out_repos,
        'languages': dict(sorted(langs.items(), key=lambda kv: -kv[1])),
        'calendar': cal,
    }


def load(user, offline=False, extra=()):
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if not offline:
        try:
            data = fetch(user, token, extra)
            os.makedirs(os.path.dirname(CACHE), exist_ok=True)
            with open(CACHE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
            return data
        except Exception as e:  # noqa: BLE001
            print('fetch failed, using cache:', e)
    with open(CACHE, encoding='utf-8') as f:
        return json.load(f)


def calendar_stats(days):
    active = [d for d in days if d['count'] > 0]
    best = cur = 0
    prev = None
    for d in days:
        day = dt.date.fromisoformat(d['date'])
        if d['count'] > 0:
            cur = cur + 1 if prev and (day - prev).days == 1 and cur else 1
            best = max(best, cur)
        else:
            cur = 0
        prev = day
    top = max(days, key=lambda d: d['count']) if days else None
    return {'active_days': len(active), 'longest_streak': best, 'busiest': top}
