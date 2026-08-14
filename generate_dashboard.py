#!/usr/bin/env python3
"""
Generates dashboard.html (a self-contained HTML dashboard) from data.json.

Usage:
    python3 generate_dashboard.py [data.json path] [output html path]

Reads the canonical predictions/results data (data.json) and renders:
  - Two league tables (Premier League, Championship) with current standings
  - Each participant's predicted table (once predictions exist)
  - A leaderboard: total points per participant, lowest wins
  - A "last checked" timestamp

This script has no external dependencies (stdlib only) so it can run in any
fresh session that has data.json available.
"""
import json
import sys
import html
import colorsys
from datetime import datetime, timezone

DATA_PATH = sys.argv[1] if len(sys.argv) > 1 else "data.json"
OUT_PATH = sys.argv[2] if len(sys.argv) > 2 else "dashboard.html"

with open(DATA_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

LEAGUES = ["premier_league", "championship"]

# Shorter labels so the prediction grid (one column per participant) stays compact.
SHORT_NAMES = {
    "AFC Bournemouth": "Bournemouth",
    "Brighton & Hove Albion": "Brighton",
    "Manchester City": "Man City",
    "Manchester United": "Man Utd",
    "Newcastle United": "Newcastle",
    "Nottingham Forest": "Nott'm Forest",
    "Tottenham Hotspur": "Spurs",
    "West Ham United": "West Ham",
    "Wolverhampton Wanderers": "Wolves",
    "Birmingham City": "Birmingham",
    "Blackburn Rovers": "Blackburn",
    "Bolton Wanderers": "Bolton",
    "Bristol City": "Bristol City",
    "Cardiff City": "Cardiff",
    "Charlton Athletic": "Charlton",
    "Derby County": "Derby",
    "Lincoln City": "Lincoln",
    "Norwich City": "Norwich",
    "Preston North End": "Preston",
    "Queens Park Rangers": "QPR",
    "Sheffield United": "Sheff Utd",
    "Stoke City": "Stoke",
    "Swansea City": "Swansea",
    "Watford": "Watford",
    "West Bromwich Albion": "WBA",
    "Wrexham AFC": "Wrexham",
    "Hull City": "Hull",
    "Ipswich Town": "Ipswich",
    "Leeds United": "Leeds",
    "Coventry City": "Coventry",
}


def esc(s):
    return html.escape(str(s))


def hsl_to_hex(h, s, l):
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360.0, l / 100.0, s / 100.0)
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


def relative_luminance(hex_color):
    vals = [int(hex_color[i:i+2], 16) / 255 for i in (1, 3, 5)]

    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(v) for v in vals)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(hex_a, hex_b):
    la, lb = relative_luminance(hex_a), relative_luminance(hex_b)
    la, lb = max(la, lb), min(la, lb)
    return (la + 0.05) / (lb + 0.05)


def text_color_for(hex_bg):
    return "#0b0b0b" if relative_luminance(hex_bg) > 0.42 else "#ffffff"


