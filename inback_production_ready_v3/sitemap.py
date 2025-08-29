#!/usr/bin/env python3
"""
Sitemap generator for InBack.ru
Generates XML sitemap for all pages including dynamic routes
"""

import os
from datetime import datetime
from flask import Flask, url_for
from app import app

# List of all static routes
STATIC_ROUTES = [
    'index',
    'about', 
    'how_it_works',
    'reviews',
    'contacts',
    'blog',
    'news',
    'security',
    'careers',
    'properties',
    'residential_complexes', 
    'developers',
    'map_view',
    'districts',
    'streets',
    'ipoteka',
    'family_mortgage',
    'it_mortgage', 
    'military_mortgage',
    'developer_mortgage',
    'maternal_capital',
    'privacy_policy',
    'data_processing_consent'
]

# Districts (54 total)
DISTRICTS = [
    'tsentralnyy', 'zapadny', 'karasunsky', 'festivalny', 'gidrostroitelei', 
    'yubileynyy', 'pashkovsky', 'prikubansky', 'enka', 'solnechny', 
    'panorama', 'vavilova', 'yablonovskiy', 'uchhoz-kuban', 'dubinka',
    'komsomolsky', 'kolosistiy', 'kozhzavod', 'kubansky', 'krasnodarskiy',
    '9i-kilometr', 'aviagorodok', 'avrora', 'basket-hall', 'berezovy',
    'cheremushki', 'gorkhutor', 'hbk', 'kalinino', 'kkb', 'ksk', 
    'krasnaya-ploshad', '40-let-pobedy', 'tsiolkovskogo', 'stasova',
    'kalinovaya', 'kotliarevskogo', 'akademika-lukianenko', 'starokorsunskaya',
    'im-40-letiya-pobedy', 'rossiyskaya', 'turgenevsky', 'slavyansky',
    'novorossiysky', 'tbilissky', 'severo-kavkazsky', 'adygeysky',
    'prochorzhsky', 'kievsky', 'dneprovskiy', 'moldavsky', 'sovetsky',
    'universitetsky', 'industrialny', 'shevchenko'
]

# Blog categories  
BLOG_CATEGORIES = ['cashback', 'districts', 'mortgage', 'market', 'legal', 'tips']

# Sample streets (using first 50 from the dataset)
STREETS = [
    'krasnaya', 'severnaya', 'stavropovskaya', 'turgenevskogo', 'krasnoarmeyskaya',
    'sovietskaya', 'dimitrova', 'kalinina', 'komsomolskaya', 'lenina',
    'pushkinskaya', 'gagarina', 'mira', 'pobedy', 'oktyabrskaya',
    'pervomayskaya', 'kirova', 'chkalova', 'gorkogo', 'mayakovskogo',
    # Add more streets as needed
]

def generate_sitemap():
    """Generate XML sitemap"""
    
    sitemap_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xsi:schemaLocation="http://www.sitemaps.org/schemas/sitemap/0.9
        http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd">
'''

    base_url = "https://inback.ru"
    today = datetime.now().strftime('%Y-%m-%d')
    
    with app.app_context():
        # Static pages
        for route in STATIC_ROUTES:
            try:
                url = url_for(route)
                priority = '1.0' if route == 'index' else '0.8'
                changefreq = 'daily' if route in ['index', 'properties', 'blog', 'news'] else 'weekly'
                
                sitemap_xml += f'''  <url>
    <loc>{base_url}{url}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>{changefreq}</changefreq>
    <priority>{priority}</priority>
  </url>
'''
            except Exception as e:
                print(f"Skipping route {route}: {e}")
        
        # District pages
        for district in DISTRICTS:
            try:
                url = url_for('district_detail', district_name=district)
                sitemap_xml += f'''  <url>
    <loc>{base_url}{url}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>
'''
            except Exception as e:
                print(f"Skipping district {district}: {e}")
        
        # Street pages (sample)
        for street in STREETS[:50]:  # First 50 streets
            try:
                url = f"/streets/{street}"
                sitemap_xml += f'''  <url>
    <loc>{base_url}{url}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>
'''
            except Exception as e:
                print(f"Skipping street {street}: {e}")
        
        # Blog categories
        for category in BLOG_CATEGORIES:
            try:
                url = url_for('blog_category', category=category)
                sitemap_xml += f'''  <url>
    <loc>{base_url}{url}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.7</priority>
  </url>
'''
            except Exception as e:
                print(f"Skipping blog category {category}: {e}")
    
    sitemap_xml += '</urlset>'
    
    # Write to file
    with open('static/sitemap.xml', 'w', encoding='utf-8') as f:
        f.write(sitemap_xml)
    
    print(f"Sitemap generated with {len(STATIC_ROUTES + DISTRICTS + STREETS[:50] + BLOG_CATEGORIES)} URLs")
    return sitemap_xml

if __name__ == '__main__':
    generate_sitemap()