# SecBoard Community Edition

Open Core ISMS / GRC Platform for Information Security, Compliance and Governance.

AGPL v3 licensed community edition with a dual-license model for enterprise deployments.

[SecBoard Community Edition](docs/social-preview.jpg)

## 🚀 Overview

SecBoard Community Edition provides a complete open-core stack for building and operating an Information Security Management System (ISMS).

Designed for organizations implementing:

* ISO 27001
* PCI DSS
* GDPR
* NIS2
* Internal Security Programs
* Risk Management Frameworks

The platform is suitable for self-hosting, NGOs, pilots, educational projects, startups, and small teams.

### Community Edition

✅ AGPL v3 Open Source

✅ Risk Management

✅ Compliance Management

✅ GDPR Management

✅ Access Management

✅ Asset Management

✅ Incident Management

✅ SOC Operations

✅ Self-Hosted

✅ Free Community License (up to 100 users)

### Enterprise Edition

Commercial licensing for:

* Production deployments at scale
* Closed-source modifications
* Enterprise modules
* Priority support
* SLA agreements

See [LICENSING.md](LICENSING.md) for details.

---

## 🎬 Video Demo

[Watch SecBoard Demo on YouTube](https://www.youtube.com/@SecBoard)

Watch product demonstrations, installation guides, compliance workflows, and release updates on the official SecBoard YouTube channel.

📺 YouTube: https://www.youtube.com/@SecBoard

---

## ✨ Key Features

### Governance, Risk & Compliance

* Risk Register
* Risk Assessments
* Risk Treatment Plans
* Compliance Management
* Internal Controls
* Evidence Collection
* Audit Preparation

### Security Operations

* Incident Management
* Security Event Tracking
* Corrective Actions
* Vulnerability Tracking
* SOC Operations

### Asset & Access Management

* Asset Inventory
* Asset Ownership
* Access Reviews
* User Management
* Role-Based Access Control

### Platform

* Multi-tenant architecture
* AI Assistant
* Celery + Redis background processing
* Licensing subsystem
* Public and internal portals
* English, Ukrainian and Russian localization

---

## 📦 Requirements

* Python 3.12+
* MySQL 8+ or MariaDB 10.6+
* Redis
* Ubuntu/Debian build dependencies:

```bash
python3-venv
python3-dev
default-libmysqlclient-dev
build-essential
pkg-config
```

---

## ⚡ Quick Start

```bash
cp .env.example .env

# Edit:
# SECRET_KEY
# DB_*
# ALLOWED_HOSTS
# SITE_DOMAIN

python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser
python manage.py init_site_settings
python manage.py collectstatic --noinput
python manage.py check
```

Optional setup commands:

```bash
python manage.py load_company_types
python manage.py setup_all_periodic_tasks
```

---

## 🔑 License Activation

A valid Community or Enterprise license key is required.

Generate hardware ID:

```bash
python manage.py get_hardware_id
```

Request a free Community key:

https://secboard.online

Activate:

```bash
python manage.py activate_license YOUR_COMMUNITY_KEY
python manage.py runserver
```

Or activate from:

```text
/about/license/activate/
```

Open:

```text
http://127.0.0.1:8000/
```

---

## 📊 Licensing

| Edition            | License    | Users        |
| ------------------ | ---------- | ------------ |
| Community Edition  | AGPL v3    | Up to 100    |
| Enterprise Edition | Commercial | Per Contract |

Full details:

* LICENSE
* LICENSE-COMMERCIAL
* LICENSING.md
* CONTRIBUTING.md

---

## 🎥 Demo Videos

Available on the SecBoard YouTube Channel:

* Platform Overview
* Installation Guide
* Risk Management
* Compliance Management
* Asset Inventory
* Incident Management
* Access Reviews
* PCI DSS Workflows
* ISO 27001 Workflows

https://www.youtube.com/@SecBoard

---

## 🚀 Production Deployment

Deployment examples:

* deploy/secboard_base.service.example
* deploy/nginx.example.conf

Production checklist:

1. Install under `/opt/secboard-base`
2. Configure `.env`
3. Set `DEBUG=0`
4. Activate license
5. Run migrations
6. Collect static files
7. Configure Gunicorn + Nginx + Systemd

---

## 🔒 Security

* Never commit `.env`
* Never commit license keys
* Rotate database credentials
* Rotate SECRET_KEY when required
* Set `DEBUG=0` in production

---

## 🤝 Contributing

Contributions, bug reports, feature requests and pull requests are welcome.

See:

* CONTRIBUTING.md
* SDK/README.md

---

## 🌐 Community

Website: https://secboard.online

GitHub: https://github.com/Dimcas2012/SecBoard

YouTube: https://www.youtube.com/@SecBoard

Open. Secure. Together.
