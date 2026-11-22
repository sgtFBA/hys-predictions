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


def season_start_year(data):
    """'2026-27' -> 2026. Passing the season explicitly stops the API from
    silently switching which season it treats as 'current'."""
    try:
        return int(str(data.get("season", "")).split("-")[0].split("/")[0])
    except ValueError:
        return None


def api_get(url):
    req = urllib.request.Request(url, headers={"X-Auth-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_finished_matches(competition_code, season=None):
    """football-data.org's precomputed /standings endpoint lags noticeably for
    lower-profile competitions on the free tier (observed: still showing 0
    games played many hours after full time). Match results themselves are
    recorded promptly, so we pull finished matches and compute the table
    ourselves instead of trusting their standings cache."""
    url = f"https://api.football-data.org/v4/competitions/{competition_code}/matches?status=FINISHED"
    if season:
        url += f"&season={season}"
    return api_get(url)


def fetch_standings_table(competition_code, canonical, alias_map, season=None):
    """Second opinion: football-data's own precomputed table. Returns
    (ordered, played_total, problems) in the same shape as compute_table,
    or None if it can't be used."""
    url = f"https://api.football-data.org/v4/competitions/{competition_code}/standings"
    if season:
        url += f"?season={season}"
    payload = api_get(url)
    total = next((s for s in payload.get("standings", []) if s.get("type") == "TOTAL"), None)
    if not total:
        return None
    ordered, problems = [], []
    for row in total.get("table", []):
        raw = row["team"]["name"]
        name = normalize_name(raw, alias_map)
        if name is None or name not in canonical:
            problems.append(raw)
            continue
        ordered.append({
            "team": name,
            "played": row.get("playedGames", 0),
            "won": row.get("won", 0),
            "drawn": row.get("draw", 0),
            "lost": row.get("lost", 0),
            "gf": row.get("goalsFor", 0),
            "ga": row.get("goalsAgainst", 0),
            "gd": row.get("goalDifference", 0),
            "points": row.get("points", 0),
        })
    if len(ordered) != len(canonical):
        problems.append(f"standings had {len(ordered)} usable teams, expected {len(canonical)}")
    played_total = sum(t["played"] for t in ordered) // 2
    return ordered, played_total, problems


def matches_in_table(table):
    """How many matches an existing current_tables entry is built from."""
    try:
        return sum(int(t.get("played", 0)) for t in table) // 2
    except (AttributeError, TypeError):
        return 0


def compute_table(matches, canonical, alias_map):
    """Returns (ordered_team_stat_dicts, played_total, problems) where
    problems is a list of raw team names we couldn't map to a canonical
    team - caller should treat that as reason to bail out rather than
    write a possibly-wrong table.

    Each entry in ordered_team_stat_dicts is
    {"team", "played", "won", "drawn", "lost", "gf", "ga", "gd", "points"} -
    the dashboard (generate_dashboard.py) reads this richer shape to show
    a full P/W/D/L/GD/Pts table, not just finishing order."""
    stats = {
        name: {"points": 0, "won": 0, "drawn": 0, "lost": 0, "gf": 0, "ga": 0, "played": 0}
        for name in canonical
    }
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
            stats[home]["won"] += 1
            stats[away]["lost"] += 1
        elif away_goals > home_goals:
            stats[away]["points"] += 3
            stats[away]["won"] += 1
            stats[home]["lost"] += 1
        else:
            stats[home]["points"] += 1
            stats[away]["points"] += 1
            stats[home]["drawn"] += 1
            stats[away]["drawn"] += 1

    ordered_names = sorted(
        canonical,
        key=lambda name: (
            -stats[name]["points"],
            -(stats[name]["gf"] - stats[name]["ga"]),
            -stats[name]["gf"],
            name,
        ),
    )
    ordered = [
        {
            "team": name,
            "played": stats[name]["played"],
            "won": stats[name]["won"],
            "drawn": stats[name]["drawn"],
            "lost": stats[name]["lost"],
            "gf": stats[name]["gf"],
            "ga": stats[name]["ga"],
            "gd": stats[name]["gf"] - stats[name]["ga"],
            "points": stats[name]["points"],
        }
        for name in ordered_names
    ]
    return ordered, played_total, problems


def main():
    if not TOKEN:
        print("ERROR: FOOTBALL_DATA_TOKEN is not set. Add it as a repo secret "
              "(Settings > Secrets and variables > Actions).", file=sys.stderr)
        sys.exit(1)

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    any_auth_error = False
    season = season_start_year(data)

    for league_key, comp_code in COMPETITIONS.items():
        canonical = set(data["leagues"][league_key]["teams"])
        alias_map = build_alias_map(
            CHAMPIONSHIP_NAME_MAP if league_key == "championship" else PREMIER_LEAGUE_NAME_MAP
        )
        candidates = []  # (played_total, source, ordered)

        try:
            payload = fetch_finished_matches(comp_code, season)
            ordered, played_total, problems = compute_table(payload.get("matches", []), canonical, alias_map)
            if problems:
                print(f"WARNING: {league_key} matches: unrecognized team name(s) {sorted(set(problems))}", file=sys.stderr)
            elif played_total:
                candidates.append((played_total, "matches", ordered))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                print(f"AUTH ERROR fetching {league_key}: HTTP {e.code} - check FOOTBALL_DATA_TOKEN", file=sys.stderr)
                any_auth_error = True
            else:
                print(f"WARNING: HTTP {e.code} fetching {league_key} matches", file=sys.stderr)
        except Exception as e:
            print(f"WARNING: failed to fetch {league_key} matches ({e})", file=sys.stderr)

        try:
            result = fetch_standings_table(comp_code, canonical, alias_map, season)
            if result:
                ordered, played_total, problems = result
                if problems:
                    print(f"WARNING: {league_key} standings unusable: {problems}", file=sys.stderr)
                elif played_total:
                    candidates.append((played_total, "standings", ordered))
        except Exception as e:
            print(f"WARNING: failed to fetch {league_key} standings ({e})", file=sys.stderr)

        if not candidates:
            print(f"{league_key}: no usable data this run, leaving current_tables as-is")
            continue

        for total, source, _ in candidates:
            print(f"{league_key}: {source} source has {total} finished matches")
        best_total, best_source, best_ordered = max(candidates, key=lambda c: c[0])

        # Matches never un-finish. If the API now returns fewer than we
        # already have, its feed has gone patchy (this happened 17 Nov 2026
        # for the Championship: 180 -> 6). Keep the table we have.
        # NB: at the start of a new season, clear current_tables in data.json
        # so this check starts from zero.
        existing_total = matches_in_table(data["current_tables"].get(league_key) or [])
        if best_total < existing_total:
            print(f"WARNING: {league_key}: API only has {best_total} finished matches but current table "
                  f"has {existing_total} - API feed looks incomplete, keeping existing table", file=sys.stderr)
            continue

        data["current_tables"][league_key] = best_ordered
        print(f"{league_key}: updated current_tables from {best_source} ({best_total} finished matches)")

    data["last_checked"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"last_checked set to {data['last_checked']}")

    if any_auth_error:
        sys.exit(1)


if __name__ == "__main__":
    main()
