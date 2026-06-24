# ISO 27001:2022 CSV Import Command

## Опис
Django management command для імпорту контролів ISO 27001:2022 з CSV файлу в Template Frameworks.

## Використання

### Базовий імпорт
```bash
python manage.py import_iso27001_csv
```

Це використає файл за замовчуванням: `app_compliance/ISO 27001_2022 controls.csv`

### Імпорт з власного файлу
```bash
python manage.py import_iso27001_csv /path/to/your/file.csv
```

### Оновлення існуючого framework
```bash
python manage.py import_iso27001_csv --update
```

### Очищення та повторний імпорт
```bash
python manage.py import_iso27001_csv --update --clear
```

## Параметри

- `csv_file` (опціонально) - Шлях до CSV файлу
- `--update` - Оновити існуючий framework, якщо він вже є
- `--clear` - Очистити всі існуючі контроли перед імпортом

## Формат CSV файлу

CSV файл повинен містити наступні колонки:
- `Framework requirement` - Номер вимоги (наприклад, "C.4.1", "A.5.1")
- `Framework code` - Код контролю
- `Title` - Назва контролю
- `ID` - Внутрішній ідентифікатор контролю (наприклад, "GOV-89")
- `UID` - Унікальний ідентифікатор контролю (наприклад, "77yz851y")
- `Url` - Посилання на контроль
- `Description` - Опис контролю
- `Description modified?` - Чи змінений опис
- `Evidence status` - Статус підтвердження (OK, Needs evidence, Not applicable, Fail)
- `Domain` - Домен контролю (SECURITY_PRIVACY_GOVERNANCE, ACCESS_MANAGEMENT, тощо)
- `Owner` - Власник
- `Note` - Примітки
- `Test name` - Назва тесту
- `Test url` - URL тесту
- `Test description` - Опис тесту
- `Test outcome` - Результат тесту

## Що робить команда

1. **Створює ComplianceFramework**
   
   - Назва: ISO 27001:2022
   - Тип: ISO 27001
   - Версія: 2022
   - Статус: Active
   - Позначається як Template (is_template=True)

2. **Створює 11 категорій (ControlCategory)**
   
   **Основні розділи (Clauses):**
   - C.4: Context of the Organization
   - C.5: Leadership
   - C.6: Planning
   - C.7: Support
   - C.8: Operation
   - C.9: Performance Evaluation
   - C.10: Improvement
   
   **Додатки (Annexes):**
   - A.5: Organizational Controls (37 контролів)
   - A.6: People Controls (8 контролів)
   - A.7: Physical Controls (14 контролів)
   - A.8: Technological Controls (34 контроля)

3. **Створює контроли (Control)**
   - Імпортує всі унікальні контроли з CSV (106 контролів)
   - Автоматично обробляє дублікати (об'єднує тести для одного контролю)
   - Мапить статуси:
     - "OK" → completed
     - "Needs evidence" → not_started
     - "Not applicable" → not_applicable
     - "Fail" → failed

4. **Обробка дублікатів**
   - CSV файл містить дублікати для різних тестових процедур
   - Команда автоматично виявляє дублікати за UID
   - Додає інформацію про тести до існуючого контролю

## Приклад виконання

```bash
$ python manage.py import_iso27001_csv --update --clear

Starting import from: app_compliance/ISO 27001_2022 controls.csv
Created new framework: ISO 27001:2022
  Created category: C.4 - Clause 4: Context of the Organization
  Created category: C.5 - Clause 5: Leadership
  Created category: C.6 - Clause 6: Planning
  Created category: C.7 - Clause 7: Support
  Created category: C.8 - Clause 8: Operation
  Created category: C.9 - Clause 9: Performance Evaluation
  Created category: C.10 - Clause 10: Improvement
  Created category: A.5 - Annex A.5: Organizational Controls
  Processed 50 controls...
  Created category: A.6 - Annex A.6: People Controls
  Created category: A.7 - Annex A.7: Physical Controls
  Created category: A.8 - Annex A.8: Technological Controls
  Processed 100 controls...

======================================================================
Import completed successfully!
======================================================================
Framework: ISO 27001:2022
Categories: 11
Controls created: 106
Controls updated: 0
Controls skipped (duplicates/invalid): 321
Total unique controls: 106
======================================================================
```

## Структура ISO 27001:2022

### Розділи стандарту (Clauses)
- **C.4-C.10**: Вимоги до системи менеджменту інформаційної безпеки (ISMS)
  - C.4: Контекст організації
  - C.5: Лідерство
  - C.6: Планування
  - C.7: Підтримка
  - C.8: Операційна діяльність
  - C.9: Оцінка ефективності
  - C.10: Покращення

### Додаток A (Annex A) - Контролі безпеки
- **A.5**: Організаційні контролі (37 контролів)
- **A.6**: Контролі персоналу (8 контролів)
- **A.7**: Фізичні контролі (14 контролів)
- **A.8**: Технологічні контролі (34 контроля)

**Загалом: 93 контроля в Додатку A + 13 вимог в розділах = 106 контролів**

## Перевірка результатів

Після імпорту:
1. Перейдіть на сторінку Frameworks: `/compliance/frameworks/`
2. Знайдіть "ISO 27001:2022" з міткою TEMPLATE
3. Перевірте кількість категорій (11) та контролів (106)
4. Відкрийте деталі framework для перегляду всіх контролів

### Перевірка через shell
```bash
python manage.py shell -c "
from app_compliance.models import ComplianceFramework, Control
fw = ComplianceFramework.objects.get(name='ISO 27001:2022')
print(f'Categories: {fw.categories.count()}')
print(f'Controls: {Control.objects.filter(category__framework=fw).count()}')
"
```

## Помилки та рішення

### "Framework already exists"
Використайте прапорець `--update`:
```bash
python manage.py import_iso27001_csv --update
```

### "CSV file not found"
Перевірте шлях до файлу. За замовчуванням файл має бути в:
```
SecBoard/app_compliance/ISO 27001_2022 controls.csv
```

### "Row X: Skipping - missing required fields"
Це нормально для рядків-дублікатів або неповних даних. Команда автоматично пропускає такі рядки.

## Відмінності від PCI DSS

1. **Структура категорій**: ISO 27001 має 11 категорій (7 розділів + 4 додатки), PCI DSS має 12 вимог
2. **Кількість контролів**: ISO 27001 має 106 контролів, PCI DSS 4.0.1 має 1857 контролів
3. **Обробка дублікатів**: ISO 27001 CSV містить дублікати для різних тестів, команда автоматично об'єднує їх
4. **Домени**: ISO 27001 використовує інші домени (SECURITY_PRIVACY_GOVERNANCE, ACCESS_MANAGEMENT, тощо)

## Застосування до компанії

Після імпорту template можна застосувати до компанії:
```bash
python manage.py apply_template --framework "ISO 27001:2022" --company "Company Name"
```

Або через веб-інтерфейс:
1. Перейдіть до Frameworks
2. Знайдіть "ISO 27001:2022" [TEMPLATE]
3. Натисніть "Apply to Company"
4. Виберіть компанію та підтвердіть

## Технічні деталі

- **Транзакції**: Весь імпорт виконується в одній транзакції (atomic)
- **Унікальність**: Контролі ідентифікуються за UID
- **Кодування**: UTF-8
- **Статус**: Всі імпортовані контролі мають статус 'not_started' або відповідний до CSV
- **Пріоритет**: Автоматично визначається на основі домену

## Розширення

Для додавання нових категорій або модифікації опису, відредагуйте словник `CATEGORY_DESCRIPTIONS` у файлі `import_iso27001_csv.py`.

