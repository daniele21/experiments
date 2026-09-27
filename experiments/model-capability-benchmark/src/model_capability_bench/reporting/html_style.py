REPORT_CSS = """
:root {
  color-scheme: light dark;
  --bg: #f7f7f8;
  --panel: #ffffff;
  --text: #171719;
  --muted: #65656d;
  --line: #dedee3;
  --soft: #f0f0f3;
  --accent: #2d4c7c;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #111114;
    --panel: #19191d;
    --text: #f3f3f4;
    --muted: #aaaab2;
    --line: #33333a;
    --soft: #232329;
    --accent: #9ebce7;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--text);
  font: 14px/1.5 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
main { max-width: 1500px; margin: 0 auto; padding: 32px 24px 80px; }
header, section {
  background: var(--panel); border: 1px solid var(--line);
  border-radius: 14px; padding: 24px; margin-bottom: 18px;
}
h1 { margin: 0 0 8px; font-size: 28px; }
h2 { margin: 0 0 12px; font-size: 20px; }
h3 { margin: 22px 0 10px; font-size: 16px; }
h5 { margin: 0 0 6px; }
.meta, .section-note { color: var(--muted); }
.meta { display: flex; flex-wrap: wrap; gap: 10px 22px; }
.note {
  border-left: 3px solid var(--accent); padding: 10px 12px;
  background: var(--soft); margin-top: 18px;
}
.table-wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; min-width: 720px; }
th, td {
  border-bottom: 1px solid var(--line); padding: 10px 12px;
  text-align: left; vertical-align: top;
}
thead th { background: var(--soft); position: sticky; top: 0; }
.row-head span {
  display: block; color: var(--muted); font-weight: 400; font-size: 12px;
}
.metric-cell { min-width: 160px; }
.metric-value { font-size: 20px; font-weight: 700; }
.metric-name, .metric-meta { color: var(--muted); font-size: 12px; }
.model-details {
  border: 1px solid var(--line); border-radius: 10px;
  padding: 10px 12px; margin: 8px 0;
}
summary { cursor: pointer; font-weight: 650; }
pre {
  white-space: pre-wrap; overflow-wrap: anywhere; max-width: 620px;
  padding: 10px; border-radius: 8px; background: var(--soft);
}
pre.compact { margin: 0; padding: 6px; max-height: 140px; overflow: auto; }
.evidence-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 12px; margin-top: 10px;
}
.case-table { margin-top: 10px; }
code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
"""
