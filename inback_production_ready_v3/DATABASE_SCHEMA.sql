-- InBack Real Estate Platform Database Schema
-- PostgreSQL 13+ compatible
-- Generated: 2025-08-25

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(120) UNIQUE NOT NULL,
    phone VARCHAR(20),
    telegram_id VARCHAR(50),
    full_name VARCHAR(100),
    password_hash VARCHAR(256),
    temp_password_hash VARCHAR(256),
    created_by_admin BOOLEAN DEFAULT FALSE,
    preferred_contact VARCHAR(20) DEFAULT 'email',
    email_notifications BOOLEAN DEFAULT TRUE,
    telegram_notifications BOOLEAN DEFAULT FALSE,
    notify_recommendations BOOLEAN DEFAULT TRUE,
    notify_saved_searches BOOLEAN DEFAULT TRUE,
    notify_applications BOOLEAN DEFAULT TRUE,
    notify_cashback BOOLEAN DEFAULT TRUE,
    notify_marketing BOOLEAN DEFAULT FALSE,
    profile_image VARCHAR(255),
    user_id VARCHAR(50) UNIQUE,
    role VARCHAR(20) DEFAULT 'client',
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    verification_token VARCHAR(100),
    is_demo BOOLEAN DEFAULT FALSE,
    verified BOOLEAN DEFAULT FALSE,
    registration_source VARCHAR(50),
    client_notes TEXT,
    assigned_manager_id INTEGER,
    client_status VARCHAR(20) DEFAULT 'new',
    preferred_district VARCHAR(100),
    property_type VARCHAR(50),
    room_count VARCHAR(10),
    budget_range VARCHAR(50),
    quiz_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- Managers table
