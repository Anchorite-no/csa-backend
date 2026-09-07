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
