# App GDPR - GDPR Compliance Management Module

## Опис

Модуль для автоматизації процесів, пов'язаних з GDPR (General Data Protection Regulation) у компанії. Забезпечує повний цикл управління персональними даними згідно з вимогами GDPR.

## Основні можливості

### 1. Управління суб'єктами даних (Data Subjects)
- Реєстр всіх суб'єктів даних
- Управління згодами на обробку
- Автоматичне планування видалення/анонімізації
- Експорт даних (право на переносимість)

### 2. Запити суб'єктів даних (DSR - Data Subject Requests)
- Право на доступ (Article 15)
- Право на виправлення (Article 16)
- Право на видалення/забуття (Article 17)
- Право на обмеження обробки (Article 18)
- Право на переносимість даних (Article 20)
- Право на заперечення (Article 21)
- Автоматичний контроль дедлайнів (30 днів)

### 3. Управління інцидентами витоку даних (Data Breach)
- Реєстрація інцидентів
- 72-годинний дедлайн для повідомлення (Article 33)
- Автоматичні нагадування
- Повідомлення постраждалих осіб (Article 34)

### 4. DPIA (Data Protection Impact Assessment)
- Оцінка впливу на захист даних (Article 35)
- Оцінка ризиків
- Заходи безпеки
- Процес затвердження

### 5. Реєстр діяльності з обробки даних (Article 30)
- Опис обробки даних
- Правова підстава
- Категорії даних
- Термін зберігання
- Міжнародні передачі

### 6. Політики утримання даних
- Автоматичне застосування політик
- Видалення або анонімізація
- Відповідність термінам зберігання

## Автоматизація

### Celery Tasks (автоматичні задачі)

#### Щоденні задачі:
- `check_consent_expiration` - перевірка закінчення згод
- `check_data_retention_deadlines` - перевірка термінів утримання
- `send_dsr_deadline_reminder` - нагадування про DSR дедлайни

#### Щогодинні задачі:
- `check_breach_notification_deadline` - контроль 72-годинного дедлайну

#### Щотижневі задачі:
- `generate_gdpr_compliance_report` - звіт про відповідність

#### Щомісячні задачі:
- `cleanup_old_anonymized_data` - очищення старих даних
- `audit_data_processing_activities` - аудит обробки даних

## Management Commands

### Генерація звіту
```bash
# Для всіх компаній
python manage.py generate_gdpr_report

# Для конкретної компанії
python manage.py generate_gdpr_report --company 1

# У форматі JSON
python manage.py generate_gdpr_report --output json
```

### Очищення даних
```bash
# Dry run (без змін)
python manage.py cleanup_expired_data --dry-run

# Реальне виконання
python manage.py cleanup_expired_data
```

## URL маршрути

### Головний дашборд
- `/app_gdpr/` - GDPR Compliance Dashboard

### Суб'єкти даних
- `/app_gdpr/data-subjects/` - список
- `/app_gdpr/data-subjects/create/` - створити
- `/app_gdpr/data-subjects/<id>/` - деталі
- `/app_gdpr/data-subjects/<id>/export/` - експорт даних
- `/app_gdpr/data-subjects/<id>/anonymize/` - анонімізація

### DSR (Data Subject Requests)
- `/app_gdpr/dsr/` - дашборд DSR
- `/app_gdpr/dsr/create/` - новий запит
- `/app_gdpr/dsr/<id>/` - деталі
- `/app_gdpr/dsr/<id>/process/` - обробка
- `/app_gdpr/dsr/<id>/complete/` - завершити
- `/app_gdpr/dsr/<id>/extend/` - продовжити термін

### Витоки даних
- `/app_gdpr/breaches/` - список
- `/app_gdpr/breaches/create/` - зареєструвати
- `/app_gdpr/breaches/<id>/` - деталі
- `/app_gdpr/breaches/<id>/report/` - повідомити регулятору

### DPIA
- `/app_gdpr/dpia/` - список
- `/app_gdpr/dpia/create/` - нова оцінка
- `/app_gdpr/dpia/<id>/` - деталі
- `/app_gdpr/dpia/<id>/approve/` - затвердити

