"""Export the availability grid as a self-contained HTML file and open it.

For privacy the export shows only Available (green) vs not — busy task titles are not
included. A slot counts as available only if the user marked it AND it isn't busy.
"""

from __future__ import annotations

import datetime
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from app.ui.availability_view import AvailSetup, AvailState, BusyMap


def _html(setup: AvailSetup, state: AvailState, busy: BusyMap) -> str:
    dates = setup.dates()
    slots = setup.slots_per_day()
    avail = {k: set(v) for k, v in state.items()}

    header_cells = "".join(
        f'<th><span class="dow">{d.strftime("%a")}</span><br>'
        f'<span class="dnum">{d.strftime("%b")} {d.day}</span></th>'
        for d in dates
    )

    body_rows = ""
    for r in range(slots):
        cells = ""
        for d in dates:
            d_iso = d.isoformat()
            is_busy = r in busy.get(d_iso, {})
            free = (r in avail.get(d_iso, set())) and not is_busy
            cells += f'<td class="{"a" if free else "u"}"></td>'
        body_rows += (
            f'<tr><td class="t">{setup.slot_label(r)}</td>{cells}</tr>'
        )

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>Availability — {setup.date_label()}</title>
<style>
  body {{ font-family:-apple-system,"Segoe UI",sans-serif; background:#1b1d22; color:#e6e8ec;
         display:flex; flex-direction:column; align-items:center; padding:32px 16px; margin:0; }}
  h1 {{ font-size:20px; margin:0 0 4px; }}
  .sub {{ color:#8b909a; font-size:13px; margin-bottom:20px; }}
  .legend {{ display:flex; gap:18px; margin-bottom:16px; font-size:13px; }}
  .sw {{ width:14px; height:14px; border-radius:3px; display:inline-block; margin-right:5px;
        vertical-align:-2px; }}
  table {{ border-collapse:collapse; }}
  th {{ font-weight:400; padding:4px 2px 8px; }}
  .dow {{ font-size:11px; color:#8b909a; }}
  .dnum {{ font-weight:700; font-size:13px; }}
  td {{ width:90px; height:30px; border:1px solid #3a3e48; }}
  td.t {{ width:64px; border:none; text-align:right; padding-right:8px; font-size:11px;
         color:#8b909a; white-space:nowrap; }}
  td.a {{ background:#2d7a3f; }}
  td.u {{ background:#2c2f37; }}
</style></head>
<body>
<h1>My Availability</h1>
<div class="sub">{setup.date_label()} &nbsp;·&nbsp;
{setup.slot_label(0)} – {setup.slot_label(slots)}</div>
<div class="legend">
  <span><span class="sw" style="background:#2c2f37;border:1px solid #3a3e48"></span>Unavailable</span>
  <span><span class="sw" style="background:#2d7a3f"></span>Available</span>
</div>
<table><thead><tr><th></th>{header_cells}</tr></thead>
<tbody>{body_rows}</tbody></table>
</body></html>"""


def export_and_open(setup: AvailSetup, state: AvailState, busy: BusyMap) -> None:
    today = datetime.date.today().isoformat()
    path = Path.home() / "Desktop" / f"availability_{today}.html"
    path.write_text(_html(setup, state, busy), encoding="utf-8")
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
