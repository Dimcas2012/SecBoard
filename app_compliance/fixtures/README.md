# 📦 Local Compliance Fixtures

JSON fixtures для швидкого завантаження sample даних для Local Compliance модуля.

---

## 📂 Файли

### 1. `sample_local_regulators.json`
**Що містить**: 12 регуляторів для України, Литви та Казахстану

**Структура**:
- 🇺🇦 Ukraine: 5 регуляторів (NBU, NSSMC, STS, MinDigital, NFSC)
- 🇱🇹 Lithuania: 3 регулятори (LB, SDPI, ISC)
- 🇰🇿 Kazakhstan: 4 регулятори (NBK, ARDFM, CCPDP, SRC)

**Завантажити**:
```bash
python manage.py loaddata app_compliance/fixtures/sample_local_regulators.json
```

---

### 2. `sample_requirements_templates.json`
**Що містить**: 6 requirement templates

**Структура**:
- NBU-2023-77: Cybersecurity Regulation (Ukraine) [Critical]
- NBU-2022-95: Business Continuity (Ukraine) [High]
- NBU-2021-65: Data Protection (Ukraine) [High]
- MINDIGITAL-2023-12: Critical Infrastructure (Ukraine) [Critical]
- LB-2023-01: ICT Security (Lithuania) [High]
- NBK-2023-154: Information Security (Kazakhstan) [Critical]

**Завантажити**:
```bash
python manage.py loaddata app_compliance/fixtures/sample_requirements_templates.json
```

**⚠️ Примітка**: Спочатку завантажте `sample_local_regulators.json`!

---

### 3. `sample_requirements_controls.json`
**Що містить**: 18 template controls для requirement templates

**Структура**:
- 5 controls для NBU-2023-77 (Cybersecurity)
- 3 controls для NBU-2022-95 (BCM)
- 2 controls для NBU-2021-65 (Data Protection)
- 1 control для MINDIGITAL-2023-12 (Critical Infrastructure)
- 4 controls для LB-2023-01 (ICT Security)
- 4 controls для NBK-2023-154 (InfoSec)

**Завантажити**:
```bash
python manage.py loaddata app_compliance/fixtures/sample_requirements_controls.json
```

**⚠️ Примітка**: Спочатку завантажте `sample_requirements_templates.json`!

---

## 🚀 Як використовувати

### Варіант 1: Завантажити все послідовно

```bash
# Крок 1: Регулятори
python manage.py loaddata app_compliance/fixtures/sample_local_regulators.json

# Крок 2: Requirements
python manage.py loaddata app_compliance/fixtures/sample_requirements_templates.json

# Крок 3: Controls
python manage.py loaddata app_compliance/fixtures/sample_requirements_controls.json
```

### Варіант 2: Завантажити все одразу (якщо працює)

```bash
python manage.py loaddata \
  app_compliance/fixtures/sample_local_regulators.json \
  app_compliance/fixtures/sample_requirements_templates.json \
  app_compliance/fixtures/sample_requirements_controls.json
```

### Варіант 3: Використати Python script (найкращий)

```bash
python manage.py shell
>>> exec(open('app_compliance/load_sample_data.py').read())
```

Цей варіант:
- ✅ Автоматично створює всі залежності
- ✅ Уникає дублювання (використовує get_or_create)
- ✅ Показує progress
- ✅ Показує статистику після завантаження

---

## 📊 Що буде завантажено

### Регулятори (12):

| ID | Acronym | Name | Country | Type |
|----|---------|------|---------|------|
| 1 | NBU | Національний банк України | UA | Banking |
| 2 | NSSMC | Комісія з цінних паперів | UA | Securities |
| 3 | STS | Податкова служба | UA | Tax |
| 4 | MinDigital | Мінцифри | UA | Data Protection |
| 5 | NFSC | Нацкомфінпослуг | UA | Financial |
| 6 | LB | Bank of Lithuania | LT | Banking |
| 7 | SDPI | Data Protection Inspectorate | LT | Data Protection |
| 8 | ISC | Insurance Supervision | LT | Insurance |
| 9 | NBK | National Bank of Kazakhstan | KZ | Banking |
| 10 | ARDFM | Financial Market Agency | KZ | Financial |
| 11 | CCPDP | Data Protection Committee | KZ | Data Protection |
| 12 | SRC | State Revenue Committee | KZ | Tax |

