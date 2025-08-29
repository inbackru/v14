import os
import json
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, abort, Blueprint, send_from_directory
from sqlalchemy import text
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename

# Import smart search
from smart_search import smart_search
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
import secrets
import re
from email_service import send_notification

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Session configuration for better cookie handling
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['PERMANENT_SESSION_LIFETIME'] = 60 * 60 * 24  # 24 hours

# Enable permanent sessions by default
from datetime import timedelta
app.permanent_session_lifetime = timedelta(hours=24)

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///properties.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Configure file uploads
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Add route for uploaded files
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Initialize the app with the extension
db.init_app(app)

# Create API blueprint without login requirement
api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/debug/session')
def debug_session():
    """Debug session information"""
    return jsonify({
        'session_keys': list(session.keys()),
        'session_data': dict(session),
        'manager_id': session.get('manager_id'),
        'user_id': session.get('user_id'),
        'current_user_authenticated': getattr(current_user, 'is_authenticated', False) if current_user else False,
        'current_user_id': getattr(current_user, 'id', None) if current_user else None
    })

@api_bp.route('/property/<int:property_id>/cashback')
def api_property_cashback(property_id):
    """Get cashback information for a property"""
    try:
        # Load properties data
        properties = load_properties()
        complexes = load_residential_complexes()
        
        # Find property by ID
        property_data = None
        for prop in properties:
            if prop.get('id') == property_id:
                property_data = prop
                break
        
        if not property_data:
            return jsonify({'success': False, 'error': 'Property not found'})
        
        # Calculate cashback
        price = property_data.get('price', 0)
        cashback_percent = 2.5  # Default cashback
        
        # Determine cashback percentage based on price
        if price >= 10000000:  # 10M+
            cashback_percent = 3.0
        elif price >= 5000000:  # 5M+
            cashback_percent = 2.8
        else:
            cashback_percent = 2.5
        
        cashback_amount = price * (cashback_percent / 100)
        
        # Get complex info
        complex_name = "Не указан"
        if property_data.get('residential_complex_id'):
            complex_id = property_data['residential_complex_id']
            for complex_data in complexes:
                if complex_data.get('id') == complex_id:
                    complex_name = complex_data.get('name', 'Не указан')
                    break
        
        # Format property name
        rooms = property_data.get('rooms', 0)
        room_text = f"{rooms}-комнатная квартира" if rooms > 0 else "Студия"
        property_name = f"{room_text} в ЖК «{complex_name}»"
        
        return jsonify({
            'success': True,
            'property_id': property_id,
            'property_name': property_name,
            'property_price': price,
            'cashback_percent': cashback_percent,
            'cashback_amount': int(cashback_amount),
            'complex_name': complex_name,
            'rooms': rooms
        })
        
    except Exception as e:
        print(f"Error getting property cashback: {e}")
        return jsonify({'success': False, 'error': 'Server error'})

# Custom Jinja2 filters
def street_slug(street_name):
    """Convert street name to URL slug"""
    # Сохраняем кириллицу для корректной работы URL
    return street_name.lower().replace(' ', '-').replace('.', '').replace('(', '').replace(')', '').replace(',', '')

def number_format(value):
    """Format number with space separators"""
    try:
        if isinstance(value, str):
            value = int(value)
        return f"{value:,}".replace(',', ' ')
    except (ValueError, TypeError):
        return str(value)

def developer_slug(developer_name):
    """Convert developer name to URL slug"""
    return developer_name.lower().replace(' ', '-').replace('.', '').replace('(', '').replace(')', '').replace(',', '').replace('"', '').replace('«', '').replace('»', '')

app.jinja_env.filters['street_slug'] = street_slug
app.jinja_env.filters['number_format'] = number_format
app.jinja_env.filters['developer_slug'] = developer_slug

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # type: ignore
login_manager.login_message = 'Войдите в аккаунт для доступа к этой странице.'
login_manager.login_message_category = 'info'



