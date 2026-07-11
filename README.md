# Laundrex Django Starter

## Quick start (Windows)
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open:
- Login: http://127.0.0.1:8000/accounts/login/
- Admin: http://127.0.0.1:8000/admin/

## Assets location
Put your files inside:
`static/assets/`

Required filenames used by templates:
- laundrex-icon-512x512.png
- laundrex-icon-64x64.png
- favicon.ico
