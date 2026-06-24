# SecBoard — Open Core + Dual License

**Єдиний орієнтир для публікації та комерції.**  
Цей документ описує обрану модель ліцензування SecBoard Community Edition (цей репозиторій) та SecBoard Enterprise Edition.

## Модель

| | Community Edition | Enterprise Edition |
|---|---|---|
| **Ліцензія на код** | AGPL v3 | Commercial License (proprietary) |
| **Аудиторія** | НУО, пілоти, малі команди, спільнота, EU evaluation | Компанії в production, enterprise, інтегратори |
| **GitHub** | Повний source, форки, PR | Той самий репозиторій; платні можливості — за ключем/договором |
| **License server** | Так (`license.secboard.online`) | Так |
| **License key** | Безкоштовний community key | Платний enterprise key |
| **Ліміти** | до 100 users (м'який cap) | За контрактом (seats / unlimited tiers) |
| **Модулі** | Open core (базовий GRC/ISMS стек) | Усі модулі (+ AI, GoPhish, advanced SOC тощо) |
| **Зміни коду** | Форки під AGPL — network use → copyleft | Зміни можна не публікувати |
| **Support / SLA** | Community (docs, issues) | Платний SLA, security advisories |
| **Білди** | Збірка з source (`.py`) | Офіційні signed/compiled білди (опційно) |
| **Дохід** | — | Підписка / seat / module |

---

## Community Edition (AGPL v3)

```
Community Edition
├── AGPL v3 — форки дозволені, network use → copyleft
├── Безкоштовний community license key (license server)
├── Ліміт: до 100 користувачів (enforced через key / max_users)
├── Відкритий GitHub, issues, PR, CONTRIBUTING
├── Open core модулі (повний базовий GRC/ISMS стек)
└── Санкції: LICENSE + ToS + відмова в community key для restricted jurisdictions
```

### Навіщо key при AGPL

AGPL дає право на код; **key — це не заміна ліцензії**, а технічний + договірний контроль:

- ліміт users (`max_users`)
- heartbeat та offline grace
- блокування санкційних юрисдикцій
- telemetry для security updates (за потреби)

**Популярність:** висока — можна форкнути, аудитувати, self-host без оплати (до 100 users).

### Активація Community

1. `python manage.py get_hardware_id` — отримати Server ID
2. Запросити безкоштовний community key: https://secboard.online (за умови відповідності ToS/AUP)
3. `python manage.py activate_license YOUR_COMMUNITY_KEY`
4. Або через UI: `/about/license/activate/`

---

## Enterprise Edition (Commercial)

```
Enterprise Edition
├── Commercial License — без copyleft
├── Платний license key + license server
├── max_users / modules / term — з Order Form
├── Усі модулі, SLA, пріоритетні патчі
├── Офіційні enterprise-білди (.so / manifest integrity — опційно)
└── Дохід: річна підписка, per-seat, per-module, implementation
```

### Навіщо платити, якщо є AGPL

- більше 100 users
- закриті зміни без публікації
- enterprise-модулі
- SLA, DPA, indemnification (за tier)
- офіційна підтримка та відповідальність

Деталі: [LICENSE-COMMERCIAL](LICENSE-COMMERCIAL)

---

## Санкції (важливе уточнення)

| Де | Що |
|---|---|
| **ToS / Acceptable Use Policy** | Заборона для РФ, РБ, Іран, КНДР, окупованих територій України, sanctioned persons |
| **License server** | Не видавати / revoke community і commercial keys |
| **AGPL-текст** | Не додавати geo-обмеження в тіло AGPL (суперечить copyleft/OSI) |
| **Окремий rider** | Use of SecBoard trademark/services subject to AUP — узгодити з юристом |

**Код під AGPL; сервіс ключів і комерція — під умовами SecBoard та санкціями.**

---

## Dual License — як це працює для клієнта

| Сценарій | Рішення |
|---|---|
| Self-host, &lt;100 users, відкриті зміни | Community (AGPL) + free key |
| &gt;100 users або закритий форк | Commercial License |
| Enterprise-модулі / SLA | Enterprise subscription |
| Інтегратор вбудовує в proprietary продукт | Commercial (не AGPL) |

---

## Файли в репозиторії

| Файл | Призначення |
|---|---|
| [LICENSE](LICENSE) | AGPL v3 для Community Edition source |
| [LICENSE-COMMERCIAL](LICENSE-COMMERCIAL) | Підсумок комерційних умов Enterprise |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Правила внеску (AGPL для PR) |
| `/terms-of-service/` | ToS + AUP (санкції) |
| `/privacy-policy/` | Privacy Policy |

---

## Технічна реалізація

- `LICENSE_SERVER_URL` → `https://license.secboard.online/api/v1/`
- `SecureLicenseMiddleware` — перевірка ключа на кожному запиті
- `max_users` — ліміт активних Django users
- `verification_enforced` — політика сервера (community vs relaxed dev)
- `source` — тип ліцензії з payload ключа

**Без права розповсюджувати власні модифікації як пропрієтарний продукт без дотримання AGPL** (для Community) або без Commercial License (для Enterprise use cases).
