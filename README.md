# SplitEase

A Splitwise-style web app for splitting group expenses. Django, PostgreSQL (SQLite locally), custom CSS.

## Features
- Accounts, groups, and invite links; add guests who have no account
- Expenses split equally, by exact amount, by percentage, or by shares
- Money stored as integer centavos; uneven splits use the largest-remainder method so shares always sum exactly
- Live balances per member, plus debt simplification (at most n-1 payments to clear a group)
- Record payments to settle up; delete expenses (payer or group owner)

## Run locally
```
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
python manage.py test        # unit tests for split + settlement logic
```

## Deploy
Set `SECRET_KEY`, `DEBUG=0`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` and `DATABASE_URL` (PostgreSQL), then run
`python manage.py migrate && python manage.py collectstatic`. Any host that runs Django works (Render, Railway, Fly.io, etc.).
Vercel needs extra serverless config for Django, so a persistent-server host is simpler.

## Layout
- `bills/services.py` – split, balance, and simplification logic (the part worth explaining in interviews)
- `bills/tests.py` – tests for all of the above