### Звіти
- `/app_gdpr/reports/` - звіт про відповідність

## Email повідомлення

Автоматичні повідомлення:
- Підтвердження отримання DSR
- Повідомлення про завершення DSR
- Нагадування про закінчення згод
- Попередження про дедлайни
- Повідомлення про витоки даних

## Права доступу

Налаштовується через модель `GDPRAccess` для кожної групи користувачів:

### Базові права доступу (перегляд)
Права з префіксом `has_access_*` дозволяють перегляд відповідних розділів:

- `has_access_compliance_dashboard` - доступ до головного дашборду GDPR
- `has_access_data_subjects` - перегляд суб'єктів даних
- `has_access_dsr` - перегляд DSR (Data Subject Requests)
- `has_access_consents` - перегляд згод
- `has_access_breach_management` - перегляд інцидентів витоку даних
- `has_access_dpia` - перегляд DPIA оцінок

### Додаткові права (дії)
Права з префіксом `can_*` дозволяють виконувати специфічні операції:

#### Data Subjects
- `can_export_data_subjects` - експорт даних суб'єктів

#### DSR Management
- `can_process_dsr` - створення та обробка DSR
- `can_approve_dsr` - затвердження та завершення DSR

#### Consent Management
- `can_manage_consents` - створення та відкликання згод

#### Breach Management
- `can_report_breach` - створення повідомлень про витоки
- `can_investigate_breach` - розслідування та оновлення інцидентів

#### DPIA
- `can_conduct_dpia` - створення та проведення DPIA оцінок
- `can_approve_dpia` - затвердження DPIA

#### Reporting
- `can_generate_reports` - генерація звітів відповідності

## Використання в коді

### Перевірка прав доступу

```python
from app_gdpr.permissions import has_gdpr_permission, require_gdpr_permission

# У view функціях
@require_gdpr_permission('can_process_dsr')
def process_dsr_view(request, dsr_id):
    ...

# У class-based views
from app_gdpr.permissions import GDPRPermissionMixin

class DSRProcessView(GDPRPermissionMixin, UpdateView):
    required_permission = 'can_process_dsr'
    ...

# Програмна перевірка
if has_gdpr_permission(request.user, 'can_export_data_subjects'):
    # Дозволити експорт
```

### Робота з даними

```python
from app_gdpr.utils import (
    export_data_subject_data,
    anonymize_personal_data,
    generate_compliance_report_data
)

# Експорт даних суб'єкта
response = export_data_subject_data(data_subject, format='json')

# Анонімізація
anonymize_personal_data(data_subject)

# Звіт про відповідність
report = generate_compliance_report_data(company=company)
```

### Email повідомлення

```python
from app_gdpr.email_utils import (
    send_dsr_confirmation_email,
    send_dsr_completion_email,
    send_breach_notification_email
)

# Підтвердження DSR
send_dsr_confirmation_email(dsr)

# Завершення DSR
send_dsr_completion_email(dsr)

# Повідомлення про витік
send_breach_notification_email(incident, recipients=['email@example.com'])
```

## Адміністрування

Всі моделі доступні через Django Admin панель (`/secboard_admin/`) з розширеним функціоналом:
- Кольорові badge для статусів
- Фільтри по датам, статусам, компаніям
- Пошук по ключових полях
- Попередження про прострочені дедлайни

## Відповідність GDPR

Модуль реалізує вимоги наступних статей GDPR:
- Article 15: Право на доступ
- Article 16: Право на виправлення
- Article 17: Право на забуття
- Article 18: Право на обмеження обробки
- Article 20: Право на переносимість
- Article 21: Право на заперечення
- Article 30: Реєстр діяльності з обробки
- Article 33: Повідомлення про витік (72 години)
- Article 34: Повідомлення суб'єктів даних
- Article 35: DPIA оцінки

## Підтримка

Для питань та підтримки звертайтесь до команди розробки SecBoard.

