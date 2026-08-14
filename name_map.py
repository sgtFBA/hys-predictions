CHAMPIONSHIP_NAME_MAP = {
    "west ham": "West Ham United", "westham": "West Ham United", "west ham united": "West Ham United",
    "wolves": "Wolverhampton Wanderers", "wolverhampton wanderers": "Wolverhampton Wanderers",
    "middlesbrough": "Middlesbrough", "boro": "Middlesbrough",
    "millwall": "Millwall",
    "burnley": "Burnley",
    "southampton": "Southampton", "saints": "Southampton",
    "wrexham": "Wrexham AFC", "wrexham afc": "Wrexham AFC",
    "birmingham city": "Birmingham City", "birmingham": "Birmingham City",
    "norwich city": "Norwich City", "norwich": "Norwich City", "scum": "Norwich City",
    "stoke city": "Stoke City", "stoke": "Stoke City",
    "sheffield united": "Sheffield United", "sheff united": "Sheffield United", "sheff utd": "Sheffield United",
    "bristol city": "Bristol City", "bristol": "Bristol City",
    "swansea city": "Swansea City", "swansea": "Swansea City",
    "derby county": "Derby County", "derby": "Derby County",
    "portsmouth": "Portsmouth", "pompey": "Portsmouth",
    "watford": "Watford",
    "preston north end": "Preston North End", "preston": "Preston North End", "pne": "Preston North End",
    "blackburn rovers": "Blackburn Rovers", "blackburn": "Blackburn Rovers",
    "qpr": "Queens Park Rangers", "queens park rangers": "Queens Park Rangers",
    "cardiff city": "Cardiff City", "cardiff": "Cardiff City",
    "charlton athletic": "Charlton Athletic", "charlton": "Charlton Athletic",
    "bolton wanderers": "Bolton Wanderers", "bolton": "Bolton Wanderers",
    "west bromwich albion": "West Bromwich Albion", "west brom": "West Bromwich Albion", "westbrom": "West Bromwich Albion", "wba": "West Bromwich Albion",
    "lincoln city": "Lincoln City", "lincoln": "Lincoln City",
}

PREMIER_LEAGUE_NAME_MAP = {
    "afc bournemouth": "AFC Bournemouth", "bournemouth": "AFC Bournemouth",
    "arsenal": "Arsenal",
    "aston villa": "Aston Villa", "villa": "Aston Villa",
    "brentford": "Brentford",
    "brighton & hove albion": "Brighton & Hove Albion", "brighton": "Brighton & Hove Albion",
    "chelsea": "Chelsea",
    "coventry city": "Coventry City", "coventry": "Coventry City",
    "crystal palace": "Crystal Palace", "palace": "Crystal Palace",
    "everton": "Everton",
    "fulham": "Fulham",
    "hull city": "Hull City", "hull": "Hull City",
    "ipswich town": "Ipswich Town", "ipswich": "Ipswich Town",
    "leeds united": "Leeds United", "leeds": "Leeds United",
    "liverpool": "Liverpool",
    "manchester city": "Manchester City", "man city": "Manchester City", "man c": "Manchester City",
    "manchester united": "Manchester United", "man utd": "Manchester United", "man u": "Manchester United", "man united": "Manchester United",
    "newcastle united": "Newcastle United", "newcastle": "Newcastle United",
    "nottingham forest": "Nottingham Forest", "forest": "Nottingham Forest", "nottm forest": "Nottingham Forest",
    "sunderland": "Sunderland",
    "tottenham hotspur": "Tottenham Hotspur", "tottenham": "Tottenham Hotspur", "spurs": "Tottenham Hotspur",
}


def normalize(raw, canonical, who):
    name_map = CHAMPIONSHIP_NAME_MAP if len(canonical) == 24 else PREMIER_LEAGUE_NAME_MAP
    out = []
    for t in raw:
        key = t.strip().lower()
        if key not in name_map:
            raise ValueError(f"{who}: unrecognized team '{t}'")
        out.append(name_map[key])
    if len(out) != len(canonical):
        raise ValueError(f"{who}: {len(out)} teams, need {len(canonical)}")
    if len(set(out)) != len(out):
        raise ValueError(f"{who}: duplicate team in list")
    if set(out) != canonical:
        raise ValueError(f"{who} mismatch: missing={canonical-set(out)} extra={set(out)-canonical}")
    return out
