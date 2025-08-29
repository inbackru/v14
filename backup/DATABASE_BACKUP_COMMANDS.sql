-- InBack Real Estate Platform Database Backup Commands
-- Created: 29 August 2025
-- Use these commands to verify and restore database state

-- =====================================================
-- VERIFICATION COMMANDS
-- =====================================================

-- Check total records in main tables
SELECT 'excel_properties' as table_name, COUNT(*) as record_count FROM excel_properties
UNION ALL
SELECT 'residential_complexes' as table_name, COUNT(*) as record_count FROM residential_complexes  
UNION ALL
SELECT 'it_companies' as table_name, COUNT(*) as record_count FROM it_companies
UNION ALL
SELECT 'users' as table_name, COUNT(*) as record_count FROM users
UNION ALL
SELECT 'managers' as table_name, COUNT(*) as record_count FROM managers
UNION ALL
SELECT 'applications' as table_name, COUNT(*) as record_count FROM applications;

-- Expected results:
-- excel_properties: 462
-- residential_complexes: 29
-- it_companies: 7579

-- =====================================================
-- INTEGRITY CHECKS
-- =====================================================

-- Check for complex_id conflicts (one ID with multiple ЖК names)
SELECT complex_id, 
       COUNT(DISTINCT complex_name) as name_count, 
       STRING_AGG(DISTINCT complex_name, ', ') as all_names
FROM excel_properties 
GROUP BY complex_id 
HAVING COUNT(DISTINCT complex_name) > 1 
ORDER BY name_count DESC;

-- Check residential_complexes consistency
SELECT rc.complex_id, rc.name as rc_name, ep.complex_name as ep_name, COUNT(*) as property_count
FROM residential_complexes rc
LEFT JOIN excel_properties ep ON rc.complex_id = ep.complex_id::varchar
WHERE rc.name != ep.complex_name
GROUP BY rc.complex_id, rc.name, ep.complex_name
ORDER BY property_count DESC;

-- =====================================================
-- PROBLEM RESOLUTION COMMANDS
-- =====================================================

-- Fix known conflicts (run only if conflicts found):

-- Fix complex_id 113046 (should be "ЖК Летний")
-- UPDATE residential_complexes SET name = 'ЖК "Летний"' WHERE complex_id = '113046';

-- Fix complex_id 116104 (should be "ЖК Чайные холмы") 
-- UPDATE residential_complexes SET name = 'ЖК "Чайные холмы"' WHERE complex_id = '116104';

-- Fix complex_id 115226 (should be "ЖК Кислород")
-- UPDATE residential_complexes SET name = 'ЖК "Кислород"' WHERE complex_id = '115226';

-- =====================================================
-- DATA EXPLORATION COMMANDS
-- =====================================================

-- Top 10 properties by price
SELECT inner_id, complex_name, price_full, total_area, room_type 
FROM excel_properties 
WHERE price_full IS NOT NULL 
ORDER BY price_full DESC 
LIMIT 10;

-- Properties distribution by ЖК
SELECT complex_name, COUNT(*) as property_count, 
       MIN(price_full) as min_price, MAX(price_full) as max_price
FROM excel_properties 
WHERE price_full IS NOT NULL
GROUP BY complex_name 
ORDER BY property_count DESC 
LIMIT 10;

-- IT companies sample
SELECT inn, company_name 
FROM it_companies 
LIMIT 10;

-- =====================================================
-- MAINTENANCE COMMANDS
-- =====================================================

-- Update complex data from Excel (refresh aggregated info)
-- This should be run after importing new Excel data
UPDATE residential_complexes 
SET updated_at = NOW() 
WHERE complex_id IN (
    SELECT DISTINCT complex_id FROM excel_properties
);

-- Clean up orphaned records
DELETE FROM residential_complexes 
WHERE complex_id NOT IN (
    SELECT DISTINCT complex_id FROM excel_properties
);

-- Refresh property counts
-- (Add trigger or scheduled job for this in production)

-- =====================================================
-- BACKUP VERIFICATION
-- =====================================================

-- Final verification query - should match expected totals
SELECT 
    (SELECT COUNT(*) FROM excel_properties) as properties,
    (SELECT COUNT(*) FROM residential_complexes) as complexes,
    (SELECT COUNT(*) FROM it_companies) as it_companies,
    (SELECT COUNT(*) FROM users) as users,
    (SELECT COUNT(*) FROM applications) as applications;

-- Schema version check
SELECT schemaname, tablename, 
       (SELECT COUNT(*) FROM pg_attribute 
        WHERE attrelid = (schemaname||'.'||tablename)::regclass 
        AND attnum > 0 AND NOT attisdropped) as column_count
FROM pg_tables 
WHERE schemaname = 'public' 
ORDER BY tablename;