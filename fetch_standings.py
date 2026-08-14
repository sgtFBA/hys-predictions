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
    # try stripping a trailing " fc" / " afc"
    for suffix in (" fc", " afc"):
        if key.endswith(suffix) and key[: -len(suffix)] in alias_map:
            return alias_map[key[: -len(suffix)]]
    return None


def fetch_standings(competition_code):
    url = f"https://api.football-data.org/v4/competitions/{competition_code}/standings"
    req = urllib.request.Request(url, headers={"X-Auth-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


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
            payload = fetch_standings(comp_code)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                print(f"AUTH ERROR fetching {league_key}: HTTP {e.code} - check FOOTBALL_DATA_TOKEN", file=sys.stderr)
                any_auth_error = True
            else:
                print(f"WARNING: HTTP {e.code} fetching {league_key} standings, leaving as-is", file=sys.stderr)
            continue
        except Exception as e:
            print(f"WARNING: failed to fetch {league_key} standings ({e}), leaving as-is", file=sys.stderr)
            continue

        try:
            table = next(s for s in payload["standings"] if s["type"] == "TOTAL")["table"]
        except (KeyError, StopIteration):
            print(f"WARNING: unexpected response shape for {league_key}, leaving as-is", file=sys.stderr)
            continue

        played_total = sum(row.get("playedGames", 0) for row in table)
        if played_total == 0:
            print(f"{league_key}: season not started (0 games played), leaving current_tables as-is")
            continue

        ordered = sorted(table, key=lambda r: r["position"])
        mapped = []
        problems = []
        for row in ordered:
            raw_name = row["team"]["name"]
            canon = normalize_name(raw_name, alias_map)
            if canon is None:
                problems.append(raw_name)
            else:
                mapped.append(canon)

        if problems:
            print(f"WARNING: {league_key} unrecognized team name(s) {problems} - leaving current_tables as-is", file=sys.stderr)
            continue
        if set(mapped) != canonical or len(mapped) != len(canonical):
            print(f"WARNING: {league_key} mapped team set doesn't match canonical list - leaving current_tables as-is "
                  f"(missing={canonical - set(mapped)} extra={set(mapped) - canonical})", file=sys.stderr)
            continue

        data["current_tables"][league_key] = mapped
        print(f"{league_key}: updated current_tables ({played_total} games played across the league)")

    data["last_checked"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"last_checked set to {data['last_checked']}")

    if any_auth_error:
        sys.exit(1)


if __name__ == "__main__":
    main()
