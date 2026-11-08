# Adding a service (new work for a role)

A service is a folder in `app/services/`. It only **builds tables** — the core
does Excel, PDF, images, history, preview, WhatsApp and scheduling.

## Steps

1. Copy `app/services/_template` to `app/services/<service_id>`
   (lowercase with underscores, e.g. `hr_attendance`).
2. In `__init__.py` fill in `SERVICE`:
   - `id`, `name`, `description`
   - `roles` — e.g. `["hr_assistant"]`
   - `sfa_pages` — page keys it downloads (set up in Settings → SFA pages)
   - `reports` — one `ReportDef(id, name, build_function)` per report.
     Report ids must be unique across Hydra.
   - `readiness` — returns `[{"item", "ok", "detail", "needed_by"}]` for the Run Center data check.
3. Write each builder in `reports.py`: `def my_report(d: date) -> Table`.
   - `Column(key, header, kind, width, sum, formula, calc)` — kind is
     `text | money | int | pct | number`. A formula column gives both the Excel
     template (`"=IF({b}=0,0,{a}/{b})"`) and the Python `calc` so PDF/PNG show values.
   - `Row(kind, label, values, children, level, style)` — kind `territory |
     subtotal | total | plain`; `style="winner"` or `"red"`.
   - Raise a `ReportError("clear message")` when data is missing; the run carries on
     with the other reports.
4. Add the id to `INSTALLED` in `app/services/__init__.py`.
5. Add `tests/test_<service_id>.py`; run `python -m pytest -q tests`.

## Rules

- Never write files from a service; return a `Table`.
- Read data through `app.db` (tables are created by migrations in `app/db.py` —
  add a new migration version for new tables, never edit an old one).
- Keep company data (sample Excel files) out of the repo; tests read them from
  the folder in the `HYDRA_SAMPLES` environment variable.
