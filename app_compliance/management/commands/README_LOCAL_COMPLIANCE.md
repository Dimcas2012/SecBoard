# Local Compliance Regulators - Sample Data

Цей management command завантажує приклади регуляторів та вимог для України, Литви та Казахстану.

## Використання

### Завантажити всі регулятори:
```bash
python manage.py load_sample_regulators
```

### Завантажити тільки для України:
```bash
python manage.py load_sample_regulators --country UA
```

### Завантажити з прикладами контролів:
```bash
python manage.py load_sample_regulators --with-controls
```

### Завантажити для конкретної країни з контролями:
```bash
python manage.py load_sample_regulators --country LT --with-controls
```

## Що завантажується

### 🇺🇦 Україна (UA)

#### Регулятори:
1. **NBU** - Національний банк України
   - Тип: Banking Regulator
   - Вимоги: Кібербезпека, Безперервність бізнесу, Захист даних

2. **NSSMC** - Національна комісія з цінних паперів та фондового ринку
   - Тип: Securities Regulator

3. **STS** - Державна податкова служба України
   - Тип: Tax Authority

4. **MinDigital** - Міністерство цифрової трансформації
   - Тип: Data Protection Authority

5. **NFSC** - Національна комісія з регулювання ринків фінансових послуг
   - Тип: Financial Regulator

#### Приклади вимог NBU:
- **NBU-2023-77**: Постанова про кібербезпеку банків (Critical)
- **NBU-2022-95**: Вимоги до управління безперервністю діяльності (High)
- **NBU-2021-65**: Вимоги щодо захисту персональних даних (High)

### 🇱🇹 Литва (LT)

#### Регулятори:
1. **LB** - Bank of Lithuania (Lietuvos bankas)
   - Тип: Banking Regulator
   - Вимоги: ICT та безпека

2. **SDPI** - State Data Protection Inspectorate
   - Тип: Data Protection Authority

3. **ISC** - Insurance Supervision Commission
   - Тип: Insurance Regulator

#### Приклади вимог:
- **LB-2023-01**: ICT and Security Risk Management Requirements (High)

### 🇰🇿 Казахстан (KZ)

#### Регулятори:
1. **NBK** - National Bank of Kazakhstan (Қазақстан Ұлттық Банкі)
   - Тип: Banking Regulator
   - Вимоги: Інформаційна безпека

2. **ARDFM** - Agency for Regulation and Development of Financial Market
   - Тип: Financial Regulator

3. **CCPDP** - Committee for Control in Personal Data Protection
   - Тип: Data Protection Authority

4. **SRC** - State Revenue Committee
   - Тип: Tax Authority

#### Приклади вимог:
- **NBK-2023-154**: Information Security Requirements for Financial Organizations (Critical)

## Структура даних

### Template Requirements
Всі вимоги створюються як **Templates** (`is_template=True`), що дозволяє:
- Застосовувати їх до багатьох компаній
- Змінювати template і синхронізувати instances
- Додавати контролі один раз і копіювати автоматично

### Sample Controls (якщо --with-controls)
Для кожної вимоги створюються приклади контролів:
- Security Policy Documentation (Critical)
- Access Control Implementation (High)
- Security Monitoring and Logging (High)
- Incident Response Procedures (Critical)
- Employee Security Training (Medium)
- Vulnerability Management (High)

## Після завантаження

1. Перейти до **Local Requirements Library**:
   ```
   /compliance/local/requirements/
   ```

2. Переглянути створені templates

3. Застосувати templates до компаній:
   - Відкрити template
   - Обрати компанії
   - Натиснути "Apply"

4. Переглянути результати в **Local Compliance Dashboard**:
   ```
   /compliance/local/
   ```

## Видалення тестових даних

```python
# В Django shell
from app_compliance.models import LocalComplianceRegulator

# Видалити всі регулятори України
LocalComplianceRegulator.objects.filter(country='UA').delete()

# Видалити всі тестові дані
LocalComplianceRegulator.objects.all().delete()
```

## Примітки

- Всі вимоги створюються як Templates
- Контролі прив'язані до templates (company=None)
- Дати встановлені умовно для демонстрації
- Після застосування до компаній, створюються instances з копіями контролів