CREATE TABLE IF NOT EXISTS managers (
    id SERIAL PRIMARY KEY,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(256),
    full_name VARCHAR(100),
    phone VARCHAR(20),
    telegram_id VARCHAR(50),
    manager_id VARCHAR(50) UNIQUE,
    role VARCHAR(20) DEFAULT 'manager',
    department VARCHAR(50),
    position VARCHAR(100),
    hire_date DATE,
    salary DECIMAL(10,2),
    commission_rate DECIMAL(5,2),
    max_cashback_approval DECIMAL(12,2),
    permissions TEXT,
    avatar VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- Admins table
CREATE TABLE IF NOT EXISTS admins (
    id SERIAL PRIMARY KEY,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(256),
    full_name VARCHAR(100),
    admin_id VARCHAR(50) UNIQUE,
    role VARCHAR(20) DEFAULT 'admin',
    permissions TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- Properties table
CREATE TABLE IF NOT EXISTS properties (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255),
    description TEXT,
    slug VARCHAR(255) UNIQUE,
    price DECIMAL(12,2),
    rooms INTEGER,
    area DECIMAL(8,2),
    floor INTEGER,
    total_floors INTEGER,
    district VARCHAR(100),
    address TEXT,
    latitude DECIMAL(10,6),
    longitude DECIMAL(10,6),
    developer VARCHAR(100),
    residential_complex VARCHAR(100),
    residential_complex_id INTEGER,
    images TEXT,
    features TEXT,
    cashback_amount DECIMAL(12,2),
    status VARCHAR(20) DEFAULT 'available',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Residential Complexes table
CREATE TABLE IF NOT EXISTS residential_complexes (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE,
    description TEXT,
    developer VARCHAR(100),
    district VARCHAR(100),
    address TEXT,
    latitude DECIMAL(10,6),
    longitude DECIMAL(10,6),
    images TEXT,
    amenities TEXT,
    completion_year INTEGER,
    total_buildings INTEGER,
    parking_spaces INTEGER,
    website VARCHAR(255),
    min_price DECIMAL(12,2),
    max_price DECIMAL(12,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Developers table
CREATE TABLE IF NOT EXISTS developers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    slug VARCHAR(255) UNIQUE,
    description TEXT,
    logo VARCHAR(255),
    website VARCHAR(255),
    phone VARCHAR(20),
    email VARCHAR(120),
    address TEXT,
    experience_years INTEGER,
    total_projects INTEGER,
    active_projects INTEGER,
    rating DECIMAL(3,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Districts table
CREATE TABLE IF NOT EXISTS districts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) UNIQUE,
    description TEXT,
    latitude DECIMAL(10,6),
    longitude DECIMAL(10,6),
    properties_count INTEGER DEFAULT 0,
    avg_price DECIMAL(12,2),
    avg_cashback DECIMAL(12,2),
    infrastructure TEXT,
    transport TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Applications table
CREATE TABLE IF NOT EXISTS applications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    property_id INTEGER,
    manager_id INTEGER REFERENCES managers(id),
    full_name VARCHAR(100),
    phone VARCHAR(20),
    email VARCHAR(120),
    property_title VARCHAR(255),
    cashback_amount DECIMAL(12,2),
    status VARCHAR(20) DEFAULT 'pending',
    source VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Callback Requests table
CREATE TABLE IF NOT EXISTS callback_requests (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    phone VARCHAR(20),
    preferred_time VARCHAR(50),
    interest_type VARCHAR(50),
    status VARCHAR(20) DEFAULT 'pending',
    assigned_manager_id INTEGER REFERENCES managers(id),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Cashback Applications table
CREATE TABLE IF NOT EXISTS cashback_applications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    application_id INTEGER REFERENCES applications(id),
    amount DECIMAL(12,2),
    status VARCHAR(20) DEFAULT 'pending',
    approved_amount DECIMAL(12,2),
    approved_by INTEGER REFERENCES managers(id),
    approved_at TIMESTAMP,
    payment_method VARCHAR(50),
    payment_details TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Blog Articles table
CREATE TABLE IF NOT EXISTS blog_articles (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE,
    content TEXT,
    excerpt TEXT,
    featured_image VARCHAR(255),
    author VARCHAR(100),
    category_id INTEGER,
    status VARCHAR(20) DEFAULT 'draft',
    views INTEGER DEFAULT 0,
    meta_title VARCHAR(255),
    meta_description TEXT,
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Blog Categories table
CREATE TABLE IF NOT EXISTS blog_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    slug VARCHAR(100) UNIQUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Favorites table
CREATE TABLE IF NOT EXISTS favorites (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    property_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, property_id)
);

-- Notifications table
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    type VARCHAR(50),
    title VARCHAR(255),
    message TEXT,
    read_status BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Search History table
CREATE TABLE IF NOT EXISTS search_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    search_query VARCHAR(255),
    filters TEXT,
    results_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_properties_price ON properties(price);
CREATE INDEX IF NOT EXISTS idx_properties_district ON properties(district);
CREATE INDEX IF NOT EXISTS idx_properties_developer ON properties(developer);
CREATE INDEX IF NOT EXISTS idx_properties_status ON properties(status);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_applications_user_id ON applications(user_id);
CREATE INDEX IF NOT EXISTS idx_favorites_user_id ON favorites(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);

-- Insert default admin user
INSERT INTO admins (email, password_hash, full_name, admin_id, role, is_active) 
VALUES (
    'admin@inback.ru', 
    'scrypt:32768:8:1$Q9XgGxOfKkVBg4QG$f2a75c8d4c5b3e9f8d1a7c6b5a4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9e8d7c6b5a4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9e8d7c6b5a', 
    'Администратор', 
    'admin001', 
    'admin', 
    true
) ON CONFLICT (email) DO NOTHING;

-- Insert sample districts
INSERT INTO districts (name, slug, description, properties_count, avg_price, avg_cashback) VALUES
('Центральный', 'tsentralnyy', 'Исторический центр города с развитой инфраструктурой', 8, 7500000, 150000),
('Западный', 'zapadnyy', 'Современный развивающийся район', 5, 6200000, 124000),
('Прикубанский', 'prikubanskiy', 'Спокойный жилой район у реки', 4, 5800000, 116000),
('Карасунский', 'karasunskiy', 'Район с парками и зелеными зонами', 6, 6800000, 136000),
('Фестивальный', 'festivalnyy', 'Динамично развивающийся микрорайон', 4, 5500000, 110000)
ON CONFLICT (slug) DO NOTHING;

-- Insert sample developers
INSERT INTO developers (name, slug, description, total_projects, active_projects, rating) VALUES
('ГК «Неометрия»', 'neometriya', 'Один из крупнейших застройщиков Краснодара', 15, 5, 4.8),
('ГК «ССК»', 'ssk', 'Федеральный застройщик с 30-летним опытом', 25, 8, 4.9),
('ЮгСтройІнвест', 'yugstroyinvest', 'Региональный застройщик премиум-класса', 12, 4, 4.7),
('ЮИТ Краснодар', 'yit-krasnodar', 'Финский застройщик качественного жилья', 8, 3, 4.9),
('МИЦ', 'mits', 'Местный застройщик доступного жилья', 10, 6, 4.5)
ON CONFLICT (slug) DO NOTHING;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO inback_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO inback_user;