# Real club colours: (primary = cell fill, secondary = cell text), sourced from
# each club's actual home-kit identity. A handful of clubs' "primary" colour is
# white/near-white (Fulham, Leeds, Tottenham, Bolton, Derby, Preston, Swansea) —
# those use an off-white fill so the cell still reads against the panel surface.
TEAM_BRAND_COLORS = {
    # Premier League
    "AFC Bournemouth": ("#DA291C", "#000000"),
    "Arsenal": ("#EF0107", "#063672"),
    "Aston Villa": ("#670E36", "#95BFE5"),
    "Brentford": ("#E30613", "#FFFFFF"),
    "Brighton & Hove Albion": ("#0057B8", "#FFFFFF"),
    "Chelsea": ("#034694", "#FFFFFF"),
    "Coventry City": ("#78D0F2", "#000B34"),
    "Crystal Palace": ("#C4122E", "#1B458F"),
    "Everton": ("#003399", "#FFFFFF"),
    "Fulham": ("#E7E6E1", "#000000"),
    "Hull City": ("#F18A00", "#000000"),
    "Ipswich Town": ("#0044A9", "#FFFFFF"),
    "Leeds United": ("#E7E6E1", "#1D428A"),
    "Liverpool": ("#C8102E", "#F6EB61"),
    "Manchester City": ("#6CABDD", "#1C2C5B"),
    "Manchester United": ("#DA291C", "#FBE122"),
    "Newcastle United": ("#241F20", "#FFFFFF"),
    "Nottingham Forest": ("#DD0000", "#FFFFFF"),
    "Sunderland": ("#EB172B", "#000000"),
    "Tottenham Hotspur": ("#E7E6E1", "#132257"),
    # Championship
    "Birmingham City": ("#0044A3", "#FFFFFF"),
    "Blackburn Rovers": ("#005DAA", "#FFFFFF"),
    "Bolton Wanderers": ("#E7E6E1", "#003C71"),
    "Bristol City": ("#E21C21", "#FFFFFF"),
    "Burnley": ("#6C1D45", "#99D6EA"),
    "Cardiff City": ("#0070B5", "#FFFFFF"),
    "Charlton Athletic": ("#D2122E", "#FFFFFF"),
    "Derby County": ("#E7E6E1", "#000000"),
    "Lincoln City": ("#C8102E", "#000000"),
    "Middlesbrough": ("#CC0000", "#FFFFFF"),
    "Millwall": ("#00285E", "#FFFFFF"),
    "Norwich City": ("#FFF200", "#00A650"),
    "Portsmouth": ("#001489", "#FFFFFF"),
    "Preston North End": ("#E7E6E1", "#1B1464"),
    "Queens Park Rangers": ("#1D5BA4", "#FFFFFF"),
    "Sheffield United": ("#EE2737", "#000000"),
    "Southampton": ("#D71920", "#FFFFFF"),
    "Stoke City": ("#E03A3E", "#FFFFFF"),
    "Swansea City": ("#E7E6E1", "#000000"),
    "Watford": ("#FBEE23", "#000000"),
    "West Bromwich Albion": ("#122F67", "#FFFFFF"),
    "West Ham United": ("#7A263A", "#1BB1E7"),
    "Wolverhampton Wanderers": ("#FDB913", "#000000"),
    "Wrexham AFC": ("#C8102E", "#FFFFFF"),
}


def team_colors(teams):
    """Each team's real primary/secondary club colours (fill/text). Falls back to
    a generated colour only for a name we don't have branding for."""
    colors = {}
    for i, team in enumerate(teams):
        if team in TEAM_BRAND_COLORS:
            colors[team] = TEAM_BRAND_COLORS[team]
        else:
            hue = (i * 137.508) % 360
            bg = hsl_to_hex(hue, 60, 48)
            colors[team] = (bg, text_color_for(bg))
    return colors


def compute_scores(league_key):
    """Return dict participant -> points for a league, or {} if not computable."""
    league = data["leagues"][league_key]
    teams = league["teams"]
    current = data["current_tables"].get(league_key) or []
    preds = data["predictions"].get(league_key) or {}
    if not current or not preds:
        return {}
    actual_pos = {team: i + 1 for i, team in enumerate(current)}
    scores = {}
    for participant, order in preds.items():
        total = 0
        missing = False
        for i, team in enumerate(order):
            predicted_pos = i + 1
            if team not in actual_pos:
                missing = True
                continue
            total += abs(predicted_pos - actual_pos[team])
        if not missing and len(order) == len(teams):
            scores[participant] = total
    return scores


def league_table_html(league_key):
    league = data["leagues"][league_key]
    current = data["current_tables"].get(league_key) or []
    name = league["name"]
    if not current:
        rows = "".join(
            f'<tr><td class="pos">{i+1}</td><td>{esc(t)}</td></tr>'
            for i, t in enumerate(league["teams"])
        )
        badge = '<span class="badge badge-muted">Season not started — alphabetical listing</span>'
    else:
        rows = "".join(
            f'<tr><td class="pos">{i+1}</td><td>{esc(t)}</td></tr>'
            for i, t in enumerate(current)
        )
        badge = '<span class="badge badge-live">Live standings</span>'
    return f"""
    <section class="panel">
      <div class="panel-head">
        <h2>{esc(name)}</h2>
        {badge}
      </div>
      <div class="table-scroll">
        <table class="league-table">
          <thead><tr><th>#</th><th>Team</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </section>
    """


