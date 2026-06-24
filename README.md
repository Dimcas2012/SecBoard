# SecBoard Community Edition

Open Core ISMS / GRC platform — **AGPL v3** + Dual License model.

SecBoard Community Edition provides the full open-core stack (GRC, ISMS, risk, compliance, access, and more) for self-hosting, NGOs, pilots, and small teams — up to **100 users** with a free community license key.

**Enterprise Edition** (commercial license) is available for production at scale, closed modifications, enterprise modules, and SLA.

See **[LICENSING.md](LICENSING.md)** for the complete licensing model.

## Features

- Multi-tenant company and user management (`app_cabinet`)
- Site configuration, licensing, public pages (`app_conf`)
- AI assistant (`app_ai`)
- Open-core ISMS modules: risk, compliance, GDPR, access, assets, incidents, SOC, and more
- Celery + Redis for background tasks
- i18n: English, Ukrainian, Russian

## Requirements

- Python 3.12+
- MySQL 8+ or MariaDB 10.6+
- Redis (for Celery)
- Ubuntu/Debian build deps: `python3-venv python3-dev default-libmysqlclient-dev build-essential pkg-config`

## Quick start

```bash
cp .env.example .env
# Edit .env — set SECRET_KEY, DB_*, ALLOWED_HOSTS, SITE_DOMAIN

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
python manage.py check
```

### License activation (required)

A valid **community** or **enterprise** license key is required to run the platform.

```bash
python manage.py get_hardware_id
# Request a free community key: https://secboard.online (subject to ToS/AUP)

python manage.py activate_license YOUR_COMMUNITY_KEY
python manage.py runserver
```

Or activate via UI: `/about/license/activate/`

Open `http://127.0.0.1:8000/`.

## Licensing summary

| Edition | License | Key | Users |
|---------|---------|-----|-------|
| **Community** | AGPL v3 | Free community key | Up to 100 |
| **Enterprise** | Commercial | Paid key | Per contract |

- **Forks:** allowed under AGPL; network use requires source availability.
- **Sanctions:** community/commercial keys are not issued for restricted jurisdictions (see [Terms of Service](/terms-of-service/)).
- **No redistribution of proprietary forks** without AGPL compliance (Community) or Commercial License (Enterprise scenarios).

Full details: [LICENSING.md](LICENSING.md) · [LICENSE](LICENSE) · [LICENSE-COMMERCIAL](LICENSE-COMMERCIAL) · [CONTRIBUTING.md](CONTRIBUTING.md)

## Production deployment

See `deploy/secboard_base.service.example` and `deploy/nginx.example.conf`.

1. Install app under `/opt/secboard-base`
2. Configure `.env` with `DEBUG=0`
3. Activate license key
4. `collectstatic`, `migrate`
5. systemd + nginx + gunicorn (port 9006 by default)

## Building a release archive

```bash
./scripts/build_release.sh 1.0.0
```

## Extending the platform

See `SDK/README.md` for conventions when adding custom Django apps.

## Documentation

- `commands.txt` — common Django/Celery commands (EN/UK)
- `.env.example` — configuration reference
- `LICENSING.md` — Open Core + Dual License model

## Security

- Never commit `.env` or license keys
- Rotate `SECRET_KEY` and database passwords per installation
- Set `DEBUG=0` in production
