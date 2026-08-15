#!/usr/bin/env python3
"""
Fetches current Premier League & Championship standings from football-data.org
and writes them into data.json's current_tables, then updates last_checked.

Requires env var FOOTBALL_DATA_TOKEN (a free API key from
https://www.football-data.org/client/register).

Only overwrites a league's current_tables entry if matches have actually been
played (i.e. at least one team shows playedGames > 0) - otherwise leaves
whatever was already there untouched, so we never clobber real data with an
empty/not-started table.
"""
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

from name_map import CHAMPIONSHIP_NAME_MAP, PREMIER_LEAGUE_NAME_MAP

DATA_PATH = sys.argv[1] if len(sys.argv) > 1 else "data.json"
TOKEN = os.environ.get("FOOTBALL_DATA_TOKEN", "").strip()

# football-data.org sometimes returns names with "FC"/"AFC" suffixes or
# slightly different formatting than our canonical team names. These extra
# aliases get merged on top of the existing name_map dictionaries.
EXTRA_ALIASES = {
    "afc bournemouth": "AFC Bournemouth",
    "bournemouth": "AFC Bournemouth",
    "brighton hove albion fc": "Brighton & Hove Albion",
    "brighton & hove albion fc": "Brighton & Hove Albion",
    "nottingham forest fc": "Nottingham Forest",
    "wolverhampton wanderers fc": "Wolverhampton Wanderers",
    "west ham united fc": "West Ham United",
    "manchester city fc": "Manchester City",
    "manchester united fc": "Manchester United",
    "newcastle united fc": "Newcastle United",
    "tottenham hotspur fc": "Tottenham Hotspur",
    "crystal palace fc": "Crystal Palace",
    "aston villa fc": "Aston Villa",
    "leeds united fc": "Leeds United",
    "sunderland afc": "Sunderland",
    "everton fc": "Everton",
    "fulham fc": "Fulham",
    "brentford fc": "Brentford",
    "chelsea fc": "Chelsea",
    "arsenal fc": "Arsenal",
    "liverpool fc": "Liverpool",
    "coventry city fc": "Coventry City",
    "hull city afc": "Hull City",
    "ipswich town fc": "Ipswich Town",
    "west bromwich albion fc": "West Bromwich Albion",
    "sheffield united fc": "Sheffield United",
    "middlesbrough fc": "Middlesbrough",
    "millwall fc": "Millwall",
    "burnley fc": "Burnley",
    "southampton fc": "Southampton",
    "birmingham city fc": "Birmingham City",
    "norwich city fc": "Norwich City",
    "stoke city fc": "Stoke City",
    "bristol city fc": "Bristol City",
    "swansea city afc": "Swansea City",
    "derby county fc": "Derby County",
    "portsmouth fc": "Portsmouth",
    "watford fc": "Watford",
    "preston north end fc": "Preston North End",
    "blackburn rovers fc": "Blackburn Rovers",
    "queens park rangers fc": "Queens Park Rangers",
    "cardiff city fc": "Cardiff City",
    "charlton athletic fc": "Charlton Athletic",
    "bolton wanderers fc": "Bolton Wanderers",
    "west bromwich albion": "West Bromwich Albion",
    "lincoln city fc": "Lincoln City",
    "wrexham afc": "Wrexham AFC",
}

COMPETITIONS = {
    "premier_league": "PL",
    "championship": "ELC",
}


def build_alias_map(canonical_map):
    merged = dict(canonical_map)
    merged.update(EXTRA_ALIASES)
    return merged


def normalize_name(raw, alias_map):
    key = raw.strip().lower()
    if key in alias_map:
        return alias_map[key]
    for suffix in (" fc", " afc"):
        if key.endswith(suffix) and key[: -len(suffix)] in alias_map:
            return alias_map[key[: -len(suffix)]]
    return None