def league_scores_table_html(league_key):
    """Plain ranked table of just this league's scores — Prem and Championship are
    separate competitions, so they each get their own scores table rather than
    one merged table."""
    league = data["leagues"][league_key]
    scores = compute_scores(league_key)
    participants = [p for p in (data.get("participants") or []) if p in (data["predictions"].get(league_key) or {})]
    if not participants:
        return ""

    rows_data = [(p, scores.get(p)) for p in participants]
    rows_data.sort(key=lambda r: (r[1] is None, r[1] if r[1] is not None else 0, r[0].lower()))

    body_rows = []
    for idx, (p, score) in enumerate(rows_data):
        rank = idx + 1 if score is not None else "—"
        score_txt = score if score is not None else "—"
        row_cls = "scores-row-leader" if idx == 0 and score is not None else ""
        body_rows.append(
            f'<tr class="{row_cls}"><td class="scores-rank">{rank}</td><td class="scores-name">{esc(p)}</td>'
            f'<td class="scores-num scores-total">{score_txt}</td></tr>'
        )

    return f"""
    <section class="panel">
      <div class="panel-head">
        <h2>{esc(league['name'])} Scores</h2>
        <span class="badge badge-muted">Lowest total wins</span>
      </div>
      <div class="table-scroll">
        <table class="scores-table">
          <thead><tr><th>#</th><th>Name</th><th>Score</th></tr></thead>
          <tbody>{''.join(body_rows)}</tbody>
        </table>
      </div>
    </section>
    """


def leaderboard_html():
    pl_scores = compute_scores("premier_league")
    champ_scores = compute_scores("championship")
    participants = data.get("participants") or []

    if not participants:
        return """
        <section class="panel">
          <div class="panel-head"><h2>Leaderboard</h2></div>
          <p class="empty-state">No predictions added yet. Once everyone's predicted final tables
          are in, this leaderboard will rank the group automatically — lowest total score wins,
          highest total score loses.</p>
        </section>
        """

    combined = {}
    any_scores = False
    for p in participants:
        pl = pl_scores.get(p)
        ch = champ_scores.get(p)
        if pl is None and ch is None:
            continue
        total = (pl or 0) + (ch or 0)
        combined[p] = {"pl": pl, "ch": ch, "total": total}
        any_scores = True

    if not any_scores:
        return """
        <section class="panel">
          <div class="panel-head"><h2>Leaderboard</h2></div>
          <p class="empty-state">Predictions are in, but the season hasn't produced a live table yet
          — scores will appear here as soon as results start counting.</p>
        </section>
        """

    ranked = sorted(combined.items(), key=lambda kv: kv[1]["total"])
    max_total = max(v["total"] for _, v in ranked) or 1

    rows = []
    for idx, (participant, v) in enumerate(ranked):
        pct = round((v["total"] / max_total) * 100)
        tag = ""
        if idx == 0:
            tag = '<span class="tag tag-good">Leading</span>'
        elif idx == len(ranked) - 1 and len(ranked) > 1:
            tag = '<span class="tag tag-critical">Trailing</span>'
        pl_txt = v["pl"] if v["pl"] is not None else "—"
        ch_txt = v["ch"] if v["ch"] is not None else "—"
        rows.append(f"""
        <div class="lb-row">
          <div class="lb-rank">{idx + 1}</div>
          <div class="lb-name">{esc(participant)} {tag}</div>
          <div class="lb-bar-wrap">
            <div class="lb-bar" style="width:{pct}%"></div>
          </div>
          <div class="lb-total">{v['total']} pts</div>
          <div class="lb-split">PL {pl_txt} &middot; Champ {ch_txt}</div>
        </div>
        """)

    return f"""
    <section class="panel">
      <div class="panel-head">
        <h2>Leaderboard</h2>
        <span class="badge badge-muted">Lowest total wins</span>
      </div>
      <div class="leaderboard">
        {''.join(rows)}
      </div>
    </section>
    """


