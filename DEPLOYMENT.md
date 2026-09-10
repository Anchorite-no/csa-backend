# Recruitment deadline configuration

The recruitment deadline is stored under `recruit_deadline` in the database's
`site_setting` table. Every request reads the current database value; changing
the deadline in the admin page takes effect across all workers without restart.

The API accepts ISO 8601 date-times. Values without an offset use Beijing time
(`Asia/Shanghai`, UTC+08:00); legacy date-only inputs use 23:59 on that date.
The form closes at the specified instant. The public response includes an
explicit offset, the server time, and `is_open`, so browser timezone or clock
differences do not decide whether an application can be submitted.

For the first deployment, back up the database and `.env`, then run once from
the backend working directory using the application's Python environment:

```sh
python -m misc.recruit_deadline
```

This creates only the new settings table and seeds it from the existing
`RECRUIT_DEADLINE` when no database value exists. It never overwrites a saved
database deadline with the legacy environment setting. Run this before
starting multiple workers. Existing installations managed through Alembic
can use migration `6e862f28b037` to create the table as well.

To deliberately set a deadline during deployment:

```sh
python -m misc.recruit_deadline --set '2026-09-30T23:59:00+08:00'
```

Then restart the application once to load the new code. Subsequent admin
deadline changes require no restart. Authentication on the admin API remains
enforced by its existing router dependencies. Expired application submissions
are also rejected by the backend before changing data or sending notifications.

Regression tests use temporary databases and a loopback-only four-worker
Uvicorn fixture; no production data or notifications are used:

```sh
python -m unittest tests.test_recruit_deadline -v
```

## New enrollment cohorts

The public `/api/recruit/options` endpoint supplies the current Beijing year,
valid enrollment grades, and the grades with an installed official major CSV.
For a cohort without a catalog (including 2026 at this deployment), applicants
enter their actual major and college. No older cohort's catalog or identifiers
are substituted. The database stores null major/college identifiers and the
admin API/UI marks these undergraduate entries as requiring verification.
Adding a verified `major/specialties_data_2026.csv` automatically enables catalog
selection for subsequent applications; previously hand-entered records remain
marked for verification.

## Admission notification contacts

Copy `config/recruitment.example.json` to `config/recruitment.json` and fill in
the current ministers' WeChat IDs before deploying the admission route:

- `office`: 办公室部
- `competition`: 竞赛部
- `research`: 科研部
- `activity`: 活动部

Keep `config/recruitment.json` on the server and copy it into each new backend
release. Git ignores this file; the repository contains only an empty example.
The file is resolved relative to the backend source directory, independent of
the process's working directory. Keep it readable by the backend service user.

Restart the backend once after deploying the new Python code. Later contact
changes take effect on the next admission without restarting any workers.
Replace the JSON file atomically when updating it. Invalid JSON, missing files,
or an empty/invalid contact for the selected department reject the operation
before admission, account changes, or DingTalk notification delivery.

Run contact and admission regressions with mocked notification delivery:

```sh
DB_PATH=sqlite:///:memory: python -m unittest tests.test_recruit_contacts -v
```