# Property data loading functions
def load_properties():
    """Load properties from JSON file with priority to full data"""
    try:
        # Try full data first (from Domclick parsing)
        with open('data/properties_new.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        try:
            # Fallback to expanded data
            with open('data/properties_expanded.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            try:
                # Last fallback to basic data
                with open('data/properties.json', 'r', encoding='utf-8') as f:
                    return json.load(f)
            except FileNotFoundError:
                return []

def load_residential_complexes():
    """Load residential complexes from JSON file"""
    try:
        with open('static/data/residential_complexes_expanded.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        try:
            with open('data/residential_complexes_expanded.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            try:
                with open('data/residential_complexes_new.json', 'r', encoding='utf-8') as f:
                    return json.load(f)
            except FileNotFoundError:
                try:
                    with open('data/residential_complexes.json', 'r', encoding='utf-8') as f:
                        return json.load(f)
                except FileNotFoundError:
                    return []

def load_blog_articles():
    """Load blog articles from JSON file"""
    try:
        with open('data/blog_articles.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def load_blog_categories():
    """Load blog categories from JSON file"""
    try:
        with open('data/blog_categories.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def load_search_data():
    """Load search data from JSON file"""
    try:
        with open('data/search_data.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def load_streets():
    """Load streets from JSON file"""
    try:
        with open('data/streets.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def load_developers():
    """Load developers from residential complexes data"""
    try:
        complexes = load_residential_complexes()
        developers = {}
        
        for complex in complexes:
            dev_name = complex.get('developer', 'Неизвестный застройщик')
            if dev_name not in developers:
                developers[dev_name] = {
                    'name': dev_name,
                    'projects_count': 0,
                    'complexes': []
                }
            developers[dev_name]['projects_count'] += 1
            developers[dev_name]['complexes'].append(complex['name'])
        
        return list(developers.values())
    except Exception:
        return []

def search_global(query):
    """Global search across all types: ЖК, districts, developers, streets"""
    if not query or len(query.strip()) < 2:
        return []
    
    search_data = load_search_data()
    results = []
    query_lower = query.lower().strip()
    
    # Search through all categories
    for category in ['residential_complexes', 'districts', 'developers', 'streets']:
        items = search_data.get(category, [])
        for item in items:
            # Search in name and keywords
            name_match = query_lower in item['name'].lower()
            keyword_match = any(query_lower in keyword.lower() for keyword in item.get('keywords', []))
            
            if name_match or keyword_match:
                # Calculate relevance score
                score = 0
                if query_lower in item['name'].lower():
                    score += 10  # Higher score for name matches
                if query_lower == item['name'].lower():
                    score += 20  # Even higher for exact matches
                    
                result = {
                    'id': item['id'],
                    'name': item['name'],
                    'type': item['type'],
                    'url': item['url'],
                    'score': score
                }
                
                # Add additional context based on type
                if item['type'] == 'residential_complex':
                    result['district'] = item.get('district', '')
                    result['developer'] = item.get('developer', '')
                elif item['type'] == 'street':
                    result['district'] = item.get('district', '')
                    
                results.append(result)
    
    # Sort by relevance score (highest first)
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:10]  # Return top 10 results

def get_article_by_slug(slug):
    """Get a single article by slug"""
    articles = load_blog_articles()
    for article in articles:
        if article['slug'] == slug:
            return article
    return None

def search_articles(query, category=None):
    """Search articles by title, excerpt, content, and tags"""
    articles = load_blog_articles()
    if not query and not category:
        return articles
    
    filtered_articles = []
    for article in articles:
        # Filter by category if specified
        if category and article['category'].lower() != category.lower():
            continue
        
        # If no search query, return all articles in category
        if not query:
            filtered_articles.append(article)
            continue
        
        # Search in title, excerpt, content, and tags
        query_lower = query.lower()
        if (query_lower in article['title'].lower() or 
            query_lower in article['excerpt'].lower() or 
            query_lower in article['content'].lower() or 
            any(query_lower in tag.lower() for tag in article['tags'])):
            filtered_articles.append(article)
    
    return filtered_articles

def calculate_cashback(price):
    """Calculate cashback amount based on property price"""
    if price < 3000000:
        return int(price * 0.05)  # 5%
    elif price < 5000000:
        return int(price * 0.07)  # 7%
    else:
        return min(int(price * 0.10), 500000)  # 10% up to 500k

def get_property_by_id(property_id):
    """Get a single property by ID"""
    properties = load_properties()
    for prop in properties:
        if str(prop['id']) == str(property_id):
            return prop
    return None

def get_filtered_properties(filters):
    """Filter properties based on criteria"""
    properties = load_properties()
    filtered = []
    
    for prop in properties:
        # Keywords filter (для типов недвижимости, классов, материалов)
        if filters.get('keywords') and len(filters['keywords']) > 0:
            keywords_matched = False
            for keyword in filters['keywords']:
                keyword_lower = keyword.lower()
                
                # Check property type
                prop_type_lower = prop.get('property_type', 'Квартира').lower()
                if keyword_lower == 'дом' and prop_type_lower == 'дом':
                    keywords_matched = True
                    break
                elif keyword_lower == 'таунхаус' and prop_type_lower == 'таунхаус':
                    keywords_matched = True
                    break
                elif keyword_lower == 'пентхаус' and prop_type_lower == 'пентхаус':
                    keywords_matched = True
                    break
                elif keyword_lower == 'апартаменты' and prop_type_lower == 'апартаменты':
                    keywords_matched = True
                    break
                elif keyword_lower == 'студия' and (prop_type_lower == 'студия' or prop.get('rooms') == 0):
                    keywords_matched = True
                    break
                elif keyword_lower == 'квартира' and prop_type_lower == 'квартира':
                    keywords_matched = True
                    break
                
                # Check property class
                elif keyword_lower == prop.get('property_class', '').lower():
                    keywords_matched = True
                    break
                
                # Check wall material
                elif keyword_lower in prop.get('wall_material', '').lower():
                    keywords_matched = True
                    break
                
                # Check features
                elif any(keyword_lower in feature.lower() for feature in prop.get('features', [])):
                    keywords_matched = True
                    break
                
                # Check in property type as fallback  
                elif keyword_lower in (f"{prop.get('rooms', 0)}-комн" if prop.get('rooms', 0) > 0 else "студия").lower():
                    keywords_matched = True
                    break
                    
            if not keywords_matched:
                continue
        
        # Text search
        if filters.get('search'):
            search_term = filters['search'].lower()
            property_title = f"{prop.get('rooms', 0)}-комн" if prop.get('rooms', 0) > 0 else "студия"
            searchable_text = f"{property_title} {prop['developer']} {prop['district']} {prop.get('residential_complex', '')} {prop.get('location', '')}".lower()
            if search_term not in searchable_text:
                continue
        
        # Rooms filter - handle both single value and array
        if filters.get('rooms'):
            rooms_filter = filters['rooms']
            property_rooms = prop['rooms']
            property_type = prop.get('type', '')
            
            # Handle array of rooms from saved searches
            if isinstance(rooms_filter, list):
                rooms_match = False
                for room_filter in rooms_filter:
                    # Handle special cases
                    if room_filter == '4+-комн':
                        if property_rooms >= 4 and property_type == '4+-комн':
                            rooms_match = True
                            break
                        continue
                    elif room_filter == 'студия':
                        if property_rooms == 0 and property_type == 'студия':
                            rooms_match = True
                            break
                        continue
                    # Handle both "2-комн" and "2" formats - match type exactly
                    elif room_filter.endswith('-комн'):
                        # For X-комн format, match the type field exactly
                        if property_type == room_filter:
                            rooms_match = True
                            break
                        continue
                    elif room_filter == '4+':
                        if property_rooms >= 4 and property_type == '4+-комн':
                            rooms_match = True
                            break
                        continue
                    else:
                        try:
                            room_number = int(room_filter)
                            expected_type = f'{room_number}-комн'
                            if property_rooms == room_number and property_type == expected_type:
                                rooms_match = True
                                break
                        except (ValueError, TypeError):
                            continue
                
                if not rooms_match:
                    continue
            else:
                # Handle single room value
                if rooms_filter == '4+-комн':
                    if property_type != '4+-комн':
                        continue
                elif rooms_filter == '4+':
                    if property_type != '4+-комн':
                        continue
                elif rooms_filter == 'студия':
                    if property_type != 'студия':
                        continue
                else:
                    try:
                        if rooms_filter.endswith('-комн'):
                            # For X-комн format, match the type field exactly
                            if property_type != rooms_filter:
                                continue
                        else:
                            room_number = int(rooms_filter)
                            expected_type = f'{room_number}-комн'
                            if property_type != expected_type:
                                continue
                    except (ValueError, TypeError):
                        continue
        
        # Price filter - handle both raw rubles and millions
        if filters.get('price_min') and filters['price_min']:
            try:
                min_price = int(filters['price_min'])
                # If value is small, assume it's in millions
                if min_price < 1000:
                    min_price = min_price * 1000000
                if prop['price'] < min_price:
                    continue
            except (ValueError, TypeError):
                pass
        if filters.get('price_max') and filters['price_max']:
            try:
                max_price = int(filters['price_max'])
                # If value is small, assume it's in millions
                if max_price < 1000:
                    max_price = max_price * 1000000
                if prop['price'] > max_price:
                    continue
            except (ValueError, TypeError):
                pass
        
        # District filter
        if filters.get('district') and prop['district'] != filters['district']:
            continue
        
        # Developer filter
        if filters.get('developer') and prop['developer'] != filters['developer']:
            continue
        
        # Residential complex filter
        if filters.get('residential_complex'):
            residential_complex = filters['residential_complex'].lower()
            prop_complex = prop.get('complex_name', '').lower()
            if residential_complex not in prop_complex:
                continue
        
        # Street filter
        if filters.get('street'):
            street = filters['street'].lower()
            prop_location = prop.get('location', '').lower()
            prop_address = prop.get('full_address', '').lower()
            if street not in prop_location and street not in prop_address:
                continue
        
        # Mortgage filter
        if filters.get('mortgage') and not prop.get('mortgage_available', False):
            continue
        
        filtered.append(prop)
    
    return filtered

def get_developers_list():
    """Get list of unique developers"""
    properties = load_properties()
    developers = set()
    for prop in properties:
        if 'developer' in prop and prop['developer']:
            developers.add(prop['developer'])
    return sorted(list(developers))

def get_districts_list():
    """Get list of unique districts"""
    properties = load_properties()
    districts = set()
    for prop in properties:
        districts.add(prop['district'])
    return sorted(list(districts))

def sort_properties(properties, sort_type):
    """Sort properties by specified criteria"""
    if sort_type == 'price_asc':
        return sorted(properties, key=lambda x: x['price'])
    elif sort_type == 'price_desc':
        return sorted(properties, key=lambda x: x['price'], reverse=True)
    elif sort_type == 'cashback_desc':
        return sorted(properties, key=lambda x: calculate_cashback(x['price']), reverse=True)
    elif sort_type == 'area_asc':
        return sorted(properties, key=lambda x: x['area'])
    elif sort_type == 'area_desc':
        return sorted(properties, key=lambda x: x['area'], reverse=True)
    else:
        return properties

def get_similar_properties(property_id, district, limit=3):
    """Get similar properties in the same district"""
    properties = load_properties()
    similar = []
    
    for prop in properties:
        if str(prop['id']) != str(property_id) and prop['district'] == district:
            similar.append(prop)
            if len(similar) >= limit:
                break
    
    return similar

# Routes
@app.route('/')
def index():
    """Home page with featured content"""
    properties = load_properties()
    complexes = load_residential_complexes()
    developers_file = os.path.join('data', 'developers.json')
    with open(developers_file, 'r', encoding='utf-8') as f:
        developers = json.load(f)
    
    # Get featured properties (top 6 with highest cashback)
    featured_properties = sorted(properties, key=lambda x: x.get('cashback_amount', 0), reverse=True)[:6]
    
    # Calculate cashback for featured properties
    for prop in featured_properties:
        prop['cashback'] = calculate_cashback(prop['price'])
    
    # Get districts with statistics
    districts_data = {}
    for complex in complexes:
        district = complex['district']
        if district not in districts_data:
            districts_data[district] = {
                'name': district,
                'complexes_count': 0,
                'price_from': float('inf'),
                'apartments_count': 0
            }
        districts_data[district]['complexes_count'] += 1
        districts_data[district]['price_from'] = min(districts_data[district]['price_from'], complex.get('price_from', 0))
        districts_data[district]['apartments_count'] += complex.get('apartments_count', 0)
    
    districts = sorted(districts_data.values(), key=lambda x: x['complexes_count'], reverse=True)[:8]
    
    # Get featured developers (top 3 with most complexes)
    featured_developers = []
    for developer in developers[:3]:
        developer_complexes = [c for c in complexes if c.get('developer_id') == developer['id']]
        developer_properties = [p for p in properties if any(c['id'] == p.get('complex_id') for c in developer_complexes)]
        
        developer_info = {
            'id': developer['id'],
            'name': developer['name'],
            'complexes_count': len(developer_complexes),
            'apartments_count': len(developer_properties),
            'price_from': min([p['price'] for p in developer_properties]) if developer_properties else 0,
            'max_cashback': max([c.get('cashback_percent', 5) for c in developer_complexes]) if developer_complexes else 5
        }
        featured_developers.append(developer_info)
    
    return render_template('index.html',
                         featured_properties=featured_properties,
                         districts=districts,
                         featured_developers=featured_developers,
                         residential_complexes=complexes[:3])

@app.route('/properties')
def properties():
    """Properties listing page"""
    try:
        print(f"DEBUG: Properties route accessed with args: {dict(request.args)}")
        
        # Get filter parameters with proper handling of multiple values
        filters = {}
        
        # Handle multiple rooms values from saved searches
        rooms_values = request.args.getlist('rooms')
        print(f"DEBUG: Rooms values from request: {rooms_values}")
        
        if rooms_values:
            # Clean and validate room values
            clean_rooms = []
            for room in rooms_values:
                try:
                    # Handle URL decoding issues
                    clean_room = room.strip()
                    if clean_room:
                        clean_rooms.append(clean_room)
                    print(f"DEBUG: Processed room value: '{room}' -> '{clean_room}'")
                except Exception as e:
                    print(f"DEBUG: Error processing room value '{room}': {e}")
                    continue
            
            filters['rooms'] = clean_rooms
        else:
            filters['rooms'] = []
        
        # Handle price parameters
        filters['price_min'] = request.args.get('priceFrom', request.args.get('price_min', ''))
        filters['price_max'] = request.args.get('priceTo', request.args.get('price_max', ''))
        
        # Handle other filter parameters 
        filters['district'] = request.args.get('district', '')
        filters['developer'] = request.args.get('developer', '')
        filters['residential_complex'] = request.args.get('residential_complex', '')
        
        print(f"DEBUG: Final filters object: {filters}")
    except Exception as e:
        print(f"ERROR in properties route: {e}")
        # Return basic page without filters in case of error
        filters = {
            'rooms': [],
            'price_min': '',
            'price_max': '',
            'district': '',
            'developer': '',
            'residential_complex': ''
        }
    filters['street'] = request.args.get('street', '')
    filters['mortgage'] = request.args.get('mortgage', '')
    filters['search'] = request.args.get('search', '')
    
    # Check for saved search by search_id
    search_id = request.args.get('search_id')
    if search_id:
        try:
            from models import SavedSearch
            search = SavedSearch.query.get(int(search_id))
            if search:
                print(f"DEBUG: Loading saved search '{search.name}' (ID: {search_id})")
                # Load filters from additional_filters field
                if search.additional_filters:
                    try:
                        saved_filters = json.loads(search.additional_filters)
                        print(f"DEBUG: Loaded filters from additional_filters: {saved_filters}")
                        
                        # Apply saved filters - override existing filters
                        if saved_filters.get('priceFrom'):
                            filters['price_min'] = saved_filters['priceFrom']
                        if saved_filters.get('priceTo'):
                            filters['price_max'] = saved_filters['priceTo']
                        if saved_filters.get('rooms'):
                            filters['rooms'] = saved_filters['rooms']
                        if saved_filters.get('districts') and len(saved_filters['districts']) > 0:
                            filters['district'] = saved_filters['districts'][0]
                        if saved_filters.get('developers') and len(saved_filters['developers']) > 0:
                            filters['developer'] = saved_filters['developers'][0]
                        
                        print(f"DEBUG: Final filters after applying saved search: {filters}")
                    except (json.JSONDecodeError, TypeError) as e:
                        print(f"DEBUG: Error parsing saved search filters: {e}")
        except (ValueError, TypeError) as e:
            print(f"DEBUG: Error loading saved search {search_id}: {e}")
    
    # Check for additional filters from collection search
    additional_filters_param = request.args.get('additional_filters')
    if additional_filters_param:
        try:
            additional_filters = json.loads(additional_filters_param)
            # Apply additional filters from collection
            if additional_filters.get('priceFrom'):
                filters['price_min'] = additional_filters['priceFrom']
            if additional_filters.get('priceTo'):
                filters['price_max'] = additional_filters['priceTo']
            if additional_filters.get('rooms'):
                filters['rooms'] = additional_filters['rooms']
            if additional_filters.get('districts') and len(additional_filters['districts']) > 0:
                filters['district'] = additional_filters['districts'][0]  # Use first district
            if additional_filters.get('developers') and len(additional_filters['developers']) > 0:
                filters['developer'] = additional_filters['developers'][0]  # Use first developer
        except (json.JSONDecodeError, TypeError):
            pass  # Ignore invalid JSON
    
    try:
        # Get properties based on filters
        print(f"DEBUG: Getting filtered properties with filters: {filters}")
        filtered_properties = get_filtered_properties(filters)
        print(f"DEBUG: Got {len(filtered_properties)} filtered properties")
        
        developers = get_developers_list()
        districts = get_districts_list()
        
        # Sort options
        sort_type = request.args.get('sort', 'price_asc')
        filtered_properties = sort_properties(filtered_properties, sort_type)
        print(f"DEBUG: Properties sorted by {sort_type}")
        
        # Add cashback to each property
        for prop in filtered_properties:
            prop['cashback'] = calculate_cashback(prop['price'])
        
        # Pagination
        page = int(request.args.get('page', 1))
        per_page = 24  # Increased from 12 to 24 for better user experience
        total_properties = len(filtered_properties)
        total_pages = (total_properties + per_page - 1) // per_page
        offset = (page - 1) * per_page
        properties_page = filtered_properties[offset:offset + per_page]
        print(f"DEBUG: Pagination - page {page}, showing {len(properties_page)} of {total_properties} properties")
        
        # Prepare pagination info
        pagination = {
            'page': page,
            'per_page': per_page,
            'total': total_properties,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages,
            'prev_page': page - 1 if page > 1 else None,
            'next_page': page + 1 if page < total_pages else None
        }
        
        print(f"DEBUG: Rendering properties.html template")
        
        # Check if user is authenticated (either as user or manager)
        user_authenticated = current_user.is_authenticated if hasattr(current_user, 'is_authenticated') else False
        manager_id = session.get('manager_id')
        manager_authenticated = bool(manager_id)
        
        print(f"DEBUG: Authentication status - user: {user_authenticated}, manager_id: {manager_id}, manager_auth: {manager_authenticated}")
        
        # Get current manager info if authenticated as manager
        current_manager = None
        if manager_authenticated:
            from models import Manager
            current_manager = Manager.query.get(manager_id)
            print(f"DEBUG: Current manager: {current_manager}")
        else:
            print("DEBUG: No manager authentication found")
        
        return render_template('properties.html', 
                             properties=properties_page,
                             all_properties=filtered_properties,  # Pass all filtered properties for JS
                             filters=filters,
                             developers=developers,
                             districts=districts,
                             residential_complexes=load_residential_complexes(),
                             sort_type=sort_type,
                             pagination=pagination,
                             user_authenticated=user_authenticated,
                             manager_authenticated=manager_authenticated,
                             current_manager=current_manager)
                             
    except Exception as e:
        print(f"ERROR in properties route after filters processing: {e}")
        import traceback
        traceback.print_exc()
        return f"Error 500: {str(e)}", 500

@app.route('/object/<int:property_id>')
def property_detail(property_id):
    """Individual property page"""
    try:
        property_data = get_property_by_id(property_id)
        
        if not property_data:
            print(f"Property {property_id} not found")
            return redirect(url_for('properties'))
        
        # Ensure all required fields exist for template
        if 'cashback_amount' not in property_data:
            property_data['cashback_amount'] = calculate_cashback(property_data['price'])
        
        # Add missing image field for new properties
        if 'image' not in property_data:
            property_data['image'] = f"https://via.placeholder.com/800x600/0088CC/FFFFFF?text={property_data.get('title', 'Квартира').replace(' ', '+')}"
        
        # Add missing gallery field
        if 'gallery' not in property_data:
            property_data['gallery'] = []
            
        # Add other missing template fields
        if 'description' not in property_data:
            property_data['description'] = f"Продается {property_data.get('title', 'квартира')} в {property_data.get('residential_complex', 'жилом комплексе')}. Отличная планировка, качественная отделка."
        
        # Generate full title format for property detail page: "Студия, 28.5 м², 3/20 эт."
        rooms = property_data.get('rooms', 0)
        area = property_data.get('area', 0)
        floor = property_data.get('floor', 1)
        total_floors = property_data.get('total_floors', 20)
        
        # Generate room type text
        if rooms > 0:
            room_text = f"{rooms}-комнатная квартира"
        else:
            room_text = "Студия"
            
        # Create full detailed title for property page
        title_parts = [room_text]
        
        if area:
            title_parts.append(f"{area} м²")
            
        title_parts.append(f"{floor}/{total_floors} эт.")
        
        # Join with commas for full format
        property_data['title'] = ", ".join(title_parts)
        
        if 'property_type' not in property_data:
            property_data['property_type'] = f"{rooms}-комн" if rooms > 0 else "Студия"
            
        if 'completion_date' not in property_data:
            property_data['completion_date'] = '2025'
            
        if 'total_floors' not in property_data:
            property_data['total_floors'] = 20
            
        if 'apartment_number' not in property_data:
            property_data['apartment_number'] = str(property_data['id'])
            
        if 'building' not in property_data:
            property_data['building'] = 'Корпус 1'
            
        # Add template-required fields
        if 'complex_id' not in property_data:
            property_data['complex_id'] = property_data.get('residential_complex_id', 1)
            
        if 'complex_name' not in property_data:
            property_data['complex_name'] = property_data.get('residential_complex', 'ЖК')
            
        if 'cashback_percent' not in property_data:
            property_data['cashback_percent'] = 3.5
            
        print(f"Rendering property {property_id}: {property_data.get('title', 'Unknown')}")
        return render_template('property_detail_full.html', property=property_data)
        
    except Exception as e:
        print(f"ERROR in property detail route: {e}")
        import traceback
        traceback.print_exc()
        return f"Error 500: {str(e)}", 500

@app.route('/residential_complex/<int:complex_id>')
@app.route('/residential-complex/<int:complex_id>')  # Support both formats
def residential_complex_detail(complex_id):
    """Individual residential complex page"""
    try:
        complexes = load_residential_complexes()
        complex_data = None
        
        for complex_item in complexes:
            if complex_item['id'] == complex_id:
                complex_data = complex_item
                break
        
        if not complex_data:
            print(f"Complex {complex_id} not found")
            return redirect(url_for('properties'))
        
        # Ensure required fields exist
        if 'price_from' not in complex_data:
            complex_data['price_from'] = 3000000
        if 'real_price_from' not in complex_data:
            complex_data['real_price_from'] = complex_data['price_from']
        if 'cashback_percent' not in complex_data:
            complex_data['cashback_percent'] = 3.5
        
        # Add developer_id for link functionality
        if 'developer_id' not in complex_data:
            developer_mapping = {
                'ГК «Инвестстройкуб»': 1,
                'ЖК Девелопмент': 2,
                'Краснодар Строй': 3,
                'Южный Дом': 4,
                'Кубань Девелопмент': 5
            }
            developer_name = complex_data.get('developer', '')
            complex_data['developer_id'] = developer_mapping.get(developer_name, 1)
        
        # Get all properties in this complex - use correct field mapping
        properties = load_properties()
        complex_properties = [
            prop for prop in properties 
            if prop.get('residential_complex_id') == complex_id or
               prop.get('residential_complex', '').lower() == complex_data['name'].lower()
        ]
        
        # Ensure cashback_amount exists for all properties
        for prop in complex_properties:
            if 'cashback_amount' not in prop and 'price' in prop:
                prop['cashback_amount'] = int(prop['price'] * 0.035)
        
        # Group properties by room count
        properties_by_rooms = {}
        for prop in complex_properties:
            room_type = prop.get('type', '1-комн')
            if room_type not in properties_by_rooms:
                properties_by_rooms[room_type] = []
            properties_by_rooms[room_type].append(prop)
        
        print(f"Rendering complex {complex_id}: {complex_data.get('name', 'Unknown')}")
        return render_template('residential_complex_detail.html', 
                             complex=complex_data,
                             properties=complex_properties,
                             properties_by_rooms=properties_by_rooms)
                             
    except Exception as e:
        print(f"ERROR in complex detail route: {e}")
        import traceback
        traceback.print_exc()
        return f"Error 500: {str(e)}", 500

@app.route('/developer/<int:developer_id>')
def developer_detail(developer_id):
    """Individual developer page"""
    try:
        # Load developer data from JSON file instead of DB to avoid conflicts
        with open('data/developers.json', 'r', encoding='utf-8') as f:
            developers_data = json.load(f)
        
        # Find developer by ID
        developer = None
        for dev in developers_data:
            if dev['id'] == developer_id:
                developer = dev
                break
        
        if not developer:
            return "Застройщик не найден", 404
        
        # Add missing template fields for new developers
        if 'total_apartments_sold' not in developer:
            developer['total_apartments_sold'] = 150
        if 'projects_completed' not in developer:
            developer['projects_completed'] = 8
        if 'years_experience' not in developer:
            developer['years_experience'] = 10
        if 'rating' not in developer:
            developer['rating'] = 4.5
        if 'construction_technology' not in developer:
            developer['construction_technology'] = 'Монолитно-каркасная'
        if 'warranty_years' not in developer:
            developer['warranty_years'] = 5
        if 'advantages' not in developer:
            developer['advantages'] = [
                'Качественное строительство',
                'Соблюдение сроков сдачи',
                'Развитая инфраструктура',
                'Выгодные условия покупки'
            ]
        
        # Get all complexes by this developer
        complexes = load_residential_complexes()
        developer_complexes = [c for c in complexes if c.get('developer_id') == developer_id or c.get('developer') == developer['name']]
        
        # Get all properties by this developer
        properties = load_properties()
        developer_properties = [p for p in properties if p.get('developer') == developer['name']]
        
        return render_template('developer_detail.html',
                             developer=developer,
                             complexes=developer_complexes,
                             properties=developer_properties)
    except Exception as e:
        print(f"ERROR in developer_detail route: {e}")
        import traceback
        traceback.print_exc()
        return f"Error 500: {str(e)}", 500

@app.route('/object/<int:property_id>/pdf')
def property_pdf(property_id):
    """Property PDF card page"""
    property_data = get_property_by_id(property_id)
    if not property_data:
        return redirect(url_for('properties'))
    
    # Calculate cashback for this property
    cashback = calculate_cashback(property_data['price'])
    
    # Get current date for PDF generation
    current_date = datetime.now().strftime('%d.%m.%Y')
    
    return render_template('property_pdf.html', 
                         property=property_data,
                         cashback=cashback,
                         current_date=current_date)

@app.route('/about')
def about():
    """About page"""
    return render_template('about.html')

@app.route('/how-it-works')
def how_it_works():
    """How it works page"""
    return render_template('how-it-works.html')

@app.route('/reviews')
def reviews():
    """Reviews page"""
    return render_template('reviews_original.html')

@app.route('/contacts')
def contacts():
    """Contacts page"""
    return render_template('contacts.html')

@app.route('/blog')
def blog():
    """Blog main page with articles listing, search, and categories"""
    from models import BlogPost, BlogCategory
    from sqlalchemy import text
    
    # Get search parameters  
    search_query = request.args.get('search', '')
    category_filter = request.args.get('category', '')
    page = int(request.args.get('page', 1))
    per_page = 6
    
    # Use blog_posts table which has the actual content including "Тенденции рынка недвижимости"
    query = BlogPost.query.filter_by(status='published')
    
    # Apply search filter
    if search_query:
        query = query.filter(
            db.or_(
                BlogPost.title.contains(search_query),
                BlogPost.content.contains(search_query),
                BlogPost.excerpt.contains(search_query)
            )
        )
    
    # Apply category filter
    if category_filter:
        if category_filter.lower() == 'test':
            category_name = 'Тест'
        else:
            category = BlogCategory.query.filter(
                (BlogCategory.slug == category_filter) | 
                (BlogCategory.name == category_filter)
            ).first()
            if category:
                category_name = category.name
            else:
                category_name = category_filter
        
        query = query.filter_by(category=category_name)
    
    # Get paginated results
    total_articles = query.count()
    articles = query.order_by(
        BlogPost.published_at.desc().nulls_last(),
        BlogPost.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    # Get categories with article counts
    categories = []
    for category in BlogCategory.query.filter_by(is_active=True).order_by(BlogCategory.name).all():
        article_count = BlogPost.query.filter_by(category=category.name, status='published').count()
        if article_count > 0:
            category.articles_count = article_count
            categories.append(category)
    
    # Get featured articles
    featured_articles = BlogPost.query.filter_by(status='published').limit(3).all()
    
    return render_template('blog.html',
                         articles=articles.items,
                         categories=categories,
                         featured_articles=featured_articles,
                         search_query=search_query,
                         category_filter=category_filter,
                         current_page=page,
                         total_pages=articles.pages,
                         total_articles=total_articles)

# Removed duplicate blog route - using blog_post function at line 7515

@app.route('/blog/category/<category_slug>')
def blog_category(category_slug):
    """Blog category page"""
    from models import BlogPost, BlogCategory
    
    # Поиск категории по slug или по имени
    category = BlogCategory.query.filter(
        (BlogCategory.slug == category_slug) | 
        (BlogCategory.name.ilike(f'%{category_slug}%'))
    ).first()
    
    if not category:
        return redirect(url_for('blog'))
    
    # Get articles in this category
    page = int(request.args.get('page', 1))
    per_page = 6
    
    # Ищем статьи по названию категории
    articles_query = BlogPost.query.filter_by(status='published').filter(
        BlogPost.category == category.name
    ).order_by(BlogPost.published_at.desc(), BlogPost.created_at.desc())
    
    articles = articles_query.paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get all categories for navigation
    categories = BlogCategory.query.all()
    
    return render_template('blog_category.html',
                         category=category,
                         articles=articles.items,
                         categories=categories,
                         current_page=page,
                         total_pages=articles.pages)

@app.route('/news')
def news():
    """News article page"""
    return render_template('news.html')

@app.route('/streets')
def streets():
    """Streets page"""
    streets_data = load_streets()
    
    # Sort streets alphabetically
    streets_data.sort(key=lambda x: x['name'])
    
    return render_template('streets.html', 
                         streets=streets_data)

@app.route('/streets/<path:street_name>')
def street_detail(street_name):
    """Страница конкретной улицы с описанием и картой"""
    try:
        streets_data = load_streets()
        
        # Ищем улицу по имени (учитываем URL-кодирование)
        street_name_decoded = street_name.replace('-', ' ').replace('_', ' ')
        street = None
        
        # Логируем для отладки
        app.logger.debug(f"Looking for street: {street_name} -> {street_name_decoded}")
        
        # Функция транслитерации для поиска старых URL
        def translit_to_latin(text):
            translit_map = {
                'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
                'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'i', 'к': 'k', 'л': 'l', 'м': 'm',
                'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
                'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
                'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
            }
            result = ''
            for char in text.lower():
                result += translit_map.get(char, char)
            return result
        
        for s in streets_data:
            # Создаем URL-slug точно так же, как в фильтре (с кириллицей)
            street_slug_generated = s['name'].lower().replace(' ', '-').replace('.', '').replace('(', '').replace(')', '').replace(',', '')
            
            # Создаем полную транслитерацию для обратной совместимости
            translit_name = translit_to_latin(s['name'])
            translit_slug = translit_name.replace(' ', '-').replace('.', '').replace('(', '').replace(')', '').replace(',', '')
            
            # Простая замена символов (как было раньше)
            simple_translit = s['name'].lower().replace(' ', '-').replace('.', '').replace('ё', 'e').replace('й', 'i').replace('а', 'a').replace('г', 'g').replace('р', 'r').replace('и', 'i').replace('н', 'n').replace('(', '').replace(')', '').replace(',', '')
            
            # Множественные варианты поиска
            if (street_slug_generated == street_name.lower() or
                translit_slug == street_name.lower() or
                simple_translit == street_name.lower() or
                s['name'].lower() == street_name_decoded.lower() or
                s['name'].lower().replace(' ул.', '').replace(' ул', '') == street_name_decoded.lower().replace(' ул.', '').replace(' ул', '')):
                street = s
                app.logger.debug(f"Found street: {s['name']} with slug: {street_slug_generated}, translit: {translit_slug}")
                break
        
        if not street:
            # Пробуем найти частичное совпадение
            for s in streets_data:
                street_name_clean = street_name_decoded.lower().replace('ул', '').replace('.', '').strip()
                street_db_clean = s['name'].lower().replace('ул.', '').replace('ул', '').replace('.', '').strip()
                
                if (street_name_clean in street_db_clean or 
                    street_db_clean in street_name_clean or
                    street_name_decoded.lower() in s['name'].lower()):
                    street = s
                    app.logger.debug(f"Found street by partial match: {s['name']}")
                    break
        
        if not street:
            app.logger.error(f"Street not found: {street_name} ({street_name_decoded})")
            abort(404)
        
        # Генерируем координаты для карты (примерные координаты Краснодара)
        import random
        random.seed(hash(street['name']))  # Фиксированные координаты для каждой улицы
        
        # Краснодар: широта 45.035470, долгота 38.975313
        base_lat = 45.035470
        base_lng = 38.975313
        
        # Добавляем случайное смещение в пределах города
        lat_offset = random.uniform(-0.08, 0.08)  # примерно ±9 км
        lng_offset = random.uniform(-0.12, 0.12)  # примерно ±9 км
        
        coordinates = {
            'lat': base_lat + lat_offset,
            'lng': base_lng + lng_offset
        }
        
        # Загружаем данные о свойствах для этой улицы (если есть)
        properties_on_street = []
        try:
            with open('data/properties_new.json', 'r', encoding='utf-8') as f:
                properties_data = json.load(f)
            
            # Фильтруем свойства по улице
            for prop in properties_data:
                if (street['name'].lower() in prop.get('location', '').lower() or
                    street['name'].lower() in prop.get('full_address', '').lower()):
                    properties_on_street.append(prop)
        except:
            pass
        
        return render_template('street_detail.html',
                             street=street,
                             coordinates=coordinates,
                             properties=properties_on_street,
                             title=f'{street["name"]} - новостройки с кэшбеком | InBack')
    
    except Exception as e:
        app.logger.error(f"Error loading street detail: {e}")
        abort(404)

@app.route('/sitemap.xml')
def sitemap():
    """Generate XML sitemap with all street pages"""
    try:
        streets_data = load_streets()
        
        # Создаем XML для sitemap
        xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml_content += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        
        # Основные страницы
        main_pages = [
            ('/', '2025-08-04', 'daily', '1.0'),
            ('/streets', '2025-08-04', 'weekly', '0.9'),
            ('/properties', '2025-08-04', 'daily', '0.8'),
            ('/about', '2025-08-04', 'monthly', '0.7'),
            ('/contacts', '2025-08-04', 'monthly', '0.7'),
        ]
        
        for url, lastmod, changefreq, priority in main_pages:
            xml_content += f'  <url>\n'
            xml_content += f'    <loc>{request.host_url.rstrip("/")}{url}</loc>\n'
            xml_content += f'    <lastmod>{lastmod}</lastmod>\n'
            xml_content += f'    <changefreq>{changefreq}</changefreq>\n'
            xml_content += f'    <priority>{priority}</priority>\n'
            xml_content += f'  </url>\n'
        
        # Страницы улиц
        for street in streets_data:
            slug = street['name'].lower().replace(' ', '-').replace('.', '').replace('ё', 'е').replace('й', 'и').replace('(', '').replace(')', '').replace(',', '')
            xml_content += f'  <url>\n'
            xml_content += f'    <loc>{request.host_url.rstrip("/")}/streets/{slug}</loc>\n'
            xml_content += f'    <lastmod>2025-08-04</lastmod>\n'
            xml_content += f'    <changefreq>weekly</changefreq>\n'
            xml_content += f'    <priority>0.8</priority>\n'
            xml_content += f'  </url>\n'
        
        xml_content += '</urlset>'
        
        response = app.response_class(
            response=xml_content,
            status=200,
            mimetype='application/xml'
        )
        
        return response
        
    except Exception as e:
        app.logger.error(f"Error generating sitemap: {e}")
        abort(500)

@app.route('/comparison')
def comparison():
    """Unified comparison page for properties and complexes"""
    return render_template('comparison.html')

@app.route('/thank-you')
def thank_you():
    """Thank you page after form submission"""
    return render_template('thank_you.html')

@app.route('/api/property/<int:property_id>')
def api_property_detail(property_id):
    """API endpoint to get property data for comparison"""
    property_data = get_property_by_id(property_id)
    
    if not property_data:
        return jsonify({'error': 'Property not found'}), 404
    
    # Calculate cashback for the property
    property_data['cashback'] = calculate_cashback(property_data['price'])
    
    return jsonify(property_data)

@app.route('/complex-comparison')
def complex_comparison():
    """Complex comparison page"""
    return render_template('complex_comparison.html')

@app.route('/api/complex/<int:complex_id>')
def api_complex_detail(complex_id):
    """API endpoint to get complex data for comparison"""
    complexes = load_residential_complexes()
    complex_data = None
    
    for complex in complexes:
        if complex['id'] == complex_id:
            complex_data = complex
            break
    
    if not complex_data:
        return jsonify({'error': 'Complex not found'}), 404
    
    return jsonify(complex_data)

@app.route('/favorites')
def favorites():
    """Favorites page with animated heart pulse effects"""
    return render_template('favorites.html')



@app.route('/robots.txt')
def robots_txt():
    """Robots.txt for search engine crawlers"""
    robots_content = """User-agent: *
Allow: /
Disallow: /admin/
Disallow: /auth/
Disallow: /api/
Disallow: /manager/
Disallow: /dashboard

Sitemap: https://inback.ru/sitemap.xml

# Crawl-delay for better server performance
Crawl-delay: 1

# Specific rules for major search engines
User-agent: Googlebot
Allow: /
Disallow: /admin/
Disallow: /auth/
Disallow: /api/
Disallow: /manager/

User-agent: Yandex
Allow: /
Disallow: /admin/
Disallow: /auth/
Disallow: /api/
Disallow: /manager/

User-agent: Bingbot
Allow: /
Disallow: /admin/
Disallow: /auth/
Disallow: /api/
Disallow: /manager/"""
    
    return app.response_class(
        response=robots_content,
        status=200,
        mimetype='text/plain'
    )

# Old blog search function removed - using updated version at bottom of file


@app.route('/api/residential-complexes')
def api_residential_complexes():
    """API endpoint for getting residential complexes for cashback calculator"""
    try:
        from models import ResidentialComplex
        
        complexes = ResidentialComplex.query.all()
        api_complexes = []
        
        for complex in complexes:
            api_complexes.append({
                'id': complex.id,
                'name': complex.name,
                'cashback_rate': float(complex.cashback_rate) if complex.cashback_rate else 5.0
            })
        
        return jsonify({'complexes': api_complexes})
    
    except Exception as e:
        # Fallback to simple list if model not available
        return jsonify({
            'complexes': [
                {'id': 1, 'name': 'ЖК «Первое место»', 'cashback_rate': 5.5},
                {'id': 2, 'name': 'ЖК «Аврора»', 'cashback_rate': 6.0},
                {'id': 3, 'name': 'ЖК «Седьмое небо»', 'cashback_rate': 7.0},
                {'id': 4, 'name': 'ЖК «Морская волна»', 'cashback_rate': 5.0},
                {'id': 5, 'name': 'ЖК «Комплекс-3»', 'cashback_rate': 6.5},
                {'id': 6, 'name': 'ЖК «Комплекс-8»', 'cashback_rate': 5.5},
                {'id': 7, 'name': 'ЖК «Комплекс-18»', 'cashback_rate': 7.5},
                {'id': 8, 'name': 'ЖК «Комплекс-25»', 'cashback_rate': 8.0}
            ]
        })

@app.route('/api/residential-complexes-full')
def api_residential_complexes_full():
    """API endpoint for getting all residential complexes from JSON file"""
    complexes = load_residential_complexes()
    return jsonify({'complexes': complexes})

@app.route('/api/cashback/calculate', methods=['POST'])
def api_calculate_cashback():
    """API endpoint for calculating cashback"""
    try:
        data = request.get_json()
        price = float(data.get('price', 0))
        complex_id = data.get('complex_id')
        
        if not price or price <= 0:
            return jsonify({'error': 'Invalid price'}), 400
        
        # Get cashback rate from database
        cashback_rate = 5.0  # default
        
        if complex_id:
            try:
                from models import ResidentialComplex
                complex = ResidentialComplex.query.get(complex_id)
                if complex and complex.cashback_rate:
                    cashback_rate = float(complex.cashback_rate)
            except:
                # Fallback rates
                complex_rates = {
                    1: 5.5, 2: 6.0, 3: 7.0, 4: 5.0,
                    5: 6.5, 6: 5.5, 7: 7.5, 8: 8.0
                }
                cashback_rate = complex_rates.get(int(complex_id), 5.0)
        
        cashback_amount = price * (cashback_rate / 100)
        
        # Cap at maximum
        max_cashback = 500000
        if cashback_amount > max_cashback:
            cashback_amount = max_cashback
        
        return jsonify({
            'cashback_amount': int(cashback_amount),
            'cashback_rate': cashback_rate,
            'price': int(price),
            'formatted_amount': f"{int(cashback_amount):,}".replace(',', ' ')
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cashback/apply', methods=['POST'])
def api_apply_cashback():
    """API endpoint for submitting cashback application"""
    try:
        from models import CallbackRequest
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Неверный формат данных'}), 400
            
        price = data.get('price')
        complex_id = data.get('complex_id')
        complex_name = data.get('complex_name', 'Не указан')
        cashback_amount = data.get('cashback_amount')
        user_phone = data.get('phone', '')
        user_name = data.get('name', '')
        
        # Validate required fields
        if not all([price, cashback_amount, user_phone, user_name]):
            return jsonify({'error': 'Заполните все обязательные поля'}), 400
        
        # Validate data types
        try:
            price = float(price)
            cashback_amount = float(cashback_amount)
        except (ValueError, TypeError):
            return jsonify({'error': 'Неверный формат числовых данных'}), 400
        
        # Create callback request
        callback = CallbackRequest(
            name=user_name,
            phone=user_phone,
            notes=f"Заявка на кешбек {int(cashback_amount):,} ₽ при покупке квартиры в {complex_name} стоимостью {int(price):,} ₽".replace(',', ' ')
        )
        
        db.session.add(callback)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Заявка успешно отправлена! Менеджер свяжется с вами в ближайшее время.'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Ошибка при отправке заявки: {str(e)}'}), 500

@app.route('/api/search/suggestions')
def search_suggestions():
    """API endpoint for search suggestions (autocomplete)"""
    query = request.args.get('q', '').lower().strip()
    if not query or len(query) < 2:
        return jsonify([])
    
    suggestions = []
    
    try:
        # Search in residential complexes
        complexes = load_residential_complexes()
        for complex in complexes[:50]:  # Limit results
            if query in complex['name'].lower():
                suggestions.append({
                    'type': 'complex',
                    'name': complex['name'],
                    'subtitle': f"{complex['district']} • от {complex['price_from']:,} ₽".replace(',', ' '),
                    'url': url_for('properties', complex=complex['name'])
                })
        
        # Search in developers
        developers = load_developers()
        for developer in developers[:20]:
            if query in developer['name'].lower():
                suggestions.append({
                    'type': 'developer',
                    'name': developer['name'],
                    'subtitle': f"Застройщик • {developer.get('projects_count', 'много')} проектов",
                    'url': url_for('properties', developer=developer['name'])
                })
        
        # Search in streets
        streets = load_streets()
        for street in streets[:30]:
            if query in street['name'].lower():
                suggestions.append({
                    'type': 'street',
                    'name': street['name'],
                    'subtitle': f"{street['district']} • {street['properties_count']} квартир",
                    'url': url_for('properties', street=street['name'])
                })
        
        # Sort by relevance (exact matches first)
        suggestions.sort(key=lambda x: (
            0 if x['name'].lower().startswith(query) else 1,
            len(x['name'])
        ))
        
        return jsonify(suggestions[:10])  # Return top 10 suggestions
        
    except Exception as e:
        app.logger.error(f"Error in search suggestions: {e}")
        return jsonify([])

# Mortgage routes
@app.route('/ipoteka')
def ipoteka():
    """Main mortgage page"""
    return render_template('ipoteka.html')

@app.route('/family-mortgage')
def family_mortgage():
    """Family mortgage page"""
    return render_template('family_mortgage.html')

@app.route('/it-mortgage')
def it_mortgage():
    """IT mortgage page"""
    return render_template('it_mortgage.html')

@app.route('/military-mortgage')
def military_mortgage():
    """Military mortgage page"""
    return render_template('military_mortgage.html')

@app.route('/developer-mortgage')
def developer_mortgage():
    """Developer mortgage page"""
    return render_template('developer_mortgage.html')

@app.route('/maternal-capital')
def maternal_capital():
    """Maternal capital page"""
    return render_template('maternal_capital.html')

@app.route('/residential')
def residential():
    """Residential complexes page"""
    return render_template('residential.html')

@app.route('/residential-complexes')
def residential_complexes():
    complexes = load_residential_complexes()
    properties = load_properties()
    
    
    # Add real estate statistics to each complex
    for complex in complexes:
        complex_properties = [prop for prop in properties if prop.get('complex_id') == complex['id'] or prop.get('residential_complex_id') == complex['id']]
        complex['available_apartments'] = len(complex_properties)
        
        # Calculate real statistics from properties
        if complex_properties:
            # Real price range from actual properties
            prices = [prop['price'] for prop in complex_properties]
            complex['real_price_from'] = min(prices)
            complex['real_price_to'] = max(prices)
            
            # Real area range
            areas = [prop['area'] for prop in complex_properties]
            complex['real_area_from'] = min(areas)
            complex['real_area_to'] = max(areas)
            
            # Real buildings count
            buildings = set(prop.get('building', 'Корпус 1') for prop in complex_properties)
            complex['real_buildings_count'] = len(buildings)
            
            # Real room type distribution
            room_stats = {}
            for prop in complex_properties:
                room_type = f"{prop['rooms']}-комн" if prop['rooms'] > 0 else "Студия"
                if room_type not in room_stats:
                    room_stats[room_type] = 0
                room_stats[room_type] += 1
            complex['real_room_distribution'] = room_stats
    
    # Get unique districts and developers
    districts = sorted(list(set(complex['district'] for complex in complexes)))
    developers = sorted(list(set(complex['developer'] for complex in complexes)))
    
    # Pagination
    page = int(request.args.get('page', 1))
    per_page = 35  # Show all complexes on one page
    total_complexes = len(complexes)
    total_pages = (total_complexes + per_page - 1) // per_page
    offset = (page - 1) * per_page
    complexes_page = complexes[offset:offset + per_page]
    
    # Prepare pagination info
    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total_complexes,
        'total_pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_page': page - 1 if page > 1 else None,
        'next_page': page + 1 if page < total_pages else None
    }
    
    return render_template('residential_complexes.html',
                         residential_complexes=complexes_page,
                         all_complexes=complexes,  # For JavaScript filtering
                         districts=districts,
                         developers=developers,
                         pagination=pagination)





@app.route('/map')
def map_view():
    """Enhanced interactive map view page using the same data as /properties"""
    # Use the same filtering logic as properties page
    filters = {
        'rooms': request.args.getlist('rooms'),
        'price_min': request.args.get('price_min', ''),
        'price_max': request.args.get('price_max', ''),
        'district': request.args.get('district', ''),
        'developer': request.args.get('developer', ''),
        'residential_complex': request.args.get('residential_complex', ''),
        'street': request.args.get('street', ''),
        'mortgage': request.args.get('mortgage', ''),
        'search': request.args.get('search', '')
    }
    
    # Get filtered properties using the same function as /properties
    properties = get_filtered_properties(filters)
    residential_complexes = load_residential_complexes()
    
    # Add coordinates to properties if missing
    for i, prop in enumerate(properties):
        prop['cashback'] = calculate_cashback(prop['price'])
        prop['cashback_available'] = True
        if 'coordinates' not in prop:
            # Generate realistic coordinates around Krasnodar
            base_lat = 45.0448
            base_lng = 38.9760
            property_title = f"{prop.get('rooms', 0)}-комн-{prop.get('area', 0)}"
            lat_offset = (hash(str(i) + property_title) % 1000) / 10000 - 0.05
            lng_offset = (hash(str(i) + prop.get('location', '')) % 1000) / 10000 - 0.05
            prop['coordinates'] = {
                'lat': base_lat + lat_offset,
                'lng': base_lng + lng_offset
            }
    
    # Add coordinates to complexes if missing
    for i, complex in enumerate(residential_complexes):
        if 'coordinates' not in complex:
            base_lat = 45.0448
            base_lng = 38.9760
            lat_offset = (hash(str(i) + complex.get('name', '')) % 1000) / 8000 - 0.0625
            lng_offset = (hash(str(i) + complex.get('district', '')) % 1000) / 8000 - 0.0625
            complex['coordinates'] = {
                'lat': base_lat + lat_offset,
                'lng': base_lng + lng_offset
            }
    
    # Get unique values for filter options - same as properties page
    all_districts = sorted(list(set(prop.get('district', 'Не указан') for prop in properties)))
    all_developers = sorted(list(set(prop.get('developer', 'Не указан') for prop in properties)))
    all_complexes = sorted(list(set(prop.get('residential_complex', 'Не указан') for prop in properties)))
    
    return render_template('map.html', 
                         properties=properties, 
                         residential_complexes=residential_complexes,
                         all_districts=all_districts,
                         all_developers=all_developers,
                         all_complexes=all_complexes,
                         filters=filters)

# API Routes
@app.route('/api/properties')
def api_properties():
    """API endpoint for properties with enhanced data for map using the same filters as /properties"""
    # Use the same filtering logic as properties page
    filters = {
        'rooms': request.args.getlist('rooms'),
        'price_min': request.args.get('price_min', ''),
        'price_max': request.args.get('price_max', ''),
        'district': request.args.get('district', ''),
        'developer': request.args.get('developer', ''),
        'residential_complex': request.args.get('residential_complex', ''),
        'street': request.args.get('street', ''),
        'mortgage': request.args.get('mortgage', ''),
        'search': request.args.get('search', '')
    }
    
    # Get filtered properties using the same function as /properties
    properties = get_filtered_properties(filters)
    
    # Enhance properties data for map
    for i, prop in enumerate(properties):
        prop['cashback'] = calculate_cashback(prop['price'])
        prop['cashback_available'] = True
        
        # Add coordinates if missing
        if 'coordinates' not in prop:
            base_lat = 45.0448
            base_lng = 38.9760
            property_title = f"{prop.get('rooms', 0)}-комн-{prop.get('area', 0)}"
            lat_offset = (hash(str(i) + property_title) % 1000) / 10000 - 0.05
            lng_offset = (hash(str(i) + prop.get('location', '')) % 1000) / 10000 - 0.05
            prop['coordinates'] = {
                'lat': base_lat + lat_offset,
                'lng': base_lng + lng_offset
            }
        
        # Ensure required fields exist
        if 'status' not in prop:
            prop['status'] = 'new' if prop.get('status') == 'building' else 'existing'
        
        if 'address' not in prop:
            prop['address'] = prop.get('location', 'Краснодар')
            
    return jsonify(properties)

@app.route('/api/residential-complexes-map')
def api_residential_complexes_map():
    """API endpoint for residential complexes with enhanced data for map"""
    complexes = load_residential_complexes()
    
    # Enhance complexes data for map
    for i, complex in enumerate(complexes):
        # Add coordinates if missing
        if 'coordinates' not in complex:
            base_lat = 45.0448
            base_lng = 38.9760
            lat_offset = (hash(str(i) + complex.get('name', '')) % 1000) / 8000 - 0.0625
            lng_offset = (hash(str(i) + complex.get('district', '')) % 1000) / 8000 - 0.0625
            complex['coordinates'] = {
                'lat': base_lat + lat_offset,
                'lng': base_lng + lng_offset
            }
        
        # Ensure required fields exist
        if 'buildings_count' not in complex:
            complex['buildings_count'] = 3 + (i % 8)
        if 'apartments_count' not in complex:
            complex['apartments_count'] = 100 + (i % 300)
            
    return jsonify(complexes)

@app.route('/api/property/<int:property_id>')
def api_property(property_id):
    """API endpoint for single property"""
    property_data = get_property_by_id(property_id)
    if property_data:
        property_data['cashback'] = calculate_cashback(property_data['price'])
        return jsonify(property_data)
    return jsonify({'error': 'Property not found'}), 404

@app.route('/api/complex/<int:complex_id>')
def api_complex(complex_id):
    """API endpoint for single residential complex"""
    complexes = load_residential_complexes()
    for complex in complexes:
        if complex.get('id') == complex_id:
            return jsonify(complex)
    return jsonify({'error': 'Complex not found'}), 404

@app.route('/api/property/<int:property_id>/pdf')
def download_property_pdf(property_id):
    """Generate and download PDF for property"""
    try:
        property_data = get_property_by_id(property_id)
        if not property_data:
            return jsonify({'error': 'Property not found'}), 404
        
        # Create simple HTML for PDF generation
        html_content = f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .property-details {{ margin-bottom: 20px; }}
                .detail-row {{ margin-bottom: 10px; }}
                .label {{ font-weight: bold; }}
                .price {{ color: #0088CC; font-size: 24px; font-weight: bold; }}
                .cashback {{ color: #FF5722; font-size: 18px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>InBack - Информация о квартире</h1>
                <p>Квартира #{property_id}</p>
            </div>
            
            <div class="property-details">
                <div class="detail-row">
                    <span class="label">Тип:</span> {property_data.get('rooms', 'Не указано')}
                </div>
                <div class="detail-row">
                    <span class="label">Площадь:</span> {property_data.get('area', 'Не указана')} м²
                </div>
                <div class="detail-row">
                    <span class="label">Этаж:</span> {property_data.get('floor', 'Не указан')}
                </div>
                <div class="detail-row">
                    <span class="label">Застройщик:</span> {property_data.get('developer', 'Не указан')}
                </div>
                <div class="detail-row">
                    <span class="label">ЖК:</span> {property_data.get('residential_complex', 'Не указан')}
                </div>
                <div class="detail-row">
                    <span class="label">Район:</span> {property_data.get('district', 'Не указан')}
                </div>
                <div class="detail-row">
                    <span class="label">Адрес:</span> {property_data.get('location', 'Не указан')}
                </div>
                <div class="detail-row">
                    <span class="label">Статус:</span> {property_data.get('status', 'Не указан')}
                </div>
                
                <div class="detail-row" style="margin-top: 30px;">
                    <div class="price">Цена: {property_data.get('price', 0):,} ₽</div>
                </div>
                <div class="detail-row">
                    <div class="cashback">Кешбек: до {calculate_cashback(property_data.get('price', 0)):,} ₽ (5%)</div>
                </div>
            </div>
            
            <div style="margin-top: 50px; text-align: center; color: #666;">
                <p>InBack.ru - ваш кешбек за новостройки</p>
                <p>Телефон: +7 (800) 123-12-12</p>
            </div>
        </body>
        </html>
        """
        
        # Return HTML for PDF conversion (browser will handle PDF generation)
        response = app.response_class(
            response=html_content,
            status=200,
            mimetype='text/html'
        )
        response.headers['Content-Disposition'] = f'attachment; filename=property-{property_id}.html'
        return response
        
    except Exception as e:
        print(f"Error generating PDF for property {property_id}: {e}")
        return jsonify({'error': 'Failed to generate PDF'}), 500

@app.route('/developers')
def developers():
    """Developers listing page"""
    try:
        # Use the same list of partners as in index.html
        partner_names = [
            'ГК ССК', 'DOGMA', 'ТОЧНО', 'AVA GROUP', 'ЮГСТРОЙИНВЕСТ',
            'НЕОМЕТРИЯ', 'ВКБ-НОВОСТРОЙКИ', 'МЕТРИКС', 'АЛЬФАСТРОЙИНВЕСТ', 'ГИНСИТИ',
            'СЕМЬЯ', 'ЕВРОПЕЯ', 'ГАРАНТИЯ', 'ЕКАТЕРИНОДАРИНВЕСТ-СТРОЙ', 
            'РОМЕКС ДЕВЕЛОПМЕНТ', 'ДАРСТРОЙ', 'БАУИНВЕСТ'
        ]
        
        # Load residential complexes to get real developers
        with open('static/data/residential_complexes_expanded.json', 'r', encoding='utf-8') as f:
            complexes = json.load(f)
        
        # Load properties for statistics
        with open('data/properties_new.json', 'r', encoding='utf-8') as f:
            properties = json.load(f)
        
        # Get developers with slugs from database
        db_developers = db.session.execute(
            db.text("SELECT name, slug FROM developers")
        ).fetchall()
        
        developer_slugs = {dev.name: dev.slug for dev in db_developers}
        
        # Create developers data only for partners
        developers_data = {}
        for complex_item in complexes:
            developer_name = complex_item.get('developer', 'Не указан')
            if developer_name in partner_names:  # Only include partners
                if developer_name not in developers_data:
                    developers_data[developer_name] = {
                        'name': developer_name,
                        'slug': developer_slugs.get(developer_name, developer_name.lower().replace(' ', '-')),
                        'complexes': [],
                        'complexes_count': 0,
                        'properties_count': 0,
                        'min_price': float('inf'),
                        'max_cashback': 0
                    }
                developers_data[developer_name]['complexes'].append(complex_item)
                developers_data[developer_name]['complexes_count'] += 1
                
                # Update price range
                if complex_item.get('price_from'):
                    developers_data[developer_name]['min_price'] = min(
                        developers_data[developer_name]['min_price'], 
                        complex_item['price_from']
                    )
                
                # Update max cashback
                if complex_item.get('cashback_percent'):
                    developers_data[developer_name]['max_cashback'] = max(
                        developers_data[developer_name]['max_cashback'],
                        complex_item['cashback_percent']
                    )
        
        # Count properties per developer
        for prop in properties:
            developer_name = prop.get('developer', 'Не указан')
            if developer_name in developers_data:
                developers_data[developer_name]['properties_count'] += 1
        
        # Add partners that don't have complexes in database yet (with sample data)
        for partner_name in partner_names:
            if partner_name not in developers_data:
                # Estimate stats based on partner name position
                partner_index = partner_names.index(partner_name)
                developers_data[partner_name] = {
                    'name': partner_name,
                    'slug': developer_slugs.get(partner_name, partner_name.lower().replace(' ', '-')),
                    'complexes': [],
                    'complexes_count': 2 + (partner_index % 8),  # 2-9 complexes
                    'properties_count': 50 + (partner_index * 15),  # 50+ properties
                    'min_price': 4500000 + (partner_index * 200000),  # From 4.5M
                    'max_cashback': 3 + (partner_index % 8)  # 3-10% cashback
                }
        
        # Convert to list and sort by complexes count
        developers_list = []
        for dev_name, dev_data in developers_data.items():
            # Fix infinite price
            if dev_data['min_price'] == float('inf'):
                dev_data['min_price'] = 4500000  # Default minimum
            developers_list.append(dev_data)
        
        # Sort by complexes count (descending)
        developers_list.sort(key=lambda x: x['complexes_count'], reverse=True)
        
        return render_template('developers.html', developers=developers_list)
        
    except Exception as e:
        print(f"Error loading developers: {e}")
        return render_template('developers.html', developers=[])

@app.route('/developer/<developer_name>')
def developer_page(developer_name):
    """Individual developer page by name"""
    try:
        # Decode URL-encoded name
        import urllib.parse
        developer_name_decoded = urllib.parse.unquote(developer_name).replace('-', ' ')
        
        # Try to find developer in database
        developer = db.session.execute(
            db.text("SELECT * FROM developers WHERE name = :name OR slug = :slug LIMIT 1"),
            {"name": developer_name_decoded, "slug": developer_name}
        ).fetchone()
        
        if not developer:
            print(f"Developer not found in database: {developer_name_decoded}")
            return redirect(url_for('developers'))
        
        # Convert row to dict-like object for template
        developer_dict = dict(developer._mapping)
        
        # Load residential complexes to get real data
        with open('static/data/residential_complexes_expanded.json', 'r', encoding='utf-8') as f:
            complexes = json.load(f)
        
        # Load properties for statistics
        with open('data/properties_new.json', 'r', encoding='utf-8') as f:
            properties = json.load(f)
        
        # Find complexes by this developer
        developer_complexes = []
        for complex_item in complexes:
            if complex_item.get('developer', '').upper() == developer_dict['name'].upper():
                developer_complexes.append(complex_item)
        
        # Find properties (apartments) by this developer
        developer_properties = []
        properties_count = 0
        min_price = float('inf')
        for prop in properties:
            if prop.get('developer', '').upper() == developer_dict['name'].upper():
                developer_properties.append(prop)
                properties_count += 1
                if prop.get('price'):
                    min_price = min(min_price, prop['price'])
        
        # Fix infinite price
        if min_price == float('inf'):
            min_price = developer_dict.get('min_price', 0) or 0
        
        # Parse features and infrastructure if they exist
        import json as json_lib
        features = []
        infrastructure = []
        
        if developer_dict.get('features'):
            try:
                features = json_lib.loads(developer_dict['features'])
            except:
                features = []
        
        if developer_dict.get('infrastructure'):
            try:
                infrastructure = json_lib.loads(developer_dict['infrastructure'])
            except:
                infrastructure = []
        
        return render_template('developer.html', 
                             developer=developer_dict,
                             developer_name=developer_dict['name'],
                             complexes=developer_complexes,
                             apartments=developer_properties,
                             total_properties=properties_count or developer_dict.get('total_properties', 0),
                             min_price=min_price,
                             features=features,
                             infrastructure=infrastructure)
        
    except Exception as e:
        print(f"Error loading developer page for {developer_name}: {e}")
        import traceback
        traceback.print_exc()
        return redirect(url_for('developers'))

# Districts routes
@app.route('/districts')
def districts():
    """Districts listing page"""
    return render_template('districts.html')

@app.route('/district/<district>')
def district_detail(district):
    """Individual district page"""
    # Get properties and complexes in this district
    properties = load_properties()
    complexes = load_residential_complexes()
    
    # Filter by district (simplified district matching)
    district_properties = [p for p in properties if district.replace('-', ' ').lower() in p.get('address', '').lower()]
    district_complexes = [c for c in complexes if district.replace('-', ' ').lower() in c.get('district', '').lower()]
    
    # Add cashback calculations
    for prop in district_properties:
        prop['cashback'] = calculate_cashback(prop['price'])
    
    # District info mapping - all 54 districts
    district_names = {
        '40-let-pobedy': '40 лет Победы',
        '9i-kilometr': '9-й километр', 
        'aviagorodok': 'Авиагородок',
        'avrora': 'Аврора',
        'basket-hall': 'Баскет-холл',
        'berezovy': 'Березовый',
        'cheremushki': 'Черемушки',
        'dubinka': 'Дубинка',
        'enka': 'Энка',
        'festivalny': 'Фестивальный',
        'gidrostroitelei': 'Гидростроителей',
        'gorkhutor': 'Горхутор',
        'hbk': 'ХБК',
        'kalinino': 'Калинино',
        'karasunsky': 'Карасунский',
        'kolosistiy': 'Колосистый',
        'komsomolsky': 'Комсомольский',
        'kozhzavod': 'Кожзавод',
        'krasnaya-ploshchad': 'Красная площадь',
        'krasnodarskiy': 'Краснодарский',
        'kubansky': 'Кубанский',
        'mkg': 'МКГ',
        'molodezhny': 'Молодежный',
        'muzykalny-mkr': 'Музыкальный микрорайон',
        'nemetskaya-derevnya': 'Немецкая деревня',
        'novoznamenskiy': 'Новознаменский',
        'panorama': 'Панорама',
        'pashkovskiy': 'Пашковский',
        'pashkovsky': 'Пашковский-2',
        'pokrovka': 'Покровка',
        'prikubansky': 'Прикубанский',
        'rayon-aeroporta': 'Район аэропорта',
        'repino': 'Репино',
        'rip': 'РИП',
        'severny': 'Северный',
        'shkolny': 'Школьный',
        'shmr': 'ШМРП',
        'skhi': 'СХИП',
        'slavyansky': 'Славянский',
        'slavyansky2': 'Славянский-2',
        'solnechny': 'Солнечный',
        'tabachnaya-fabrika': 'Табачная фабрика',
        'tec': 'ТЭЦ',
        'tsentralnyy': 'Центральный',
        'uchhoz-kuban': 'Учхоз Кубань',
        'vavilova': 'Вавилова',
        'votochno-kruglikovskii': 'Восточно-Кругликовский',
        'yablonovskiy': 'Яблоновский',
        'zapadny': 'Западный',
        'zapadny-obhod': 'Западный обход',
        'zapadny-okrug': 'Западный округ',
        'zip-zhukova': 'ЗИП Жукова'
    }
    
    district_name = district_names.get(district, district.replace('-', ' ').title())
    
    return render_template('district_detail.html', 
                         district=district,
                         district_name=district_name,
                         properties=district_properties,
                         complexes=district_complexes)

# Content pages routes are already defined above

# Privacy and legal pages
@app.route('/privacy-policy')
def privacy_policy():
    """Privacy policy page"""
    return render_template('privacy_policy.html')

@app.route('/data-processing-consent')
def data_processing_consent():
    """Data processing consent page"""
    return render_template('data_processing_consent.html')

# Override Flask-Login unauthorized handler for API routes
@login_manager.unauthorized_handler  
def handle_unauthorized():
    # Check if this is an API route
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401
    # Regular redirect for web routes
    return redirect(url_for('login', next=request.url))

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    from models import User, Manager
    
    # First try to load as a regular user
    user = User.query.get(int(user_id))
    if user:
        return user
    
    # If not found, try as manager
    manager = Manager.query.get(int(user_id))
    if manager:
        return manager
    
    return None

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        from models import User
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember') == 'on'
        
        if not email or not password:
            flash('Заполните все поля', 'error')
            return render_template('auth/login.html')
        
        # Check if email or phone
        user = User.query.filter(
            (User.email == email) | (User.phone == email)
        ).first()
        
        if user:
            # Check if user needs to set password
            if user.needs_password_setup():
                session['temp_user_id'] = user.id
                flash('Необходимо установить пароль для входа', 'info')
                return redirect(url_for('setup_password'))
            
            # Normal password check
            if user.check_password(password):
                login_user(user, remember=remember)
                user.last_login = datetime.utcnow()
                db.session.commit()
                
                # Redirect to next page or dashboard
                next_page = request.args.get('next')
                return redirect(next_page) if next_page else redirect(url_for('dashboard'))
            else:
                flash('Неверный email или пароль', 'error')
        else:
            flash('Пользователь не найден', 'error')
    
    return render_template('auth/login.html')

@app.route('/setup-password', methods=['GET', 'POST'])
def setup_password():
    """Setup password for users created by managers"""
    temp_user_id = session.get('temp_user_id')
    if not temp_user_id:
        flash('Сессия истекла', 'error')
        return redirect(url_for('login'))
    
    from models import User
    user = User.query.get(temp_user_id)
    if not user or not user.needs_password_setup():
        flash('Пользователь не найден или пароль уже установлен', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not password or not confirm_password:
            flash('Заполните все поля', 'error')
            return render_template('auth/setup_password.html', user=user)
        
        if len(password) < 8:
            flash('Пароль должен содержать минимум 8 символов', 'error')
            return render_template('auth/setup_password.html', user=user)
        
        if password != confirm_password:
            flash('Пароли не совпадают', 'error')
            return render_template('auth/setup_password.html', user=user)
        
        # Set password
        user.set_password(password)
        user.is_verified = True
        db.session.commit()
        
        # Clear temp session
        session.pop('temp_user_id', None)
        
        # Login user
        login_user(user)
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        flash('Пароль успешно установлен!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('auth/setup_password.html', user=user)

@app.route('/register', methods=['POST'])
def register():
    """User registration"""
    from models import User
    
    full_name = request.form.get('full_name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    terms = request.form.get('terms')
    
    # Validation
    if not all([full_name, email, password, confirm_password, terms]):
        flash('Заполните все обязательные поля', 'error')
        return redirect(url_for('login'))
    
    if password != confirm_password:
        flash('Пароли не совпадают', 'error')
        return redirect(url_for('login'))
    
    if not password or len(password) < 8:
        flash('Пароль должен содержать минимум 8 символов', 'error')
        return redirect(url_for('login'))
    
    # Check if user exists
    if User.query.filter_by(email=email).first():
        flash('Пользователь с таким email уже существует', 'error')
        return redirect(url_for('login'))
    
    # Create new user
    user = User(
        full_name=full_name,
        email=email,
        phone=phone
    )
    user.set_password(password)
    
    try:
        db.session.add(user)
        db.session.commit()
        
        # Send welcome notification
        try:
            from email_service import send_welcome_email
            send_welcome_email(user, base_url=request.url_root.rstrip('/'))
        except Exception as e:
            print(f"Error sending welcome notification: {e}")
        
        # Login user immediately
        login_user(user)
        
        flash('Регистрация успешна! Проверьте email для подтверждения.', 'success')
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        db.session.rollback()
        print(f"Registration error: {e}")
        flash(f'Ошибка при регистрации: {str(e)}', 'error')
        return redirect(url_for('login'))

@app.route('/quiz-registration')
def quiz_registration():
    """Show quiz registration page"""
    return render_template('quiz_registration.html')

@app.route('/callback-request')
def callback_request_page():
    """Show callback request page"""
    return render_template('callback_request.html')

@app.route('/api/property-selection', methods=['POST'])
def property_selection():
    """Property selection application"""
    from models import Application, User
    data = request.get_json()
    
    try:
        # Extract data
        email = data.get('email', '').strip().lower()
        name = data.get('name', '').strip()
        phone = data.get('phone', '').strip()
        
        # Application preferences
        preferred_district = data.get('preferred_district', '')
        property_type = data.get('property_type', '')
        room_count = data.get('room_count', '')
        budget_range = data.get('budget_range', '')
        
        # Validation
        if not email or not name or not phone:
            return jsonify({'success': False, 'error': 'Все обязательные поля должны быть заполнены'})
        
        # Create application without user account
        application = Application(
            user_id=None,  # No user account needed for applications
            property_id=None,  # No specific property for general selection
            property_name='Подбор квартиры',
            complex_name='По предпочтениям',
            message=f"Заявка на подбор квартиры:\n"
                   f"Имя: {name}\n"
                   f"Email: {email}\n"
                   f"Телефон: {phone}\n"
                   f"Район: {preferred_district or 'Любой'}\n"
                   f"Тип: {property_type or 'Не указан'}\n"
                   f"Комнат: {room_count or 'Не указано'}\n"
                   f"Бюджет: {budget_range or 'Не указан'}",
            status='new',
            contact_name=name,
            contact_email=email,
            contact_phone=phone
        )
        
        db.session.add(application)
        
        # Application submitted successfully
        db.session.commit()
        
        # Send Telegram notification
        try:
            from telegram_bot import send_telegram_message
            from datetime import datetime
            
            # Calculate potential cashback (2% of average budget)
            potential_cashback = ""
            if budget_range:
                if "млн" in budget_range:
                    # Extract average from range like "3-5 млн"
                    numbers = [float(x) for x in budget_range.replace(" млн", "").split("-") if x.strip().replace(".", "").replace(",", "").isdigit()]
                    if numbers:
                        avg_price = sum(numbers) / len(numbers) * 1000000
                        cashback = int(avg_price * 0.02)
                        potential_cashback = f"💰 *Потенциальный кэшбек:* {cashback:,} руб. (2%)\n"
            
            telegram_message = f"""🏠 *НОВАЯ ЗАЯВКА НА ПОДБОР КВАРТИРЫ*

👤 *КОНТАКТНАЯ ИНФОРМАЦИЯ:*
• Имя: {name}
• Телефон: {phone}
• Email: {email}

🔍 *КРИТЕРИИ ПОИСКА:*
• Район: {preferred_district or 'Любой'}
• Тип недвижимости: {property_type or 'Не указан'}
• Количество комнат: {room_count or 'Не указано'}
• Бюджет: {budget_range or 'Не указан'}

{potential_cashback}📅 *ВРЕМЯ ЗАЯВКИ:* {datetime.now().strftime('%d.%m.%Y в %H:%M')}
🌐 *ИСТОЧНИК:* Форма на сайте InBack.ru

📋 *СЛЕДУЮЩИЕ ШАГИ:*
1️⃣ Связаться с клиентом в течение 15 минут
2️⃣ Уточнить дополнительные предпочтения
3️⃣ Подготовить подборку объектов
4️⃣ Назначить встречу для просмотра

⚡ *ВАЖНО:* Быстрая реакция повышает конверсию!"""
            
            send_telegram_message('730764738', telegram_message)
            
        except Exception as notify_error:
            print(f"Notification error: {notify_error}")
        
        return jsonify({
            'success': True,
            'message': 'Заявка отправлена! Менеджер свяжется с вами.'
        })
    except Exception as e:
        db.session.rollback()
        print(f"Application error: {e}")
        return jsonify({'success': False, 'error': 'Ошибка при отправке заявки'})

@app.route('/api/callback-request', methods=['POST'])
def api_callback_request():
    """Submit callback request"""
    from models import CallbackRequest, Manager
    data = request.get_json()
    
    try:
        # Extract data
        name = data.get('name', '').strip()
        phone = data.get('phone', '').strip()
        email = data.get('email', '').strip()
        preferred_time = data.get('preferred_time', '')
        notes = data.get('notes', '').strip()
        
        # Quiz responses
        interest = data.get('interest', '')
        budget = data.get('budget', '')
        timing = data.get('timing', '')
        
        # Validation
        if not name or not phone:
            return jsonify({'success': False, 'error': 'Имя и телефон обязательны для заполнения'})
        
        # Create callback request
        callback_req = CallbackRequest(
            name=name,
            phone=phone,
            email=email or None,
            preferred_time=preferred_time,
            notes=notes,
            interest=interest,
            budget=budget,
            timing=timing
        )
        
        # Auto-assign to first available manager
        available_manager = Manager.query.filter_by(is_active=True).first()
        if available_manager:
            callback_req.assigned_manager_id = available_manager.id
        
        db.session.add(callback_req)
        db.session.commit()
        
        # Send notifications
        try:
            send_callback_notification_email(callback_req, available_manager)
            send_callback_notification_telegram(callback_req, available_manager)
        except Exception as e:
            print(f"Failed to send callback notifications: {e}")
        
        return jsonify({
            'success': True,
            'message': 'Заявка отправлена! Наш менеджер свяжется с вами в ближайшее время.'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Callback request error: {e}")
        return jsonify({'success': False, 'error': 'Ошибка при отправке заявки. Попробуйте еще раз.'})

@app.route('/forgot-password', methods=['POST'])
def forgot_password():
    """Password reset request"""
    email = request.form.get('email')
    
    if not email:
        flash('Введите email адрес', 'error')
        return redirect(url_for('login'))
    
    from models import User
    user = User.query.filter_by(email=email).first()
    
    if user:
        # Generate reset token and send email
        token = user.generate_verification_token()
        db.session.commit()
        
        try:
            from email_service import send_password_reset_email
            send_password_reset_email(user, token)
        except Exception as e:
            print(f"Error sending password reset email: {e}")
        
        flash('Инструкции по восстановлению пароля отправлены на ваш email', 'success')
    else:
        # Don't reveal that user doesn't exist
        flash('Инструкции по восстановлению пароля отправлены на ваш email', 'success')
    
    return redirect(url_for('login'))

# API endpoints for dashboard functionality
@app.route('/api/cashback-application', methods=['POST'])
@login_required
def create_cashback_application():
    """Create new cashback application"""
    from models import CashbackApplication
    data = request.get_json()
    
    try:
        app = CashbackApplication(
            user_id=current_user.id,
            property_name=data['property_name'],
            property_type=data['property_type'],
            property_size=float(data['property_size']),
            property_price=int(data['property_price']),
            complex_name=data['complex_name'],
            developer_name=data['developer_name'],
            cashback_amount=int(data['cashback_amount']),
            cashback_percent=float(data['cashback_percent'])
        )
        db.session.add(app)
        db.session.commit()
        
        return jsonify({'success': True, 'application_id': app.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/favorites', methods=['POST'])
@login_required  
def add_to_favorites():
    """Add property to favorites"""
    from models import FavoriteProperty
    data = request.get_json()
    
    # Check if already in favorites
    existing = FavoriteProperty.query.filter_by(
        user_id=current_user.id,
        property_name=data['property_name']
    ).first()
    
    if existing:
        return jsonify({'success': False, 'error': 'Уже в избранном'})
    
    try:
        favorite = FavoriteProperty(
            user_id=current_user.id,
            property_name=data['property_name'],
            property_type=data['property_type'],
            property_size=float(data['property_size']),
            property_price=int(data['property_price']),
            complex_name=data['complex_name'],
            developer_name=data['developer_name'],
            property_image=data.get('property_image'),
            cashback_amount=int(data.get('cashback_amount', 0)),
            cashback_percent=float(data.get('cashback_percent', 0))
        )
        db.session.add(favorite)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/favorites/<property_id>', methods=['DELETE'])
@login_required
def remove_from_favorites(property_id):
    """Remove property from favorites"""
    from models import FavoriteProperty
    
    favorite = FavoriteProperty.query.filter_by(
        user_id=current_user.id,
        property_id=property_id
    ).first()
    
    if favorite:
        try:
            db.session.delete(favorite)
            db.session.commit()
            return jsonify({'success': True})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 400
    else:
        return jsonify({'success': False, 'error': 'Не найдено в избранном'}), 404

@app.route('/api/favorites/toggle', methods=['POST'])
@login_required
def toggle_favorite():
    """Toggle favorite status for property"""
    from models import FavoriteProperty
    data = request.get_json()
    property_id = data.get('property_id')
    
    print(f"DEBUG: Favorites toggle called by user {current_user.id} for property {property_id}")
    print(f"DEBUG: Request data: {data}")
    
    if not property_id:
        return jsonify({'success': False, 'error': 'property_id required'}), 400
    
    # Check if already in favorites
    existing = FavoriteProperty.query.filter_by(
        user_id=current_user.id,
        property_id=property_id
    ).first()
    
    try:
        if existing:
            # Remove from favorites
            db.session.delete(existing)
            db.session.commit()
            return jsonify({'success': True, 'action': 'removed', 'is_favorite': False})
        else:
            # Add to favorites
            favorite = FavoriteProperty(
                user_id=current_user.id,
                property_id=property_id,
                property_name=data.get('property_name', ''),
                property_type=data.get('property_type', ''),
                property_size=float(data.get('property_size', 0)),
                property_price=int(data.get('property_price', 0)),
                complex_name=data.get('complex_name', ''),
                developer_name=data.get('developer_name', ''),
                property_image=data.get('property_image'),
                cashback_amount=int(data.get('cashback_amount', 0)),
                cashback_percent=float(data.get('cashback_percent', 0))
            )
            db.session.add(favorite)
            db.session.commit()
            return jsonify({'success': True, 'action': 'added', 'is_favorite': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400



@app.route('/api/collections', methods=['POST'])
@login_required
def create_collection():
    """Create new property collection"""
    from models import Collection
    data = request.get_json()
    
    try:
        collection = Collection(
            user_id=current_user.id,
            title=data['name'],
            description=data.get('description'),
            image_url=data.get('image_url'),
            category=data.get('category')
        )
        db.session.add(collection)
        db.session.commit()
        
        return jsonify({'success': True, 'collection_id': collection.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/collections/<int:collection_id>', methods=['DELETE'])
@login_required
def delete_collection(collection_id):
    """Delete a collection"""
    from models import Collection
    collection = Collection.query.filter_by(
        id=collection_id,
        user_id=current_user.id
    ).first()
    
    if not collection:
        return jsonify({'success': False, 'error': 'Подборка не найдена'}), 404
    
    try:
        db.session.delete(collection)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/documents/upload', methods=['POST'])
@login_required
def upload_documents():
    """Upload documents"""
    from models import Document
    import os
    from werkzeug.utils import secure_filename
    from datetime import datetime
    
    if 'files' not in request.files:
        return jsonify({'success': False, 'error': 'Нет файлов для загрузки'}), 400
    
    files = request.files.getlist('files')
    uploaded_files = []
    
    # Create uploads directory if it doesn't exist
    upload_dir = 'instance/uploads'
    os.makedirs(upload_dir, exist_ok=True)
    
    for file in files:
        if file.filename == '':
            continue
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Add timestamp to avoid conflicts
            timestamp = str(int(datetime.utcnow().timestamp()))
            filename = f"{timestamp}_{filename}"
            file_path = os.path.join(upload_dir, filename)
            
            try:
                file.save(file_path)
                file_size = os.path.getsize(file_path)
                file_ext = filename.rsplit('.', 1)[1].lower()
                
                # Create document record
                document = Document(
                    user_id=current_user.id,
                    original_filename=secure_filename(file.filename),
                    stored_filename=filename,
                    file_path=file_path,
                    file_size=file_size,
                    file_type=file_ext,
                    document_type=determine_document_type(file.filename),
                    status='На проверке'
                )
                db.session.add(document)
                uploaded_files.append({
                    'filename': file.filename,
                    'size': file_size
                })
            except Exception as e:
                return jsonify({'success': False, 'error': f'Ошибка загрузки файла {file.filename}: {str(e)}'}), 400
    
    try:
        db.session.commit()
        return jsonify({'success': True, 'uploaded_files': uploaded_files})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/documents/<int:document_id>', methods=['DELETE'])
@login_required
def delete_document(document_id):
    """Delete a document"""
    from models import Document
    import os
    
    document = Document.query.filter_by(
        id=document_id,
        user_id=current_user.id
    ).first()
    
    if not document:
        return jsonify({'success': False, 'error': 'Документ не найден'}), 404
    
    try:
        # Delete physical file
        if os.path.exists(document.file_path):
            os.remove(document.file_path)
        
        # Delete database record
        db.session.delete(document)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def determine_document_type(filename):
    """Determine document type from filename"""
    filename_lower = filename.lower()
    if any(word in filename_lower for word in ['паспорт', 'passport']):
        return 'Паспорт'
    elif any(word in filename_lower for word in ['справка', 'доходы', 'income']):
        return 'Справка о доходах'
    elif any(word in filename_lower for word in ['договор', 'contract']):
        return 'Договор'
    elif any(word in filename_lower for word in ['снилс', 'снилс']):
        return 'СНИЛС'
    elif any(word in filename_lower for word in ['инн', 'inn']):
        return 'ИНН'
    else:
        return 'Другое'

# Manager authentication and dashboard routes
@app.route('/manager/logout')
def manager_logout():
    """Manager logout"""
    session.pop('manager_id', None)
    session.pop('is_manager', None)
    flash('Вы успешно вышли из системы', 'success')
    return redirect(url_for('manager_login'))

@app.route('/manager/login', methods=['GET', 'POST'])
def manager_login():
    if request.method == 'POST':
        try:
            from models import Manager
            email = request.form.get('email')
            password = request.form.get('password')
            
            print(f"DEBUG: Login attempt - email: {email}, password: {password}")
            
            if not email or not password:
                print("DEBUG: Missing email or password")
                flash('Заполните все поля', 'error')
                return render_template('auth/manager_login.html')
            
            manager = Manager.query.filter_by(email=email, is_active=True).first()
            print(f"DEBUG: Manager found: {manager}")
            print(f"DEBUG: Manager ID: {manager.id if manager else 'None'}")
            print(f"DEBUG: Manager email: {manager.email if manager else 'None'}")
            print(f"DEBUG: Manager active: {manager.is_active if manager else 'None'}")
            
            if manager:
                print(f"DEBUG: Checking password for manager {manager.id}")
                password_check = manager.check_password(password)
                print(f"DEBUG: Password check result: {password_check}")
                
                if password_check:
                    print("DEBUG: Password correct, setting up session")
                    session.permanent = True
                    session['manager_id'] = manager.id
                    session['is_manager'] = True
                    print(f"DEBUG: Session before commit: {dict(session)}")
                    
                    manager.last_login = datetime.utcnow()
                    db.session.commit()
                    print("DEBUG: Database commit successful")
                    
                    flash('Добро пожаловать!', 'success')
                    print(f"DEBUG: Successfully logged in manager {manager.email}")
                    print(f"DEBUG: Final session data: {dict(session)}")
                    return redirect(url_for('manager_dashboard'))
                else:
                    print("DEBUG: Password incorrect")
            else:
                print("DEBUG: Manager not found or inactive")
            
            print(f"DEBUG: Login failed")
            flash('Неверный email или пароль', 'error')
            
        except Exception as e:
            print(f"DEBUG: Exception during login: {str(e)}")
            import traceback
            traceback.print_exc()
            flash('Произошла ошибка при входе', 'error')
    
    return render_template('auth/manager_login.html')



def manager_required(f):
    """Decorator to require manager authentication"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        manager_id = session.get('manager_id')
        print(f"DEBUG: manager_required check - manager_id: {manager_id}")
        if not manager_id:
            print(f"DEBUG: manager_required - no manager_id, rejecting request")
            # For AJAX requests, return JSON error instead of redirect
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
                return jsonify({'success': False, 'error': 'Authentication required'}), 401
            return redirect(url_for('manager_login'))
        print(f"DEBUG: manager_required - authentication passed")
        return f(*args, **kwargs)
    return decorated_function

@app.route('/manager/dashboard')
@manager_required
def manager_dashboard():
    from models import Manager, User, CashbackApplication, Document
    
    manager_id = session.get('manager_id')
    print(f"DEBUG: Manager dashboard - manager_id: {manager_id}")
    current_manager = Manager.query.get(manager_id)
    print(f"DEBUG: Manager dashboard - current_manager: {current_manager}")
    
    if not current_manager:
        print("DEBUG: Manager not found, redirecting to login")
        return redirect(url_for('manager_login'))
    
    # Get statistics
    total_clients = User.query.filter_by(assigned_manager_id=manager_id).count()
    new_clients_count = User.query.filter_by(
        assigned_manager_id=manager_id, 
        client_status='Новый'
    ).count()
    
    pending_applications_count = CashbackApplication.query.join(User).filter(
        User.assigned_manager_id == manager_id,
        CashbackApplication.status == 'На рассмотрении'
    ).count()
    
    pending_documents_count = Document.query.join(User).filter(
        User.assigned_manager_id == manager_id,
        Document.status == 'На проверке'
    ).count()
    
    # Calculate total approved cashback
    total_approved_cashback = 0
    try:
        from models import CashbackApplication, User
        approved_apps = CashbackApplication.query.join(User).filter(
            User.assigned_manager_id == manager_id,
            CashbackApplication.status == 'Одобрена'
        ).all()
        total_approved_cashback = sum(app.cashback_amount for app in approved_apps)
    except Exception as e:
        print(f"Error calculating cashback: {e}")
        total_approved_cashback = 0
    
    # Recent activities (mock data for now)
    recent_activities = [
        {
            'message': 'Новый клиент Иван Петров зарегистрировался',
            'time_ago': '5 минут назад',
            'color': 'blue',
            'icon': 'user-plus'
        },
        {
            'message': 'Заявка на кешбек от Анны Сидоровой требует проверки',
            'time_ago': '1 час назад',
            'color': 'yellow',
            'icon': 'file-alt'
        }
    ]
    
    # Get collections statistics  
    from models import Collection
    collections_count = Collection.query.filter_by(created_by_manager_id=manager_id).count()
    sent_collections_count = Collection.query.filter_by(created_by_manager_id=manager_id, status='Отправлена').count()
    recent_collections = Collection.query.filter_by(created_by_manager_id=manager_id).order_by(Collection.created_at.desc()).limit(5).all()
    
    # Load data for manager filters
    districts = get_districts_list()
    developers = get_developers_list()
    
    print(f"DEBUG: Rendering dashboard with manager: {current_manager.full_name}")
    try:
        return render_template('auth/manager_dashboard.html',
                             current_manager=current_manager,
                             total_clients=total_clients,
                             new_clients_count=new_clients_count,
                             pending_applications_count=pending_applications_count,
                             pending_documents_count=pending_documents_count,
                             total_approved_cashback=total_approved_cashback,
                             recent_activities=recent_activities,
                             pending_notifications=pending_applications_count + pending_documents_count,
                             collections_count=collections_count,
                             sent_collections_count=sent_collections_count,
                             recent_collections=recent_collections,
                             districts=districts,
                             developers=developers)
    except Exception as e:
        print(f"DEBUG: Error rendering dashboard: {e}")
        import traceback
        traceback.print_exc()
        return f"Error rendering dashboard: {e}", 500

# API routes for manager actions
@app.route('/api/manager/clients')
@manager_required
def get_manager_clients_unified():
    """Get all clients (buyers) for managers - unified for both old and new systems"""
    # Get manager ID from session (already verified by manager_required decorator)
    manager_id = session.get('manager_id')
    
    try:
        print(f"DEBUG: Getting clients for manager {manager_id}")
        # Get all buyers as potential clients
        clients = User.query.filter_by(role='buyer').all()
        print(f"DEBUG: Found {len(clients)} clients total")
        clients_data = []
        
        for client in clients:
            # Get latest search as preference indicator
            latest_search = SavedSearch.query.filter_by(user_id=client.id).order_by(SavedSearch.last_used.desc()).first()
            
            client_data = {
                'id': client.id,
                'full_name': client.full_name,
                'email': client.email,
                'phone': client.phone or '',
                'created_at': client.created_at.isoformat() if client.created_at else None,
                'search_preferences': None,
                'status': 'active'  # Default status
            }
            
            if latest_search:
                # Create readable search description
                prefs = []
                if latest_search.property_type:
                    prefs.append(latest_search.property_type)
                if latest_search.location:
                    prefs.append(f"район {latest_search.location}")
                if latest_search.price_min or latest_search.price_max:
                    price_range = []
                    if latest_search.price_min:
                        price_range.append(f"от {latest_search.price_min:,} ₽")
                    if latest_search.price_max:
                        price_range.append(f"до {latest_search.price_max:,} ₽")
                    prefs.append(" ".join(price_range))
                
                client_data['search_preferences'] = ", ".join(prefs) if prefs else "Поиск сохранен"
            
            clients_data.append(client_data)
        
        print(f"DEBUG: Returning {len(clients_data)} clients data")
        return jsonify({
            'success': True,
            'clients': clients_data
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/manager/update_client_status', methods=['POST'])
@manager_required  
def update_client_status():
    from models import User
    
    data = request.get_json()
    client_id = data.get('client_id')
    new_status = data.get('status')
    notes = data.get('notes', '')
    
    client = User.query.get(client_id)
    if not client or client.assigned_manager_id != session.get('manager_id'):
        return jsonify({'success': False, 'error': 'Клиент не найден'}), 404
    
    try:
        client.client_status = new_status
        if notes:
            client.client_notes = notes
        client.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/manager/approve_cashback', methods=['POST'])
@manager_required
def approve_cashback():
    from models import CashbackApplication, Manager
    
    data = request.get_json()
    application_id = data.get('application_id')
    action = data.get('action')  # approve, reject
    manager_notes = data.get('manager_notes', '')
    
    manager_id = session.get('manager_id')
    manager = Manager.query.get(manager_id)
    
    application = CashbackApplication.query.get(application_id)
    if not application:
        return jsonify({'success': False, 'error': 'Заявка не найдена'}), 404
    
    # Check if client is assigned to this manager
    if application.user.assigned_manager_id != manager_id:
        return jsonify({'success': False, 'error': 'У вас нет доступа к этой заявке'}), 403
    
    try:
        if action == 'approve':
            # Check approval limits
            if application.cashback_amount > manager.max_cashback_approval:
                return jsonify({
                    'success': False, 
                    'error': f'Сумма превышает ваш лимит на одобрение ({manager.max_cashback_approval:,} ₽)'
                }), 400
            
            application.status = 'Одобрена'
            application.approved_date = datetime.utcnow()
            application.approved_by_manager_id = manager_id
            
        elif action == 'reject':
            application.status = 'Отклонена'
        
        if manager_notes:
            application.manager_notes = manager_notes
        
        application.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/manager/applications')
@manager_required
def get_manager_applications():
    from models import CashbackApplication, User
    manager_id = session.get('manager_id')
    
    applications = CashbackApplication.query.join(User).filter(
        User.assigned_manager_id == manager_id,
        CashbackApplication.status == 'На рассмотрении'
    ).all()
    
    applications_data = []
    for app in applications:
        applications_data.append({
            'id': app.id,
            'client_name': app.user.full_name,
            'client_email': app.user.email,
            'property_name': app.property_name,
            'complex_name': app.complex_name,
            'cashback_amount': app.cashback_amount,
            'cashback_percent': app.cashback_percent,
            'application_date': app.application_date.strftime('%d.%m.%Y'),
            'status': app.status
        })
    
    return jsonify({'applications': applications_data})

@app.route('/api/manager/documents')
@manager_required
def get_manager_documents():
    from models import Document, User
    manager_id = session.get('manager_id')
    
    documents = Document.query.join(User).filter(
        User.assigned_manager_id == manager_id,
        Document.status == 'На проверке'
    ).all()
    
    documents_data = []
    for doc in documents:
        documents_data.append({
            'id': doc.id,
            'client_name': doc.user.full_name,
            'client_email': doc.user.email,
            'document_type': doc.document_type or 'Не определен',
            'original_filename': doc.original_filename,
            'file_size': doc.file_size,
            'created_at': doc.created_at.strftime('%d.%m.%Y %H:%M'),
            'status': doc.status
        })
    
    return jsonify({'documents': documents_data})

@app.route('/api/manager/document_action', methods=['POST'])
@manager_required
def manager_document_action():
    from models import Document, Manager
    
    data = request.get_json()
    document_id = data.get('document_id')
    action = data.get('action')  # approve, reject
    notes = data.get('notes', '')
    
    manager_id = session.get('manager_id')
    document = Document.query.get(document_id)
    
    if not document:
        return jsonify({'success': False, 'error': 'Документ не найден'}), 404
    
    # Check if client is assigned to this manager
    if document.user.assigned_manager_id != manager_id:
        return jsonify({'success': False, 'error': 'У вас нет доступа к этому документу'}), 403
    
    try:
        if action == 'approve':
            document.status = 'Проверен'
        elif action == 'reject':
            document.status = 'Отклонен'
        
        document.reviewed_by_manager_id = manager_id
        document.reviewed_at = datetime.utcnow()
        if notes:
            document.reviewer_notes = notes
        
        document.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/manager/application_action', methods=['POST'])
@manager_required
def manager_application_action():
    from models import CashbackApplication, Manager, User
    
    data = request.get_json()
    application_id = data.get('application_id')
    action = data.get('action')  # approve, reject
    notes = data.get('notes', '')
    
    manager_id = session.get('manager_id')
    application = CashbackApplication.query.get(application_id)
    
    if not application:
        return jsonify({'success': False, 'error': 'Заявка не найдена'}), 404
    
    # Check if client is assigned to this manager
    if application.user.assigned_manager_id != manager_id:
        return jsonify({'success': False, 'error': 'У вас нет доступа к этой заявке'}), 403
    
    try:
        if action == 'approve':
            application.status = 'Одобрена'
            # Add cashback to user's balance
            user = application.user
            user.total_cashback = (user.total_cashback or 0) + application.cashback_amount
        elif action == 'reject':
            application.status = 'Отклонена'
        
        application.reviewed_by_manager_id = manager_id
        application.reviewed_at = datetime.utcnow()
        if notes:
            application.manager_notes = notes
        
        application.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/manager/collections')
@manager_required
def get_manager_collections():
    from models import Collection, User
    manager_id = session.get('manager_id')
    
    collections = Collection.query.filter_by(created_by_manager_id=manager_id).all()
    
    collections_data = []
    for collection in collections:
        collections_data.append({
            'id': collection.id,
            'title': collection.title,
            'description': collection.description,
            'status': collection.status,
            'assigned_to_name': collection.assigned_to.full_name if collection.assigned_to else 'Не назначено',
            'assigned_to_id': collection.assigned_to_user_id,
            'properties_count': len(collection.properties),
            'created_at': collection.created_at.strftime('%d.%m.%Y'),
            'tags': collection.tags
        })
    
    return jsonify({'collections': collections_data})

@app.route('/api/manager/collection/create', methods=['POST'])
@manager_required
def api_create_collection():
    from models import Collection, User
    
    data = request.get_json()
    title = data.get('title')
    description = data.get('description', '')
    assigned_to_user_id = data.get('assigned_to_user_id')
    tags = data.get('tags', '')
    
    if not title:
        return jsonify({'success': False, 'error': 'Название подборки обязательно'}), 400
    
    manager_id = session.get('manager_id')
    
    try:
        collection = Collection()
        collection.title = title
        collection.description = description
        collection.created_by_manager_id = manager_id
        collection.assigned_to_user_id = assigned_to_user_id if assigned_to_user_id else None
        collection.tags = tags
        collection.status = 'Черновик'
        
        db.session.add(collection)
        db.session.commit()
        
        return jsonify({'success': True, 'collection_id': collection.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/manager/collection/<int:collection_id>/properties')
@manager_required
def get_collection_properties(collection_id):
    from models import Collection, CollectionProperty
    manager_id = session.get('manager_id')
    
    collection = Collection.query.filter_by(
        id=collection_id,
        created_by_manager_id=manager_id
    ).first()
    
    if not collection:
        return jsonify({'success': False, 'error': 'Подборка не найдена'}), 404
    
    properties_data = []
    for prop in collection.properties:
        properties_data.append({
            'id': prop.id,
            'property_id': prop.property_id,
            'property_name': prop.property_name,
            'property_price': prop.property_price,
            'complex_name': prop.complex_name,
            'property_type': prop.property_type,
            'property_size': prop.property_size,
            'manager_note': prop.manager_note,
            'order_index': prop.order_index
        })
    
    # Sort by order_index
    properties_data.sort(key=lambda x: x['order_index'])
    
    return jsonify({
        'collection': {
            'id': collection.id,
            'title': collection.title,
            'description': collection.description,
            'status': collection.status
        },
        'properties': properties_data
    })



@app.route('/api/searches/save', methods=['POST'])
@login_required
def api_save_search():
    """Save a search with filters"""
    from models import SavedSearch
    
    data = request.get_json()
    name = data.get('name')
    filters = data.get('filters', {})
    
    if not name:
        return jsonify({'success': False, 'error': 'Название поиска обязательно'}), 400
    
    try:
        search = SavedSearch()
        search.name = name
        search.filters = json.dumps(filters)
        search.user_id = current_user.id
        search.created_at = datetime.utcnow()
        
        db.session.add(search)
        db.session.commit()
        
        return jsonify({'success': True, 'search_id': search.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/manager/searches', methods=['POST'])
def api_manager_save_search():
    """Save a search for a manager"""
    from models import ManagerSavedSearch, Manager, SentSearch
    
    # Check if user is authenticated as manager
    manager_id = session.get('manager_id')
    if not manager_id:
        return jsonify({'success': False, 'error': 'Требуется авторизация менеджера'}), 401
    
    data = request.get_json()
    name = data.get('name')
    filters = data.get('filters', {})
    client_email = data.get('client_email', '')
    
    if not name:
        return jsonify({'success': False, 'error': 'Название поиска обязательно'}), 400
    
    try:
        # Create saved search
        search = ManagerSavedSearch()
        search.name = name
        search.filters = json.dumps(filters)
        search.manager_id = manager_id
        search.created_at = datetime.utcnow()
        
        db.session.add(search)
        db.session.commit()
        
        # If client email provided, also create sent search record and send notification
        if client_email:
            sent_search = SentSearch()
            sent_search.saved_search_id = search.id
            sent_search.recipient_email = client_email
            sent_search.sent_at = datetime.utcnow()
            sent_search.manager_id = manager_id
            
            db.session.add(sent_search)
            db.session.commit()
            
            # Send notification to client
            manager = Manager.query.get(manager_id)
            manager_name = manager.name if manager else "Менеджер"
            
            try:
                send_notification(
                    recipient_email=client_email,
                    subject=f"Новый подбор недвижимости от {manager_name}",
                    message=f"Менеджер {manager_name} подготовил для вас персональный подбор недвижимости '{name}'. Посмотрите варианты на сайте InBack.ru",
                    notification_type='saved_search',
                    user_id=None,
                    manager_id=manager_id
                )
                return jsonify({'success': True, 'search_id': search.id, 'sent_to_client': True})
            except Exception as email_error:
                print(f"Failed to send email notification: {email_error}")
                return jsonify({'success': True, 'search_id': search.id, 'sent_to_client': False, 'email_error': str(email_error)})
        
        return jsonify({'success': True, 'search_id': search.id, 'sent_to_client': False})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/manager/send_recommendation', methods=['POST'])
def api_manager_send_recommendation():
    """Send a recommendation (property or complex) to a client"""
    from models import Recommendation, Manager, User, RecommendationCategory
    from datetime import datetime
    
    # Check if user is authenticated as manager
    manager_id = session.get('manager_id')
    if not manager_id:
        return jsonify({'success': False, 'error': 'Требуется авторизация менеджера'}), 401
    
    data = request.get_json()
    title = data.get('title', '').strip()
    client_id = data.get('client_id')  # Now using client_id instead of email
    client_email = data.get('client_email', '').strip()
    recommendation_type = data.get('recommendation_type')  # 'property' or 'complex'
    item_id = data.get('item_id')
    item_name = data.get('item_name', '').strip()
    description = data.get('description', '').strip()
    manager_notes = data.get('manager_notes', '').strip()
    highlighted_features = data.get('highlighted_features', [])
    priority_level = data.get('priority_level', 'normal')
    category_id = data.get('category_id')  # New field for category
    category_name = data.get('category_name', '').strip()  # For creating new category
    
    # Debug logging (removing verbose logs for production)
    print(f"DEBUG: Recommendation sent - type={recommendation_type}, item_id={item_id}, client_id={client_id}")
    
    # Validation
    missing_fields = []
    if not title:
        missing_fields.append('заголовок')
    if not client_id:
        missing_fields.append('клиент')
    if not recommendation_type:
        missing_fields.append('тип рекомендации')
    if not item_id:
        missing_fields.append('ID объекта')
    if not item_name:
        missing_fields.append('название объекта')
    
    if missing_fields:
        return jsonify({'success': False, 'error': f'Заполните обязательные поля: {", ".join(missing_fields)}'}), 400
    
    if recommendation_type not in ['property', 'complex']:
        return jsonify({'success': False, 'error': 'Неверный тип рекомендации'}), 400
    
    try:
        # Find client by ID
        client = User.query.get(client_id)
        if not client:
            return jsonify({'success': False, 'error': 'Клиент не найден'}), 400
        
        # Handle category
        category = None
        if category_id == 'new' and category_name:
            # Create new category
            category = RecommendationCategory(
                name=category_name,
                manager_id=manager_id,
                client_id=client_id
            )
            db.session.add(category)
            db.session.flush()  # To get the ID
        elif category_id and category_id != 'new':
            # Use existing category
            category = RecommendationCategory.query.filter_by(
                id=category_id,
                manager_id=manager_id,
                client_id=client_id,
                is_active=True
            ).first()
        
        # Create recommendation
        recommendation = Recommendation()
        recommendation.manager_id = manager_id
        recommendation.client_id = client.id
        recommendation.title = title
        recommendation.description = description
        recommendation.recommendation_type = recommendation_type
        recommendation.item_id = item_id
        recommendation.item_name = item_name
        recommendation.manager_notes = manager_notes
        recommendation.highlighted_features = json.dumps(highlighted_features) if highlighted_features else None
        recommendation.priority_level = priority_level
        recommendation.item_data = json.dumps(data.get('item_data', {}))  # Store full item details
        recommendation.category_id = category.id if category else None
        
        db.session.add(recommendation)
        
        # Update category statistics
        if category:
            category.recommendations_count += 1
            category.last_used = datetime.utcnow()
        
        db.session.commit()
        
        # Send notification to client
        manager = Manager.query.get(manager_id)
        manager_name = manager.name if manager else "Менеджер"
        
        try:
            # Get priority text for notifications
            priority_texts = {
                'urgent': 'Срочно',
                'high': 'Высокий', 
                'normal': 'Обычный'
            }
            priority_text = priority_texts.get(priority_level, 'Обычный')
            
            send_notification(
                recipient_email=client_email,
                subject=f"Новая рекомендация от {manager_name}",
                message=f"Менеджер {manager_name} рекомендует вам: {title}",
                notification_type='recommendation',
                user_id=client.id,
                manager_id=manager_id,
                title=title,
                item_id=item_id,
                item_name=item_name,
                description=description,
                manager_name=manager_name,
                priority_text=priority_text,
                recommendation_type=recommendation_type
            )
            return jsonify({'success': True, 'recommendation_id': recommendation.id, 'sent_to_client': True})
        except Exception as email_error:
            print(f"Failed to send email notification: {email_error}")
            return jsonify({'success': True, 'recommendation_id': recommendation.id, 'sent_to_client': False, 'email_error': str(email_error)})
        
    except Exception as e:
        db.session.rollback()
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error creating recommendation: {str(e)}")
        print(f"Full traceback: {error_trace}")
        return jsonify({'success': False, 'error': str(e), 'traceback': error_trace}), 400

@app.route('/api/manager/recommendations', methods=['GET'])
def api_manager_get_recommendations():
    """Get manager's sent recommendations with filters"""
    from models import Recommendation
    
    # Check if user is authenticated as manager
    manager_id = session.get('manager_id')
    if not manager_id:
        return jsonify({'success': False, 'error': 'Требуется авторизация менеджера'}), 401
    
    try:
        # Start with base query
        query = Recommendation.query.filter_by(manager_id=manager_id)
        
        # Apply filters from request params
        client_id = request.args.get('client_id')
        status = request.args.get('status')
        rec_type = request.args.get('type')
        priority = request.args.get('priority')
        
        if client_id:
            query = query.filter(Recommendation.client_id == client_id)
        if status:
            query = query.filter(Recommendation.status == status)
        if rec_type:
            query = query.filter(Recommendation.item_type == rec_type)
        if priority:
            query = query.filter(Recommendation.priority == priority)
        
        recommendations = query.order_by(Recommendation.sent_at.desc()).all()
        
        recommendations_data = []
        stats = {'sent': 0, 'viewed': 0, 'interested': 0, 'scheduled': 0}
        
        for rec in recommendations:
            rec_dict = rec.to_dict()
            rec_dict['client_email'] = rec.client.email
            rec_dict['client_name'] = rec.client.full_name
            recommendations_data.append(rec_dict)
            
            # Update stats
            stats['sent'] += 1
            if rec.status == 'viewed':
                stats['viewed'] += 1
            elif rec.status == 'interested':
                stats['interested'] += 1
            elif rec.status == 'scheduled_viewing':
                stats['scheduled'] += 1
        
        return jsonify({
            'success': True, 
            'recommendations': recommendations_data,
            'stats': stats
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/manager/recommendations/<int:recommendation_id>', methods=['DELETE'])
@manager_required  
def api_manager_delete_recommendation(recommendation_id):
    """Delete a recommendation"""
    from models import Recommendation
    
    manager_id = session.get('manager_id')
    
    try:
        # Find recommendation that belongs to this manager
        recommendation = Recommendation.query.filter_by(
            id=recommendation_id, 
            manager_id=manager_id
        ).first()
        
        if not recommendation:
            return jsonify({'success': False, 'error': 'Рекомендация не найдена'}), 404
        
        db.session.delete(recommendation)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Рекомендация успешно удалена'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/manager/clients-list', methods=['GET'])
@manager_required
def api_manager_get_clients_list():
    """Get manager's clients for filters"""
    from models import User
    
    manager_id = session.get('manager_id')
    
    try:
        # Get clients assigned to this manager or all buyers
        clients = User.query.filter_by(role='buyer').order_by(User.full_name).all()
        
        clients_data = []
        for client in clients:
            clients_data.append({
                'id': client.id,
                'full_name': client.full_name or 'Без имени',
                'email': client.email
            })
        
        return jsonify({
            'success': True,
            'clients': clients_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/properties/search', methods=['POST'])
@login_required
def api_search_properties():
    """Search properties with filters from dashboard"""
    data = request.get_json()
    filters = data.get('filters', {})
    
    try:
        # Convert collection filters to property filters
        property_filters = {}
        
        if filters.get('priceFrom'):
            property_filters['price_min'] = filters['priceFrom']
        if filters.get('priceTo'):
            property_filters['price_max'] = filters['priceTo']
        if filters.get('rooms'):
            property_filters['rooms'] = filters['rooms']
        if filters.get('districts') and filters['districts']:
            property_filters['district'] = filters['districts'][0]
        if filters.get('developers') and filters['developers']:
            property_filters['developer'] = filters['developers'][0]
        if filters.get('areaFrom'):
            property_filters['area_min'] = filters['areaFrom']
        if filters.get('areaTo'):
            property_filters['area_max'] = filters['areaTo']
        
        # Get filtered properties
        filtered_properties = get_filtered_properties(property_filters)
        
        # Add cashback to each property
        for prop in filtered_properties:
            prop['cashback'] = calculate_cashback(prop['price'])
        
        # Sort by price ascending
        filtered_properties = sort_properties(filtered_properties, 'price_asc')
        
        return jsonify({
            'success': True,
            'properties': filtered_properties[:50],  # Limit to 50 results
            'total_count': len(filtered_properties)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/manager/send-property', methods=['POST'])
@manager_required
def api_send_property_to_client():
    """Send saved search results to client via email"""
    from models import SavedSearch, User, ClientPropertyRecommendation
    
    data = request.get_json()
    client_id = data.get('client_id')
    search_id = data.get('search_id')
    message = data.get('message', '')
    
    if not client_id or not search_id:
        return jsonify({'success': False, 'error': 'Клиент и поиск обязательны'}), 400
    
    try:
        # Get the search
        search = SavedSearch.query.get(search_id)
        if not search:
            return jsonify({'success': False, 'error': 'Поиск не найден'}), 404
        
        # Get the client
        client = User.query.get(client_id)
        if not client:
            return jsonify({'success': False, 'error': 'Клиент не найден'}), 404
        
        # Get search filters
        filters = json.loads(search.filters) if search.filters else {}
        
        # Filter properties based on search criteria
        properties = load_properties()
        filtered_properties = filter_properties(properties, filters)
        
        # Create recommendation record
        recommendation = ClientPropertyRecommendation()
        recommendation.client_id = client_id
        recommendation.manager_id = session.get('manager_id')
        recommendation.search_name = search.name
        recommendation.search_filters = search.filters
        recommendation.message = message
        recommendation.properties_count = len(filtered_properties)
        recommendation.sent_at = datetime.utcnow()
        
        db.session.add(recommendation)
        db.session.commit()
        
        # Send email with property recommendations
        send_property_email(client, search.name, filtered_properties, message)
        
        return jsonify({'success': True, 'properties_sent': len(filtered_properties)})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

def filter_properties(properties, filters):
    """Filter properties based on search criteria"""
    filtered = []
    
    for prop in properties:
        # Price filter
        if filters.get('priceFrom'):
            try:
                if prop.get('price', 0) < int(filters['priceFrom']):
                    continue
            except (ValueError, TypeError):
                pass
        
        if filters.get('priceTo'):
            try:
                if prop.get('price', 0) > int(filters['priceTo']):
                    continue
            except (ValueError, TypeError):
                pass
        
        # Rooms filter
        if filters.get('rooms'):
            prop_rooms = str(prop.get('rooms', ''))
            if filters['rooms'] == 'studio' and prop_rooms != 'studio':
                continue
            elif filters['rooms'] != 'studio' and prop_rooms != str(filters['rooms']):
                continue
        
        # District filter
        if filters.get('districts') and len(filters['districts']) > 0:
            prop_district = prop.get('district', '')
            if prop_district not in filters['districts']:
                continue
        
        # Area filter
        if filters.get('areaFrom'):
            try:
                if prop.get('area', 0) < int(filters['areaFrom']):
                    continue
            except (ValueError, TypeError):
                pass
        
        if filters.get('areaTo'):
            try:
                if prop.get('area', 0) > int(filters['areaTo']):
                    continue
            except (ValueError, TypeError):
                pass
        
        # Developer filter
        if filters.get('developers') and len(filters['developers']) > 0:
            prop_developer = prop.get('developer', '')
            if prop_developer not in filters['developers']:
                continue
        
        filtered.append(prop)
    
    return filtered

def send_property_email(client, search_name, properties, message):
    """Send email with property recommendations"""
    try:
        subject = f"Новая подборка недвижимости: {search_name}"
        
        properties_html = ""
        for prop in properties[:10]:  # Limit to first 10 properties
            properties_html += f"""
            <div style="border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
                <h3 style="margin: 0 0 8px 0; color: #1f2937;">{prop.get('name', 'Без названия')}</h3>
                <p style="margin: 0 0 4px 0; color: #6b7280;">ЖК: {prop.get('complex_name', 'Не указан')}</p>
                <p style="margin: 0 0 4px 0; color: #6b7280;">Цена: {prop.get('price', 0):,} ₽</p>
                <p style="margin: 0 0 4px 0; color: #6b7280;">Площадь: {prop.get('area', 0)} м²</p>
                <p style="margin: 0 0 8px 0; color: #6b7280;">Комнат: {prop.get('rooms', 'Не указано')}</p>
                <a href="https://inback.ru/properties/{prop.get('id', '')}" style="color: #0088cc; text-decoration: none;">Подробнее →</a>
            </div>
            """
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #0088cc;">Персональная подборка недвижимости</h2>
                
                <p>Здравствуйте, {client.full_name}!</p>
                
                <p>Ваш менеджер подготовил для вас подборку недвижимости: <strong>{search_name}</strong></p>
                
                {f'<div style="background: #f3f4f6; padding: 16px; border-radius: 8px; margin: 16px 0;"><p style="margin: 0; font-style: italic;">"{message}"</p></div>' if message else ''}
                
                <h3>Найденные варианты ({len(properties)} объектов):</h3>
                
                {properties_html}
                
                {f'<p style="color: #6b7280;">И еще {len(properties) - 10} объектов в полном каталоге...</p>' if len(properties) > 10 else ''}
                
                <div style="margin-top: 32px; padding: 20px; background: #f9fafb; border-radius: 8px; text-align: center;">
                    <h3 style="margin: 0 0 8px 0;">Нужна консультация?</h3>
                    <p style="margin: 0 0 16px 0;">Свяжитесь с вашим персональным менеджером</p>
                    <a href="mailto:manager@inback.ru" style="background: #0088cc; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">Написать менеджеру</a>
                </div>
                
                <div style="margin-top: 20px; text-align: center; color: #6b7280; font-size: 14px;">
                    <p>С уважением,<br>Команда InBack.ru</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return send_notification(
            client.email,
            subject,
            html_content,
            notification_type="property_recommendation",
            user_id=client.id
        )
    except Exception as e:
        print(f"Error sending property email: {e}")
        return False

@app.route('/api/manager/collection/<int:collection_id>/add_property', methods=['POST'])
@manager_required
def add_property_to_collection(collection_id):
    from models import Collection, CollectionProperty
    import json
    
    data = request.get_json()
    property_id = data.get('property_id')
    manager_note = data.get('manager_note', '')
    
    manager_id = session.get('manager_id')
    
    collection = Collection.query.filter_by(
        id=collection_id,
        created_by_manager_id=manager_id
    ).first()
    
    if not collection:
        return jsonify({'success': False, 'error': 'Подборка не найдена'}), 404
    
    # Load property data from JSON
    try:
        with open('data/properties.json', 'r', encoding='utf-8') as f:
            properties_data = json.load(f)
        
        property_info = None
        for prop in properties_data:
            if str(prop['id']) == str(property_id):
                property_info = prop
                break
        
        if not property_info:
            return jsonify({'success': False, 'error': 'Квартира не найдена'}), 404
        
        # Check if property already in collection
        existing = CollectionProperty.query.filter_by(
            collection_id=collection_id,
            property_id=str(property_id)
        ).first()
        
        if existing:
            return jsonify({'success': False, 'error': 'Квартира уже добавлена в подборку'}), 400
        
        # Get max order_index
        max_order = db.session.query(db.func.max(CollectionProperty.order_index)).filter_by(
            collection_id=collection_id
        ).scalar() or 0
        
        collection_property = CollectionProperty()
        collection_property.collection_id = collection_id
        collection_property.property_id = str(property_id)
        collection_property.property_name = property_info['title']
        collection_property.property_price = property_info['price']
        collection_property.complex_name = property_info.get('residential_complex', 'ЖК не указан')
        collection_property.property_type = f"{property_info['rooms']}-комн"
        collection_property.property_size = property_info['area']
        collection_property.manager_note = manager_note
        collection_property.order_index = max_order + 1
        
        db.session.add(collection_property)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/manager/collection/<int:collection_id>/send', methods=['POST'])
@manager_required
def send_collection(collection_id):
    from models import Collection
    
    manager_id = session.get('manager_id')
    
    collection = Collection.query.filter_by(
        id=collection_id,
        created_by_manager_id=manager_id
    ).first()
    
    if not collection:
        return jsonify({'success': False, 'error': 'Подборка не найдена'}), 404
    
    if not collection.assigned_to_user_id:
        return jsonify({'success': False, 'error': 'Клиент не назначен'}), 400
    
    if len(collection.properties) == 0:
        return jsonify({'success': False, 'error': 'В подборке нет квартир'}), 400
    
    try:
        collection.status = 'Отправлена'
        collection.sent_at = datetime.utcnow()
        collection.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/properties/search')
@manager_required
def search_properties():
    import json
    
    query = request.args.get('q', '').lower()
    limit = int(request.args.get('limit', 20))
    
    try:
        with open('data/properties.json', 'r', encoding='utf-8') as f:
            properties_data = json.load(f)
        
        filtered_properties = []
        for prop in properties_data:
            prop_type = f"{prop['rooms']}-комн"
            complex_name = prop.get('residential_complex', 'ЖК не указан')
            
            property_title = f"{prop.get('rooms', 0)}-комн {prop.get('area', 0)} м²" if prop.get('rooms', 0) > 0 else f"Студия {prop.get('area', 0)} м²"
            if (query in property_title.lower() or 
                query in complex_name.lower() or 
                query in prop_type.lower() or
                query in prop.get('developer', '').lower() or
                query in prop.get('district', '').lower()):
                filtered_properties.append({
                    'id': prop['id'],
                    'title': f"{prop.get('rooms', 0)}-комн {prop.get('area', 0)} м²" if prop.get('rooms', 0) > 0 else f"Студия {prop.get('area', 0)} м²",
                    'price': prop['price'],
                    'complex': complex_name,
                    'type': prop_type,
                    'size': prop['area'],
                    'image': prop.get('image', '/static/images/property-placeholder.jpg')
                })
            
            if len(filtered_properties) >= limit:
                break
        
        return jsonify({'properties': filtered_properties})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/client/collections')
@login_required
def get_client_collections():
    """Get collections assigned to current user"""
    from models import Collection, CollectionProperty
    from datetime import datetime
    
    user_id = current_user.id
    
    collections = Collection.query.filter_by(assigned_to_user_id=user_id).all()
    
    collections_data = []
    for collection in collections:
        properties_count = len(collection.properties)
        
        # Mark as viewed if not already
        if collection.status == 'Отправлена':
            collection.status = 'Просмотрена'
            collection.viewed_at = datetime.utcnow()
            db.session.commit()
        
        collections_data.append({
            'id': collection.id,
            'title': collection.title,
            'description': collection.description,
            'status': collection.status,
            'created_by_manager_name': collection.created_by.full_name,
            'properties_count': properties_count,
            'created_at': collection.created_at.strftime('%d.%m.%Y'),
            'sent_at': collection.sent_at.strftime('%d.%m.%Y %H:%M') if collection.sent_at else None,
            'tags': collection.tags
        })
    
    return jsonify({'collections': collections_data})

@app.route('/api/client/collection/<int:collection_id>/properties')
@login_required
def get_client_collection_properties(collection_id):
    """Get properties in a collection for client view"""
    from models import Collection, CollectionProperty
    
    user_id = current_user.id
    
    collection = Collection.query.filter_by(
        id=collection_id,
        assigned_to_user_id=user_id
    ).first()
    
    if not collection:
        return jsonify({'success': False, 'error': 'Подборка не найдена'}), 404
    
    properties_data = []
    for prop in collection.properties:
        # Calculate potential cashback (example: 2% of price)
        cashback_percent = 2.0
        cashback_amount = int(prop.property_price * cashback_percent / 100)
        
        properties_data.append({
            'id': prop.id,
            'property_id': prop.property_id,
            'property_name': prop.property_name,
            'property_price': prop.property_price,
            'complex_name': prop.complex_name,
            'property_type': prop.property_type,
            'property_size': prop.property_size,
            'manager_note': prop.manager_note,
            'cashback_amount': cashback_amount,
            'cashback_percent': cashback_percent
        })
    
    # Sort by order_index
    properties_data.sort(key=lambda x: collection.properties[0].order_index if collection.properties else 0)
    
    return jsonify({
        'collection': {
            'id': collection.id,
            'title': collection.title,
            'description': collection.description,
            'status': collection.status,
            'manager_name': collection.created_by.full_name,
            'sent_at': collection.sent_at.strftime('%d.%m.%Y %H:%M') if collection.sent_at else None
        },
        'properties': properties_data
    })

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard"""
    try:
        from models import CashbackApplication, FavoriteProperty, Document, Collection, Recommendation, SentSearch, SavedSearch
        
        # Get user's data for dashboard
        cashback_apps = CashbackApplication.query.filter_by(user_id=current_user.id).all()
        favorites = FavoriteProperty.query.filter_by(user_id=current_user.id).all()
        documents = Document.query.filter_by(user_id=current_user.id).all()
        collections = Collection.query.filter_by(assigned_to_user_id=current_user.id).order_by(Collection.created_at.desc()).limit(3).all()
        
        # Get recommendations from managers (exclude dismissed) with categories
        recommendations = Recommendation.query.filter(
            Recommendation.client_id == current_user.id,
            Recommendation.status != 'dismissed'
        ).options(db.joinedload(Recommendation.category)).order_by(Recommendation.created_at.desc()).all()
        
        # Get unique categories for the client (import here to avoid circular imports)
        from models import RecommendationCategory
        categories = RecommendationCategory.query.filter_by(client_id=current_user.id, is_active=True).all()
        
        # Enrich recommendations with property details
        for rec in recommendations:
            if rec.recommendation_type == 'property' and rec.item_id:
                try:
                    properties = load_properties()
                    complexes = load_residential_complexes()
                    property_data = next((p for p in properties if str(p.get('id')) == str(rec.item_id)), None)
                    if property_data:
                        # Create a simple object to store property details
                        class PropertyDetails:
                            def __init__(self, data, complexes):
                                for key, value in data.items():
                                    setattr(self, key, value)
                                
                                # Add residential complex name - try multiple sources
                                self.residential_complex = None
                                
                                # First try complex_name field (direct from expanded data)
                                if data.get('complex_name'):
                                    self.residential_complex = data.get('complex_name')
                                # Then try complex_id lookup
                                elif data.get('complex_id'):
                                    complex_data = next((c for c in complexes if c.get('id') == data.get('complex_id')), None)
                                    if complex_data:
                                        self.residential_complex = complex_data.get('name')
                                # Legacy support for residential_complex_id
                                elif data.get('residential_complex_id'):
                                    complex_data = next((c for c in complexes if c.get('id') == data.get('residential_complex_id')), None)
                                    if complex_data:
                                        self.residential_complex = complex_data.get('name')
                                
                                # Map property type from Russian to English for template logic
                                type_mapping = {
                                    'Квартира': 'apartment',
                                    'Таунхаус': 'townhouse', 
                                    'Дом': 'house'
                                }
                                original_type = data.get('property_type', 'Квартира')
                                self.property_type = type_mapping.get(original_type, 'apartment')
                                self.property_type_ru = original_type
                        
                        rec.property_details = PropertyDetails(property_data, complexes)
                        complex_name = rec.property_details.residential_complex or 'Не указан'
                        print(f"Loaded property {rec.item_id}: {property_data.get('rooms')} комн, ЖК {complex_name}")
                    else:
                        print(f"Property {rec.item_id} not found in data files")
                        rec.property_details = None
                except Exception as e:
                    print(f"Error loading property details for recommendation {rec.id}: {e}")
                    rec.property_details = None
        
        # Get sent searches from managers
        sent_searches = SentSearch.query.filter_by(client_id=current_user.id).order_by(SentSearch.sent_at.desc()).all()
        
        # Get user's saved searches
        saved_searches = SavedSearch.query.filter_by(user_id=current_user.id).order_by(SavedSearch.created_at.desc()).all()
        
        # Calculate totals
        total_cashback = sum(app.cashback_amount for app in cashback_apps if app.status == 'Выплачена')
        pending_cashback = sum(app.cashback_amount for app in cashback_apps if app.status == 'Одобрена')
        active_apps = len([app for app in cashback_apps if app.status in ['На рассмотрении', 'Требуются документы']])
        
        # Get developer appointments
        from models import DeveloperAppointment
        appointments = DeveloperAppointment.query.filter_by(user_id=current_user.id).order_by(DeveloperAppointment.appointment_date.desc()).limit(3).all()
        
        # Load data for manager filters
        districts = get_districts_list()
        developers = get_developers_list()
        
        return render_template('auth/dashboard.html', 
                             cashback_applications=cashback_apps,
                             favorites=favorites,
                             documents=documents,
                             collections=collections,
                             appointments=appointments,
                             recommendations=recommendations,
                             categories=categories,
                             sent_searches=sent_searches,
                             saved_searches=saved_searches,
                             total_cashback=total_cashback,
                             pending_cashback=pending_cashback,
                             active_apps=active_apps,
                             districts=districts,
                             developers=developers)
    except Exception as e:
        print(f"Dashboard error: {str(e)}")
        import traceback
        traceback.print_exc()
        # Return basic dashboard on error
        districts = get_districts_list()
        developers = get_developers_list()
        
        return render_template('auth/dashboard.html', 
                             cashback_applications=[],
                             favorites=[],
                             documents=[],
                             collections=[],
                             appointments=[],
                             recommendations=[],
                             sent_searches=[],
                             saved_searches=[],
                             total_cashback=0,
                             pending_cashback=0,
                             active_apps=0,
                             districts=districts,
                             developers=developers)

@app.route('/logout')
@login_required
def logout():
    """Logout user"""
    logout_user()
    flash('Вы успешно вышли из системы', 'success')
    return redirect(url_for('index'))

@app.route('/api/search')
def api_search():
    """API endpoint for global search"""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
    
    results = search_global(query)
    return jsonify(results)

@app.route('/search')
def search_results():
    """Search results page"""
    query = request.args.get('q', '').strip()
    search_type = request.args.get('type', 'all')  # all, residential_complex, district, developer, street
    
    results = []
    if query:
        results = search_global(query)
        
        # Filter by type if specified
        if search_type != 'all':
            results = [r for r in results if r['type'] == search_type]
    
    return render_template('search_results.html', 
                         query=query, 
                         results=results,
                         search_type=search_type)


@app.route('/api/smart-search-suggestions')
def smart_search_suggestions():
    """API endpoint for search suggestions with intelligent keyword matching"""
    query = request.args.get('q', '').strip().lower()
    if not query or len(query) < 1:
        return jsonify({'suggestions': []})
    
    suggestions = []
    
    try:
        # Intelligent room type matching patterns
        room_patterns = {
            # Single room patterns
            ('1', '1-', '1-к', '1-ко', '1-ком', '1 к', '1 ко', '1 ком', 'одн', 'одно', 'однок', 'однокомн', 'однокомнат', 'однокомнатн', 'один', 'одной'): ('1-комнатная квартира', 'rooms', '1'),
            # Two room patterns  
            ('2', '2-', '2-к', '2-ко', '2-ком', '2 к', '2 ко', '2 ком', 'двух', 'двухк', 'двухком', 'двухкомн', 'двухкомнат', 'два', 'двой', 'двойн'): ('2-комнатная квартира', 'rooms', '2'),
            # Three room patterns
            ('3', '3-', '3-к', '3-ко', '3-ком', '3 к', '3 ко', '3 ком', 'трех', 'трёх', 'трехк', 'трёхк', 'трехком', 'трёхком', 'три', 'трой'): ('3-комнатная квартира', 'rooms', '3'),
            # Four room patterns
            ('4', '4-', '4-к', '4-ко', '4-ком', '4 к', '4 ко', '4 ком', 'четыр', 'четырех', 'четырёх', 'четырехк', 'четырёхк', 'четыре'): ('4-комнатная квартира', 'rooms', '4'),
            # Studio patterns
            ('студ', 'studio', 'студий', 'студия'): ('Студия', 'rooms', 'studio'),
        }
        
        # Check room type patterns first
        for patterns, (room_text, type_val, value) in room_patterns.items():
            for pattern in patterns:
                if query.startswith(pattern) or pattern in query:
                    suggestions.append({
                        'text': room_text,
                        'type': type_val,
                        'value': value,
                        'category': 'Тип квартиры'
                    })
                    break
        
        # Search in database categories (districts, developers, complexes)
        cursor = db.session.execute(text("""
            SELECT name, category_type, slug 
            FROM search_categories 
            WHERE LOWER(name) LIKE :query 
            ORDER BY 
                CASE 
                    WHEN LOWER(name) LIKE :exact_start THEN 1
                    WHEN LOWER(name) LIKE :word_start THEN 2
                    ELSE 3
                END,
                LENGTH(name)
            LIMIT 15
        """), {
            'query': f'%{query}%',
            'exact_start': f'{query}%',
            'word_start': f'% {query}%'
        })
        
        category_names = {
            'district': 'Район',
            'developer': 'Застройщик', 
            'complex': 'ЖК',
            'rooms': 'Тип квартиры'
        }
        
        for row in cursor:
            name, category_type, slug = row
            suggestions.append({
                'text': name,
                'type': category_type,
                'value': slug,
                'category': category_names.get(category_type, category_type.title())
            })
        
        # Remove duplicates while preserving order
        seen = set()
        unique_suggestions = []
        for s in suggestions:
            key = (s['text'], s['type'])
            if key not in seen:
                seen.add(key)
                unique_suggestions.append(s)
        
        return jsonify({'suggestions': unique_suggestions[:12]})
        
    except Exception as e:
        app.logger.error(f"Smart search error: {e}")
        return jsonify({'suggestions': []})

def init_search_data():
    """Initialize search data in database"""
    from models import District, Developer, ResidentialComplex, Street, RoomType
    
    # Districts
    districts_data = [
        ('Центральный', 'tsentralnyy'), ('Западный', 'zapadny'), 
        ('Карасунский', 'karasunsky'), ('Прикубанский', 'prikubansky'),
        ('Фестивальный', 'festivalny'), ('Юбилейный', 'yubileynyy'),
        ('Гидростроителей', 'gidrostroitelei'), ('Солнечный', 'solnechny'),
        ('Панорама', 'panorama'), ('Музыкальный', 'muzykalnyy')
    ]
    
    for name, slug in districts_data:
        if not District.query.filter_by(slug=slug).first():
            district = District(name=name, slug=slug)
            db.session.add(district)
    
    # Room types
    room_types_data = [
        ('Студия', 0), ('1-комнатная квартира', 1), 
        ('2-комнатная квартира', 2), ('3-комнатная квартира', 3), 
        ('4-комнатная квартира', 4), ('Пентхаус', 5)
    ]
    
    for name, rooms_count in room_types_data:
        if not RoomType.query.filter_by(name=name).first():
            room_type = RoomType(name=name, rooms_count=rooms_count)
            db.session.add(room_type)
    
    # Developers
    developers_data = [
        ('Краснодар Инвест', 'krasnodar-invest'),
        ('ЮгСтройИнвест', 'yugstroyinvest'),
        ('Флагман', 'flagman'),
        ('Солнечный город', 'solnechny-gorod'),
        ('Премьер', 'premier')
    ]
    
    for name, slug in developers_data:
        if not Developer.query.filter_by(slug=slug).first():
            developer = Developer(name=name, slug=slug)
            db.session.add(developer)
    
    # Residential complexes
    complexes_data = [
        ('Солнечный', 'solnechny', 1, 1),
        ('Панорама', 'panorama', 1, 2),
        ('Гармония', 'garmoniya', 2, 3),
        ('Европейский квартал', 'evropeyskiy-kvartal', 3, 1),
        ('Флагман', 'flagman', 4, 4)
    ]
    
    for name, slug, district_id, developer_id in complexes_data:
        if not ResidentialComplex.query.filter_by(slug=slug).first():
            complex = ResidentialComplex(name=name, slug=slug, district_id=district_id, developer_id=developer_id)
            db.session.add(complex)
    
    db.session.commit()


# ==================== ADMIN ROUTES ====================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        from models import Admin
        email = request.form.get('email')
        password = request.form.get('password')
        
        admin = Admin.query.filter_by(email=email, is_active=True).first()
        
        if admin and admin.check_password(password):
            session.permanent = True
            session['admin_id'] = admin.id
            session['is_admin'] = True
            admin.last_login = datetime.utcnow()
            db.session.commit()
            flash('Добро пожаловать в панель администратора!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Неверный email или пароль', 'error')
    
    return render_template('admin/admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.pop('admin_id', None)
    session.pop('is_admin', None)
    flash('Вы вышли из панели администратора', 'info')
    return redirect(url_for('admin_login'))

def admin_required(f):
    """Decorator to require admin authentication"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin') or not session.get('admin_id'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """Admin dashboard with analytics"""
    from models import Admin, User, Manager, CashbackApplication, CallbackRequest
    
    admin_id = session.get('admin_id')
    current_admin = Admin.query.get(admin_id)
    
    if not current_admin:
        return redirect(url_for('admin_login'))
    
    # Analytics data
    stats = {
        'total_users': User.query.count(),
        'total_managers': Manager.query.count(),
        'total_applications': CashbackApplication.query.count(),
        'pending_applications': CashbackApplication.query.filter_by(status='На рассмотрении').count(),
        'approved_applications': CashbackApplication.query.filter_by(status='Одобрена').count(),
        'paid_applications': CashbackApplication.query.filter_by(status='Выплачена').count(),
        'total_cashback_approved': sum(app.cashback_amount for app in CashbackApplication.query.filter_by(status='Одобрена').all()),
        'total_cashback_paid': sum(app.cashback_amount for app in CashbackApplication.query.filter_by(status='Выплачена').all()),
        'active_users': User.query.filter_by(is_active=True).count(),
        'active_managers': Manager.query.filter_by(is_active=True).count(),
        'cashback_requests': CallbackRequest.query.filter(CallbackRequest.notes.contains('кешбек')).count(),
        'new_requests': CallbackRequest.query.filter_by(status='Новая').count(),
    }
    
    # Recent activity
    recent_applications = CashbackApplication.query.order_by(CashbackApplication.created_at.desc()).limit(10).all()
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    recent_cashback_requests = CallbackRequest.query.filter(
        CallbackRequest.notes.contains('кешбек')
    ).order_by(CallbackRequest.created_at.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html',
                         admin=current_admin,
                         stats=stats,
                         recent_applications=recent_applications,
                         recent_users=recent_users,
                         recent_cashback_requests=recent_cashback_requests,
                         current_date=datetime.now())

@app.route('/admin/cashback-requests')
@admin_required
def admin_cashback_requests():
    """View all cashback requests"""
    from models import CallbackRequest
    
    # Get page number
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Filter cashback requests
    cashback_requests = CallbackRequest.query.filter(
        CallbackRequest.notes.contains('кешбек')
    ).order_by(CallbackRequest.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('admin/cashback_requests.html',
                         requests=cashback_requests)

@app.route('/admin/callback-request/<int:request_id>/status', methods=['POST'])
@admin_required
def update_callback_request_status(request_id):
    """Update callback request status"""
    from models import CallbackRequest
    
    try:
        data = request.get_json()
        new_status = data.get('status')
        
        callback_request = CallbackRequest.query.get_or_404(request_id)
        callback_request.status = new_status
        
        if new_status == 'Обработана':
            callback_request.processed_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Статус обновлен'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/favorites/count', methods=['GET'])
@login_required  
def get_favorites_count():
    """Get count of user's favorites"""
    from models import FavoriteProperty, FavoriteComplex
    
    try:
        properties_count = FavoriteProperty.query.filter_by(user_id=current_user.id).count()
        complexes_count = FavoriteComplex.query.filter_by(user_id=current_user.id).count()
        
        return jsonify({
            'success': True,
            'properties_count': properties_count,
            'complexes_count': complexes_count,
            'total_count': properties_count + complexes_count
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/favorites/list', methods=['GET'])
@login_required  
def get_favorites_list():
    """Get user's favorite properties with full details"""
    from models import FavoriteProperty
    
    try:
        favorites = db.session.query(FavoriteProperty).filter_by(user_id=current_user.id).order_by(FavoriteProperty.created_at.desc()).all()
        print(f"Found {len(favorites)} favorites in database for user {current_user.id}")
        
        # Load properties data
        properties_data = load_properties()
        print(f"Loaded {len(properties_data)} properties from JSON")
        
        # Debug: show first few property IDs
        if properties_data:
            ids = [str(p.get('id')) for p in properties_data[:5]]
            print(f"First 5 property IDs from JSON: {ids}")
        
        favorites_list = []
        for fav in favorites:
            print(f"Looking for property_id {fav.property_id} (type: {type(fav.property_id)})")
            # Get property data from JSON files - compare as integers
            property_data = None
            for prop in properties_data:
                if int(prop.get('id')) == int(fav.property_id):
                    property_data = prop
                    break
            
            if property_data:
                print(f"Found property data for ID {fav.property_id}")
                # Add to favorites list with complete data including timestamp
                favorites_list.append({
                    'id': property_data.get('id'),
                    'title': property_data.get('title', 'Квартира'),
                    'complex': property_data.get('complex_name', 'ЖК не указан'),
                    'district': property_data.get('district', 'Район не указан'),
                    'price': property_data.get('price', 0),
                    'image': property_data.get('image', '/static/images/no-photo.jpg'),
                    'cashback_amount': calculate_cashback(property_data.get('price', 0)),
                    'created_at': fav.created_at.strftime('%d.%m.%Y в %H:%M') if fav.created_at else 'Недавно'
                })
            else:
                print(f"No property data found for ID {fav.property_id}")
                # Create fallback entry with minimal data
                favorites_list.append({
                    'id': fav.property_id,
                    'title': f'Объект #{fav.property_id}',
                    'complex': 'ЖК не найден',
                    'district': 'Данные обновляются...',
                    'price': 0,
                    'image': '/static/images/no-photo.jpg',
                    'cashback_amount': 0
                })
        
        return jsonify({
            'success': True,
            'favorites': favorites_list
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Complex Favorites API
@app.route('/api/complexes/favorites', methods=['POST'])
@login_required  
def add_complex_to_favorites():
    """Add residential complex to favorites"""
    from models import FavoriteComplex
    data = request.get_json()
    
    complex_id = data.get('complex_id')
    complex_name = data.get('complex_name', 'ЖК')
    
    if not complex_id:
        return jsonify({'success': False, 'error': 'complex_id is required'}), 400
    
    # Check if already in favorites
    existing = FavoriteComplex.query.filter_by(
        user_id=current_user.id,
        complex_id=str(complex_id)
    ).first()
    
    if existing:
        return jsonify({'success': False, 'error': 'Complex already in favorites'}), 400
    
    try:
        # Create favorite complex record
        favorite = FavoriteComplex(
            user_id=current_user.id,
            complex_id=str(complex_id),
            complex_name=complex_name,
            developer_name=data.get('developer_name', ''),
            complex_address=data.get('address', ''),
            district=data.get('district', ''),
            min_price=data.get('min_price'),
            max_price=data.get('max_price'),
            complex_image=data.get('image', ''),
            complex_url=data.get('url', ''),
            status=data.get('status', 'В продаже')
        )
        
        db.session.add(favorite)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'ЖК добавлен в избранное'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/complexes/favorites/<complex_id>', methods=['DELETE'])
@login_required
def remove_complex_from_favorites(complex_id):
    """Remove residential complex from favorites"""
    from models import FavoriteComplex
    
    favorite = FavoriteComplex.query.filter_by(
        user_id=current_user.id,
        complex_id=str(complex_id)
    ).first()
    
    if not favorite:
        return jsonify({'success': False, 'error': 'Complex not in favorites'}), 404
    
    try:
        db.session.delete(favorite)
        db.session.commit()
        return jsonify({'success': True, 'message': 'ЖК удален из избранного'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/complexes/favorites/toggle', methods=['POST'])
@login_required
def toggle_complex_favorite():
    """Toggle favorite status for residential complex"""
    from models import FavoriteComplex
    data = request.get_json()
    complex_id = data.get('complex_id')
    
    if not complex_id:
        return jsonify({'success': False, 'error': 'complex_id is required'}), 400
    
    try:
        existing = FavoriteComplex.query.filter_by(
            user_id=current_user.id,
            complex_id=str(complex_id)
        ).first()
        
        if existing:
            # Remove from favorites
            db.session.delete(existing)
            db.session.commit()
            return jsonify({'success': True, 'favorited': False, 'message': 'ЖК удален из избранного'})
        else:
            # Add to favorites
            favorite = FavoriteComplex(
                user_id=current_user.id,
                complex_id=str(complex_id),
                complex_name=data.get('complex_name', 'ЖК'),
                developer_name=data.get('developer_name', ''),
                complex_address=data.get('address', ''),
                district=data.get('district', ''),
                min_price=data.get('min_price'),
                max_price=data.get('max_price'),
                complex_image=data.get('image', ''),
                complex_url=data.get('url', ''),
                status=data.get('status', 'В продаже')
            )
            
            db.session.add(favorite)
            db.session.commit()
            return jsonify({'success': True, 'favorited': True, 'message': 'ЖК добавлен в избранное'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/complexes/favorites/list', methods=['GET'])
@login_required  
def get_complex_favorites_list():
    """Get user's favorite complexes with full details"""
    from models import FavoriteComplex
    
    try:
        favorites = db.session.query(FavoriteComplex).filter_by(user_id=current_user.id).order_by(FavoriteComplex.created_at.desc()).all()
        
        favorites_list = []
        for fav in favorites:
            favorites_list.append({
                'id': fav.complex_id,
                'name': fav.complex_name,
                'developer': fav.developer_name,
                'address': fav.complex_address,
                'district': fav.district,
                'min_price': fav.min_price,
                'max_price': fav.max_price,
                'image': fav.complex_image,
                'url': fav.complex_url,
                'status': fav.status,
                'created_at': fav.created_at.strftime('%d.%m.%Y в %H:%M') if fav.created_at else 'Недавно'
            })
        
        return jsonify({
            'success': True,
            'complexes': favorites_list
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# User Management Routes
@app.route('/admin/users')
@admin_required
def admin_users():
    """User management page"""
    from models import Admin, User
    
    admin_id = session.get('admin_id')
    current_admin = Admin.query.get(admin_id)
    
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    status = request.args.get('status', '', type=str)
    
    query = User.query
    
    if search:
        query = query.filter(User.email.contains(search) | User.full_name.contains(search))
    
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)
    elif status == 'verified':
        query = query.filter_by(is_verified=True)
    elif status == 'unverified':
        query = query.filter_by(is_verified=False)
    
    users = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('admin/users.html', 
                         admin=current_admin, 
                         users=users,
                         search=search,
                         status=status)

@app.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_user(user_id):
    """Edit user details"""
    from models import Admin, User, Manager
    
    admin_id = session.get('admin_id')
    current_admin = Admin.query.get(admin_id)
    user = User.query.get_or_404(user_id)
    managers = Manager.query.filter_by(is_active=True).all()
    
    if request.method == 'POST':
        user.email = request.form.get('email')
        user.full_name = request.form.get('full_name')
        user.phone = request.form.get('phone')
        user.client_status = request.form.get('client_status')
        user.client_notes = request.form.get('client_notes')
        user.is_active = 'is_active' in request.form
        user.is_verified = 'is_verified' in request.form
        
        assigned_manager_id = request.form.get('assigned_manager_id')
        if assigned_manager_id and assigned_manager_id.isdigit():
            user.assigned_manager_id = int(assigned_manager_id)
        else:
            user.assigned_manager_id = None
        
        try:
            db.session.commit()
            flash('Пользователь успешно обновлен', 'success')
            return redirect(url_for('admin_users'))
        except Exception as e:
            db.session.rollback()
            flash('Ошибка при обновлении пользователя', 'error')
    
    return render_template('admin/edit_user.html', 
                         admin=current_admin, 
                         user=user,
                         managers=managers)

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    """Delete user"""
    from models import User
    
    user = User.query.get_or_404(user_id)
    
    try:
        db.session.delete(user)
        db.session.commit()
        flash('Пользователь успешно удален', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Ошибка при удалении пользователя', 'error')
    
    return redirect(url_for('admin_users'))

@app.route('/admin/users/create', methods=['GET', 'POST'])
@admin_required
def admin_create_user():
    """Create new user by admin"""
    from models import Admin, User, Manager
    import re
    import secrets
    
    admin_id = session.get('admin_id')
    current_admin = Admin.query.get(admin_id)
    managers = Manager.query.filter_by(is_active=True).all()
    
    if request.method == 'POST':
        try:
            # Validate required fields
            full_name = request.form.get('full_name', '').strip()
            email = request.form.get('email', '').strip().lower()
            phone = request.form.get('phone', '').strip()
            
            if not all([full_name, email, phone]):
                flash('Заполните все обязательные поля', 'error')
                return render_template('admin/create_user.html', 
                                     admin=current_admin, 
                                     managers=managers)
            
            # Validate email format
            if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
                flash('Некорректный формат email', 'error')
                return render_template('admin/create_user.html', 
                                     admin=current_admin, 
                                     managers=managers)
            
            # Check if user already exists
            existing_user = User.query.filter(
                (User.email == email) | (User.phone == phone)
            ).first()
            
            if existing_user:
                flash('Пользователь с таким email или телефоном уже существует', 'error')
                return render_template('admin/create_user.html', 
                                     admin=current_admin, 
                                     managers=managers)
            
            # Clean phone number
            phone_clean = re.sub(r'[^\d]', '', phone)
            if len(phone_clean) == 11 and phone_clean.startswith('8'):
                phone_clean = '7' + phone_clean[1:]
            elif len(phone_clean) == 10:
                phone_clean = '7' + phone_clean
            
            if len(phone_clean) != 11 or not phone_clean.startswith('7'):
                flash('Некорректный формат телефона', 'error')
                return render_template('admin/create_user.html', 
                                     admin=current_admin, 
                                     managers=managers)
            
            # Generate temporary password
            temp_password = secrets.token_urlsafe(12)
            
            # Create user
            user = User(
                email=email,
                full_name=full_name,
                phone=phone_clean,
                client_status=request.form.get('client_status', 'Новый'),
                client_notes=request.form.get('client_notes', ''),
                is_active='is_active' in request.form,
                is_verified='is_verified' in request.form,
                temp_password_hash=temp_password,  # Store temp password for sending
                created_by_admin=True
            )
            
            # Set assigned manager
            assigned_manager_id = request.form.get('assigned_manager_id')
            if assigned_manager_id and assigned_manager_id.isdigit():
                user.assigned_manager_id = int(assigned_manager_id)
            
            # Set temporary password
            user.set_password(temp_password)
            
            db.session.add(user)
            db.session.commit()
            
            print(f"DEBUG: Successfully created user {user.id}: {user.full_name} by admin")
            
            # Send credentials if requested
            if 'send_credentials' in request.form:
                try:
                    from email_service import send_email_smtp
                    from sms_service import send_sms
                    
                    # Prepare email content
                    subject = "Ваш аккаунт создан в InBack.ru - Данные для входа"
                    email_content = f"""Здравствуйте, {full_name}!

Для вас создан аккаунт в системе InBack.ru.

Данные для входа:
• Email: {email}
• Временный пароль: {temp_password}

Войдите в систему по адресу: https://inback.ru/login
При первом входе вам будет предложено установить собственный пароль.

С уважением,
Команда InBack.ru"""
                    
                    # Send email using HTML template
                    send_email_smtp(
                        to_email=email,
                        subject=subject,
                        template_name='emails/user_credentials.html',
                        user_name=full_name,
                        email=email,
                        temp_password=temp_password,
                        login_url='https://inback.ru/login'
                    )
                    
                    # Send SMS
                    sms_message = f"InBack.ru: Ваш аккаунт создан. Логин: {email}, Пароль: {temp_password}. Войти: https://inback.ru/login"
                    send_sms(phone_clean, sms_message)
                    
                    flash(f'Пользователь {full_name} успешно создан. Данные для входа отправлены на email и SMS.', 'success')
                    
                except Exception as e:
                    print(f"Error sending credentials: {str(e)}")
                    flash(f'Пользователь создан, но не удалось отправить данные для входа: {str(e)}', 'warning')
            else:
                flash(f'Пользователь {full_name} успешно создан.', 'success')
            
            return redirect(url_for('admin_users'))
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating user: {str(e)}")
            flash(f'Ошибка при создании пользователя: {str(e)}', 'error')
            return render_template('admin/create_user.html', 
                                 admin=current_admin, 
                                 managers=managers)
    
    return render_template('admin/create_user.html', 
                         admin=current_admin, 
                         managers=managers)

@app.route('/admin/users/<int:user_id>/toggle-status', methods=['POST'])
@admin_required
def admin_toggle_user_status(user_id):
    """Toggle user active status"""
    from models import User
    
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    
    try:
        db.session.commit()
        status = 'активирован' if user.is_active else 'заблокирован'
        flash(f'Пользователь {status}', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Ошибка при изменении статуса пользователя', 'error')
    
    return redirect(url_for('admin_users'))

# Manager Management Routes
@app.route('/admin/managers')
@admin_required
def admin_managers():
    """Manager management page"""
    from models import Admin, Manager
    
    admin_id = session.get('admin_id')
    current_admin = Admin.query.get(admin_id)
    
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    status = request.args.get('status', '', type=str)
    
    query = Manager.query
    
    if search:
        query = query.filter(Manager.email.contains(search) | Manager.first_name.contains(search) | Manager.last_name.contains(search))
    
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)
    
    managers = query.order_by(Manager.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('admin/managers.html', 
                         admin=current_admin, 
                         managers=managers,
                         search=search,
                         status=status)

@app.route('/admin/managers/<int:manager_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_manager(manager_id):
    """Edit manager details"""
    from models import Admin, Manager
    
    try:
        admin_id = session.get('admin_id')
        current_admin = Admin.query.get(admin_id)
        manager = Manager.query.get(manager_id)
        
        if not manager:
            flash(f'Менеджер с ID {manager_id} не найден', 'error')
            return redirect(url_for('admin_managers'))
            
        print(f"DEBUG: Found manager {manager_id}: {manager.email}")
    except Exception as e:
        print(f"ERROR in admin_edit_manager: {e}")
        flash('Ошибка при загрузке менеджера', 'error')
        return redirect(url_for('admin_managers'))
    
    if request.method == 'POST':
        manager.email = request.form.get('email')
        manager.first_name = request.form.get('first_name')
        manager.last_name = request.form.get('last_name')
        manager.phone = request.form.get('phone')
        manager.position = request.form.get('position')
        manager.is_active = 'is_active' in request.form
        
        new_password = request.form.get('new_password')
        if new_password:
            manager.set_password(new_password)
        
        try:
            db.session.commit()
            flash('Менеджер успешно обновлен', 'success')
            return redirect(url_for('admin_managers'))
        except Exception as e:
            db.session.rollback()
            flash('Ошибка при обновлении менеджера', 'error')
    
    from datetime import datetime
    
    return render_template('admin/edit_manager.html', 
                         admin=current_admin, 
                         manager=manager,
                         current_date=datetime.utcnow())



# Blog Management Routes
@app.route('/admin/blog')
@admin_required
def admin_blog():
    """Blog management page"""
    from models import Admin, BlogPost
    
    admin_id = session.get('admin_id')
    current_admin = Admin.query.get(admin_id)
    
    if not current_admin:
        return redirect(url_for('admin_login'))
    
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    status = request.args.get('status', '', type=str)
    category = request.args.get('category', '', type=str)
    
    query = BlogPost.query
    
    if search:
        query = query.filter(BlogPost.title.contains(search) | BlogPost.content.contains(search))
    
    if status:
        query = query.filter_by(status=status)
    
    if category:
        query = query.filter_by(category=category)
    
    posts = query.order_by(BlogPost.created_at.desc()).paginate(
        page=page, per_page=10, error_out=False
    )
    
    # Get categories for filter
    categories = db.session.query(BlogPost.category).distinct().filter(BlogPost.category.isnot(None)).all()
    categories = [cat[0] for cat in categories if cat[0]]
    
    return render_template('admin/blog.html', 
                         admin=current_admin, 
                         posts=posts,
                         search=search,
                         status=status,
                         category=category,
                         categories=categories)

@app.route('/admin/blog/create', methods=['GET', 'POST'])
@admin_required
def admin_create_post():
    """Create new blog post with full TinyMCE integration"""
    from models import Admin, BlogPost, BlogCategory
    import re
    
    admin_id = session.get('admin_id')
    current_admin = Admin.query.get(admin_id)
    
    if not current_admin:
        return redirect(url_for('admin_login'))
    
    if request.method == 'GET':
        # Load categories for the form
        categories = BlogCategory.query.order_by(BlogCategory.name).all()
        return render_template('admin/create_article.html', admin=current_admin, categories=categories)
    
    if request.method == 'POST':
        try:
            title = request.form.get('title')
            content = request.form.get('content')
            excerpt = request.form.get('excerpt')
            category_id = request.form.get('category_id')
            
            if not title or not content or not category_id:
                flash('Заголовок, содержание и категория обязательны', 'error')
                categories = BlogCategory.query.order_by(BlogCategory.name).all()
                return render_template('admin/create_article.html', admin=current_admin, categories=categories)
            
            # Get category name from category_id
            category = BlogCategory.query.get(int(category_id))
            if not category:
                flash('Выбранная категория не найдена', 'error')
                categories = BlogCategory.query.order_by(BlogCategory.name).all()
                return render_template('admin/create_article.html', admin=current_admin, categories=categories)
            
            # Generate slug from title
            slug = request.form.get('slug', '')
            if not slug:
                # Auto-generate slug from title
                def transliterate(text):
                    rus_to_eng = {
                        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'zh', 'з': 'z',
                        'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
                        'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'c', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
                        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
                    }
                    return ''.join(rus_to_eng.get(char.lower(), char) for char in text)
                
                slug = transliterate(title.lower())
                slug = re.sub(r'[^\w\s-]', '', slug)
                slug = re.sub(r'[-\s]+', '-', slug).strip('-')
            
            # Ensure unique slug
            original_slug = slug
            counter = 1
            while BlogPost.query.filter_by(slug=slug).first():
                slug = f"{original_slug}-{counter}"
                counter += 1
            
            post = BlogPost(
                title=title,
                slug=slug,
                content=content,
                excerpt=excerpt,
                meta_title=request.form.get('meta_title'),
                meta_description=request.form.get('meta_description'),
                meta_keywords=request.form.get('meta_keywords'),
                category=category.name,  # Store category name for compatibility
                tags=request.form.get('tags'),
                featured_image=request.form.get('featured_image'),
                status=request.form.get('status', 'draft'),
                author_id=current_admin.id,
                created_at=datetime.utcnow()
            )
            
            if post.status == 'published':
                post.published_at = datetime.utcnow()
            
            db.session.add(post)
            db.session.commit()
            
            # Update category article count
            if post.status == 'published':
                category.articles_count = BlogPost.query.filter_by(category=category.name, status='published').count()
                db.session.commit()
            
            flash('Статья успешно создана!', 'success')
            return redirect(url_for('admin_blog'))
            
        except Exception as e:
            db.session.rollback()
            print(f'ERROR creating blog post: {str(e)}')
            flash(f'Ошибка при создании статьи: {str(e)}', 'error')
            categories = BlogCategory.query.order_by(BlogCategory.name).all()
            return render_template('admin/create_article.html', admin=current_admin, categories=categories)

@app.route('/admin/blog/<int:post_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_post(post_id):
    """Edit blog post"""
    from models import Admin, BlogPost, BlogCategory
    
    admin_id = session.get('admin_id')
    current_admin = Admin.query.get(admin_id)
    
    if not current_admin:
        flash('Требуется авторизация администратора', 'error')
        return redirect(url_for('admin_login'))
    
    try:
        post = BlogPost.query.get_or_404(post_id)
    except Exception as e:
        flash(f'Статья не найдена: {str(e)}', 'error')
        return redirect(url_for('admin_blog'))
    
    if request.method == 'POST':
        post.title = request.form.get('title')
        post.content = request.form.get('content')
        post.excerpt = request.form.get('excerpt')
        post.meta_title = request.form.get('meta_title')
        post.meta_description = request.form.get('meta_description')
        post.meta_keywords = request.form.get('meta_keywords')
        post.category = request.form.get('category')
        post.tags = request.form.get('tags')
        post.featured_image = request.form.get('featured_image')
        
        old_status = post.status
        post.status = request.form.get('status', 'draft')
        
        # Handle publishing
        if post.status == 'published' and old_status != 'published':
            post.published_at = datetime.utcnow()
        elif post.status != 'published':
            post.published_at = None
        
        try:
            db.session.commit()
            flash('Статья успешно обновлена', 'success')
            return redirect(url_for('admin_blog'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении статьи: {str(e)}', 'error')
    
    # Get categories for dropdown
    try:
        categories = BlogCategory.query.order_by(BlogCategory.name).all()
    except Exception as e:
        print(f'Error loading categories: {e}')
        categories = []
    
    return render_template('admin/blog_edit.html', 
                         admin=current_admin, 
                         post=post, 
                         categories=categories)

@app.route('/admin/blog/<int:post_id>/delete', methods=['POST'])
@admin_required
def admin_delete_post(post_id):
    """Delete blog post"""
    from models import BlogPost
    
    post = BlogPost.query.get_or_404(post_id)
    
    try:
        db.session.delete(post)
        db.session.commit()
        flash('Статья успешно удалена', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Ошибка при удалении статьи', 'error')
    
    return redirect(url_for('admin_blog'))

# Analytics Routes
@app.route('/admin/analytics/cashback')
@admin_required
def admin_cashback_analytics():
    """Cashback analytics page"""
    from models import Admin, CashbackApplication
    from sqlalchemy import func
    
    admin_id = session.get('admin_id')
    current_admin = Admin.query.get(admin_id)
    
    if not current_admin:
        return redirect(url_for('admin_login'))
    
    # Monthly cashback stats
    monthly_stats = db.session.query(
        func.date_trunc('month', CashbackApplication.created_at).label('month'),
        func.count(CashbackApplication.id).label('count'),
        func.sum(CashbackApplication.cashback_amount).label('total_amount')
    ).group_by(func.date_trunc('month', CashbackApplication.created_at)).order_by('month').all()
    
    # Status breakdown
    status_stats = db.session.query(
        CashbackApplication.status,
        func.count(CashbackApplication.id).label('count'),
        func.sum(CashbackApplication.cashback_amount).label('total_amount')
    ).group_by(CashbackApplication.status).all()
    
    # Recent large cashbacks
    large_cashbacks = CashbackApplication.query.filter(
        CashbackApplication.cashback_amount >= 100000
    ).order_by(CashbackApplication.created_at.desc()).limit(10).all()
    
    return render_template('admin/cashback_analytics.html',
                         admin=current_admin,
                         monthly_stats=monthly_stats,
                         status_stats=status_stats,
                         large_cashbacks=large_cashbacks)

# Admin Blog Management Routes

@app.route('/admin/blog/<int:article_id>/edit', methods=['GET', 'POST'])
@admin_required  
def admin_edit_article(article_id):
    """Edit blog article"""
    from models import Admin, BlogPost
    import re
    
    admin_id = session.get('admin_id')
    current_admin = Admin.query.get(admin_id)
    article = BlogPost.query.get_or_404(article_id)
    
    if request.method == 'POST':
        article.title = request.form.get('title')
        article.slug = request.form.get('slug')
        article.content = request.form.get('content')
        article.excerpt = request.form.get('excerpt')
        article.category = request.form.get('category')
        article.tags = request.form.get('tags')
        article.featured_image = request.form.get('featured_image')
        article.meta_title = request.form.get('meta_title')
        article.meta_description = request.form.get('meta_description')
        article.meta_keywords = request.form.get('meta_keywords')
        action = request.form.get('action', 'save')
        
        # Auto-generate slug if empty
        if not article.slug:
            slug = re.sub(r'[^\w\s-]', '', article.title.lower())
            slug = re.sub(r'[\s_-]+', '-', slug)
            article.slug = slug.strip('-')
        
        # Set status based on action
        if action == 'publish':
            article.status = 'published'
            if not article.published_at:
                article.published_at = datetime.now()
        else:
            article.status = request.form.get('status', 'draft')
        
        # Handle scheduled posts
        if article.status == 'scheduled':
            scheduled_str = request.form.get('scheduled_for')
            if scheduled_str:
                try:
                    article.scheduled_for = datetime.fromisoformat(scheduled_str)
                except:
                    pass
        else:
            article.scheduled_for = None
            
        article.updated_at = datetime.now()
        
        try:
            db.session.commit()
            flash('Статья успешно обновлена', 'success')
            return redirect(url_for('admin_blog'))
        except Exception as e:
            db.session.rollback()
            flash('Ошибка при обновлении статьи', 'error')
    
    return render_template('admin/create_article.html', admin=current_admin, article=article)

@app.route('/admin/blog/<int:article_id>/delete', methods=['POST'])
@admin_required
def admin_delete_article(article_id):
    """Delete blog article"""
    from models import BlogPost
    
    article = BlogPost.query.get_or_404(article_id)
    
    try:
        db.session.delete(article)
        db.session.commit()
        flash('Статья успешно удалена', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Ошибка при удалении статьи', 'error')
    
    return redirect(url_for('admin_blog'))

@app.route('/admin/blog/<int:article_id>/publish', methods=['POST'])
@admin_required
def admin_publish_article(article_id):
    """Publish blog article"""
    from models import BlogPost
    
    article = BlogPost.query.get_or_404(article_id)
    article.status = 'published'
    article.published_at = datetime.now()
    article.updated_at = datetime.now()
    
    try:
        db.session.commit()
        flash('Статья успешно опубликована', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Ошибка при публикации статьи', 'error')
    
    return redirect(url_for('admin_blog'))

# Admin Manager Management Routes  
@app.route('/admin/managers/create', methods=['GET', 'POST'])
@admin_required
def admin_create_manager():
    """Create new manager"""
    from models import Admin, Manager
    from werkzeug.security import generate_password_hash
    import json
    import random
    
    admin_id = session.get('admin_id')
    current_admin = Admin.query.get(admin_id)
    
    if request.method == 'POST':
        full_name = request.form.get('full_name', '')
        email = request.form.get('email')
        phone = request.form.get('phone')
        position = request.form.get('position', 'Менеджер')
        profile_image = request.form.get('profile_image')
        password = request.form.get('password', 'demo123')  # Default password
        password_confirm = request.form.get('password_confirm', 'demo123')
        is_active = request.form.get('is_active') != 'False'  # Default True
        
        # Split full name into first and last name
        name_parts = full_name.split(' ', 1)
        first_name = name_parts[0] if name_parts else 'Имя'
        last_name = name_parts[1] if len(name_parts) > 1 else 'Фамилия'
        
        # Validate passwords
        if password != password_confirm:
            flash('Пароли не совпадают', 'error')
            return render_template('admin/create_manager.html', admin=current_admin)
        
        if not password:
            password = 'demo123'  # Default password
        
        # Check if email already exists
        if email:
            existing_manager = Manager.query.filter_by(email=email).first()
            if existing_manager:
                flash('Менеджер с таким email уже существует', 'error')
                return render_template('admin/create_manager.html', admin=current_admin)
        
        # Create manager
        manager = Manager()
        manager.email = email or f'manager{random.randint(1000,9999)}@inback.ru'
        manager.first_name = first_name
        manager.last_name = last_name
        manager.phone = phone
        manager.position = position
        manager.profile_image = profile_image or 'https://randomuser.me/api/portraits/men/1.jpg'
        manager.set_password(password)
        manager.is_active = is_active
        
        try:
            db.session.add(manager)
            db.session.commit()
            flash('Менеджер успешно создан', 'success')
            return redirect(url_for('admin_managers'))
        except Exception as e:
            db.session.rollback()
            flash('Ошибка при создании менеджера', 'error')
    
    return render_template('admin/create_manager.html', admin=current_admin)

@app.route('/admin/managers/<int:manager_id>/delete', methods=['POST'])
@admin_required
def admin_delete_manager(manager_id):
    """Delete manager"""
    from models import Manager
    
    manager = Manager.query.get_or_404(manager_id)
    
    try:
        db.session.delete(manager)
        db.session.commit()
        flash('Менеджер успешно удален', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Ошибка при удалении менеджера', 'error')
    
    return redirect(url_for('admin_managers'))

@app.route('/admin/managers/<int:manager_id>/toggle-status', methods=['POST'])
@admin_required
def admin_toggle_manager_status(manager_id):
    """Toggle manager active status"""
    from models import Manager
    
    manager = Manager.query.get_or_404(manager_id)
    manager.is_active = not manager.is_active
    
    try:
        db.session.commit()
        status = 'активирован' if manager.is_active else 'заблокирован'
        flash(f'Менеджер {status}', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Ошибка при изменении статуса менеджера', 'error')
    
    return redirect(url_for('admin_managers'))

# Additional Pages Routes
@app.route('/careers')
def careers():
    """Careers page"""
    return render_template('careers.html')

@app.route('/security')
def security():
    """Security page"""
    return render_template('security.html')


if __name__ == '__main__':
    with app.app_context():
        from models import User, CashbackRecord, Application, Favorite, Notification, District, Developer, ResidentialComplex, Street, RoomType, Admin, BlogPost, City
        db.create_all()
        
        # Initialize cities
        try:
            init_cities()
            print("Cities initialized successfully")
        except Exception as e:
            print(f"Error initializing cities: {e}")
            db.session.rollback()
        
        # Initialize search data
        try:
            init_search_data()
            print("Search data initialized successfully")
        except Exception as e:
            print(f"Error initializing search data: {e}")
            db.session.rollback()

# Collection routes for clients
@app.route('/collections')
@login_required
def client_collections():
    """Show all collections assigned to current user"""
    from models import Collection
    collections = Collection.query.filter_by(assigned_to_user_id=current_user.id).order_by(Collection.created_at.desc()).all()
    return render_template('auth/client_collections.html', collections=collections)

@app.route('/collection/<int:collection_id>')
@login_required
def view_collection(collection_id):
    """View specific collection details"""
    from models import Collection
    collection = Collection.query.filter_by(id=collection_id, assigned_to_user_id=current_user.id).first()
    if not collection:
        flash('Подборка не найдена', 'error')
        return redirect(url_for('client_collections'))
    
    # Mark as viewed
    if collection.status == 'Отправлена':
        collection.status = 'Просмотрена'
        collection.viewed_at = datetime.utcnow()
        db.session.commit()
    
    return render_template('auth/view_collection.html', collection=collection)

@app.route('/collection/<int:collection_id>/mark-viewed', methods=['POST'])
@login_required
def mark_collection_viewed(collection_id):
    """Mark collection as viewed"""
    from models import Collection
    collection = Collection.query.filter_by(id=collection_id, assigned_to_user_id=current_user.id).first()
    if collection and collection.status == 'Отправлена':
        collection.status = 'Просмотрена'
        collection.viewed_at = datetime.utcnow()
        db.session.commit()
    return jsonify({'success': True})

# Manager collection routes
@app.route('/manager/collections')
@manager_required
def manager_collections():
    """Manager collections list"""
    from models import Collection, Manager
    manager_id = session.get('manager_id')
    manager = Manager.query.get(manager_id)
    collections = Collection.query.filter_by(created_by_manager_id=manager_id).order_by(Collection.created_at.desc()).all()
    return render_template('manager/collections.html', collections=collections, manager=manager)

@app.route('/manager/collections/new')
@manager_required
def manager_create_collection():
    """Create new collection"""
    from models import Manager, User
    manager_id = session.get('manager_id')
    manager = Manager.query.get(manager_id)
    # Get all clients assigned to this manager
    clients = User.query.filter_by(assigned_manager_id=manager_id).all()
    return render_template('manager/create_collection.html', manager=manager, clients=clients)

@app.route('/manager/collections/new', methods=['POST'])
@manager_required
def save_collection():
    """Save new collection"""
    from models import Collection, CollectionProperty, Manager
    
    manager_id = session.get('manager_id')
    manager = Manager.query.get(manager_id)
    
    title = request.form.get('title')
    description = request.form.get('description', '')
    assigned_to_user_id = request.form.get('assigned_to_user_id')
    tags = request.form.get('tags', '')
    action = request.form.get('action')
    property_ids = request.form.getlist('property_ids[]')
    property_notes = request.form.getlist('property_notes[]')
    
    if not title or not assigned_to_user_id:
        flash('Заполните обязательные поля', 'error')
        return render_template('manager/create_collection.html', manager=manager)
    
    try:
        # Create collection
        collection = Collection(
            title=title,
            description=description,
            created_by_manager_id=manager_id,
            assigned_to_user_id=int(assigned_to_user_id),
            tags=tags,
            status='Отправлена' if action == 'send' else 'Черновик',
            sent_at=datetime.utcnow() if action == 'send' else None
        )
        
        db.session.add(collection)
        db.session.flush()  # Get collection ID
        
        # Add properties to collection
        import json
        with open('data/properties.json', 'r', encoding='utf-8') as f:
            properties_data = json.load(f)
        
        properties_dict = {prop['id']: prop for prop in properties_data}
        
        for i, prop_id in enumerate(property_ids):
            if prop_id in properties_dict:
                prop_data = properties_dict[prop_id]
                note = property_notes[i] if i < len(property_notes) else ''
                
                collection_property = CollectionProperty(
                    collection_id=collection.id,
                    property_id=prop_id,
                    property_name=prop_data['title'],
                    property_price=prop_data['price'],
                    complex_name=prop_data.get('residential_complex', ''),
                    property_type=f"{prop_data['rooms']}-комн",
                    property_size=prop_data.get('area'),
                    manager_note=note,
                    order_index=i
                )
                db.session.add(collection_property)
        
        db.session.commit()
        
        action_text = 'отправлена клиенту' if action == 'send' else 'сохранена как черновик'
        flash(f'Подборка "{title}" успешно {action_text}', 'success')
        return redirect(url_for('manager_collections'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при сохранении подборки: {str(e)}', 'error')
        return render_template('manager/create_collection.html', manager=manager)

@app.route('/manager/analytics')
@manager_required
def manager_analytics():
    """Manager analytics page"""
    from models import Manager, User, Collection, CashbackApplication
    from sqlalchemy import func
    
    manager_id = session.get('manager_id')
    current_manager = Manager.query.get(manager_id)
    
    if not current_manager:
        return redirect(url_for('manager_login'))
    
    # Manager stats
    clients_count = User.query.filter_by(assigned_manager_id=current_manager.id).count()
    collections_count = Collection.query.filter_by(created_by_manager_id=current_manager.id).count()
    sent_collections = Collection.query.filter_by(created_by_manager_id=current_manager.id, status='Отправлена').count()
    
    # Monthly collection stats
    monthly_collections = db.session.query(
        func.date_trunc('month', Collection.created_at).label('month'),
        func.count(Collection.id).label('count')
    ).filter_by(created_by_manager_id=current_manager.id).group_by(
        func.date_trunc('month', Collection.created_at)
    ).order_by('month').all()
    
    # Client activity stats
    client_stats = db.session.query(
        User.client_status,
        func.count(User.id).label('count')
    ).filter_by(assigned_manager_id=current_manager.id).group_by(User.client_status).all()
    
    # Recent activity
    recent_collections = Collection.query.filter_by(
        created_by_manager_id=current_manager.id
    ).order_by(Collection.created_at.desc()).limit(5).all()
    
    return render_template('manager/analytics.html',
                         manager=current_manager,
                         clients_count=clients_count,
                         collections_count=collections_count,
                         sent_collections=sent_collections,
                         monthly_collections=monthly_collections,
                         client_stats=client_stats,
                         recent_collections=recent_collections)

@app.route('/manager/search-properties', methods=['POST'])
@manager_required
def manager_search_properties():
    """Search properties for collection"""
    import json
    
    data = request.get_json()
    min_price = data.get('min_price')
    max_price = data.get('max_price')
    rooms = data.get('rooms')
    
    try:
        with open('data/properties.json', 'r', encoding='utf-8') as f:
            properties_data = json.load(f)
        
        filtered_properties = []
        for prop in properties_data:
            # Apply filters
            if min_price and prop['price'] < int(min_price):
                continue
            if max_price and prop['price'] > int(max_price):
                continue
            if rooms and str(prop['rooms']) != str(rooms):
                continue
                
            filtered_properties.append({
                'id': prop['id'],
                'title': f"{prop.get('rooms', 0)}-комн {prop.get('area', 0)} м²" if prop.get('rooms', 0) > 0 else f"Студия {prop.get('area', 0)} м²",
                'price': prop['price'],
                'complex_name': prop.get('residential_complex', 'ЖК не указан'),
                'rooms': prop['rooms'],
                'size': prop.get('area', 0)
            })
        
        return jsonify({'properties': filtered_properties[:50]})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# Additional API routes for collection management
@app.route('/api/manager/collection/<int:collection_id>/send', methods=['POST'])
@manager_required
def api_send_collection(collection_id):
    """Send collection to client"""
    from models import Collection
    
    manager_id = session.get('manager_id')
    collection = Collection.query.filter_by(id=collection_id, created_by_manager_id=manager_id).first()
    
    if not collection:
        return jsonify({'success': False, 'error': 'Подборка не найдена'}), 404
    
    if not collection.assigned_to_user_id:
        return jsonify({'success': False, 'error': 'Клиент не назначен'}), 400
    
    try:
        collection.status = 'Отправлена'
        collection.sent_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/manager/collection/<int:collection_id>/delete', methods=['DELETE'])
@manager_required 
def api_delete_collection(collection_id):
    """Delete collection"""
    from models import Collection
    
    manager_id = session.get('manager_id')
    collection = Collection.query.filter_by(id=collection_id, created_by_manager_id=manager_id).first()
    
    if not collection:
        return jsonify({'success': False, 'error': 'Подборка не найдена'}), 404
    
    try:
        db.session.delete(collection)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

# Manager Saved Searches API routes
@app.route('/api/manager/saved-searches')
@manager_required
def get_manager_saved_searches():
    """Get manager's saved searches"""
    from models import ManagerSavedSearch
    
    manager_id = session.get('manager_id')
    try:
        searches = ManagerSavedSearch.query.filter_by(manager_id=manager_id).order_by(ManagerSavedSearch.last_used.desc()).all()
        
        return jsonify({
            'success': True,
            'searches': [search.to_dict() for search in searches]
        })
    except Exception as e:
        print(f"Error loading manager saved searches: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/manager/saved-searches', methods=['POST'])
@manager_required
def create_manager_saved_search():
    """Create a new saved search for manager"""
    from models import ManagerSavedSearch
    import json
    
    print(f"DEBUG: ===== create_manager_saved_search API CALLED =====")
    print(f"DEBUG: Method: {request.method}")
    print(f"DEBUG: Path: {request.path}")
    print(f"DEBUG: Headers: {dict(request.headers)}")
    
    manager_id = session.get('manager_id')
    print(f"DEBUG: Manager ID from session: {manager_id}")
    
    data = request.get_json()
    print(f"DEBUG: Raw request JSON: {data}")
    print(f"DEBUG: JSON type: {type(data)}")
    
    try:
        # Extract filters from the request
        filters = data.get('filters', {})
        print(f"DEBUG: Creating manager search with filters: {filters}")
        print(f"DEBUG: Full request data: {data}")
        print(f"DEBUG: Filters type: {type(filters)}")
        print(f"DEBUG: Filters empty check: {bool(filters)}")
        
        # Test if filters is actually empty - force some test data if needed
        if not filters or not any(filters.values()):
            print("DEBUG: Filters are empty, checking raw JSON...")
            raw_json = request.get_data(as_text=True)
            print(f"DEBUG: Raw request body: {raw_json}")
        
        filters_json = json.dumps(filters) if filters else None
        print(f"DEBUG: Filters JSON: {filters_json}")
        
        # Create new search
        search = ManagerSavedSearch(
            manager_id=manager_id,
            name=data.get('name'),
            description=data.get('description'),
            search_type=data.get('search_type', 'properties'),
            additional_filters=filters_json,
            is_template=data.get('is_template', False)
        )
        
        db.session.add(search)
        db.session.commit()
        print(f"DEBUG: Saved search with ID: {search.id}, additional_filters: {search.additional_filters}")
        
        # Verify the saved data
        db.session.refresh(search)
        print(f"DEBUG: Refreshed search additional_filters: {search.additional_filters}")
        
        return jsonify({
            'success': True,
            'search': search.to_dict(),
            'message': 'Поиск успешно сохранён'
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error creating manager saved search: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/manager/send-search', methods=['POST'])
@manager_required
def send_search_to_client():
    """Send manager's saved search to a client"""
    from models import ManagerSavedSearch, SentSearch, User, SavedSearch, UserNotification
    from email_service import send_notification
    import json
    
    manager_id = session.get('manager_id')
    data = request.get_json()
    
    try:
        search_id = data.get('search_id')
        client_id = data.get('client_id')
        message = data.get('message', '')
        
        # Get manager search
        manager_search = ManagerSavedSearch.query.filter_by(id=search_id, manager_id=manager_id).first()
        if not manager_search:
            return jsonify({'success': False, 'error': 'Поиск не найден'}), 404
            
        # Get client
        client = User.query.get(client_id)
        if not client:
            return jsonify({'success': False, 'error': 'Клиент не найден'}), 404
            
        # Create SavedSearch for client (copy manager search to client)
        client_search = SavedSearch(
            user_id=client_id,
            name=f"От менеджера: {manager_search.name}",
            description=f"{manager_search.description or ''}\n\n{message}".strip(),
            search_type=manager_search.search_type,
            additional_filters=manager_search.additional_filters,
            notify_new_matches=True
        )
        
        db.session.add(client_search)
        db.session.flush()  # Get the ID before final commit
        
        # Create sent search record
        sent_search = SentSearch(
            manager_id=manager_id,
            client_id=client_id,
            manager_search_id=search_id,
            name=manager_search.name,
            description=manager_search.description,
            additional_filters=manager_search.additional_filters,
            status='sent'
        )
        
        db.session.add(sent_search)
        db.session.flush()  # Get sent_search ID
        
        # Note: client_search is now created and linked via sent_search record
        
        # Update usage count
        manager_search.usage_count = (manager_search.usage_count or 0) + 1
        manager_search.last_used = datetime.utcnow()
        
        # Create notification for client
        notification = UserNotification(
            user_id=client_id,
            title="Новый поиск от менеджера",
            message=f"Ваш менеджер отправил вам поиск: {manager_search.name}",
            notification_type='info',
            icon='fas fa-search',
            action_url='/dashboard'
        )
        
        db.session.add(notification)
        db.session.commit()
        
        # Send email notification
        try:
            send_notification(
                client.email,
                f"Новый поиск от менеджера: {manager_search.name}",
                f"Ваш менеджер отправил вам новый поиск недвижимости.\n\n"
                f"Название: {manager_search.name}\n"
                f"Описание: {manager_search.description or 'Без описания'}\n\n"
                f"{message}\n\n"
                f"Войдите в личный кабинет для просмотра: https://{request.host}/dashboard",
                user_id=client_id,
                notification_type='search_received'
            )
        except Exception as e:
            print(f"Error sending email notification: {e}")
        
        return jsonify({
            'success': True,
            'message': 'Поиск успешно отправлен клиенту'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error sending search to client: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/manager/saved-search/<int:search_id>', methods=['DELETE'])
@manager_required
def delete_manager_saved_search(search_id):
    """Delete manager's saved search"""
    from models import ManagerSavedSearch
    
    manager_id = session.get('manager_id')
    
    try:
        search = ManagerSavedSearch.query.filter_by(id=search_id, manager_id=manager_id).first()
        if not search:
            return jsonify({'success': False, 'error': 'Поиск не найден'}), 404
            
        db.session.delete(search)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Поиск удалён'})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting manager saved search: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400

# Developer appointment routes
@app.route('/book-appointment', methods=['GET', 'POST'])
@login_required
def book_appointment():
    """Book appointment with developer"""
    if request.method == 'POST':
        from models import DeveloperAppointment
        from datetime import datetime
        
        property_id = request.form.get('property_id')
        developer_name = request.form.get('developer_name')
        complex_name = request.form.get('complex_name')
        appointment_date = request.form.get('appointment_date')
        appointment_time = request.form.get('appointment_time')
        client_name = request.form.get('client_name')
        client_phone = request.form.get('client_phone')
        notes = request.form.get('notes', '')
        
        try:
            appointment = DeveloperAppointment(
                user_id=current_user.id,
                property_id=property_id,
                developer_name=developer_name,
                complex_name=complex_name,
                appointment_date=datetime.strptime(appointment_date, '%Y-%m-%d'),
                appointment_time=appointment_time,
                client_name=client_name,
                client_phone=client_phone,
                notes=notes
            )
            
            db.session.add(appointment)
            db.session.commit()
            
            flash('Запись к застройщику успешно создана! Менеджер свяжется с вами для подтверждения.', 'success')
            return redirect(url_for('dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash('Ошибка при создании записи. Попробуйте еще раз.', 'error')
    
    # Get property data if property_id provided
    property_data = None
    property_id = request.args.get('property_id')
    if property_id:
        properties = load_properties()
        for prop in properties:
            if str(prop.get('id')) == property_id:
                property_data = prop
                break
    
    return render_template('book_appointment.html', property_data=property_data)

@app.route('/api/manager/add-client-old', methods=['POST'])
@manager_required
def add_client():
    """Add new client (old version - deprecated)"""
    from models import User
    from werkzeug.security import generate_password_hash
    import secrets
    
    data = request.get_json()
    first_name = data.get('first_name')
    last_name = data.get('last_name') 
    email = data.get('email')
    phone = data.get('phone')
    
    if not all([first_name, last_name, email]):
        return jsonify({'success': False, 'error': 'Заполните все обязательные поля'}), 400
    
    # Check if user exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({'success': False, 'error': 'Пользователь с таким email уже существует'}), 400
    
    try:
        # Generate user ID and password
        user_id = secrets.token_hex(4).upper()
        password = 'demo123'  # Default password
        password_hash = generate_password_hash(password)
        
        manager_id = session.get('manager_id')
        
        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            password_hash=password_hash,
            user_id=user_id,
            assigned_manager_id=manager_id,
            client_status='Новый'
        )
        
        db.session.add(user)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'full_name': user.full_name,
                'email': user.email,
                'phone': user.phone,
                'user_id': user.user_id,
                'password': password,
                'client_status': user.client_status
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/request-payout', methods=['POST'])
@login_required
def api_request_payout():
    """Request cashback payout"""
    from models import User, CashbackPayout
    from datetime import datetime
    
    try:
        user_id = current_user.id
        
        # Check if user has available cashback
        user = User.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'error': 'Пользователь не найден'})
        
        # For demo purposes, assume available cashback of 125,000
        available_cashback = 125000
        
        if available_cashback <= 0:
            return jsonify({'success': False, 'error': 'Нет доступного кешбека для выплаты'})
        
        # Create payout request
        payout = CashbackPayout(
            user_id=user_id,
            amount=available_cashback,
            status='Запрошена',
            requested_at=datetime.utcnow()
        )
        
        db.session.add(payout)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Запрос на выплату успешно отправлен',
            'amount': available_cashback
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})



# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    db.session.rollback()
    return render_template('errors/500.html', error_details=str(error) if app.debug else None), 500

@app.errorhandler(Exception)
def handle_exception(e):
    """Handle all other exceptions"""
    db.session.rollback()
    if app.debug:
        return render_template('errors/500.html', error_details=str(e)), 500
    else:
        return render_template('errors/500.html'), 500

# City management API endpoints
@app.route('/api/change-city', methods=['POST'])
def change_city():
    """API endpoint to change current city"""
    try:
        data = request.get_json()
        city_slug = data.get('city_slug')
        city_name = data.get('city_name')
        
        if not city_slug or not city_name:
            return jsonify({'success': False, 'message': 'Missing city data'})
        
        # For now, only Krasnodar is available
        if city_slug != 'krasnodar':
            return jsonify({'success': False, 'message': 'City not available yet'})
        
        # Store in session
        session['current_city'] = city_name
        session['current_city_slug'] = city_slug
        
        return jsonify({'success': True, 'message': f'City changed to {city_name}'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': 'Error changing city'})

@app.route('/api/cities')
def get_cities():
    """Get available cities"""
    try:
        from models import City
        cities = City.query.filter_by(is_active=True).all()
        
        cities_data = []
        for city in cities:
            cities_data.append({
                'id': city.id,
                'name': city.name,
                'slug': city.slug,
                'is_default': city.is_default,
                'latitude': city.latitude,
                'longitude': city.longitude,
                'zoom_level': city.zoom_level
            })
            
        return jsonify({'cities': cities_data})
        
    except Exception as e:
        # Fallback data if database not set up yet
        return jsonify({
            'cities': [
                {
                    'id': 1,
                    'name': 'Краснодар',
                    'slug': 'krasnodar',
                    'is_default': True,
                    'latitude': 45.0355,
                    'longitude': 38.9753,
                    'zoom_level': 12
                }
            ]
        })

def init_cities():
    """Initialize default cities in database"""
    try:
        from models import City
        
        # Check if cities already exist
        if City.query.count() == 0:
            cities_data = [
                {
                    'name': 'Краснодар',
                    'slug': 'krasnodar',
                    'is_active': True,
                    'is_default': True,
                    'phone': '+7 (800) 123-45-67',
                    'email': 'krasnodar@inback.ru',
                    'address': 'г. Краснодар, ул. Красная, 32',
                    'latitude': 45.0355,
                    'longitude': 38.9753,
                    'zoom_level': 12,
                    'description': 'Кэшбек за новостройки в Краснодаре',
                    'meta_title': 'Кэшбек за новостройки в Краснодаре | InBack.ru',
                    'meta_description': 'Получите до 10% кэшбека при покупке новостройки в Краснодаре. Проверенные застройщики, юридическое сопровождение.'
                },
                {
                    'name': 'Москва',
                    'slug': 'moscow',
                    'is_active': False,
                    'is_default': False,
                    'phone': '+7 (800) 123-45-67',
                    'email': 'moscow@inback.ru',
                    'address': 'г. Москва, ул. Тверская, 1',
                    'latitude': 55.7558,
                    'longitude': 37.6176,
                    'zoom_level': 11,
                    'description': 'Кэшбек за новостройки в Москве (скоро)',
                    'meta_title': 'Кэшбек за новостройки в Москве | InBack.ru',
                    'meta_description': 'Скоро: кэшбек сервис для покупки новостроек в Москве.'
                },
                {
                    'name': 'Санкт-Петербург',
                    'slug': 'spb',
                    'is_active': False,
                    'is_default': False,
                    'phone': '+7 (800) 123-45-67',
                    'email': 'spb@inback.ru',
                    'address': 'г. Санкт-Петербург, Невский пр., 1',
                    'latitude': 59.9311,
                    'longitude': 30.3609,
                    'zoom_level': 11,
                    'description': 'Кэшбек за новостройки в Санкт-Петербурге (скоро)',
                    'meta_title': 'Кэшбек за новостройки в СПб | InBack.ru',
                    'meta_description': 'Скоро: кэшбек сервис для покупки новостроек в Санкт-Петербурге.'
                },
                {
                    'name': 'Сочи',
                    'slug': 'sochi',
                    'is_active': False,
                    'is_default': False,
                    'phone': '+7 (800) 123-45-67',
                    'email': 'sochi@inback.ru',
                    'address': 'г. Сочи, ул. Курортный пр., 1',
                    'latitude': 43.6028,
                    'longitude': 39.7342,
                    'zoom_level': 12,
                    'description': 'Кэшбек за новостройки в Сочи (скоро)',
                    'meta_title': 'Кэшбек за новостройки в Сочи | InBack.ru',
                    'meta_description': 'Скоро: кэшбек сервис для покупки новостроек в Сочи.'
                }
            ]
            
            for city_data in cities_data:
                city = City(**city_data)
                db.session.add(city)
            
            db.session.commit()
            print("Cities initialized successfully")
            
    except Exception as e:
        print(f"Error initializing cities: {e}")

# Legacy API route removed - using Blueprint version instead

@api_bp.route('/searches', methods=['POST'])
def save_search():
    """Save user search parameters with manager-to-client sharing functionality"""
    from models import SavedSearch, User
    data = request.get_json()
    
    # Check authentication using helper function
    auth_info = check_api_authentication()
    if not auth_info:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401
    
    user_id = auth_info['user_id']
    user_role = auth_info['type']
    current_logged_user = auth_info['user']
    
    try:
        client_email = data.get('client_email')  # For managers
        
        print(f"DEBUG: Saving search with raw data: {data}")
        
        # Create filter object from submitted data
        filters = {}
        
        # Check if filters are nested in 'filters' object
        filter_data = data.get('filters', {}) if 'filters' in data else data
        
        # Extract filters from the data (new format)
        if 'rooms' in filter_data and filter_data['rooms']:
            if isinstance(filter_data['rooms'], list):
                room_list = [r for r in filter_data['rooms'] if r]  # Remove empty strings
                if room_list:
                    filters['rooms'] = room_list
            elif filter_data['rooms']:
                filters['rooms'] = [filter_data['rooms']]
                
        if 'districts' in filter_data and filter_data['districts']:
            if isinstance(filter_data['districts'], list):
                district_list = [d for d in filter_data['districts'] if d]  # Remove empty strings
                if district_list:
                    filters['districts'] = district_list
            elif filter_data['districts']:
                filters['districts'] = [filter_data['districts']]
                
        if 'developers' in filter_data and filter_data['developers']:
            if isinstance(filter_data['developers'], list):
                developer_list = [d for d in filter_data['developers'] if d]  # Remove empty strings
                if developer_list:
                    filters['developers'] = developer_list
            elif filter_data['developers']:
                filters['developers'] = [filter_data['developers']]
                
        if 'completion' in filter_data and filter_data['completion']:
            if isinstance(filter_data['completion'], list):
                completion_list = [c for c in filter_data['completion'] if c]  # Remove empty strings
                if completion_list:
                    filters['completion'] = completion_list
            elif filter_data['completion']:
                filters['completion'] = [filter_data['completion']]
                
        if 'priceFrom' in filter_data and filter_data['priceFrom'] and str(filter_data['priceFrom']) not in ['0', '']:
            filters['priceFrom'] = str(filter_data['priceFrom'])
        if 'priceTo' in filter_data and filter_data['priceTo'] and str(filter_data['priceTo']) not in ['0', '']:
            filters['priceTo'] = str(filter_data['priceTo'])
        if 'areaFrom' in filter_data and filter_data['areaFrom'] and str(filter_data['areaFrom']) not in ['0', '']:
            filters['areaFrom'] = str(filter_data['areaFrom'])
        if 'areaTo' in filter_data and filter_data['areaTo'] and str(filter_data['areaTo']) not in ['0', '']:
            filters['areaTo'] = str(filter_data['areaTo'])
            
        print(f"DEBUG: Extracted filters from {filter_data}: {filters}")

        # Create search with new format
        search = SavedSearch(
            user_id=user_id,
            name=data['name'],
            description=data.get('description'),
            search_type='properties',
            additional_filters=json.dumps(filters),
            notify_new_matches=data.get('notify_new_matches', True)
        )

        # Also save in legacy format for backwards compatibility
        if 'rooms' in data and data['rooms']:
            if isinstance(data['rooms'], list) and len(data['rooms']) > 0:
                search.property_type = data['rooms'][0]  # Use first room type
            else:
                search.property_type = data['rooms']
        if 'priceTo' in data and data['priceTo']:
            try:
                search.price_max = int(float(data['priceTo']) * 1000000)  # Convert millions to rubles
            except (ValueError, TypeError):
                pass
        if 'priceFrom' in data and data['priceFrom']:
            try:
                search.price_min = int(float(data['priceFrom']) * 1000000)  # Convert millions to rubles
            except (ValueError, TypeError):
                pass
        
        db.session.add(search)
        db.session.commit()
        
        # If manager specified client email, send search to client  
        if user_role == 'manager' and client_email:
            try:
                # Check if client exists
                client = User.query.filter_by(email=client_email).first()
                
                # If client exists, also save search to their account
                if client:
                    client_search = SavedSearch(
                        user_id=client.id,
                        name=data['name'] + ' (от менеджера)',
                        description=data.get('description'),
                        search_type='properties',
                        location=data.get('location'),
                        property_type=data.get('property_type'),
                        price_min=data.get('price_min'),
                        price_max=data.get('price_max'),
                        size_min=data.get('size_min'),
                        size_max=data.get('size_max'),
                        developer=data.get('developer'),
                        complex_name=data.get('complex_name'),
                        floor_min=data.get('floor_min'),
                        floor_max=data.get('floor_max'),
                        additional_filters=json.dumps(filters),
                        notify_new_matches=True
                    )
                    db.session.add(client_search)
                    db.session.commit()
                
                # Prepare search URL for client properties page  
                search_params = []
                
                # Convert manager filter format to client filter format
                if data.get('location'):
                    search_params.append(f"district={data['location']}")
                if data.get('developer'):
                    search_params.append(f"developer={data['developer']}")
                if data.get('property_type'):
                    search_params.append(f"rooms={data['property_type']}")
                if data.get('complex_name'):
                    search_params.append(f"complex={data['complex_name']}")
                if data.get('price_min'):
                    search_params.append(f"priceFrom={data['price_min'] / 1000000}")
                if data.get('price_max'):
                    search_params.append(f"priceTo={data['price_max'] / 1000000}")
                if data.get('size_min'):
                    search_params.append(f"areaFrom={data['size_min']}")
                if data.get('size_max'):
                    search_params.append(f"areaTo={data['size_max']}")
                
                search_url = f"{request.url_root}properties"
                if search_params:
                    search_url += "?" + "&".join(search_params)
                
                # Email content for client
                subject = f"Подборка недвижимости: {data['name']}"
                
                # Generate filter description for email
                filter_descriptions = []
                if data.get('property_type'):
                    filter_descriptions.append(f"Тип: {data['property_type']}")
                if data.get('location'):
                    filter_descriptions.append(f"Район: {data['location']}")
                if data.get('developer'):
                    filter_descriptions.append(f"Застройщик: {data['developer']}")
                if data.get('price_min') or data.get('price_max'):
                    price_min = f"{(data.get('price_min', 0) / 1000000):.1f}" if data.get('price_min') else "0"
                    price_max = f"{(data.get('price_max', 0) / 1000000):.1f}" if data.get('price_max') else "∞"
                    filter_descriptions.append(f"Цена: {price_min}-{price_max} млн ₽")
                if data.get('size_min') or data.get('size_max'):
                    area_min = str(data.get('size_min', 0)) if data.get('size_min') else "0"
                    area_max = str(data.get('size_max', 0)) if data.get('size_max') else "∞"
                    filter_descriptions.append(f"Площадь: {area_min}-{area_max} м²")
                
                filter_text = "<br>".join([f"• {desc}" for desc in filter_descriptions])
                
                html_content = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #0088CC;">Подборка недвижимости от InBack</h2>
                    
                    <p>Здравствуйте!</p>
                    
                    <p>Менеджер <strong>{current_user.full_name or current_user.username}</strong> подготовил для вас персональную подборку недвижимости.</p>
                    
                    <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="margin: 0 0 15px 0; color: #333;">Параметры поиска: {data['name']}</h3>
                        <div style="color: #666; line-height: 1.6;">
                            {filter_text}
                        </div>
                    </div>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{search_url}" style="display: inline-block; background: #0088CC; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; font-weight: bold;">
                            Посмотреть подборку
                        </a>
                    </div>
                    
                    <p style="color: #666; font-size: 14px;">
                        Если у вас есть вопросы, свяжитесь с вашим менеджером:<br>
                        <strong>{current_logged_user.full_name if hasattr(current_logged_user, 'full_name') else current_logged_user.email}</strong><br>
                        Email: {current_logged_user.email}
                    </p>
                    
                    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                    <p style="color: #999; font-size: 12px; text-align: center;">
                        InBack - ваш надежный партнер в поиске недвижимости
                    </p>
                </div>
                """
                
                # Send email using existing email service
                from email_service import send_email
                email_sent = send_email(
                    to_email=client_email,
                    subject=subject,
                    html_content=html_content,
                    template_name='collection'
                )
                
                if email_sent:
                    return jsonify({
                        'success': True, 
                        'search_id': search.id, 
                        'search': search.to_dict(),
                        'message': f'Поиск сохранен и отправлен клиенту на {client_email}',
                        'email_sent': True
                    })
                else:
                    return jsonify({
                        'success': True, 
                        'search_id': search.id, 
                        'search': search.to_dict(),
                        'message': 'Поиск сохранен, но не удалось отправить email клиенту',
                        'email_sent': False
                    })
                    
            except Exception as email_error:
                # Still return success for saved search even if email fails
                print(f"Email sending error: {email_error}")
                return jsonify({
                    'success': True, 
                    'search_id': search.id, 
                    'search': search.to_dict(),
                    'message': 'Поиск сохранен, но произошла ошибка при отправке email',
                    'email_sent': False,
                    'email_error': str(email_error)
                })
        
        return jsonify({'success': True, 'search_id': search.id, 'search': search.to_dict()})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

def check_api_authentication():
    """Helper function to check API authentication for both users and managers"""
    # Check if manager is logged in
    if 'manager_id' in session:
        from models import Manager
        manager = Manager.query.get(session['manager_id'])
        if manager:
            return {'type': 'manager', 'user_id': manager.id, 'user': manager}
    
    # Check if regular user is logged in  
    if current_user and hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
        return {'type': 'user', 'user_id': current_user.id, 'user': current_user}
    
    # Also check session for user_id (alternative authentication method)
    if 'user_id' in session:
        from models import User
        user = User.query.get(session['user_id'])
        if user:
            return {'type': 'user', 'user_id': user.id, 'user': user}
    
    return None

@app.route('/api/searches', methods=['GET'])
def get_saved_searches():
    """Get user's saved searches"""
    from models import SavedSearch
    
    # Check authentication using helper function
    auth_info = check_api_authentication()
    if not auth_info:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401
    
    # Get saved searches for the authenticated user (manager or regular user) 
    searches = SavedSearch.query.filter_by(user_id=auth_info['user_id']).order_by(SavedSearch.created_at.desc()).all()
    
    return jsonify({
        'success': True,
        'searches': [search.to_dict() for search in searches]
    })

@app.route('/api/user/saved-searches/count')
@login_required
def get_user_saved_searches_count():
    """Get count of user's saved searches"""
    from models import SavedSearch
    
    try:
        count = SavedSearch.query.filter_by(user_id=current_user.id).count()
        return jsonify({
            'success': True,
            'count': count
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/saved-searches/<int:search_id>')
@login_required 
def get_saved_search(search_id):
    """Get saved search by ID - supports both user searches and manager shared searches"""
    try:
        from models import SavedSearch, SentSearch
        
        # First try user's own saved search
        search = SavedSearch.query.filter_by(id=search_id, user_id=current_user.id).first()
        
        # If not found, try manager shared search via SentSearch table
        if not search:
            sent_search = SentSearch.query.filter_by(
                client_id=current_user.id
            ).join(SavedSearch, SentSearch.manager_search_id == SavedSearch.id).filter(
                SavedSearch.id == search_id
            ).first()
            
            if sent_search:
                search = SavedSearch.query.get(search_id)
                # Use the additional_filters from sent_search if available
                if sent_search.additional_filters:
                    search._temp_filters = sent_search.additional_filters
        
        # If still not found, check if it's a global search available to all users
        if not search:
            search = SavedSearch.query.get(search_id)
            if search and not search.user_id:  # Global searches have no user_id
                pass  # Allow access
            else:
                search = None
        
        if not search:
            return jsonify({'success': False, 'error': 'Поиск не найден'})
        
        # Parse filters - check for temp filters from sent search first
        filters = {}
        if hasattr(search, '_temp_filters') and search._temp_filters:
            try:
                filters = json.loads(search._temp_filters)
            except:
                filters = {}
        elif search.additional_filters:
            try:
                filters = json.loads(search.additional_filters)
            except:
                filters = {}
        
        return jsonify({
            'success': True,
            'id': search.id,
            'name': search.name,
            'description': search.description,
            'search_filters': filters,
            'created_at': search.created_at.isoformat() if search.created_at else None
        })
        
    except Exception as e:
        print(f"Error getting saved search: {e}")
        return jsonify({'success': False, 'error': 'Ошибка сервера'})

@app.route('/api/searches/<int:search_id>', methods=['DELETE'])
def delete_saved_search(search_id):
    """Delete saved search"""
    from models import SavedSearch
    
    # Check authentication using helper function
    auth_info = check_api_authentication()
    if not auth_info:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401
    
    user_id = auth_info['user_id']
    
    search = SavedSearch.query.filter_by(id=search_id, user_id=user_id).first()
    
    if not search:
        return jsonify({'success': False, 'error': 'Поиск не найден'}), 404
    
    try:
        db.session.delete(search)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/searches/<int:search_id>/apply', methods=['POST'])
def apply_saved_search(search_id):
    """Apply saved search and update last_used"""
    from models import SavedSearch
    from datetime import datetime
    
    # Check authentication using helper function
    auth_info = check_api_authentication()
    if not auth_info:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401
    
    user_id = auth_info['user_id']
    
    search = SavedSearch.query.filter_by(id=search_id, user_id=user_id).first()
    
    if not search:
        return jsonify({'success': False, 'error': 'Поиск не найден'}), 404
    
    try:
        search.last_used = datetime.utcnow()
        db.session.commit()
        
        # Parse filters from saved search
        filters = {}
        if search.additional_filters:
            try:
                filters = json.loads(search.additional_filters)
                print(f"DEBUG: Loaded filters from additional_filters: {filters}")
            except json.JSONDecodeError as e:
                print(f"DEBUG: Error parsing additional_filters: {e}")
                pass
        
        # Include legacy fields as filters if not already in additional_filters
        if search.location and 'districts' not in filters:
            filters['districts'] = [search.location]
        if search.property_type and 'rooms' not in filters:
            # Keep the original property type format for proper filtering
            filters['rooms'] = [search.property_type]
        if search.developer and 'developers' not in filters:
            filters['developers'] = [search.developer]
        if search.price_min and 'priceFrom' not in filters:
            # Convert rubles to millions for client
            filters['priceFrom'] = str(search.price_min / 1000000)
        if search.price_max and 'priceTo' not in filters:
            # Convert rubles to millions for client
            filters['priceTo'] = str(search.price_max / 1000000)
        if search.size_min and 'areaFrom' not in filters:
            filters['areaFrom'] = str(search.size_min)
        if search.size_max and 'areaTo' not in filters:
            filters['areaTo'] = str(search.size_max)
        
        print(f"DEBUG: Search '{search.name}' raw data - additional_filters: {search.additional_filters}, price_min: {search.price_min}, price_max: {search.price_max}")
        print(f"DEBUG: Final filters for '{search.name}': {filters}")
            
        print(f"DEBUG: Applying search '{search.name}' with filters: {filters}")
        
        try:
            search_dict = search.to_dict()
        except Exception as e:
            print(f"DEBUG: Error in search.to_dict(): {e}")
            search_dict = {
                'id': search.id,
                'name': search.name,
                'description': search.description,
                'created_at': search.created_at.isoformat() if search.created_at else None
            }
        
        return jsonify({
            'success': True, 
            'search': search_dict,
            'filters': filters
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/manager/send-property', methods=['POST'])
@login_required
def send_property_to_client_endpoint():
    """Send property search to client"""
    if current_user.role != 'manager':
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    
    try:
        data = request.get_json()
        client_id = data.get('client_id')
        search_id = data.get('search_id')
        message = data.get('message', '')
        
        if not client_id or not search_id:
            return jsonify({'success': False, 'error': 'Client ID and Search ID are required'}), 400
        
        # Verify client exists and is a buyer
        client = User.query.filter_by(id=client_id, role='buyer').first()
        if not client:
            return jsonify({'success': False, 'error': 'Client not found'}), 404
        
        # Verify search exists and belongs to manager
        search = SavedSearch.query.filter_by(id=search_id, user_id=current_user.id).first()
        if not search:
            return jsonify({'success': False, 'error': 'Search not found'}), 404
        
        # Create recommendation record
        from models import ClientPropertyRecommendation
        recommendation = ClientPropertyRecommendation(
            manager_id=current_user.id,
            client_id=client_id,
            search_id=search_id,
            message=message
        )
        
        db.session.add(recommendation)
        db.session.commit()
        
        # Send notification to client (email)
        try:
            subject = f"Подборка квартир от {current_user.full_name}"
            text_message = f"""
Здравствуйте, {client.full_name}!

Ваш менеджер {current_user.full_name} подготовил для вас подборку квартир: {search.name}

{message if message else ''}

Перейдите в личный кабинет на сайте InBack.ru, чтобы посмотреть подборку.

С уважением,
Команда InBack.ru
            """
            
            from email_service import send_email
            send_email(
                to_email=client.email,
                subject=subject,
                text_content=text_message.strip(),
                template_name='recommendation'
            )
        except Exception as e:
            app.logger.warning(f"Failed to send email notification: {str(e)}")
        
        return jsonify({
            'success': True,
            'message': 'Property recommendation sent successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

# Property API routes for manager search
@app.route('/api/search/properties')
def search_properties_api():
    """Search properties for manager collection creation"""
    try:
        district = request.args.get('district')
        developer = request.args.get('developer') 
        rooms = request.args.get('rooms')
        prop_type = request.args.get('type')
        price_min = request.args.get('price_min')
        price_max = request.args.get('price_max')
        area_min = request.args.get('area_min')
        
        # Load properties from JSON file
        with open('data/properties_expanded.json', 'r', encoding='utf-8') as f:
            properties_data = json.load(f)
        
        filtered_properties = []
        for prop in properties_data:
            # Apply filters
            if district and prop.get('district', '').lower() != district.lower():
                continue
            if developer and prop.get('developer', '').lower() != developer.lower():
                continue
            if rooms and str(prop.get('rooms', '')) != str(rooms):
                continue
            if prop_type and prop.get('type', '').lower() != prop_type.lower():
                continue
            
            # Price filters
            prop_price = prop.get('price', 0)
            if price_min and prop_price < int(price_min):
                continue
            if price_max and prop_price > int(price_max):
                continue
            
            # Area filter
            prop_area = prop.get('area', 0)
            if area_min and prop_area < float(area_min):
                continue
            
            # Calculate cashback
            price = prop.get('price', 0)
            cashback = int(price * 0.05)  # 5% cashback
            
            filtered_properties.append({
                'id': prop.get('id'),
                'complex_name': prop.get('complex_name', ''),
                'district': prop.get('district', ''),
                'developer': prop.get('developer', ''),
                'rooms': prop.get('rooms', 0),
                'price': price,
                'cashback': cashback,
                'area': prop.get('area', 0),
                'floor': prop.get('floor', ''),
                'type': prop.get('type', '')
            })
        
        # Limit results to 20
        filtered_properties = filtered_properties[:20]
        
        return jsonify({
            'success': True,
            'properties': filtered_properties
        })
    except Exception as e:
        print(f"Error searching properties: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/search/apartments')
def search_apartments_api():
    """Search apartments with full filtering like main properties page"""
    try:
        district = request.args.get('district')
        developer = request.args.get('developer') 
        rooms = request.args.get('rooms')
        complex_id = request.args.get('complex')
        price_min = request.args.get('price_min')
        price_max = request.args.get('price_max')
        area_min = request.args.get('area_min')
        area_max = request.args.get('area_max')
        floor_min = request.args.get('floor_min')
        floor_max = request.args.get('floor_max')
        status = request.args.get('status')
        finishing = request.args.get('finishing')
        
        # Load properties and complexes
        with open('data/properties_expanded.json', 'r', encoding='utf-8') as f:
            properties_data = json.load(f)
        
        # Load complexes data for additional info
        complexes_data = {}
        try:
            with open('data/residential_complexes.json', 'r', encoding='utf-8') as f:
                complexes_list = json.load(f)
                for complex_item in complexes_list:
                    complexes_data[complex_item.get('id')] = complex_item
        except:
            pass
        
        filtered_apartments = []
        for prop in properties_data:
            # Apply filters
            if district and prop.get('district', '').lower() != district.lower():
                continue
            if developer and prop.get('developer', '').lower() != developer.lower():
                continue
            
            # Handle rooms filter including 'студия'
            prop_rooms = prop.get('rooms', '')
            if rooms:
                if rooms == 'студия' and prop.get('type', '') != 'студия':
                    continue
                elif rooms != 'студия' and str(prop_rooms) != str(rooms):
                    continue
                    
            if complex_id and str(prop.get('complex_id', '')) != str(complex_id):
                continue
            
            # Price filters
            prop_price = prop.get('price', 0)
            if price_min and prop_price < int(price_min):
                continue
            if price_max and prop_price > int(price_max):
                continue
            
            # Area filter
            prop_area = prop.get('area', 0)
            if area_min and prop_area < float(area_min):
                continue
            if area_max and prop_area > float(area_max):
                continue
            
            # Floor filters - use correct field name
            prop_floor = prop.get('floor', 0)
            if isinstance(prop_floor, str):
                try:
                    prop_floor = int(prop_floor.split('/')[0]) if '/' in prop_floor else int(prop_floor)
                except:
                    prop_floor = 0
            
            if floor_min and prop_floor < int(floor_min):
                continue
            if floor_max and prop_floor > int(floor_max):
                continue
            
            # Status and finishing filters
            prop_status = prop.get('completion_date', '').lower()
            if status:
                if status == 'в продаже' and 'сдан' in prop_status:
                    continue
                elif status == 'строительство' and 'кв.' not in prop_status:
                    continue
                elif status == 'сдан' and 'сдан' not in prop_status:
                    continue
                    
            prop_finishing = prop.get('finish_type', '').lower()
            if finishing:
                if finishing == 'черновая' and 'черновая' not in prop_finishing:
                    continue
                elif finishing == 'чистовая' and 'стандартная' not in prop_finishing:
                    continue
                elif finishing == 'под ключ' and 'премиум' not in prop_finishing:
                    continue
            
            # Calculate cashback
            price = prop.get('price', 0)
            cashback = int(price * 0.05)  # 5% cashback
            
            # Get complex info
            complex_info = complexes_data.get(prop.get('complex_id'), {})
            
            filtered_apartments.append({
                'id': prop.get('id'),
                'complex_name': prop.get('complex_name', ''),
                'complex_id': prop.get('complex_id'),
                'district': prop.get('district', ''),
                'developer': prop.get('developer', ''),
                'rooms': prop.get('type', '') if prop.get('type', '') == 'студия' else prop.get('rooms', 0),
                'price': price,
                'cashback': cashback,
                'area': prop.get('area', 0),
                'floor': prop.get('floor', ''),
                'max_floor': prop.get('total_floors', ''),
                'type': prop.get('type', ''),
                'status': 'сдан' if 'сдан' in prop.get('completion_date', '').lower() else 'строительство',
                'finishing': prop.get('finish_type', ''),
                'images': prop.get('gallery', []) or [prop.get('image', '')] if prop.get('image') else complex_info.get('images', []),
                'description': prop.get('description', ''),
                'features': prop.get('advantages', [])
            })
        
        # Sort by price (default)
        filtered_apartments.sort(key=lambda x: x['price'])
        
        # Limit results to 50
        filtered_apartments = filtered_apartments[:50]
        
        return jsonify({
            'success': True,
            'apartments': filtered_apartments,
            'complexes': complexes_data
        })
    except Exception as e:
        print(f"Error searching apartments: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/complexes')
def get_complexes_api():
    """Get list of residential complexes for filter"""
    try:
        with open('data/residential_complexes.json', 'r', encoding='utf-8') as f:
            complexes_data = json.load(f)
        
        complexes_list = [
            {'id': complex_item.get('id'), 'name': complex_item.get('name', '')}
            for complex_item in complexes_data
        ]
        
        return jsonify({
            'success': True,
            'complexes': complexes_list
        })
    except Exception as e:
        print(f"Error loading complexes: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/properties/<property_id>')
def get_property_details(property_id):
    """Get detailed property information"""
    try:
        with open('data/properties_expanded.json', 'r', encoding='utf-8') as f:
            properties_data = json.load(f)
        
        property_data = None
        for prop in properties_data:
            if str(prop.get('id')) == str(property_id):
                property_data = prop
                break
        
        if not property_data:
            return jsonify({'success': False, 'error': 'Property not found'}), 404
        
        # Calculate cashback
        price = property_data.get('price', 0)
        cashback = int(price * 0.05)
        
        property_info = {
            'id': property_data.get('id'),
            'complex_name': property_data.get('complex_name', ''),
            'district': property_data.get('district', ''),
            'developer': property_data.get('developer', ''),
            'rooms': property_data.get('rooms', 0),
            'price': price,
            'cashback': cashback,
            'area': property_data.get('area', 0),
            'floor': property_data.get('floor', ''),
            'type': property_data.get('type', ''),
            'description': property_data.get('description', ''),
            'features': property_data.get('features', [])
        }
        
        return jsonify({
            'success': True,
            'property': property_info
        })
    except Exception as e:
        print(f"Error getting property details: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/manager/collections', methods=['POST'])  
def create_collection_api():
    """Create a new property collection"""
    try:
        # Check manager authentication via session
        manager_id = session.get('manager_id')
        if not manager_id:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
            
        from models import Collection, CollectionProperty
        
        data = request.get_json()
        name = data.get('name')
        client_id = data.get('client_id')
        property_ids = data.get('property_ids', [])
        
        if not name or not client_id or not property_ids:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        # Create collection
        collection = Collection(
            title=name,
            assigned_to_user_id=client_id,
            created_by_manager_id=manager_id,
            status='Создана',
            description=f'Подборка из {len(property_ids)} объектов'
        )
        
        db.session.add(collection)
        db.session.flush()  # Get collection ID
        
        # Add properties to collection
        for prop_id in property_ids:
            collection_property = CollectionProperty(
                collection_id=collection.id,
                property_id=str(prop_id)
            )
            db.session.add(collection_property)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'collection_id': collection.id,
            'message': 'Подборка успешно создана'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error creating collection: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/manager/send-collection', methods=['POST'])  
def send_collection_to_client():
    """Send property collection to client via email"""
    try:
        # Check manager authentication via session
        manager_id = session.get('manager_id')
        if not manager_id:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
            
        from models import User, Manager
        
        data = request.get_json()
        name = data.get('name')
        client_id = data.get('client_id')
        property_ids = data.get('property_ids', [])
        
        if not name or not client_id or not property_ids:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        # Get client and manager info
        client = User.query.get(client_id)
        manager = Manager.query.get(manager_id)
        
        if not client or not manager:
            return jsonify({'success': False, 'error': 'Client or manager not found'}), 404
        
        # Load property details
        with open('data/properties_expanded.json', 'r', encoding='utf-8') as f:
            properties_data = json.load(f)
        
        selected_properties = []
        total_cashback = 0
        
        for prop_id in property_ids:
            for prop in properties_data:
                if str(prop.get('id')) == str(prop_id):
                    price = prop.get('price', 0)
                    cashback = int(price * 0.05)
                    total_cashback += cashback
                    
                    selected_properties.append({
                        'complex_name': prop.get('complex_name', ''),
                        'district': prop.get('district', ''),
                        'developer': prop.get('developer', ''),
                        'rooms': prop.get('rooms', 0),
                        'area': prop.get('area', 0),
                        'price': price,
                        'cashback': cashback,
                        'type': prop.get('type', ''),
                        'description': prop.get('description', '')
                    })
                    break
        
        # Create email content
        properties_list = '\n'.join([
            f"• {prop['complex_name']} ({prop['district']})\n"
            f"  {prop['rooms']}-комн., {prop['area']} м²\n"
            f"  Цена: {prop['price']:,} ₽\n"
            f"  Кешбек: {prop['cashback']:,} ₽\n"
            for prop in selected_properties
        ])
        
        subject = f"Подборка недвижимости: {name}"
        text_message = f"""
Здравствуйте, {client.full_name}!

Ваш менеджер {manager.full_name} подготовил для вас персональную подборку недвижимости "{name}".

ПОДОБРАННЫЕ ОБЪЕКТЫ ({len(selected_properties)} шт.):

{properties_list}

ОБЩИЙ КЕШБЕК: {total_cashback:,} ₽

Для получения подробной информации и записи на просмотр свяжитесь с вашим менеджером:
{manager.full_name}
Email: {manager.email}
Телефон: {manager.phone or 'не указан'}

Или перейдите в личный кабинет на сайте InBack.ru

С уважением,
Команда InBack.ru
        """.strip()
        
        # Send email
        try:
            from email_service import send_email
            send_email(
                to_email=client.email,
                subject=subject,
                text_content=text_message,
                template_name='collection'
            )
            
            return jsonify({
                'success': True,
                'message': f'Подборка отправлена на email {client.email}'
            })
            
        except Exception as e:
            print(f"Error sending email: {e}")
            return jsonify({'success': False, 'error': 'Ошибка отправки email'}), 500
        
    except Exception as e:
        print(f"Error sending collection: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/data/properties_expanded.json')
def properties_json():
    """Serve properties JSON data"""
    try:
        properties = load_properties()
        return jsonify(properties)
    except Exception as e:
        print(f"Error serving properties JSON: {e}")
        return jsonify([]), 500

# Database initialization will be done after all imports

# Client Recommendations API endpoints
@app.route('/api/user/collections', methods=['GET'])
@login_required
def api_user_get_collections():
    """Get collections assigned to current user"""
    from models import Collection
    
    try:
        collections = Collection.query.filter_by(
            assigned_to_user_id=current_user.id
        ).order_by(Collection.created_at.desc()).all()
        
        collections_data = []
        for collection in collections:
            collections_data.append({
                'id': collection.id,
                'title': collection.title,
                'description': collection.description,
                'status': collection.status,
                'created_at': collection.created_at.strftime('%d.%m.%Y'),
                'manager_name': collection.created_by_manager.full_name if collection.created_by_manager else 'Менеджер',
                'properties_count': len(collection.property_collections) if hasattr(collection, 'property_collections') else 0
            })
        
        return jsonify({
            'success': True,
            'collections': collections_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/user/saved-searches', methods=['GET'])
@login_required
def api_user_get_saved_searches():
    """Get saved searches for current user"""
    from models import SavedSearch
    
    try:
        # Get regular saved searches
        saved_searches = SavedSearch.query.filter_by(
            user_id=current_user.id
        ).order_by(SavedSearch.created_at.desc()).all()
        
        # Get sent searches from managers
        from models import SentSearch
        sent_searches = SentSearch.query.filter_by(
            client_id=current_user.id
        ).order_by(SentSearch.sent_at.desc()).all()
        
        searches_data = []
        
        # Add regular saved searches
        for search in saved_searches:
            filters = {}
            if search.filters:
                import json
                filters = json.loads(search.filters) if isinstance(search.filters, str) else search.filters
            
            searches_data.append({
                'id': search.id,
                'name': search.name,
                'filters': filters,
                'created_at': search.created_at.strftime('%d.%m.%Y'),
                'last_used': search.last_used.strftime('%d.%m.%Y') if search.last_used else None,
                'type': 'saved'
            })
        
        # Add sent searches from managers
        for search in sent_searches:
            filters = {}
            if search.additional_filters:
                import json
                filters = json.loads(search.additional_filters) if isinstance(search.additional_filters, str) else search.additional_filters
            
            searches_data.append({
                'id': search.id,
                'name': search.name,
                'filters': filters,
                'created_at': search.sent_at.strftime('%d.%m.%Y') if search.sent_at else 'Не указано',
                'last_used': search.applied_at.strftime('%d.%m.%Y') if search.applied_at else None,
                'type': 'sent',
                'from_manager': True
            })
        
        return jsonify({
            'success': True,
            'searches': searches_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/user/recommendations', methods=['GET'])
@login_required
def api_user_get_recommendations():
    """Get recommendations for current user"""
    from models import Recommendation, SentSearch
    from datetime import datetime
    
    try:
        print(f"DEBUG: Loading recommendations for user ID: {current_user.id}")
        
        # Get traditional recommendations
        recommendations = Recommendation.query.filter_by(
            client_id=current_user.id
        ).order_by(Recommendation.sent_at.desc()).all()
        
        print(f"DEBUG: Found {len(recommendations)} recommendations for user {current_user.id}")
        
        recommendations_data = []
        for rec in recommendations:
            rec_data = rec.to_dict()
            rec_data['manager_name'] = f"{rec.manager.first_name} {rec.manager.last_name}" if rec.manager else 'Менеджер'
            recommendations_data.append(rec_data)
        
        # Get sent searches from managers as recommendations  
        sent_searches = SentSearch.query.filter_by(client_id=current_user.id).order_by(SentSearch.sent_at.desc()).all()
        
        # Convert sent searches to recommendation format
        for search in sent_searches:
            search_rec = {
                'id': f'search_{search.id}',
                'title': f'Подбор недвижимости: {search.name}',
                'description': search.description or 'Персональный подбор от вашего менеджера',
                'recommendation_type': 'search',
                'item_id': str(search.id),
                'item_name': search.name,
                'manager_notes': f'Ваш менеджер {search.manager.name} подготовил персональный подбор недвижимости',
                'priority_level': 'high',
                'status': search.status,
                'viewed_at': search.viewed_at.isoformat() if search.viewed_at else None,
                'created_at': search.sent_at.isoformat() if search.sent_at else None,
                'sent_at': search.sent_at.isoformat() if search.sent_at else None,
                'manager_name': search.manager.name,
                'search_filters': search.additional_filters,
                'search_id': search.id
            }
            recommendations_data.append(search_rec)
        
        # Sort by creation date 
        recommendations_data.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        return jsonify({
            'success': True, 
            'recommendations': recommendations_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/saved-searches/<int:search_id>')
@login_required
def get_saved_search_details(search_id):
    """Get saved search details for applying filters"""
    from models import SavedSearch
    
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'User not authenticated'}), 401
        
        # Get the saved search
        saved_search = SavedSearch.query.filter_by(id=search_id, user_id=user_id).first()
        if not saved_search:
            return jsonify({'success': False, 'error': 'Поиск не найден'}), 404
        
        return jsonify({
            'success': True,
            'id': saved_search.id,
            'name': saved_search.name,
            'description': saved_search.description,
            'search_filters': saved_search.additional_filters,
            'created_at': saved_search.created_at.isoformat() if saved_search.created_at else None
        })
        
    except Exception as e:
        print(f"Error getting saved search details: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/sent-searches')
@login_required
def get_sent_searches():
    """Get sent searches from managers as recommendations"""
    from models import SentSearch
    
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'User not authenticated'}), 401
        
        # Get sent searches
        sent_searches = SentSearch.query.filter_by(client_id=user_id).order_by(SentSearch.sent_at.desc()).all()
        
        # Format as recommendation-like objects
        search_list = []
        
        for search in sent_searches:
            search_list.append({
                'id': search.id,
                'name': search.name or 'Поиск от менеджера',
                'title': search.name or 'Поиск от менеджера',
                'description': search.description,
                'status': search.status or 'sent',
                'sent_at': search.sent_at.isoformat() if search.sent_at else None,
                'created_at': search.sent_at.isoformat() if search.sent_at else None,
                'search_filters': search.additional_filters,
                'manager_id': search.manager_id,
                'recommendation_type': 'search'
            })
        
        return jsonify({
            'success': True,
            'sent_searches': search_list
        })
        
    except Exception as e:
        print(f"Error getting sent searches: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/recommendations/<rec_id>/viewed', methods=['POST'])
@login_required  
def api_mark_recommendation_viewed(rec_id):
    """Mark recommendation as viewed"""
    from models import Recommendation, SentSearch
    from datetime import datetime
    
    try:
        # Handle search recommendations
        if str(rec_id).startswith('search_'):
            search_id = int(rec_id.replace('search_', ''))
            sent_search = SentSearch.query.filter_by(
                id=search_id, 
                client_id=current_user.id
            ).first()
            
            if not sent_search:
                return jsonify({'success': False, 'error': 'Поиск не найден'}), 404
                
            if sent_search.status == 'sent':
                sent_search.status = 'viewed'
                sent_search.viewed_at = datetime.utcnow()
                db.session.commit()
            
            return jsonify({'success': True})
        
        # Handle traditional recommendations
        recommendation = Recommendation.query.filter_by(
            id=int(rec_id), 
            client_id=current_user.id
        ).first()
        
        if not recommendation:
            return jsonify({'success': False, 'error': 'Рекомендация не найдена'}), 404
            
        if recommendation.status == 'sent':
            recommendation.status = 'viewed'
            recommendation.viewed_at = datetime.utcnow()
            db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/recommendations/<int:rec_id>/dismiss', methods=['POST'])
@login_required
def api_dismiss_recommendation(rec_id):
    """Dismiss/hide recommendation"""
    from models import Recommendation
    from datetime import datetime
    
    try:
        recommendation = Recommendation.query.filter_by(
            id=rec_id, 
            client_id=current_user.id
        ).first()
        
        if not recommendation:
            return jsonify({'success': False, 'error': 'Рекомендация не найдена'}), 404
            
        # Mark as dismissed
        recommendation.status = 'dismissed'
        recommendation.viewed_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/recommendations/<rec_id>/apply', methods=['POST'])
@login_required  
def api_apply_search_recommendation(rec_id):
    """Apply search recommendation - redirect to properties with filters"""
    from models import SentSearch
    from datetime import datetime
    import json
    
    try:
        # Handle search recommendations only
        if not str(rec_id).startswith('search_'):
            return jsonify({'success': False, 'error': 'Только поиски можно применить'}), 400
            
        search_id = int(rec_id.replace('search_', ''))
        sent_search = SentSearch.query.filter_by(
            id=search_id, 
            client_id=current_user.id
        ).first()
        
        if not sent_search:
            return jsonify({'success': False, 'error': 'Поиск не найден'}), 404
        
        # Update search status
        sent_search.applied_at = datetime.utcnow()
        if sent_search.status == 'sent':
            sent_search.status = 'applied'
        db.session.commit()
        
        # Parse filters from the search
        filters = {}
        if sent_search.additional_filters:
            try:
                filters = json.loads(sent_search.additional_filters)
            except json.JSONDecodeError:
                pass
        
        return jsonify({
            'success': True, 
            'filters': filters
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/user/recommendation-categories', methods=['GET'])
@login_required
def api_user_get_categories():
    """Get all categories that have recommendations for current user"""
    from models import RecommendationCategory
    
    try:
        categories = RecommendationCategory.query.filter_by(
            client_id=current_user.id
        ).filter(RecommendationCategory.recommendations_count > 0).all()
        
        categories_data = []
        for category in categories:
            categories_data.append({
                'id': category.id,
                'name': category.name,
                'description': category.description,
                'color': category.color,
                'recommendations_count': category.recommendations_count
            })
        
        return jsonify({
            'success': True,
            'categories': categories_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/recommendations/<int:rec_id>/respond', methods=['POST'])
@login_required
def api_respond_to_recommendation(rec_id):
    """Client responds to recommendation with interest/not interested"""
    from models import Recommendation
    from datetime import datetime
    
    try:
        data = request.get_json()
        response_type = data.get('response')  # 'interested' or 'not_interested'
        
        if response_type not in ['interested', 'not_interested']:
            return jsonify({'success': False, 'error': 'Неверный тип ответа'}), 400
            
        recommendation = Recommendation.query.filter_by(
            id=rec_id,
            client_id=current_user.id
        ).first()
        
        if not recommendation:
            return jsonify({'success': False, 'error': 'Рекомендация не найдена'}), 404
            
        recommendation.status = response_type
        recommendation.client_response = response_type
        recommendation.responded_at = datetime.utcnow()
        
        db.session.commit()
        
        # Notify manager about client response
        if recommendation.manager:
            try:
                from email_service import send_notification
                subject = f"Ответ клиента на рекомендацию: {recommendation.title}"
                message = f"""
Клиент {current_user.full_name} ответил на вашу рекомендацию:

Рекомендация: {recommendation.title}
Объект: {recommendation.item_name}
Ответ: {'Интересно' if response_type == 'interested' else 'Не интересно'}

Время ответа: {datetime.now().strftime('%d.%m.%Y %H:%M')}
"""
                send_notification(
                    recommendation.manager.email,
                    subject,
                    message,
                    notification_type="client_response"
                )
            except Exception as e:
                print(f"Error sending notification to manager: {e}")
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/manager/clients', methods=['GET'])
def api_manager_get_clients():
    """Get list of clients for manager"""
    from models import User
    
    # Check if user is authenticated as manager
    manager_id = session.get('manager_id')
    if not manager_id:
        return jsonify({'success': False, 'error': 'Требуется авторизация менеджера'}), 401
    
    try:
        # Get all clients (buyers)
        clients = User.query.filter_by(
            role='buyer'
        ).order_by(User.full_name).all()
        
        clients_data = []
        for client in clients:
            clients_data.append({
                'id': client.id,
                'email': client.email,
                'full_name': client.full_name,
                'phone': client.phone,
                'created_at': client.created_at.strftime('%d.%m.%Y') if client.created_at else '',
                'client_status': getattr(client, 'client_status', 'Новый')
            })
        
        return jsonify({
            'success': True,
            'clients': clients_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/manager/recommendation-categories/<int:client_id>', methods=['GET'])
def api_get_recommendation_categories(client_id):
    """Get recommendation categories for a specific client"""
    from models import RecommendationCategory
    
    # Check if user is authenticated as manager
    manager_id = session.get('manager_id')
    if not manager_id:
        return jsonify({'success': False, 'error': 'Требуется авторизация менеджера'}), 401
    
    try:
        categories = RecommendationCategory.query.filter_by(
            manager_id=manager_id,
            client_id=client_id,
            is_active=True
        ).order_by(RecommendationCategory.last_used.desc()).all()
        
        categories_data = []
        for category in categories:
            categories_data.append({
                'id': category.id,
                'name': category.name,
                'description': category.description,
                'color': category.color,
                'recommendations_count': category.recommendations_count,
                'last_used': category.last_used.strftime('%d.%m.%Y') if category.last_used else '',
                'created_at': category.created_at.strftime('%d.%m.%Y') if category.created_at else ''
            })
        
        return jsonify({
            'success': True,
            'categories': categories_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/manager/recommendation-categories', methods=['POST'])
def api_create_recommendation_category():
    """Create new recommendation category"""
    from models import RecommendationCategory
    
    # Check if user is authenticated as manager
    manager_id = session.get('manager_id')
    if not manager_id:
        return jsonify({'success': False, 'error': 'Требуется авторизация менеджера'}), 401
    
    try:
        data = request.get_json()
        category_name = data.get('name', '').strip()
        client_id = data.get('client_id')
        description = data.get('description', '').strip()
        color = data.get('color', 'blue')
        
        if not category_name or not client_id:
            return jsonify({'success': False, 'error': 'Название категории и клиент обязательны'}), 400
        
        # Check if category with this name already exists for this client
        existing = RecommendationCategory.query.filter_by(
            manager_id=manager_id,
            client_id=client_id,
            name=category_name,
            is_active=True
        ).first()
        
        if existing:
            return jsonify({'success': False, 'error': 'Категория с таким названием уже существует'}), 400
        
        # Create new category
        category = RecommendationCategory(
            name=category_name,
            description=description,
            manager_id=manager_id,
            client_id=client_id,
            color=color
        )
        
        db.session.add(category)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'category': {
                'id': category.id,
                'name': category.name,
                'description': category.description,
                'color': category.color,
                'recommendations_count': 0,
                'created_at': category.created_at.strftime('%d.%m.%Y')
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/manager/all-categories', methods=['GET'])
def api_manager_all_categories():
    """Get all categories created by this manager"""
    from models import RecommendationCategory, User
    
    # Check if user is authenticated as manager
    manager_id = session.get('manager_id')
    if not manager_id:
        return jsonify({'success': False, 'error': 'Требуется авторизация менеджера'}), 401
    
    try:
        categories = db.session.query(
            RecommendationCategory, 
            User.email.label('client_email')
        ).outerjoin(
            User, RecommendationCategory.client_id == User.id
        ).filter(
            RecommendationCategory.manager_id == manager_id
        ).order_by(
            RecommendationCategory.last_used.desc().nulls_last(),
            RecommendationCategory.created_at.desc()
        ).all()
        
        category_data = []
        for category, client_email in categories:
            category_data.append({
                'id': category.id,
                'name': category.name,
                'description': category.description,
                'client_email': client_email or 'Общая категория',
                'recommendations_count': category.recommendations_count,
                'is_active': category.is_active,
                'last_used': category.last_used.isoformat() if category.last_used else None,
                'created_at': category.created_at.isoformat()
            })
        
        return jsonify({
            'success': True,
            'categories': category_data
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/manager/categories/global', methods=['POST'])
def api_manager_create_global_category():
    """Create a new global category template"""
    from models import RecommendationCategory
    
    # Check if user is authenticated as manager
    manager_id = session.get('manager_id')
    if not manager_id:
        return jsonify({'success': False, 'error': 'Требуется авторизация менеджера'}), 401
    
    data = request.get_json()
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    
    if not name:
        return jsonify({'success': False, 'error': 'Укажите название категории'}), 400
    
    try:
        # Create a template category without specific client
        category = RecommendationCategory(
            name=name,
            description=description,
            manager_id=manager_id,
            client_id=None,  # Global template
            is_template=True,
            recommendations_count=0
        )
        
        db.session.add(category)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'category': {
                'id': category.id,
                'name': category.name,
                'description': category.description
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/manager/categories/<int:category_id>/toggle', methods=['POST'])
def api_manager_toggle_category(category_id):
    """Toggle category active status"""
    from models import RecommendationCategory
    
    # Check if user is authenticated as manager
    manager_id = session.get('manager_id')
    if not manager_id:
        return jsonify({'success': False, 'error': 'Требуется авторизация менеджера'}), 401
    
    data = request.get_json()
    is_active = data.get('is_active', True)
    
    try:
        category = RecommendationCategory.query.filter_by(
            id=category_id,
            manager_id=manager_id
        ).first()
        
        if not category:
            return jsonify({'success': False, 'error': 'Категория не найдена'}), 404
        
        category.is_active = is_active
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# Manager Dashboard API endpoints
@app.route('/api/manager/welcome-message', methods=['GET'])
@manager_required
def api_manager_welcome_message():
    """Get adaptive welcome message based on recent activity"""
    from models import User, Recommendation, Collection, SavedSearch, Manager
    from sqlalchemy import func, desc
    from datetime import datetime, timedelta
    
    manager_id = session.get('manager_id')
    current_manager = Manager.query.get(manager_id)
    
    if not current_manager:
        return jsonify({'success': False, 'error': 'Менеджер не найден'}), 404
    
    try:
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)
        
        # Get recent activity counts
        recent_recommendations = Recommendation.query.filter(
            Recommendation.manager_id == manager_id,
            Recommendation.created_at >= week_start
        ).count()
        
        today_recommendations = Recommendation.query.filter(
            Recommendation.manager_id == manager_id,
            Recommendation.created_at >= today_start
        ).count()
        
        recent_collections = Collection.query.filter(
            Collection.created_by_manager_id == manager_id,
            Collection.created_at >= week_start
        ).count()
        
        total_clients = User.query.filter_by(assigned_manager_id=manager_id).count()
        
        new_clients_today = User.query.filter(
            User.assigned_manager_id == manager_id,
            User.created_at >= today_start
        ).count()
        
        # Get last activity time (use created_at if last_login_at doesn't exist)
        last_activity = getattr(current_manager, 'last_login_at', None) or current_manager.created_at
        hours_since_last_login = (now - last_activity).total_seconds() / 3600 if last_activity else 0
        
        # Get most recent activity
        latest_recommendation = Recommendation.query.filter_by(manager_id=manager_id).order_by(desc(Recommendation.created_at)).first()
        latest_collection = Collection.query.filter_by(created_by_manager_id=manager_id).order_by(desc(Collection.created_at)).first()
        
        # Generate adaptive message based on activity patterns
        messages = []
        
        # Time-based greeting
        hour = now.hour
        if 5 <= hour < 12:
            time_greeting = "Доброе утро"
        elif 12 <= hour < 18:
            time_greeting = "Добрый день"
        elif 18 <= hour < 23:
            time_greeting = "Добрый вечер"
        else:
            time_greeting = "Доброй ночи"
        
        first_name = current_manager.full_name.split()[0]
        
        # Activity-based messages
        if hours_since_last_login >= 24:
            messages.append(f"{time_greeting}, {first_name}! Рады видеть вас снова.")
            if recent_recommendations > 0:
                messages.append(f"За время вашего отсутствия было отправлено {recent_recommendations} рекомендаций.")
        elif hours_since_last_login >= 8:
            messages.append(f"{time_greeting}, {first_name}! Добро пожаловать обратно.")
        else:
            messages.append(f"{time_greeting}, {first_name}!")
        
        # Recent activity highlights
        if today_recommendations > 0:
            messages.append(f"Сегодня вы уже отправили {today_recommendations} рекомендаций - отличная работа!")
        elif recent_recommendations > 0:
            messages.append(f"На этой неделе вы отправили {recent_recommendations} рекомендаций клиентам.")
        
        if new_clients_today > 0:
            messages.append(f"У вас {new_clients_today} новых клиентов сегодня.")
        
        if recent_collections > 0:
            messages.append(f"Создано {recent_collections} новых подборок на этой неделе.")
        
        # Motivational suggestions based on activity
        if recent_recommendations == 0 and recent_collections == 0:
            messages.append("Готовы создать новую подборку для клиентов?")
        elif total_clients > 0 and recent_recommendations < 3:
            messages.append("Возможно, стоит отправить рекомендации активным клиентам?")
        
        # Default fallback
        if len(messages) == 1:  # Only greeting
            messages.append("Панель управления менеджера недвижимости готова к работе.")
        
        # Activity context for additional UI hints
        activity_context = {
            'has_recent_activity': recent_recommendations > 0 or recent_collections > 0,
            'needs_attention': total_clients > 0 and recent_recommendations == 0,
            'high_activity': recent_recommendations >= 5 or recent_collections >= 3,
            'new_day': hours_since_last_login >= 8,
            'latest_recommendation_date': latest_recommendation.created_at.strftime('%d.%m.%Y') if latest_recommendation else None,
            'latest_collection_date': latest_collection.created_at.strftime('%d.%m.%Y') if latest_collection else None
        }
        
        return jsonify({
            'success': True,
            'messages': messages,
            'context': activity_context,
            'stats': {
                'recent_recommendations': recent_recommendations,
                'today_recommendations': today_recommendations,
                'recent_collections': recent_collections,
                'total_clients': total_clients,
                'new_clients_today': new_clients_today
            }
        })
        
    except Exception as e:
        print(f"Error generating welcome message: {e}")
        return jsonify({
            'success': True,
            'messages': [f"{time_greeting}, {first_name}!", "Панель управления менеджера недвижимости"],
            'context': {'has_recent_activity': False},
            'stats': {}
        })

@app.route('/api/manager/dashboard-stats', methods=['GET'])
def api_manager_dashboard_stats():
    """Get manager dashboard statistics"""
    from models import User, Recommendation
    from sqlalchemy import func
    
    # Check if user is authenticated as manager
    manager_id = session.get('manager_id')
    if not manager_id:
        return jsonify({'success': False, 'error': 'Требуется авторизация менеджера'}), 401
    
    try:
        # Count clients assigned to this manager
        clients_count = User.query.filter_by(assigned_manager_id=manager_id).count()
        
        # Count recommendations sent by this manager
        recommendations_count = Recommendation.query.filter_by(manager_id=manager_id).count()
        
        # Count recommendations sent this month
        from datetime import datetime
        month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_recommendations = Recommendation.query.filter(
            Recommendation.manager_id == manager_id,
            Recommendation.sent_at >= month_start
        ).count()
        
        # Collections count (placeholder for now)
        collections_count = 5
        
        return jsonify({
            'success': True,
            'clients_count': clients_count,
            'recommendations_count': monthly_recommendations,
            'total_recommendations': recommendations_count,
            'collections_count': collections_count
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/manager/activity-feed', methods=['GET'])
def api_manager_activity_feed():
    """Get manager activity feed"""
    from models import Recommendation, User
    from datetime import datetime, timedelta
    
    # Check if user is authenticated as manager
    manager_id = session.get('manager_id')
    if not manager_id:
        return jsonify({'success': False, 'error': 'Требуется авторизация менеджера'}), 401
    
    try:
        # Get recent activities (recommendations sent)
        recent_recommendations = Recommendation.query.filter_by(
            manager_id=manager_id
        ).order_by(Recommendation.sent_at.desc()).limit(10).all()
        
        activities = []
        for rec in recent_recommendations:
            time_diff = datetime.utcnow() - rec.sent_at
            if time_diff.days > 0:
                time_ago = f"{time_diff.days} дн. назад"
            elif time_diff.seconds > 3600:
                time_ago = f"{time_diff.seconds // 3600} ч. назад"
            else:
                time_ago = f"{time_diff.seconds // 60} мин. назад"
            
            activities.append({
                'title': f'Отправлена рекомендация',
                'description': f'{rec.title} для {rec.client.full_name}',
                'time_ago': time_ago,
                'icon': 'paper-plane',
                'color': 'blue'
            })
        
        # Add some sample activities for demo
        if len(activities) < 3:
            activities.extend([
                {
                    'title': 'Новый клиент добавлен',
                    'description': 'Демо Клиентов зарегистрировался в системе',
                    'time_ago': '2 ч. назад',
                    'icon': 'user-plus',
                    'color': 'green'
                },
                {
                    'title': 'Клиент просмотрел рекомендацию',
                    'description': 'Демо Клиентов открыл рекомендацию по ЖК "Солнечный"',
                    'time_ago': '4 ч. назад',
                    'icon': 'eye',
                    'color': 'purple'
                }
            ])
        
        return jsonify({
            'success': True,
            'activities': activities
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/manager/top-clients', methods=['GET'])
def api_manager_top_clients():
    """Get top clients by interactions"""
    from models import User, Recommendation
    from sqlalchemy import func
    
    # Check if user is authenticated as manager
    manager_id = session.get('manager_id')
    if not manager_id:
        return jsonify({'success': False, 'error': 'Требуется авторизация менеджера'}), 401
    
    try:
        # Get clients with most interactions (recommendations received)
        top_clients = db.session.query(
            User,
            func.count(Recommendation.id).label('interactions_count')
        ).join(
            Recommendation, User.id == Recommendation.client_id
        ).filter(
            Recommendation.manager_id == manager_id
        ).group_by(User.id).order_by(
            func.count(Recommendation.id).desc()
        ).limit(5).all()
        
        clients_data = []
        for user, count in top_clients:
            clients_data.append({
                'id': user.id,
                'full_name': user.full_name,
                'email': user.email,
                'interactions_count': count
            })
        
        # Add demo clients if not enough data
        if len(clients_data) < 3:
            demo_clients = [
                {'id': 999, 'full_name': 'Демо Клиентов', 'email': 'demo@inback.ru', 'interactions_count': 8},
                {'id': 998, 'full_name': 'Анна Покупателева', 'email': 'buyer@test.ru', 'interactions_count': 5},
                {'id': 997, 'full_name': 'Петр Инвесторов', 'email': 'investor@test.ru', 'interactions_count': 3}
            ]
            clients_data.extend(demo_clients[:3-len(clients_data)])
        
        return jsonify({
            'success': True,
            'clients': clients_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

# Blog Management Routes for Managers
@app.route('/admin/blog-manager')
@manager_required
def admin_blog_manager():
    """Manager blog management page"""
    from models import BlogArticle, BlogCategory
    
    try:
        # Get filter parameters
        search = request.args.get('search', '')
        status = request.args.get('status', '')
        category_id = request.args.get('category_id', '')
        
        # Build query
        query = BlogArticle.query
        
        if search:
            query = query.filter(BlogArticle.title.contains(search) | 
                               BlogArticle.content.contains(search))
        
        if status:
            query = query.filter(BlogArticle.status == status)
            
        if category_id:
            query = query.filter(BlogArticle.category_id == int(category_id))
        
        # Order by creation date
        articles = query.order_by(BlogArticle.created_at.desc()).all()
        
        # Get categories for filter dropdown
        categories = BlogCategory.query.filter_by(is_active=True).order_by(BlogCategory.name).all()
        
        return render_template('admin/blog_manager.html',
                             articles=articles,
                             categories=categories,
                             search=search,
                             status=status,
                             category_id=category_id)
        
    except Exception as e:
        flash(f'Ошибка загрузки блога: {str(e)}', 'error')
        return redirect(url_for('manager_dashboard'))


@app.route('/admin/blog/create-new', methods=['GET', 'POST'])
@manager_required
def admin_create_new_article():
    """Create new blog article"""
    from models import BlogCategory, BlogArticle
    import re
    from datetime import datetime
    
    if request.method == 'GET':
        categories = BlogCategory.query.filter_by(is_active=True).order_by(BlogCategory.name).all()
        return render_template('admin/blog_create_new.html', categories=categories)
    
    try:
        # Get form data
        title = request.form.get('title')
        excerpt = request.form.get('excerpt')
        content = request.form.get('content')
        category_id = request.form.get('category_id')
        status = request.form.get('status', 'draft')
        is_featured = 'is_featured' in request.form
        
        # Generate slug from title
        slug = re.sub(r'[^\w\s-]', '', title.lower())
        slug = re.sub(r'[-\s]+', '-', slug).strip('-')
        
        # Ensure slug is unique
        original_slug = slug
        counter = 1
        while BlogArticle.query.filter_by(slug=slug).first():
            slug = f"{original_slug}-{counter}"
            counter += 1
        
        # Create article
        article = BlogArticle(
            title=title,
            slug=slug,
            excerpt=excerpt,
            content=content,
            category_id=int(category_id),
            author_id=session.get('manager_id'),
            status=status,
            is_featured=is_featured
        )
        
        # Set publish date if status is published
        if status == 'published':
            article.published_at = datetime.utcnow()
        
        # Calculate reading time (approx 200 words per minute)
        word_count = len(content.split())
        article.reading_time = max(1, word_count // 200)
        
        db.session.add(article)
        db.session.commit()
        
        flash('Статья успешно создана!', 'success')
        return redirect(url_for('admin_blog_manager'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка создания статьи: {str(e)}', 'error')
        return redirect(url_for('admin_create_new_article'))


@app.route('/admin/blog/<int:article_id>/edit-article', methods=['GET', 'POST'])
@manager_required 
def admin_edit_new_article(article_id):
    """Edit existing blog article"""
    from models import BlogArticle, BlogCategory
    import re
    from datetime import datetime
    
    article = BlogArticle.query.get_or_404(article_id)
    
    if request.method == 'GET':
        categories = BlogCategory.query.filter_by(is_active=True).order_by(BlogCategory.name).all()
        return render_template('admin/blog_edit_new.html', article=article, categories=categories)
    
    try:
        # Get form data
        title = request.form.get('title')
        excerpt = request.form.get('excerpt') 
        content = request.form.get('content')
        category_id = request.form.get('category_id')
        status = request.form.get('status')
        is_featured = 'is_featured' in request.form
        
        # Update slug if title changed
        if title != article.title:
            slug = re.sub(r'[^\w\s-]', '', title.lower())
            slug = re.sub(r'[-\s]+', '-', slug).strip('-')
            
            # Ensure slug is unique (exclude current article)
            original_slug = slug
            counter = 1
            while BlogArticle.query.filter_by(slug=slug).filter(BlogArticle.id != article_id).first():
                slug = f"{original_slug}-{counter}"
                counter += 1
            
            article.slug = slug
        
        # Update article
        article.title = title
        article.excerpt = excerpt
        article.content = content
        article.category_id = int(category_id)
        article.status = status
        article.is_featured = is_featured
        article.updated_at = datetime.utcnow()
        
        # Set/update publish date if status changed to published
        if status == 'published' and not article.published_at:
            article.published_at = datetime.utcnow()
        
        # Recalculate reading time
        word_count = len(content.split())
        article.reading_time = max(1, word_count // 200)
        
        db.session.commit()
        
        flash('Статья успешно обновлена!', 'success')
        return redirect(url_for('admin_blog_manager'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка обновления статьи: {str(e)}', 'error')
        return redirect(url_for('admin_edit_new_article', article_id=article_id))


@app.route('/admin/blog/<int:article_id>/delete-article', methods=['POST'])
@manager_required
def admin_delete_new_article(article_id):
    """Delete blog article"""
    from models import BlogArticle
    
    try:
        article = BlogArticle.query.get_or_404(article_id)
        db.session.delete(article)
        db.session.commit()
        
        flash('Статья успешно удалена!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка удаления статьи: {str(e)}', 'error')
    
    return redirect(url_for('admin_blog_manager'))


@app.route('/admin/blog/categories')
@admin_required
def admin_blog_categories():
    """Manage blog categories"""
    from models import Admin, BlogCategory
    
    admin_id = session.get('admin_id')
    current_admin = Admin.query.get(admin_id)
    
    categories = BlogCategory.query.order_by(BlogCategory.sort_order, BlogCategory.name).all()
    return render_template('admin/blog_categories.html', admin=current_admin, categories=categories)


@app.route('/admin/blog/categories/create', methods=['GET', 'POST'])
@admin_required
def admin_create_category():
    """Create new blog category - both form and JSON API"""
    from models import Admin, BlogCategory
    import re
    
    admin_id = session.get('admin_id')
    current_admin = Admin.query.get(admin_id)
    
    # Handle JSON requests (from inline category creation)
    if request.is_json:
        try:
            data = request.get_json()
            name = data.get('name')
            description = data.get('description', '')
            
            if not name:
                return jsonify({'success': False, 'error': 'Название категории обязательно'})
            
            # Generate slug from Russian name
            def transliterate(text):
                rus_to_eng = {
                    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'zh', 'з': 'z',
                    'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
                    'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'c', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
                    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
                }
                return ''.join(rus_to_eng.get(char.lower(), char) for char in text)
            
            slug = transliterate(name.lower())
            slug = re.sub(r'[^\w\s-]', '', slug)
            slug = re.sub(r'[-\s]+', '-', slug).strip('-')
            
            # Ensure unique slug
            original_slug = slug
            counter = 1
            while BlogCategory.query.filter_by(slug=slug).first():
                slug = f"{original_slug}-{counter}"
                counter += 1
            
            category = BlogCategory(
                name=name,
                slug=slug,
                description=description,
                is_active=True
            )
            
            db.session.add(category)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'category': {
                    'id': category.id,
                    'name': category.name,
                    'slug': category.slug
                }
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)})
    
    # Handle form requests (standard category creation page)
    if request.method == 'GET':
        return render_template('admin/blog_category_create.html', admin=current_admin)
    
    try:
        name = request.form.get('name')
        if not name:
            flash('Название категории обязательно', 'error')
            return render_template('admin/blog_category_create.html', admin=current_admin)
            
        description = request.form.get('description', '')
        
        # Generate slug
        slug = re.sub(r'[^\w\s-]', '', name.lower())
        slug = re.sub(r'[-\s]+', '-', slug).strip('-')
        
        # Ensure unique slug
        original_slug = slug
        counter = 1
        while BlogCategory.query.filter_by(slug=slug).first():
            slug = f"{original_slug}-{counter}"
            counter += 1
        
        category = BlogCategory(
            name=name,
            slug=slug,
            description=description
        )
        
        db.session.add(category)
        db.session.commit()
        
        flash(f'Категория "{name}" успешно создана!', 'success')
        return redirect(url_for('admin_blog'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка создания категории: {str(e)}', 'error')
        return render_template('admin/blog_category_create.html', admin=current_admin)


# Blog Public Routes  
@app.route('/blog-new')
def blog_new():
    """Public blog page"""
    from models import BlogArticle, BlogCategory
    
    try:
        # Get published articles
        articles = BlogArticle.query.filter_by(status='published').order_by(BlogArticle.published_at.desc()).all()
        categories = BlogCategory.query.filter_by(is_active=True).order_by(BlogCategory.name).all()
        
        # Add pagination variables that template expects
        return render_template('blog.html', 
                             articles=articles, 
                             categories=categories,
                             total_pages=1,
                             current_page=1,
                             has_prev=False,
                             has_next=False,
                             prev_num=None,
                             next_num=None,
                             search_query='',
                             category_filter=None)
        
    except Exception as e:
        print(f"Blog error: {str(e)}")
        import traceback
        traceback.print_exc()
        # Fallback for when there's an error
        try:
            return render_template('blog.html', articles=[], categories=[])
        except:
            return "Временные проблемы с блогом. Попробуйте позже.", 500


@app.route('/blog-new/<slug>')
def blog_article_new(slug):
    """View single blog article"""
    from models import BlogArticle
    
    try:
        article = BlogArticle.query.filter_by(slug=slug, status='published').first_or_404()
        
        # Increment view count
        article.views_count += 1
        db.session.commit()
        
        # Get related articles from same category
        related_articles = BlogArticle.query.filter_by(
            category_id=article.category_id,
            status='published'
        ).filter(
            BlogArticle.id != article.id
        ).order_by(
            BlogArticle.published_at.desc()
        ).limit(3).all()
        
        return render_template('blog_article.html', 
                             article=article,
                             related_articles=related_articles)
        
    except Exception as e:
        flash('Статья не найдена', 'error')
        return redirect(url_for('blog_new'))


@app.route('/blog-new/category/<slug>')
def blog_category_new(slug):
    """View articles by category"""
    from models import BlogCategory, BlogArticle
    
    try:
        category = BlogCategory.query.filter_by(slug=slug, is_active=True).first_or_404()
        
        articles = BlogArticle.query.filter_by(
            category_id=category.id,
            status='published'
        ).order_by(
            BlogArticle.published_at.desc()
        ).all()
        
        return render_template('blog_category.html', 
                             category=category,
                             articles=articles)
        
    except Exception as e:
        flash('Категория не найдена', 'error')
        return redirect(url_for('blog_new'))


@app.route('/blog/<slug>')
def blog_post(slug):
    """Display single blog post by slug"""
    try:
        # Find post by slug - using direct SQL query
        from sqlalchemy import text
        result = db.session.execute(text("""
            SELECT id, title, slug, content, excerpt, category, featured_image, 
                   views_count, created_at, '' as author_name
            FROM blog_posts 
            WHERE slug = :slug AND status = 'published'
        """), {'slug': slug}).fetchone()
        
        if not result:
            flash('Статья не найдена', 'error')
            return redirect(url_for('blog'))
        
        # Convert to dict for template
        post = {
            'id': result[0],
            'title': result[1],
            'slug': result[2],
            'content': result[3],
            'excerpt': result[4],
            'category': result[5],
            'featured_image': result[6],
            'views_count': result[7] or 0,
            'created_at': result[8],
            'author_name': result[9] or 'InBack'
        }
        
        # Increment view count
        try:
            db.session.execute(text("""
                UPDATE blog_posts 
                SET views_count = COALESCE(views_count, 0) + 1 
                WHERE id = :id
            """), {'id': post['id']})
            db.session.commit()
            post['views_count'] += 1
        except Exception as e:
            db.session.rollback()
        
        # Get related posts from same category
        related_results = db.session.execute(text("""
            SELECT id, title, slug, excerpt, featured_image, created_at
            FROM blog_posts 
            WHERE category = :category AND status = 'published' AND id != :id
            ORDER BY created_at DESC
            LIMIT 3
        """), {'category': post['category'], 'id': post['id']}).fetchall()
        
        related_posts = []
        for r in related_results:
            related_posts.append({
                'id': r[0],
                'title': r[1], 
                'slug': r[2],
                'excerpt': r[3],
                'featured_image': r[4],
                'created_at': r[5]
            })
        
        return render_template('blog_post.html', 
                             post=post,
                             related_posts=related_posts)
        
    except Exception as e:
        flash('Ошибка загрузки статьи', 'error')
        return redirect(url_for('blog'))


# Admin Blog Management Routes
@app.route('/admin/blog-management')
@admin_required
def admin_blog_management():
    """Admin blog management page"""
    from models import BlogPost, BlogCategory
    
    try:
        # Get filter parameters
        search = request.args.get('search', '')
        status = request.args.get('status', '')
        category_name = request.args.get('category', '')
        page = request.args.get('page', 1, type=int)
        
        # Build query
        query = BlogPost.query
        
        if search:
            query = query.filter(BlogPost.title.contains(search) | 
                               BlogPost.content.contains(search))
        
        if status:
            query = query.filter(BlogPost.status == status)
            
        if category_name:
            query = query.filter(BlogPost.category == category_name)
        
        # Order by creation date and paginate
        posts = query.order_by(BlogPost.created_at.desc()).paginate(
            page=page, per_page=10, error_out=False
        )
        
        # Get categories for filter dropdown
        categories = BlogCategory.query.filter_by(is_active=True).order_by(BlogCategory.name).all()
        
        # Get admin user for template
        from flask_login import current_user
        admin = current_user if current_user.is_authenticated else None
        
        return render_template('admin/blog_management.html',
                             posts=posts,
                             categories=categories,
                             search=search,
                             status=status,
                             category_name=category_name,
                             admin=admin)
        
    except Exception as e:
        flash(f'Ошибка загрузки блога: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))


@app.route('/admin/blog-management/create', methods=['GET', 'POST'])
@admin_required
def admin_create_blog_post():
    """Create new blog post"""
    from models import BlogPost, BlogCategory
    import re
    from datetime import datetime
    
    if request.method == 'GET':
        categories = BlogCategory.query.order_by(BlogCategory.name).all()
        return render_template('admin/blog_post_create.html', categories=categories)
    
    try:
        # Get form data
        title = request.form.get('title')
        excerpt = request.form.get('excerpt')
        content = request.form.get('content')
        category_id = request.form.get('category_id')
        status = request.form.get('status', 'draft')
        is_featured = 'is_featured' in request.form
        featured_image = request.form.get('featured_image', '')
        meta_title = request.form.get('meta_title', '')
        meta_description = request.form.get('meta_description', '')
        keywords = request.form.get('keywords', '')
        
        # Get category name from category_id
        category = BlogCategory.query.get(int(category_id))
        if not category:
            flash('Выбранная категория не найдена', 'error')
            return redirect(url_for('admin_create_blog_post'))
        
        # Generate slug from title
        slug = re.sub(r'[^\w\s-]', '', title.lower())
        slug = re.sub(r'[-\s]+', '-', slug).strip('-')
        
        # Ensure slug is unique
        original_slug = slug
        counter = 1
        while BlogPost.query.filter_by(slug=slug).first():
            slug = f"{original_slug}-{counter}"
            counter += 1
        
        # Calculate reading time (approx 200 words per minute)
        word_count = len(content.split()) if content else 0
        reading_time = max(1, word_count // 200)
        
        # Create blog post using BlogPost model
        post = BlogPost(
            title=title,
            slug=slug,
            excerpt=excerpt,
            content=content,
            category=category.name,  # Use category name, not ID
            author_id=1,  # Default author
            status=status,
            featured_image=featured_image,
            tags=keywords
        )
        
        if status == 'published':
            post.published_at = datetime.utcnow()
        
        db.session.add(post)
        db.session.commit()
        
        # Обновим счетчик статей в категории
        category.articles_count = BlogPost.query.filter_by(category=category.name, status='published').count()
        db.session.commit()
        
        print(f'DEBUG: Created article "{title}" in category "{category.name}" with status "{status}"')
        print(f'DEBUG: Updated category "{category.name}" article count to {category.articles_count}')
        
        flash('Статья успешно создана!', 'success')
        return redirect(url_for('admin_blog_management'))
        
    except Exception as e:
        db.session.rollback()
        print(f'ERROR creating blog post: {str(e)}')
        flash(f'Ошибка создания статьи: {str(e)}', 'error')
        return redirect(url_for('admin_create_blog_post'))

@app.route('/admin/upload-image', methods=['POST'])
@admin_required
def admin_upload_image():
    """Upload image for blog posts"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Файл не выбран'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Файл не выбран'}), 400
    
    # Check if file is an image
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    if not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
        return jsonify({'success': False, 'error': 'Разрешены только изображения (PNG, JPG, JPEG, GIF, WebP)'}), 400
    
    try:
        # Generate secure filename
        filename = secure_filename(file.filename)
        
        # Add timestamp to avoid naming conflicts
        import time
        timestamp = str(int(time.time()))
        name, ext = os.path.splitext(filename)
        filename = f"{name}_{timestamp}{ext}"
        
        # Save file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Return URL for TinyMCE
        file_url = f'/uploads/{filename}'
        
        return jsonify({
            'success': True,
            'url': file_url,
            'filename': filename
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Ошибка загрузки файла: {str(e)}'}), 500

# Duplicate route removed - already defined earlier


@app.route('/admin/blog-management/<int:post_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_blog_post(post_id):
    """Edit blog post"""
    from models import BlogPost, BlogCategory
    import re
    from datetime import datetime
    
    post = BlogPost.query.get_or_404(post_id)
    
    if request.method == 'GET':
        categories = BlogCategory.query.filter_by(is_active=True).order_by(BlogCategory.name).all()
        return render_template('admin/blog_post_edit.html', post=post, categories=categories)
    
    try:
        # Get form data
        title = request.form.get('title')
        excerpt = request.form.get('excerpt')
        content = request.form.get('content')
        category_id = request.form.get('category_id')
        status = request.form.get('status')
        is_featured = 'is_featured' in request.form
        featured_image = request.form.get('featured_image', '')
        meta_title = request.form.get('meta_title', '')
        meta_description = request.form.get('meta_description', '')
        keywords = request.form.get('keywords', '')
        
        # Validation
        if not title or title.strip() == '':
            flash('Заголовок статьи обязателен', 'error')
            return redirect(url_for('admin_edit_blog_post', post_id=post_id))
        
        if not content or content.strip() == '':
            flash('Содержание статьи обязательно', 'error')
            return redirect(url_for('admin_edit_blog_post', post_id=post_id))
        
        if not category_id or category_id == '':
            flash('Выберите категорию статьи', 'error')
            return redirect(url_for('admin_edit_blog_post', post_id=post_id))

        # Get category name from category_id
        category = BlogCategory.query.get(int(category_id))
        if not category:
            flash('Выбранная категория не найдена', 'error')
            return redirect(url_for('admin_edit_blog_post', post_id=post_id))
        
        # Update slug if title changed
        if title != post.title:
            slug = re.sub(r'[^\w\s-]', '', title.lower())
            slug = re.sub(r'[-\s]+', '-', slug).strip('-')
            
            original_slug = slug
            counter = 1
            while BlogPost.query.filter_by(slug=slug).filter(BlogPost.id != post_id).first():
                slug = f"{original_slug}-{counter}"
                counter += 1
            
            post.slug = slug
        
        # Calculate reading time
        word_count = len(content.split()) if content else 0
        reading_time = max(1, word_count // 200)
        
        # Update post
        old_category = post.category
        post.title = title
        post.excerpt = excerpt
        post.content = content
        post.category = category.name  # BlogPost uses category name as string
        post.status = status
        post.is_featured = is_featured
        post.featured_image = featured_image
        post.meta_title = meta_title or title
        post.meta_description = meta_description or excerpt  
        post.tags = keywords  # BlogPost uses tags field
        post.reading_time = reading_time
        post.updated_at = datetime.utcnow()
        
        if status == 'published' and not post.published_at:
            post.published_at = datetime.utcnow()
        
        db.session.commit()
        
        # Update category article counts for both old and new categories
        for cat_name in [old_category, category.name]:
            if cat_name:
                cat = BlogCategory.query.filter_by(name=cat_name).first()
                if cat:
                    cat.articles_count = BlogPost.query.filter_by(category=cat_name, status='published').count()
        
        db.session.commit()
        
        flash('Статья успешно обновлена!', 'success')
        return redirect(url_for('admin_blog_management'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка обновления статьи: {str(e)}', 'error')
        return redirect(url_for('admin_edit_blog_post', post_id=post_id))


@app.route('/admin/blog-management/<int:post_id>/delete', methods=['POST'])
@admin_required
def admin_delete_blog_post(post_id):
    """Delete blog post"""
    from models import BlogPost, BlogCategory
    
    try:
        post = BlogPost.query.get_or_404(post_id)
        category_name = post.category
        
        db.session.delete(post)
        db.session.commit()
        
        # Update category article count
        if category_name:
            category = BlogCategory.query.filter_by(name=category_name).first()
            if category:
                category.articles_count = BlogPost.query.filter_by(category=category_name, status='published').count()
                db.session.commit()
        
        flash('Статья успешно удалена!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка удаления статьи: {str(e)}', 'error')
    
    return redirect(url_for('admin_blog_management'))


@app.route('/admin/blog-categories-management')
@admin_required
def admin_blog_categories_management():
    """Admin blog categories management"""
    from models import BlogCategory
    
    try:
        categories = BlogCategory.query.order_by(BlogCategory.sort_order).all()
        return render_template('admin/blog_categories.html', categories=categories)
        
    except Exception as e:
        flash(f'Ошибка загрузки категорий: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))


@app.route('/admin/blog-categories-management/create', methods=['GET', 'POST'])
@admin_required
def admin_create_blog_category_new():
    """Create blog category"""
    from models import BlogCategory
    import re
    
    if request.method == 'GET':
        return render_template('admin/blog_category_create.html')
    
    try:
        # Get form data
        name = request.form.get('name')
        description = request.form.get('description', '')
        color = request.form.get('color', 'blue')
        icon = request.form.get('icon', 'fas fa-folder')
        sort_order = request.form.get('sort_order', 0, type=int)
        
        # Generate slug
        slug = re.sub(r'[^\w\s-]', '', name.lower())
        slug = re.sub(r'[-\s]+', '-', slug).strip('-')
        
        # Ensure slug is unique
        original_slug = slug
        counter = 1
        while BlogCategory.query.filter_by(slug=slug).first():
            slug = f"{original_slug}-{counter}"
            counter += 1
        
        category = BlogCategory(
            name=name,
            slug=slug,
            description=description,
            color=color,
            icon=icon,
            sort_order=sort_order,
            is_active=True,
            articles_count=0
        )
        
        db.session.add(category)
        db.session.commit()
        
        flash('Категория успешно создана!', 'success')
        return redirect(url_for('admin_blog_categories_management'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка создания категории: {str(e)}', 'error')
        return redirect(url_for('admin_create_blog_category_new'))


@app.route('/admin/blog-categories-management/<int:category_id>/edit', methods=['GET', 'POST'])
@admin_required  
def admin_edit_blog_category_new(category_id):
    """Edit blog category"""
    from models import BlogCategory
    import re
    
    category = BlogCategory.query.get_or_404(category_id)
    
    if request.method == 'GET':
        return render_template('admin/blog_category_edit.html', category=category)
    
    try:
        # Get form data
        name = request.form.get('name')
        description = request.form.get('description', '')
        color = request.form.get('color', 'blue')
        icon = request.form.get('icon', 'fas fa-folder')
        sort_order = request.form.get('sort_order', 0, type=int)
        is_active = 'is_active' in request.form
        
        # Update slug if name changed
        if name != category.name:
            slug = re.sub(r'[^\w\s-]', '', name.lower())
            slug = re.sub(r'[-\s]+', '-', slug).strip('-')
            
            original_slug = slug
            counter = 1
            while BlogCategory.query.filter_by(slug=slug).filter(BlogCategory.id != category_id).first():
                slug = f"{original_slug}-{counter}"
                counter += 1
            
            category.slug = slug
        
        category.name = name
        category.description = description
        category.color = color
        category.icon = icon
        category.sort_order = sort_order
        category.is_active = is_active
        
        db.session.commit()
        
        flash('Категория успешно обновлена!', 'success')
        return redirect(url_for('admin_blog_categories_management'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка обновления категории: {str(e)}', 'error')
        return redirect(url_for('admin_edit_blog_category_new', category_id=category_id))


@app.route('/admin/blog-categories-management/<int:category_id>/delete', methods=['POST'])
@admin_required
def admin_delete_blog_category_new(category_id):
    """Delete blog category"""
    from models import BlogCategory, BlogArticle
    
    try:
        category = BlogCategory.query.get_or_404(category_id)
        
        # Check if category has posts
        posts_count = BlogArticle.query.filter_by(category_id=category_id).count()
        if posts_count > 0:
            flash(f'Нельзя удалить категорию с {posts_count} статьями. Сначала переместите статьи в другие категории.', 'error')
            return redirect(url_for('admin_blog_categories_management'))
        
        db.session.delete(category)
        db.session.commit()
        
        flash('Категория успешно удалена!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка удаления категории: {str(e)}', 'error')
    
    return redirect(url_for('admin_blog_categories_management'))


# Register API blueprint
app.register_blueprint(api_bp)

# Register notification settings blueprint
try:
    from notification_settings import notification_settings_bp
    app.register_blueprint(notification_settings_bp)
except Exception as e:
    print(f"Warning: Could not register notification settings blueprint: {e}")

# Smart Search API Endpoints
@app.route('/api/smart-search')
def smart_search_api():
    """Умный поиск с OpenAI анализом"""
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify({'results': [], 'criteria': {}, 'suggestions': []})
    
    try:
        # Анализируем запрос с помощью OpenAI
        criteria = smart_search.analyze_search_query(query)
        print(f"DEBUG: Smart search criteria: {criteria}")
        
        # Получаем свойства и применяем фильтры
        properties = load_properties()
        # Применяем базовые фильтры на основе критериев
        filtered_properties = apply_smart_filters(properties, criteria)
        
        # Применяем семантический поиск если нужно
        if criteria.get('semantic_search') or criteria.get('features'):
            filtered_properties = smart_search.semantic_property_search(
                filtered_properties, query, criteria
            )
        
        # Подготавливаем результаты
        results = []
        for prop in filtered_properties[:20]:
            results.append({
                'type': 'property',
                'id': prop['id'],
                'title': f"{prop.get('rooms', 0)}-комн {prop.get('area', 0)} м²" if prop.get('rooms', 0) > 0 else f"Студия {prop.get('area', 0)} м²",
                'subtitle': f"{prop.get('complex_name', '')} • {prop['district']}",
                'price': prop['price'],
                'rooms': prop.get('rooms', 1),
                'area': prop.get('area', 0),
                'url': f"/object/{prop['id']}"
            })
        
        # Генерируем подсказки
        suggestions = smart_search.generate_search_suggestions(query)
        
        return jsonify({
            'results': results,
            'criteria': criteria,
            'suggestions': suggestions[:5],
            'total': len(filtered_properties)
        })
        
    except Exception as e:
        print(f"ERROR: Smart search failed: {e}")
        # Fallback к обычному поиску
        return jsonify({'results': [], 'error': str(e)})

@app.route('/api/smart-suggestions')
def smart_suggestions_api():
    """API для получения умных подсказок поиска"""
    query = request.args.get('q', '').strip()
    
    if len(query) < 2:
        return jsonify({'suggestions': []})
    
    try:
        suggestions = smart_search.generate_search_suggestions(query)
        return jsonify({'suggestions': suggestions})
    except Exception as e:
        print(f"ERROR: Smart suggestions failed: {e}")
        return jsonify({'suggestions': []})

def apply_smart_filters(properties, criteria):
    """Применяет умные фильтры на основе критериев OpenAI"""
    filtered = properties.copy()
    
    # Фильтр по комнатам
    if criteria.get('rooms'):
        rooms_list = criteria['rooms']
        filtered = [p for p in filtered if str(p.get('rooms', '')) in rooms_list]
    
    # Фильтр по району
    if criteria.get('district'):
        district = criteria['district']
        filtered = [p for p in filtered if p.get('district', '') == district]
    
    # Фильтр по ключевым словам (типы недвижимости, классы, материалы)
    if criteria.get('keywords'):
        keywords_filtered = []
        for prop in filtered:
            prop_matches = False
            for keyword in criteria['keywords']:
                keyword_lower = keyword.lower()
                
                # Тип недвижимости
                prop_type_lower = prop.get('property_type', 'Квартира').lower()
                if keyword_lower == prop_type_lower:
                    prop_matches = True
                    break
                
                # Класс недвижимости (точное совпадение)
                prop_class_lower = prop.get('property_class', '').lower()
                if keyword_lower == prop_class_lower:
                    prop_matches = True
                    break
                
                # Материал стен
                wall_material_lower = prop.get('wall_material', '').lower()
                if keyword_lower in wall_material_lower:
                    prop_matches = True
                    break
                
                # Особенности
                features = prop.get('features', [])
                if any(keyword_lower in feature.lower() for feature in features):
                    prop_matches = True
                    break
                
                # Особая логика для ценовых категорий
                if keyword_lower == 'дорого' or keyword_lower == 'недорого':
                    # Эти ключевые слова обрабатываются отдельно после фильтрации
                    continue
                
                # Поиск в заголовке как fallback
                property_title = f"{prop.get('rooms', 0)}-комн {prop.get('area', 0)} м²" if prop.get('rooms', 0) > 0 else f"Студия {prop.get('area', 0)} м²"
                title_lower = property_title.lower()
                if keyword_lower in title_lower:
                    prop_matches = True
                    break
            
            if prop_matches:
                keywords_filtered.append(prop)
        
        filtered = keywords_filtered
        
        # Обработка ценовых ключевых слов после основной фильтрации
        if 'дорого' in criteria.get('keywords', []):
            # Сортируем по цене и берем верхние 50%
            filtered = sorted(filtered, key=lambda x: x.get('price', 0), reverse=True)
            filtered = filtered[:max(1, len(filtered)//2)]
        elif 'недорого' in criteria.get('keywords', []):
            # Сортируем по цене и берем нижние 50%
            filtered = sorted(filtered, key=lambda x: x.get('price', 0))
            filtered = filtered[:max(1, len(filtered)//2)]
    
    # Фильтр по особенностям
    if criteria.get('features'):
        features_list = criteria['features']
        features_filtered = []
        for prop in filtered:
            prop_features = [f.lower() for f in prop.get('features', [])]
            if any(feature.lower() in prop_features for feature in features_list):
                features_filtered.append(prop)
        filtered = features_filtered
    
    # Фильтр по цене
    if criteria.get('price_range'):
        price_range = criteria['price_range']
        if len(price_range) >= 1 and price_range[0]:
            min_price = price_range[0]
            filtered = [p for p in filtered if p.get('price', 0) >= min_price]
        if len(price_range) >= 2 and price_range[1]:
            max_price = price_range[1]
            filtered = [p for p in filtered if p.get('price', 0) <= max_price]
    
    return filtered

# Manager Client Management Routes
@app.route('/manager/clients')
@manager_required
def manager_clients():
    """Manager clients page"""
    from models import User, Manager
    
    manager_id = session.get('manager_id')
    manager = Manager.query.get(manager_id)
    
    if not manager:
        return redirect(url_for('manager_login'))
    
    # Get clients assigned to this manager
    clients = User.query.filter_by(assigned_manager_id=manager_id).order_by(User.created_at.desc()).all()
    
    return render_template('manager/clients.html', 
                         manager=manager,
                         clients=clients)

@app.route('/api/manager/add-client', methods=['POST'])
@manager_required
def manager_add_client():
    """Add new client"""
    from models import User, Manager
    import re
    
    manager_id = session.get('manager_id')
    print(f"DEBUG: Add client endpoint called by manager {manager_id}")
    print(f"DEBUG: Request method: {request.method}, Content-Type: {request.content_type}")
    print(f"DEBUG: Request is_json: {request.is_json}")
    
    try:
        # Accept both JSON and form data
        if request.is_json:
            data = request.get_json()
            print(f"DEBUG: Received JSON data: {data}")
            full_name = data.get('full_name', '').strip()
            email = data.get('email', '').strip().lower()
            phone = data.get('phone', '').strip() if data.get('phone') else None
            is_active = data.get('is_active', True)
        else:
            print(f"DEBUG: Received form data: {dict(request.form)}")
            full_name = request.form.get('full_name', '').strip()
            email = request.form.get('email', '').strip().lower()
            phone = request.form.get('phone', '').strip() if request.form.get('phone') else None
            is_active = 'is_active' in request.form
        
        print(f"DEBUG: Parsed data - name: {full_name}, email: {email}, phone: {phone}, active: {is_active}")
        
        # Validation
        if not full_name or len(full_name) < 2:
            return jsonify({'success': False, 'error': 'Полное имя должно содержать минимум 2 символа'}), 400
        
        # Email validation
        email_regex = r'^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$'
        if not email or not re.match(email_regex, email):
            return jsonify({'success': False, 'error': 'Введите корректный email адрес'}), 400
        
        # Phone validation (optional but must be correct format if provided)
        if phone:
            phone_regex = r'^\+7-\d{3}-\d{3}-\d{2}-\d{2}$'
            if not re.match(phone_regex, phone):
                return jsonify({'success': False, 'error': 'Телефон должен быть в формате +7-918-123-45-67'}), 400
        
        # Check if email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({'success': False, 'error': 'Пользователь с таким email уже существует'}), 400
        
        # Generate temporary password
        import secrets
        import string
        temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))
        
        # Create new user with temporary password
        user = User(
            full_name=full_name,
            email=email,
            phone=phone,
            is_active=is_active,
            role='buyer',
            assigned_manager_id=manager_id,
            registration_source='Manager',
            client_status='Новый'
        )
        user.set_password(temp_password)  # Set temporary password
        
        db.session.add(user)
        db.session.commit()
        
        print(f"DEBUG: Successfully created client {user.id}: {user.full_name}")
        
        # Send welcome email and SMS with credentials
        try:
            from email_service import send_email
            manager = Manager.query.get(manager_id)
            manager_name = manager.full_name if manager else 'Ваш менеджер'
            
            # Email with login credentials
            subject = "Ваш аккаунт создан в InBack.ru - Данные для входа"
            email_content = f"""Здравствуйте, {full_name}!

Для вас создан аккаунт на платформе InBack.ru

📧 Email для входа: {email}
🔑 Временный пароль: {temp_password}

🌐 Ссылка для входа: {request.url_root.rstrip('/')}/login

ВАЖНО: Рекомендуем сменить пароль после первого входа в разделе "Настройки профиля"

Ваш персональный менеджер: {manager_name}

По всем вопросам обращайтесь к своему менеджеру.

С уважением,
Команда InBack.ru"""
            
            send_email(
                to_email=email,
                subject=subject,
                content=email_content,
                template_name='notification'
            )
            print(f"DEBUG: Welcome email with credentials sent to {email}")
            
            # Send SMS if phone number provided
            if phone:
                try:
                    from sms_service import send_login_credentials_sms
                    
                    sms_sent = send_login_credentials_sms(
                        phone=phone,
                        email=email,
                        password=temp_password,
                        manager_name=manager_name,
                        login_url=f"{request.url_root.rstrip('/')}/login"
                    )
                    
                    if sms_sent:
                        print(f"DEBUG: SMS sent successfully to {phone}")
                    else:
                        print(f"DEBUG: SMS sending failed for {phone}")
                    
                except Exception as sms_e:
                    print(f"DEBUG: Failed to send SMS: {sms_e}")
                    
        except Exception as e:
            print(f"DEBUG: Failed to send welcome email: {e}")
        
        return jsonify({
            'success': True, 
            'client_id': user.id,
            'message': f'Клиент {full_name} успешно добавлен. Данные для входа отправлены на email {email}' + (f' и SMS на {phone}' if phone else '') + '.',
            'client_data': {
                'id': user.id,
                'full_name': user.full_name,
                'email': user.email,
                'phone': user.phone,
                'user_id': user.user_id,
                'login_url': f"{request.url_root.rstrip('/')}/login",
                'temp_password': temp_password  # Include for manager reference
            }
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error adding client: {str(e)}")
        return jsonify({'success': False, 'error': f'Ошибка сервера: {str(e)}'}), 500

@app.route('/manager/get-client/<int:client_id>')
@manager_required
def manager_get_client(client_id):
    """Get client data for editing"""
    from models import User
    
    try:
        manager_id = session.get('manager_id')
        print(f"DEBUG: Get client {client_id}, manager_id: {manager_id}")
        
        # Try to find client assigned to this manager first, then any buyer
        client = User.query.filter_by(id=client_id, assigned_manager_id=manager_id).first()
        if not client:
            client = User.query.filter_by(id=client_id, role='buyer').first()
        
        print(f"DEBUG: Found client: {client}")
        
        if not client:
            return jsonify({'success': False, 'error': 'Клиент не найден'}), 404
        
        response_data = {
            'success': True,
            'id': client.id,
            'full_name': client.full_name or '',
            'email': client.email or '',
            'phone': client.phone or '',
            'is_active': client.is_active if hasattr(client, 'is_active') else True
        }
        print(f"DEBUG: Returning client data: {response_data}")
        return jsonify(response_data)
        
    except Exception as e:
        print(f"DEBUG: Exception in get_client: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/manager/edit-client', methods=['POST'])
@manager_required
def manager_edit_client():
    """Edit existing client"""
    from models import User
    
    manager_id = session.get('manager_id')
    
    try:
        client_id = request.form.get('client_id')
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        is_active = 'is_active' in request.form
        
        if not client_id:
            return jsonify({'success': False, 'error': 'ID клиента не указан'}), 400
        
        # Try to find client assigned to this manager first, then any buyer
        client = User.query.filter_by(id=client_id, assigned_manager_id=manager_id).first()
        if not client:
            client = User.query.filter_by(id=client_id, role='buyer').first()
        
        if not client:
            return jsonify({'success': False, 'error': 'Клиент не найден'}), 404
        
        if not all([full_name, email]):
            return jsonify({'success': False, 'error': 'Заполните обязательные поля'}), 400
        
        # Check if email already exists (excluding current client)
        existing_user = User.query.filter(User.email == email, User.id != client_id).first()
        if existing_user:
            return jsonify({'success': False, 'error': 'Пользователь с таким email уже существует'}), 400
        
        # Update client data
        client.full_name = full_name
        client.email = email
        client.phone = phone
        client.is_active = is_active
        client.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/manager/delete-client', methods=['POST'])
@manager_required
def manager_delete_client():
    """Delete client"""
    from models import User
    
    manager_id = session.get('manager_id')
    
    try:
        # Handle both JSON and form data
        if request.content_type == 'application/json':
            data = request.get_json()
            client_id = data.get('client_id')
        else:
            client_id = request.form.get('client_id')
        
        if not client_id:
            return jsonify({'success': False, 'error': 'ID клиента не указан'}), 400
        
        # Try to find client assigned to this manager first, then any buyer
        client = User.query.filter_by(id=client_id, assigned_manager_id=manager_id).first()
        if not client:
            client = User.query.filter_by(id=client_id, role='buyer').first()
        
        if not client:
            return jsonify({'success': False, 'error': 'Клиент не найден'}), 404
        
        # Instead of deleting, mark as inactive
        client.is_active = False
        client.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

def send_callback_notification_email(callback_req, manager):
    """Send email notification about callback request"""
    try:
        from email_service import send_email
        
        # Email content
        subject = f"Новая заявка на обратный звонок - {callback_req.name}"
        
        # Build message content
        content = f"""
        Получена новая заявка на обратный звонок:
        
        Клиент: {callback_req.name}
        Телефон: {callback_req.phone}
        Email: {callback_req.email or 'Не указан'}
        Удобное время: {callback_req.preferred_time}
        
        Интересует: {callback_req.interest}
        Бюджет: {callback_req.budget}
        Планирует покупку: {callback_req.timing}
        
        Дополнительно: {callback_req.notes or 'Нет дополнительной информации'}
        
        Назначенный менеджер: {manager.full_name if manager else 'Не назначен'}
        Дата заявки: {callback_req.created_at.strftime('%d.%m.%Y %H:%M')}
        """
        
        # Try to send to manager first, then to admin email
        recipient_email = manager.email if manager else 'admin@inback.ru'
        
        success = send_email(
            to_email=recipient_email,
            subject=subject,
            content=content,
            template_name='notification'
        )
        
        if success:
            print(f"✓ Callback notification email sent to {recipient_email}")
        else:
            print(f"✗ Failed to send callback notification email to {recipient_email}")
            
    except Exception as e:
        print(f"Error sending callback notification email: {e}")


def send_callback_notification_telegram(callback_req, manager):
    """Send Telegram notification about callback request"""
    try:
        # Check if telegram_bot module can be imported
        try:
            from telegram_bot import send_telegram_message
        except ImportError as e:
            print(f"Telegram bot not available: {e}")
            return False
        
        # Calculate potential cashback
        potential_cashback = ""
        if callback_req.budget:
            if "млн" in callback_req.budget:
                # Extract average from range like "3-5 млн"
                numbers = [float(x) for x in callback_req.budget.replace(" млн", "").replace("руб", "").split("-") if x.strip().replace(".", "").replace(",", "").isdigit()]
                if numbers:
                    avg_price = sum(numbers) / len(numbers) * 1000000
                    cashback = int(avg_price * 0.02)
                    potential_cashback = f"💰 *Потенциальный кэшбек:* {cashback:,} руб. (2%)\n"
        
        # Enhanced Telegram message
        message = f"""📞 *НОВАЯ ЗАЯВКА НА ОБРАТНЫЙ ЗВОНОК*

👤 *КОНТАКТНАЯ ИНФОРМАЦИЯ:*
• Имя: {callback_req.name}
• Телефон: {callback_req.phone}
• Email: {callback_req.email or 'Не указан'}
• Удобное время звонка: {callback_req.preferred_time}

🔍 *КРИТЕРИИ ПОИСКА:*
• Интересует: {callback_req.interest or 'Не указано'}
• Бюджет: {callback_req.budget or 'Не указан'}
• Планы на покупку: {callback_req.timing or 'Не указано'}

{potential_cashback}📝 *ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ:*
{callback_req.notes or 'Нет дополнительной информации'}

📅 *ВРЕМЯ ЗАЯВКИ:* {callback_req.created_at.strftime('%d.%m.%Y в %H:%M')}
🌐 *ИСТОЧНИК:* Форма обратного звонка на сайте InBack.ru
👨‍💼 *НАЗНАЧЕННЫЙ МЕНЕДЖЕР:* {manager.full_name if manager else 'Не назначен'}

📋 *СЛЕДУЮЩИЕ ШАГИ:*
1️⃣ Перезвонить клиенту в указанное время
2️⃣ Провести консультацию по критериям
3️⃣ Подготовить персональную подборку
4️⃣ Запланировать показы объектов

⚡ *ВАЖНО:* Соблюдайте время, удобное для клиента!"""
        
        # Always send to admin chat for now
        chat_id = "730764738"  # Admin chat
        
        success = send_telegram_message(chat_id, message)
        
        if success:
            print(f"✓ Callback notification sent to Telegram chat {chat_id}")
        else:
            print(f"✗ Failed to send callback notification to Telegram")
            
    except Exception as e:
        print(f"Error sending callback notification to Telegram: {e}")


# Initialize database tables after all imports
try:
    with app.app_context():
        # Import models here to create tables
        from models import User, Manager, SavedSearch
        db.create_all()
        print("Database tables created successfully!")
except Exception as e:
    print(f"Error creating database tables: {e}")

@app.route('/api/blog/search')
def blog_search_api():
    """API endpoint for instant blog search and suggestions"""
    from models import BlogPost, BlogCategory
    from sqlalchemy import or_, func
    
    try:
        query = request.args.get('q', '').strip()
        category = request.args.get('category', '').strip()
        suggestions_only = request.args.get('suggestions', '').lower() == 'true'
        
        # Start with base query - use BlogPost (where data actually is)
        search_query = BlogPost.query.filter(BlogPost.status == 'published')
        
        # Apply search filter
        if query:
            search_query = search_query.filter(
                or_(
                    BlogPost.title.ilike(f'%{query}%'),
                    BlogPost.content.ilike(f'%{query}%'),
                    BlogPost.excerpt.ilike(f'%{query}%')
                )
            )
        
        # Apply category filter
        if category:
            search_query = search_query.filter(BlogPost.category == category)
        
        # For suggestions, limit to title matches only
        if suggestions_only:
            if query:
                suggestions = search_query.filter(
                    BlogPost.title.ilike(f'%{query}%')
                ).limit(5).all()
                
                return jsonify({
                    'suggestions': [{
                        'title': post.title,
                        'slug': post.slug,
                        'category': post.category or 'Общее'
                    } for post in suggestions]
                })
            else:
                return jsonify({'suggestions': []})
        
        # For full search, return formatted articles
        articles = search_query.order_by(BlogPost.created_at.desc()).limit(20).all()
        
        formatted_articles = []
        for article in articles:
            formatted_articles.append({
                'title': article.title,
                'slug': article.slug,
                'excerpt': article.excerpt or '',
                'featured_image': article.featured_image or '',
                'category': article.category or 'Общее',
                'date': article.created_at.strftime('%d.%m.%Y'),
                'reading_time': getattr(article, 'reading_time', 5),
                'views': getattr(article, 'views', 0)
            })
        return jsonify({
            'articles': formatted_articles,
            'total': len(formatted_articles)
        })
        
    except Exception as e:
        print(f"ERROR in blog search API: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Search failed', 'articles': [], 'suggestions': []}), 500

# Developer Scraper Management Endpoints
@app.route('/admin/scraper')
@admin_required
def admin_scraper():
    """Admin panel for developer scraper management"""
    from models import Admin
    
    admin_id = session.get('admin_id')
    admin = Admin.query.get(admin_id)
    
    return render_template('admin/scraper.html', admin=admin)

@app.route('/admin/scraper/run', methods=['POST'])
@admin_required
def run_scraper():
    """Run the developer scraper"""
    try:
        from property_scraper_integration import PropertyScraperIntegration
        
        integration = PropertyScraperIntegration()
        result = integration.run_full_scraping_and_integration()
        
        return jsonify({
            'success': True,
            'message': 'Парсинг успешно выполнен',
            'stats': result['integration_stats'],
            'backup_file': result['json_backup'],
            'timestamp': result['timestamp']
        })
        
    except Exception as e:
        print(f"Scraper error: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'message': f'Ошибка при парсинге: {str(e)}'
        }), 500

@app.route('/admin/scraper/test', methods=['POST'])
@admin_required
def test_scraper():
    """Test scraper without database integration"""
    try:
        from web_scraper import KrasnodarDeveloperScraper
        
        scraper = KrasnodarDeveloperScraper()
        data = scraper.scrape_all_developers()
        
        # Calculate stats
        total_projects = sum(len(projects) for projects in data.values())
        total_apartments = sum(
            len(project.get('apartments', [])) 
            for projects in data.values() 
            for project in projects
        )
        
        return jsonify({
            'success': True,
            'message': 'Тестовый парсинг выполнен',
            'data': data,
            'stats': {
                'total_projects': total_projects,
                'total_apartments': total_apartments
            }
        })
        
    except Exception as e:
        print(f"Scraper test error: {e}")
        return jsonify({
            'success': False,
            'message': f'Ошибка при тестировании: {str(e)}'
        }), 500

@app.route('/admin/scraper/files')
@admin_required
def scraper_files():
    """List scraped data files"""
    try:
        import glob
        import os
        from datetime import datetime
        
        files = glob.glob('scraped_developers_*.json')
        file_info = []
        
        for file in files:
            stat = os.stat(file)
            file_info.append({
                'name': file,
                'size': stat.st_size,
                'created': datetime.fromtimestamp(stat.st_ctime).strftime('%d.%m.%Y %H:%M'),
                'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%d.%m.%Y %H:%M')
            })
        
        # Sort by creation time, newest first
        file_info.sort(key=lambda x: x['modified'], reverse=True)
        
        return jsonify({
            'success': True,
            'files': file_info
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Ошибка при получении списка файлов: {str(e)}'
        }), 500

@app.route('/admin/scraper/view-file/<filename>')
@admin_required
def view_scraped_file(filename):
    """View scraped data file content"""
    try:
        import json
        import os
        
        # Security check - only allow scraped files
        if not filename.startswith('scraped_developers_') or not filename.endswith('.json'):
            return jsonify({'success': False, 'message': 'Недопустимое имя файла'}), 400
        
        if not os.path.exists(filename):
            return jsonify({'success': False, 'message': 'Файл не найден'}), 404
        
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return jsonify({
            'success': True,
            'data': data,
            'filename': filename
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Ошибка при чтении файла: {str(e)}'
        }), 500

if __name__ == '__main__':
    # Telegram webhook integration
    try:
        from telegram_bot import create_webhook_route
        create_webhook_route(app)
    except ImportError as e:
        print(f"Telegram bot setup failed: ImportError with telegram package")
    
    print("Database tables and API blueprint registered successfully!")
    app.run(debug=True, host='0.0.0.0', port=5000)