def prediction_grid_html(league_key):
    """One row per finishing position, one column per participant, cell = their
    predicted team for that spot — coloured by team identity, with an 'Actual'
    reference column on the left and a totals row at the bottom. Modelled on the
    group's old spreadsheet layout."""
    league = data["leagues"][league_key]
    teams = league["teams"]
    preds = data["predictions"].get(league_key) or {}
    if not preds:
        return ""

    colors = team_colors(teams)
    current = data["current_tables"].get(league_key) or []
    scores = compute_scores(league_key)
    participants = [p for p in (data.get("participants") or []) if p in preds]
    # unlisted-but-present predictors still show up, appended at the end
    participants += [p for p in preds if p not in participants]
    ordered = sorted(participants, key=lambda p: p.lower())

    def cell(team, empty_label="—"):
        if not team:
            return f'<td class="grid-cell grid-cell-empty">{empty_label}</td>'
        pair = colors.get(team)
        if not pair:
            return f'<td class="grid-cell grid-cell-empty">{esc(team)}</td>'
        bg, fg = pair
        # club secondary colours are sometimes too close to the primary to read as
        # text (e.g. near-white on near-white) — fall back to computed b/w in that case
        if contrast_ratio(bg, fg) < 2.5:
            fg = text_color_for(bg)
        label = esc(SHORT_NAMES.get(team, team))
        return f'<td class="grid-cell" style="background:{bg};color:{fg}">{label}</td>'

    header_cells = ['<th class="grid-actual-head">Actual</th>']
    for p in ordered:
        score = scores.get(p)
        chip = f' <span class="grid-score-chip">{score}</span>' if score is not None else ""
        header_cells.append(f'<th>{esc(p)}{chip}</th>')

    body_rows = []
    for i in range(len(teams)):
        actual_team = current[i] if i < len(current) else None
        cells = [cell(actual_team, empty_label="TBD")]
        for p in ordered:
            order = preds.get(p) or []
            team = order[i] if i < len(order) else None
            cells.append(cell(team))
        body_rows.append(f'<tr><td class="grid-pos">{i + 1}</td>{"".join(cells)}</tr>')

    totals_cells = ['<td class="grid-total-label">Total</td>']
    for p in ordered:
        s = scores.get(p)
        totals_cells.append(f'<td class="grid-total">{s if s is not None else "—"}</td>')

    return f"""
    <section class="panel">
      <div class="panel-head">
        <h2>{esc(league['name'])} — Prediction Grid</h2>
        <span class="badge badge-muted">Lowest total wins</span>
      </div>
      <div class="grid-scroll">
        <table class="pred-grid-table">
          <thead><tr><th class="grid-pos-head">#</th>{''.join(header_cells)}</tr></thead>
          <tbody>{''.join(body_rows)}</tbody>
          <tfoot><tr class="grid-total-row"><td class="grid-pos-head"></td>{''.join(totals_cells)}</tr></tfoot>
        </table>
      </div>
    </section>
    """


def scores_row_html():
    """Both leagues' scores tables side by side."""
    if not data.get("participants"):
        return ""
    return f"""
    <div class="grid-2">
      <div>{league_scores_table_html('premier_league')}</div>
      <div>{league_scores_table_html('championship')}</div>
    </div>
    """


def actual_tables_row_html():
    """Both leagues' actual standings tables side by side, same layout as the
    scores row above it."""
    return f"""
    <div class="grid-2">
      <div>{league_table_html('premier_league')}</div>
      <div>{league_table_html('championship')}</div>
    </div>
    """


def predictions_section_html():
    """Full-width prediction grid per league, stacked — these are wide (one
    column per participant) so they get the full page width rather than being
    squeezed into a half-width column."""
    if not data.get("participants"):
        return ""
    return prediction_grid_html("premier_league") + prediction_grid_html("championship")