### Requirements (6 templates):

| Code | Name | Regulator | Priority | Controls |
|------|------|-----------|----------|----------|
| NBU-2023-77 | Cybersecurity | NBU | Critical | 5 |
| NBU-2022-95 | Business Continuity | NBU | High | 3 |
| NBU-2021-65 | Data Protection | NBU | High | 2 |
| MINDIGITAL-2023-12 | Critical Infrastructure | MinDigital | Critical | 1 |
| LB-2023-01 | ICT Security | LB | High | 4 |
| NBK-2023-154 | Information Security | NBK | Critical | 4 |

### Controls (19 templates):

- 7 Critical priority
- 11 High priority
- 1 Medium priority
- 0 Low priority

---

## 🔄 Після завантаження

### 1. Перевірити через Admin:
```
/admin/app_compliance/localcomplianceregulator/
→ Має бути 12 records

/admin/app_compliance/localcompliancerequirement/
→ Фільтр: is_template=Yes
→ Має бути 6 templates

/admin/app_compliance/localcompliancecontrol/
→ Фільтр: company=(empty)
→ Має бути 19 template controls
```

### 2. Переглянути у веб-інтерфейсі:
```
/compliance/local/
→ Dashboard з статистикою

/compliance/local/requirements/
→ 6 requirement templates
```

### 3. Застосувати до компанії:
```
1. Відкрити будь-який template
2. Обрати компанію в "Apply to Companies"
3. Натиснути "Apply"
4. Перевірити що створено instance з контролями
```

---

## 🗑️ Видалення тестових даних

### Видалити всі Local Compliance дані:
```python
# Django shell
from app_compliance.models import LocalComplianceRegulator

# Це видалить регуляторів та каскадно всі requirements і controls
LocalComplianceRegulator.objects.all().delete()
```

### Видалити дані конкретної країни:
```python
# Тільки Україна
LocalComplianceRegulator.objects.filter(country='UA').delete()

# Тільки Литва
LocalComplianceRegulator.objects.filter(country='LT').delete()

# Тільки Казахстан
LocalComplianceRegulator.objects.filter(country='KZ').delete()
```

### Видалити тільки templates (залишити instances):
```python
from app_compliance.models import LocalComplianceRequirement

LocalComplianceRequirement.objects.filter(is_template=True).delete()
```

---

## ⚙️ Налаштування fixtures

### Змінити Primary Keys (PKs):
Якщо у вас вже є дані з такими ж PK, можна:

1. Видалити поле `"pk"` з JSON - Django автоматично згенерує нові
2. Або змінити значення PKs на вільні

### Додати власні дані:
1. Створіть дані через Admin
2. Експортуйте:
```bash
python manage.py dumpdata app_compliance.LocalComplianceRegulator --indent 2 > my_regulators.json
```
3. Редагуйте JSON за потреби
4. Завантажте назад

---

## 📝 Примітки

- ⚠️ PK values в fixtures можуть конфліктувати з існуючими даними
- ⚠️ created_by має бути NULL або існуючий user ID
- ⚠️ Дати в форматі "YYYY-MM-DD"
- ⚠️ Завантаження в правильному порядку (regulators → requirements → controls)
- ✅ Використовуйте Python script для безпечного завантаження (get_or_create)

---

## 🎯 Best Practice

**Рекомендований спосіб** завантаження тестових даних:

```bash
python manage.py shell
```

```python
exec(open('app_compliance/load_sample_data.py').read())
```

Чому:
- ✅ Безпечно (get_or_create, не буде дублювання)
- ✅ Автоматичні залежності
- ✅ Детальний progress log
- ✅ Статистика після завантаження
- ✅ Обробка помилок

---

**Created**: November 2024  
**Module**: app_compliance - Local Compliance  
**Version**: 1.0

