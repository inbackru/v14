# InBack - Быстрое восстановление системы
*Чеклист для мгновенного восстановления платформы*

## ⚡ БЫСТРЫЙ СТАРТ (5 минут)

### 1. Создание проекта в Replit
- [ ] Создать новый Python проект
- [ ] Включить PostgreSQL базу данных
- [ ] Настроить workflow: `gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app`

### 2. Обязательные файлы (копировать в корень)
- [ ] `app.py` (499KB - основное приложение)
- [ ] `models.py` (1759 строк - модели БД)  
- [ ] `main.py` (точка входа)
- [ ] `replit.md` (документация)

### 3. Обязательные папки
- [ ] `templates/` (67 HTML файлов)
- [ ] `static/` (CSS, JS, изображения)
- [ ] `attached_assets/` (Excel файлы с данными)

### 4. Секреты Replit
- [ ] `SESSION_SECRET` - любая случайная строка
- [ ] `TELEGRAM_BOT_TOKEN` - токен бота (опционально)

### 5. Зависимости (установить через Package Manager)
```
flask==3.1.2
flask-sqlalchemy==3.1.1  
flask-login==0.6.3
gunicorn==23.0.0
psycopg2-binary==2.9.10
pandas==2.3.2
openpyxl==3.1.5
python-telegram-bot==22.3
email-validator==2.3.0
```

---

## 🔧 КРИТИЧЕСКИЕ НАСТРОЙКИ

### app.py - Основные проверки:
```python
# Убедиться что есть эти строки:
app.secret_key = os.environ.get("SESSION_SECRET")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")

# И в конце:
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
```

### models.py - Проверить импорт:
```python
from app import db  # Должно быть в начале файла
```

### main.py - Точка входа:
```python
from app import app
```

---

## 📊 ВОССТАНОВЛЕНИЕ ДАННЫХ

### 1. Автоматическое создание таблиц
После запуска приложения таблицы создадутся автоматически.

### 2. Импорт данных
Если нужно загрузить данные заново:
```python
# В Python консоли или через app.py:
import_excel_data()      # Загрузить объекты недвижимости
import_it_companies()    # Загрузить IT компании
```

### 3. Проверка данных
```sql
-- Эти цифры должны совпадать:
SELECT COUNT(*) FROM excel_properties;     -- 462
SELECT COUNT(*) FROM residential_complexes; -- 29
SELECT COUNT(*) FROM it_companies;        -- 7579
```

---

## ⚠️ ИЗВЕСТНЫЕ ПРОБЛЕМЫ И РЕШЕНИЯ

### Проблема 1: Объекты ведут в неправильные ЖК
**Симптом**: Клик "Подробнее о ЖК" открывает не тот ЖК

**Решение**:
```sql
-- Найти конфликты:
SELECT complex_id, COUNT(DISTINCT complex_name) 
FROM excel_properties 
GROUP BY complex_id 
HAVING COUNT(DISTINCT complex_name) > 1;

-- Исправить (пример):
UPDATE residential_complexes 
SET name = 'ЖК "Чайные холмы"' 
WHERE complex_id = '116104';
```

### Проблема 2: Карты не отображаются
**Проверить**:
- [ ] Leaflet.js загружается в шаблонах
- [ ] Координаты есть в excel_properties  
- [ ] Нет ошибок в browser console

### Проблема 3: IT компании не проверяются
**Проверить**:
- [ ] Таблица it_companies содержит 7579 записей
- [ ] API endpoint `/api/check-it-company` работает
- [ ] JavaScript функции в templates/it_mortgage.html

---

## 🎯 ФИНАЛЬНАЯ ПРОВЕРКА

### Основной функционал:
- [ ] Главная страница загружается
- [ ] Поиск объектов работает
- [ ] Карты отображают маркеры
- [ ] Страницы ЖК открываются
- [ ] Страницы объектов работают
- [ ] IT ипотека проверяет компании

### Критические эндпоинты:
- [ ] `/` - главная
- [ ] `/properties` - каталог объектов
- [ ] `/residential-complexes` - ЖК
- [ ] `/object/[id]` - страница объекта
- [ ] `/complex/[id]` - страница ЖК
- [ ] `/api/smart-search` - умный поиск
- [ ] `/api/check-it-company` - проверка IT компаний

---

## 📞 ЭКСТРЕННОЕ ВОССТАНОВЛЕНИЕ

Если что-то пошло не так:

### 1. Сброс базы данных
```sql
-- ВНИМАНИЕ: Удаляет все данные!
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
-- Перезапустить приложение для пересоздания таблиц
```

### 2. Переимпорт Excel данных
```python
# Удалить и пересоздать данные:
from app import db, app
with app.app_context():
    db.drop_all()
    db.create_all()
    import_excel_data()
    import_it_companies()
```

### 3. Откат к последнему рабочему состоянию
Использовать Replit Checkpoints для отката проекта.

---

## 📋 СОСТОЯНИЕ НА 29.08.2025

### ✅ Работает стабильно:
- 462 объекта недвижимости в БД
- 29 ЖК с полной информацией  
- 7,579 IT компаний для проверки
- Умный поиск по 77 полям Excel
- Интерактивные карты Leaflet.js
- Telegram бот уведомления
- Админ-панель менеджеров

### ⚠️ Требует внимания:
- Конфликты complex_id (3 проблемных ID)
- Периодическая проверка связей ЖК

### 🚀 Производительность:
- Загрузка главной: <2 сек
- Поиск: <1 сек  
- Карты: <3 сек
- Память: ~16-26 MB

---

*Этот чеклист позволяет восстановить InBack за 5-10 минут*