last_checked = data.get("last_checked")
if last_checked:
    try:
        dt = datetime.fromisoformat(last_checked.replace("Z", "+00:00"))
        last_checked_display = dt.strftime("%a %d %b %Y, %H:%M UTC")
    except Exception:
        last_checked_display = last_checked
else:
    last_checked_display = "not yet checked"

generated_display = datetime.now(timezone.utc).strftime("%a %d %b %Y, %H:%M UTC")

html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(data.get('game_name', 'League Predictions Tracker'))}</title>
<style>
  /* Theme variables live on :root (the <html> element), NOT on .viz-root — a
     custom property declared on a div only cascades to that div's own
     descendants, so body (an ANCESTOR of .viz-root) would never see it and
     would fall back to browser defaults (black text, transparent/white bg).
     That was the bug: panels went dark correctly, but the page canvas behind
     them stayed white because body's background/color never resolved. */
  :root {{
    color-scheme: light;
    --surface-1:      #fcfcfb;
    --page-plane:     #f9f9f7;
    --text-primary:   #0b0b0b;
    --text-secondary: #52514e;
    --muted:          #898781;
    --gridline:       #e1e0d9;
    --baseline:       #c3c2b7;
    --border:         rgba(11,11,11,0.10);
    --series-1:       #2a78d6;
    --good:           #006300;
    --good-bg:        #e0f5e0;
    --critical:       #b42318;
    --critical-bg:    #fbe6e4;
  }}
  :root[data-theme="dark"] {{
    color-scheme: dark;
    --surface-1:      #1a1a19;
    --page-plane:     #0d0d0d;
    --text-primary:   #ffffff;
    --text-secondary: #c3c2b7;
    --muted:          #898781;
    --gridline:       #2c2c2a;
    --baseline:       #383835;
    --border:         rgba(255,255,255,0.10);
    --series-1:       #3987e5;
    --good:           #3ecf3e;
    --good-bg:        #12301a;
    --critical:       #e66767;
    --critical-bg:    #3a1414;
  }}
  /* ITFC mode — Ipswich Town's royal blue & white, for the one true club colour */
  :root[data-theme="itfc"] {{
    color-scheme: dark;
    --surface-1:      #0d2b6b;
    --page-plane:     #071b47;
    --text-primary:   #ffffff;
    --text-secondary: #cddcf7;
    --muted:          #93a5d1;
    --gridline:       #1e3f8f;
    --baseline:       #3a5bb0;
    --border:         rgba(255,255,255,0.16);
    --series-1:       #ffffff;
    --good:           #7be87b;
    --good-bg:        #123a1e;
    --critical:       #ff9b90;
    --critical-bg:    #4a1512;
    --itfc-red:       #e30613;
  }}

  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    background: var(--page-plane);
    color: var(--text-primary);
  }}
  .viz-root {{ padding: 24px 16px 48px; max-width: 1700px; margin: 0 auto; }}
  header {{ margin-bottom: 24px; }}
  header h1 {{ margin: 0 0 4px; font-size: 1.5rem; }}
  header .sub {{ color: var(--text-secondary); font-size: 0.95rem; }}
  .meta-row {{
    display: flex; flex-wrap: wrap; gap: 8px 16px; margin-top: 12px;
    font-size: 0.85rem; color: var(--text-secondary);
  }}
  .rule {{
    margin-top: 12px; padding: 12px 14px; background: var(--surface-1);
    border: 1px solid var(--border); border-radius: 8px;
    font-size: 0.88rem; color: var(--text-secondary); line-height: 1.5;
  }}
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  @media (max-width: 760px) {{ .grid-2 {{ grid-template-columns: 1fr; }} }}
  .panel {{
    background: var(--surface-1); border: 1px solid var(--border);
    border-radius: 10px; padding: 16px; margin-bottom: 20px;
  }}
  /* ITFC mode's third colour — a red stripe and underline, not just blue/white */
  :root[data-theme="itfc"] .panel {{ border-left: 4px solid var(--itfc-red); }}
  :root[data-theme="itfc"] .panel-head h2 {{
    display: inline-block; padding-bottom: 3px; border-bottom: 3px solid var(--itfc-red);
  }}
  :root[data-theme="itfc"] header h1 {{
    display: inline-block; padding-bottom: 4px; border-bottom: 4px solid var(--itfc-red);
  }}
  :root[data-theme="itfc"] .theme-toggle {{ border-color: var(--itfc-red); }}
  .panel-head {{
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 12px; gap: 8px; flex-wrap: wrap;
  }}
  .panel-head h2 {{ margin: 0; font-size: 1.05rem; }}
  .badge {{
    font-size: 0.74rem; font-weight: 600; padding: 4px 10px; border-radius: 999px;
    border: 1px solid var(--border); color: var(--text-secondary);
    background: var(--page-plane);
    white-space: nowrap;
  }}
  .badge-live {{ color: var(--good); background: var(--good-bg); border-color: transparent; }}
  .badge-muted {{ color: var(--text-secondary); background: var(--page-plane); }}
  .table-scroll {{ max-height: 520px; overflow-y: auto; }}
  table.league-table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
  table.league-table.small {{ font-size: 0.8rem; }}
  table.league-table th {{
    text-align: left; font-size: 0.75rem; color: var(--text-secondary);
    border-bottom: 1px solid var(--gridline); padding: 6px 8px;
    position: sticky; top: 0; background: var(--surface-1);
  }}
  table.league-table td {{
    padding: 6px 8px; border-bottom: 1px solid var(--gridline);
    font-variant-numeric: tabular-nums;
  }}
  table.league-table td.pos {{ color: var(--text-secondary); width: 2.2em; }}
  table.league-table tr:last-child td {{ border-bottom: none; }}
  table.scores-table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
  table.scores-table th {{
    text-align: left; font-size: 0.75rem; color: var(--text-secondary);
    border-bottom: 1px solid var(--gridline); padding: 6px 8px;
  }}
  table.scores-table td {{ padding: 6px 8px; border-bottom: 1px solid var(--gridline); }}
  table.scores-table tr:last-child td {{ border-bottom: none; }}
  table.scores-table .scores-rank {{ color: var(--text-secondary); width: 2.2em; font-variant-numeric: tabular-nums; }}
  table.scores-table .scores-num {{ font-variant-numeric: tabular-nums; }}
  table.scores-table .scores-total {{ font-weight: 700; }}
  table.scores-table .scores-row-leader {{ background: var(--good-bg); }}
  table.scores-table .scores-row-leader td {{ color: var(--good); font-weight: 700; }}
  .empty-state {{ color: var(--text-secondary); font-size: 0.9rem; line-height: 1.5; margin: 4px 0; }}
  .leaderboard {{ display: flex; flex-direction: column; gap: 10px; }}
  .lb-row {{
    display: grid;
    grid-template-columns: 28px 1fr 2fr auto;
    grid-template-areas: "rank name bar total" ". . split split";
    align-items: center; gap: 4px 10px;
  }}
  .lb-rank {{ grid-area: rank; color: var(--text-secondary); font-size: 0.85rem; font-variant-numeric: tabular-nums; }}
  .lb-name {{ grid-area: name; font-size: 0.9rem; display: flex; align-items: center; gap: 6px; }}
  .lb-bar-wrap {{ grid-area: bar; background: var(--gridline); border-radius: 4px; height: 10px; overflow: hidden; }}
  .lb-bar {{ background: var(--series-1); height: 100%; border-radius: 4px; }}
  .lb-total {{ grid-area: total; font-size: 0.9rem; font-variant-numeric: tabular-nums; white-space: nowrap; }}
  .lb-split {{ grid-area: split; font-size: 0.75rem; color: var(--text-secondary); }}
  .tag {{ font-size: 0.68rem; padding: 2px 6px; border-radius: 999px; }}
  .tag-good {{ color: var(--good); background: var(--good-bg); }}
  .tag-critical {{ color: var(--critical); background: var(--critical-bg); }}
  footer {{ margin-top: 24px; font-size: 0.78rem; color: var(--text-secondary); text-align: center; }}
  .grid-scroll {{ overflow-x: auto; }}
  table.pred-grid-table {{
    border-collapse: collapse; font-size: 0.78rem; white-space: nowrap;
  }}
  table.pred-grid-table th, table.pred-grid-table td {{
    padding: 4px 8px; text-align: left; border: 1px solid var(--gridline);
  }}
  table.pred-grid-table thead th {{
    font-size: 0.72rem; color: var(--text-secondary); font-weight: 600;
    border-bottom: 2px solid var(--gridline); white-space: nowrap;
    position: sticky; top: 0; background: var(--surface-1);
  }}
  .grid-pos-head {{ position: sticky; left: 0; z-index: 2; background: var(--surface-1); }}
  .grid-actual-head {{ color: var(--text-primary) !important; }}
  .grid-pos {{
    position: sticky; left: 0; background: var(--surface-1);
    color: var(--text-secondary); font-variant-numeric: tabular-nums;
    text-align: center; border-right: 2px solid var(--gridline);
  }}
  .grid-cell {{ font-weight: 600; }}
  .grid-cell-empty {{ background: var(--page-plane); color: var(--text-secondary); font-weight: 400; text-align: center; }}
  .grid-score-chip {{
    font-size: 0.68rem; font-weight: 700; color: var(--text-secondary);
    font-variant-numeric: tabular-nums;
  }}
  .grid-total-row td {{ border-top: 2px solid var(--gridline); font-weight: 700; }}
  .grid-total-label {{ text-align: right; color: var(--text-secondary); font-weight: 600; }}
  .grid-total {{ text-align: center; font-variant-numeric: tabular-nums; }}
  .header-row {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }}
  .theme-toggle {{
    flex: 0 0 auto; font-size: 0.78rem; font-weight: 600; padding: 6px 12px;
    border-radius: 999px; border: 1px solid var(--border); background: var(--surface-1);
    color: var(--text-primary); cursor: pointer; white-space: nowrap;
  }}
  .theme-toggle:hover {{ background: var(--page-plane); }}
