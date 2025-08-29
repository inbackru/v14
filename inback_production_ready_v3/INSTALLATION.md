# InBack Real Estate Platform - Готовый к развертыванию пакет

## Описание системы

InBack - современная платформа недвижимости, специализирующаяся на покупке недвижимости с кешбеком в Краснодаре. Платформа включает:

- 🏠 **Каталог недвижимости** с 27+ объектами
- 🤖 **Автоматизированный парсинг** сайтов застройщиков
- 👥 **Система управления пользователями** (клиенты, менеджеры, админы)
- 💰 **Калькулятор кешбека** до 500,000 ₽
- 📊 **Админ-панель** с аналитикой
- 🔍 **Умный поиск** с автодополнением
- 📧 **Уведомления** через Email/Telegram/WhatsApp
- 📱 **Адаптивный дизайн** под все устройства

## Технические характеристики

- **Backend**: Flask + PostgreSQL
- **Frontend**: Vanilla JS + Tailwind CSS
- **Карты**: Leaflet.js + OpenStreetMap
- **Парсинг**: Trafilatura + BeautifulSoup
- **Производительность**: 0.124с загрузка главной
- **SEO**: Полная оптимизация с JSON-LD
- **Безопасность**: Защита от SQL injection, XSS, CSRF

## Установка и настройка

### 1. Системные требования

```bash
Python 3.11+
PostgreSQL 13+
Git
```

### 2. Настройка базы данных

```sql
-- Создание базы данных
CREATE DATABASE inback_db;
CREATE USER inback_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE inback_db TO inback_user;
```

### 3. Установка зависимостей

```bash
# Клонирование или распаковка
cd inback_production_ready_v3

# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# Установка зависимостей
pip install -r requirements.txt
```

### 4. Настройка переменных окружения

Создайте файл `.env`:

```env
# База данных
DATABASE_URL=postgresql://inback_user:your_secure_password@localhost/inback_db

# Безопасность
SESSION_SECRET=your-super-secret-session-key-32-chars-long

# Telegram Bot (опционально)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# Email (опционально)
SENDGRID_API_KEY=your_sendgrid_api_key
FROM_EMAIL=noreply@yourdomain.com

# WhatsApp Business API (опционально)
WHATSAPP_PHONE_NUMBER_ID=your_phone_id
WHATSAPP_ACCESS_TOKEN=your_access_token
```

### 5. Инициализация базы данных

```bash
# Запуск приложения для создания таблиц
python app.py
```

При первом запуске создаются:
- Все таблицы базы данных
- Администратор: admin@inback.ru / demo123
- Тестовые данные недвижимости

### 6. Запуск в production

```bash
# Gunicorn (рекомендуется)
gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 app:app

# Или с systemd сервисом
sudo systemctl start inback
sudo systemctl enable inback
```

### 7. Настройка Nginx (опционально)

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /static/ {
        alias /path/to/inback/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

## Пользователи и доступы

### Роли по умолчанию:

1. **Администратор**
   - Email: admin@inback.ru
   - Пароль: demo123
   - Доступ: Полный контроль системы

2. **Менеджер** (создается через админку)
   - Управление клиентами
   - Обработка заявок
   - Просмотр аналитики

3. **Клиент** (регистрация или создание)
   - Просмотр недвижимости
   - Подача заявок
   - Избранное и сравнения

### Смена паролей:

```python
# В админ-панели или через консоль
from werkzeug.security import generate_password_hash
new_password_hash = generate_password_hash('new_password')
# Обновить в БД
```

## Функциональные возможности

### Парсер недвижимости
- Автоматический сбор данных с сайтов застройщиков
- Поддержка: Неометрия, ССК, ЮгСтройІнвест
- Доступ: `/admin/scraper`

### API Endpoints
- `GET /api/search` - Умный поиск
- `GET /api/property/<id>/cashback` - Расчет кешбека
- `POST /api/scrape` - Запуск парсера
- `GET /api/debug/session` - Отладка сессий

### Уведомления
- Email через SendGrid
- Telegram Bot API
- WhatsApp Business API
- Настройка в профиле пользователя

## Мониторинг и логи

### Логирование
```bash
# Уровень логов устанавливается в app.py
logging.basicConfig(level=logging.DEBUG)

# Просмотр логов
tail -f /var/log/inback/app.log
```

### Мониторинг базы данных
```sql
-- Активные подключения
SELECT * FROM pg_stat_activity WHERE datname = 'inback_db';

-- Размер базы данных
SELECT pg_size_pretty(pg_database_size('inback_db'));

-- Производительность запросов
SELECT query, mean_time, calls FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;
```

## Резервное копирование

### База данных
```bash
# Создание бэкапа
pg_dump -h localhost -U inback_user inback_db > backup_$(date +%Y%m%d).sql

# Восстановление
psql -h localhost -U inback_user inback_db < backup_20250825.sql
```

### Файлы приложения
```bash
# Создание архива
tar -czf inback_backup_$(date +%Y%m%d).tar.gz inback_production_ready_v3/

# Исключить временные файлы
tar --exclude='*.pyc' --exclude='__pycache__' --exclude='.git' -czf inback_backup.tar.gz inback/
```

## Обновления и миграции

### Обновление кода
```bash
# Остановка сервиса
sudo systemctl stop inback

# Резервная копия
cp -r inback_production_ready_v3 inback_backup_$(date +%Y%m%d)

# Обновление файлов
# ... копирование новых файлов ...

# Обновление зависимостей
pip install -r requirements.txt

# Запуск
sudo systemctl start inback
```

### Миграции базы данных
```python
# В случае изменений моделей, создать миграцию:
from app import db
db.create_all()  # Безопасно создает только новые таблицы
```

## Устранение проблем

### Частые проблемы:

1. **Ошибка подключения к БД**
   ```bash
   # Проверить статус PostgreSQL
   sudo systemctl status postgresql
   
   # Проверить подключение
   psql -h localhost -U inback_user -d inback_db
   ```

2. **Ошибки импорта модулей**
   ```bash
   # Проверить виртуальное окружение
   which python
   pip list
   
   # Переустановить зависимости
   pip install -r requirements.txt --force-reinstall
   ```

3. **Проблемы с файлами статики**
   ```bash
   # Проверить права доступа
   chmod -R 755 static/
   
   # Проверить структуру папок
   ls -la static/
   ```

4. **Ошибки Telegram бота**
   ```bash
   # Проверить токен
   curl https://api.telegram.org/bot<TOKEN>/getMe
   
   # Логи бота в app.py
   ```

## Контакты и поддержка

- **Техническая документация**: README.md в корне проекта
- **База знаний**: replit.md - полная архитектура системы
- **Обновления**: Регулярные обновления через Git

## Лицензия

Проприетарное ПО. Все права защищены.
Copyright © 2025 InBack Real Estate Platform