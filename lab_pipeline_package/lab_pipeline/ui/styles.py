from __future__ import annotations

from IPython.display import HTML, display


APP_CSS = """
<style>
.lab-app-shell {
  font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: #1f2933;
}
.lab-header {
  background: #1f4e78;
  color: white;
  padding: 18px 22px;
  border-radius: 8px;
  margin-bottom: 14px;
}
.lab-header h1 {
  margin: 0;
  font-size: 28px;
  line-height: 1.15;
  letter-spacing: 0;
}
.lab-header p {
  margin: 6px 0 0 0;
  color: #dcebf7;
}
.lab-card {
  border: 1px solid #d7dee8;
  border-radius: 8px;
  padding: 14px 16px;
  margin: 8px 0;
  background: #ffffff;
}
.lab-card h3 {
  margin: 0 0 6px 0;
  font-size: 17px;
  letter-spacing: 0;
}
.lab-muted {
  color: #66788a;
  font-size: 13px;
}
.lab-status {
  border-radius: 6px;
  padding: 9px 11px;
  margin: 8px 0;
  border: 1px solid #c8d4e3;
  background: #f5f8fb;
}
.lab-status.success {
  border-color: #9dd3aa;
  background: #eef8f1;
}
.lab-status.error {
  border-color: #f3a6a6;
  background: #fff1f1;
}
.lab-status.warning {
  border-color: #e6cc83;
  background: #fff8e5;
}
.lab-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 10px;
}
.lab-output-link {
  display: block;
  margin: 4px 0;
}
</style>
"""


def inject_styles() -> None:
    display(HTML(APP_CSS))