</style>
</head>
<body>
<div class="viz-root">
  <header>
    <div class="header-row">
      <h1>{esc(data.get('game_name', 'League Predictions Tracker'))}</h1>
      <button class="theme-toggle" id="themeToggle" type="button" onclick="toggleTheme()">Dark mode</button>
      <!-- cycles Light → Dark → ITFC → Light; label always shows the mode you're about to switch TO -->
    </div>
    <div class="sub">Predict the final Premier League and Championship tables. Score = total distance between predicted and actual finishing position, summed across every team. Lowest combined score wins the group; highest loses.</div>
    <div class="meta-row">
      <span>Season {esc(data.get('season',''))}</span>
      <span>Results last checked: {esc(last_checked_display)}</span>
      <span>Dashboard generated: {esc(generated_display)}</span>
    </div>
  </header>

  {scores_row_html()}

  {actual_tables_row_html()}

  {predictions_section_html()}

  <footer>Auto-refreshed daily from live standings. Add participants and predictions to the tracker's data file to activate scoring.</footer>
</div>
<script>
  var THEME_ORDER = ['light', 'dark', 'itfc'];
  var THEME_LABELS = {{ light: 'Light mode', dark: 'Dark mode', itfc: 'ITFC mode' }};

  function nextTheme(current) {{
    var idx = THEME_ORDER.indexOf(current);
    return THEME_ORDER[(idx + 1) % THEME_ORDER.length];
  }}

  function updateToggleLabel() {{
    var current = document.documentElement.getAttribute('data-theme') || 'light';
    document.getElementById('themeToggle').textContent = THEME_LABELS[nextTheme(current)];
  }}

  function toggleTheme() {{
    var root = document.documentElement;
    var current = root.getAttribute('data-theme') || 'light';
    root.setAttribute('data-theme', nextTheme(current));
    updateToggleLabel();
  }}

  updateToggleLabel();
</script>
</body>
</html>
"""

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write(html_out)

print(f"Wrote {OUT_PATH}")
