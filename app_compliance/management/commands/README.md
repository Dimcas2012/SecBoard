# Compliance Framework CSV Import Commands

## Доступні команди імпорту

### 1. PCI DSS 4.0.1
Django management command для імпорту контролів PCI DSS 4.0.1 (Service Provider) з CSV файлу в Template Frameworks.

### 2. ISO 27001:2022
Django management command для імпорту контролів ISO 27001:2022 з CSV файлу в Template Frameworks.

---

# PCI DSS 4.0.1 Import

## Опис
Імпорт контролів PCI DSS 4.0.1 (Service Provider) з CSV файлу.

## Використання

### Базовий імпорт
```bash
python manage.py import_pci_dss_csv
```

Це використає файл за замовчуванням: `SecBoard/app_compliance/PCI DSS 4.0.1 - ROC - Service Provider controls.csv`

### Імпорт з власного файлу
```bash
python manage.py import_pci_dss_csv /path/to/your/file.csv
```

### Оновлення існуючого framework
```bash
python manage.py import_pci_dss_csv --update
```

### Очищення та повторний імпорт
```bash
python manage.py import_pci_dss_csv --update --clear
```

## Параметри

- `csv_file` (опціонально) - Шлях до CSV файлу
- `--update` - Оновити існуючий framework, якщо він вже є
- `--clear` - Очистити всі існуючі контроли перед імпортом

## Формат CSV файлу

CSV файл повинен містити наступні колонки:
- `Framework requirement` - Номер вимоги (наприклад, "1.1", "1.2")
- `Framework code` - Код контролю
- `Title` - Назва контролю
- `ID` - Унікальний ідентифікатор контролю
- `UID` - UID контролю
- `Url` - Посилання на контроль
- `Description` - Опис контролю
- `Description modified?` - Чи змінений опис
- `Evidence status` - Статус підтвердження (OK, Needs evidence, Not applicable)
- `Domain` - Домен контролю
- `Owner` - Власник
- `Note` - Примітки

## Що робить команда

1. **Створює ComplianceFramework**
   - Назва: "PCI DSS 4.0.1 - Service Provider"
   - Тип: PCI DSS
   - Версія: 4.0.1
   - Статус: Active
   - Позначається як Template (is_template=True)

2. **Створює категорії (ControlCategory)**
   - На основі колонки "Framework requirement"
   - Групує контроли за вимогами

3. **Створює контроли (Control)**
   - Імпортує всі контроли з CSV
   - Мапить статуси:
     - "OK" → completed
     - "Needs evidence" → not_started
     - "Not applicable" → not_applicable

## Приклад виконання

```bash
$ python manage.py import_pci_dss_csv --update --clear

Starting import from: SecBoard/app_compliance/PCI DSS 4.0.1 - ROC - Service Provider controls.csv
Updating existing framework: PCI DSS 4.0.1 - Service Provider
Cleared 1857 controls and 12 categories
  Created category: 1.1
  Created category: 1.2
  Processed 100 controls...
  Processed 200 controls...
  ...
  Processed 1800 controls...

======================================================================
Import completed successfully!
======================================================================
Framework: PCI DSS 4.0.1 - Service Provider
Categories: 12
Controls created: 1857
Controls updated: 0
Controls skipped: 0
Total controls: 1857
======================================================================
```

## Перевірка результатів

Після імпорту:
1. Перейдіть на сторінку Frameworks: `/compliance/frameworks/`
2. Знайдіть "PCI DSS 4.0.1 - Service Provider" з міткою TEMPLATE
3. Перевірте кількість категорій та контролів
4. Відкрийте деталі framework для перегляду всіх контролів

## Помилки та рішення

### "Framework already exists"
Використайте флаг `--update` для оновлення існуючого framework

### "CSV file not found"
Перевірте шлях до CSV файлу або помістіть його за замовчуванням у:
`SecBoard/app_compliance/PCI DSS 4.0.1 - ROC - Service Provider controls.csv`

### "Missing required fields"
Перевірте, що CSV містить всі необхідні колонки та правильне форматування

---

# ISO 27001:2022 Import

## Опис
Імпорт контролів ISO 27001:2022 з CSV файлу.

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

## Що робить команда

1. **Створює ComplianceFramework**
   - Назва: "ISO 27001:2022"
   - Тип: ISO 27001
   - Версія: 2022
   - Статус: Active
   - Позначається як Template (is_template=True)

2. **Створює 11 категорій (ControlCategory)**
   - **Основні розділи (Clauses C.4-C.10)**: 7 категорій
   - **Додатки (Annexes A.5-A.8)**: 4 категорії

3. **Створює 106 контролів (Control)**
   - Автоматично обробляє дублікати (об'єднує тести для одного контролю)
   - Мапить статуси:
     - "OK" → completed
     - "Needs evidence" → not_started
     - "Not applicable" → not_applicable
     - "Fail" → failed

## Приклад виконання

```bash
$ python manage.py import_iso27001_csv --update --clear

Starting import from: app_compliance/ISO 27001_2022 controls.csv
Created new framework: ISO 27001:2022
  Created category: C.4 - Clause 4: Context of the Organization
  Created category: C.5 - Clause 5: Leadership
  ...
  Processed 50 controls...
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

## Перевірка результатів

Після імпорту:
1. Перейдіть на сторінку Frameworks: `/compliance/frameworks/`
2. Знайдіть "ISO 27001:2022" з міткою TEMPLATE
3. Перевірте кількість категорій (11) та контролів (106)
4. Відкрийте деталі framework для перегляду всіх контролів

Детальна документація: [README_ISO27001.md](README_ISO27001.md)

---

## Швидкий запуск через скрипти

### Windows
```bash
cd scripts
import_pci_dss.bat --update --clear
import_iso27001.bat --update --clear
```

### Linux/Mac
```bash
cd scripts
./import_pci_dss.sh --update --clear
./import_iso27001.sh --update --clear
```

## Модифікація під інші стандарти

Команду можна легко адаптувати для імпорту інших стандартів:
1. Створіть новий command файл (наприклад, `import_soc2_csv.py`)
2. Змініть значення за замовчуванням для `name`, `framework_type`, `version`
3. Адаптуйте словник `CATEGORY_DESCRIPTIONS`
4. Адаптуйте мапінг колонок CSV під ваш формат

