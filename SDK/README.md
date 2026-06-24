# SecBoard Community Edition SDK

Conventions for building custom `app_*` modules on SecBoard Community Edition.

## Licensing

This repository is **Community Edition** under **AGPL v3**. Custom modules you distribute
with SecBoard must comply with AGPL (or you must obtain a **Commercial License** for
proprietary integration). See [LICENSING.md](../LICENSING.md).

## Core apps (open core)

| App | Role |
|-----|------|
| `app_conf` | Site settings, license, public pages, admin extensions |
| `app_cabinet` | Users, companies, groups, authentication UI |
| `app_ai` | AI assistant endpoints and configuration |

Additional ISMS modules (`app_risk`, `app_compliance`, `app_access`, etc.) are included
in the open-core source tree. Enterprise-only capabilities may require an Enterprise key.

## Creating a new module

```bash
python manage.py startapp app_myfeature
```

1. Register in `SecBoard/settings.py` → `INSTALLED_APPS`
2. Add URL include in `SecBoard/urls.py`
3. Add templates under `app_myfeature/templates/`
4. Use `app_cabinet` permissions and company scoping where applicable
5. Ship migrations with your app

## Integration points

- **Menu / dashboard**: extend via `app_cabinet` role dashboard config or context processors
- **License**: community key required; optional module checks via `app_conf.license_manager`
- **Celery**: register tasks in your app; run `setup_periodic_tasks` pattern from `app_keycert` as reference

## Example layout

```
app_myfeature/
  models.py
  views.py
  urls.py
  migrations/
  templates/app_myfeature/
  static/app_myfeature/
```

## Publishing

- **AGPL path**: publish source of your module with AGPL-compatible license.
- **Commercial path**: contact SecBoard for Commercial License if integrating into a
  proprietary product without copyleft obligations.

https://secboard.online · support@secboard.online