def fetch_finished_matches(competition_code):
    """football-data.org's precomputed /standings endpoint lags noticeably for
    lower-profile competitions on the free tier (observed: still showing 0
    games played many hours after full time). Match results themselves are
    recorded promptly, so we pull finished matches and compute the table
    ourselves instead of trusting their standings cache."""
    url = f"https://api.football-data.org/v4/competitions/{competition_code}/matches?status=FINISHED"
    req = urllib.request.Request(url, headers={"X-Auth-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def compute_table(matches, canonical, alias_map):
    """Returns (ordered_canonical_names, played_total, problems) where
    problems is a list of raw team names we couldn't map to a canonical
    team - caller should treat that as reason to bail out rather than
    write a possibly-wrong table."""
    stats = {name: {"points": 0, "gf": 0, "ga": 0, "played": 0} for name in canonical}
    problems = []
    played_total = 0

    for m in matches:
        if m.get("status") != "FINISHED":
            continue
        score = m.get("score", {}).get("fullTime", {})
        home_goals, away_goals = score.get("home"), score.get("away")
        if home_goals is None or away_goals is None:
            continue

        home_raw = m["homeTeam"]["name"]
        away_raw = m["awayTeam"]["name"]
        home = normalize_name(home_raw, alias_map)
        away = normalize_name(away_raw, alias_map)
        if home is None:
            problems.append(home_raw)
        if away is None:
            problems.append(away_raw)
        if home is None or away is None:
            continue

        played_total += 1
        stats[home]["played"] += 1
        stats[away]["played"] += 1
        stats[home]["gf"] += home_goals
        stats[home]["ga"] += away_goals
        stats[away]["gf"] += away_goals
        stats[away]["ga"] += home_goals
        if home_goals > away_goals:
            stats[home]["points"] += 3
        elif away_goals > home_goals:
            stats[away]["points"] += 3
        else:
            stats[home]["points"] += 1
            stats[away]["points"] += 1

    ordered = sorted(
        canonical,
        key=lambda name: (
            -stats[name]["points"],
            -(stats[name]["gf"] - stats[name]["ga"]),
            -stats[name]["gf"],
            name,
        ),
    )
    return ordered, played_total, problems


def main():
    if not TOKEN:
        print("ERROR: FOOTBALL_DATA_TOKEN is not set. Add it as a repo secret "
              "(Settings > Secrets and variables > Actions).", file=sys.stderr)
        sys.exit(1)

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    any_auth_error = False

    for league_key, comp_code in COMPETITIONS.items():
        canonical = set(data["leagues"][league_key]["teams"])
        alias_map = build_alias_map(
            CHAMPIONSHIP_NAME_MAP if league_key == "championship" else PREMIER_LEAGUE_NAME_MAP
        )
        try:
            payload = fetch_finished_matches(comp_code)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                print(f"AUTH ERROR fetching {league_key}: HTTP {e.code} - check FOOTBALL_DATA_TOKEN", file=sys.stderr)
                any_auth_error = True
            else:
                print(f"WARNING: HTTP {e.code} fetching {league_key} matches, leaving as-is", file=sys.stderr)
            continue
        except Exception as e:
            print(f"WARNING: failed to fetch {league_key} matches ({e}), leaving as-is", file=sys.stderr)
            continue

        matches = payload.get("matches", [])
        ordered, played_total, problems = compute_table(matches, canonical, alias_map)

        if played_total == 0:
            print(f"{league_key}: season not started (0 finished matches), leaving current_tables as-is")
            continue

        if problems:
            print(f"WARNING: {league_key} unrecognized team name(s) {sorted(set(problems))} - leaving current_tables as-is", file=sys.stderr)
            continue

        data["current_tables"][league_key] = ordered
        print(f"{league_key}: updated current_tables ({played_total} finished matches)")

    data["last_checked"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"last_checked set to {data['last_checked']}")

    if any_auth_error:
        sys.exit(1)


if __name__ == "__main__":
    main()
