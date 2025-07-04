from flask import Flask, render_template, request, redirect, url_for, flash
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import sqlite3
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'kashmiri_pandit_directory'

# Ensure the instance folder exists
os.makedirs(app.instance_path, exist_ok=True)
DB_PATH = os.path.join(app.instance_path, 'users.db')

def init_db():
    """Initialize the database with the users and events tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Create users table with expanded fields
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            city TEXT NOT NULL,
            country TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            contact_info TEXT,
            kashmir_residence TEXT,
            village_city TEXT
        )
    ''')
    
    # Create events table
    c.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            event_date TEXT NOT NULL,
            location TEXT NOT NULL,
            city TEXT NOT NULL,
            country TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            host_name TEXT NOT NULL,
            host_contact TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def geocode(address):
    """Convert address to latitude and longitude using Nominatim geocoder."""
    geolocator = Nominatim(user_agent="global_kashmiri_pandit_directory")
    try:
        location = geolocator.geocode(address)
        if location:
            return location.latitude, location.longitude
        return None, None
    except Exception as e:
        print(f"Geocoding error: {e}")
        return None, None

def add_user_to_db(name, city, country, lat, lon, contact_info="", kashmir_residence="", village_city=""):
    """Add a new user to the database with expanded information."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO users (name, city, country, latitude, longitude, contact_info, kashmir_residence, village_city) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (name, city, country, lat, lon, contact_info, kashmir_residence, village_city))
    conn.commit()
    conn.close()

def get_all_users():
    """Get all users from the database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM users')
    users = [dict(row) for row in c.fetchall()]
    conn.close()
    return users

def find_nearby_users(user_lat, user_lon, radius_km=50):
    """Find users within a given radius of the specified coordinates."""
    all_users = get_all_users()
    nearby_users = []
    
    for user in all_users:
        # Calculate distance between the two points
        user_coords = (user['latitude'], user['longitude'])
        search_coords = (user_lat, user_lon)
        
        # Calculate the distance in kilometers
        distance = geodesic(search_coords, user_coords).kilometers
        
        if distance <= radius_km:
            user['distance'] = round(distance, 2)
            nearby_users.append(user)
    
    # Sort nearby users by distance
    nearby_users.sort(key=lambda x: x['distance'])
    return nearby_users

@app.route('/')
def index():
    """Home page with upcoming events."""
    # Get upcoming events
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM events ORDER BY event_date LIMIT 5')
    upcoming_events = [dict(row) for row in c.fetchall()]
    conn.close()
    
    return render_template('index.html', upcoming_events=upcoming_events)

@app.route('/add', methods=['GET', 'POST'])
def add():
    """Add a new user to the directory with expanded information."""
    if request.method == 'POST':
        name = request.form.get('name')
        city = request.form.get('city')
        country = request.form.get('country')
        contact_info = request.form.get('contact_info', '')
        kashmir_residence = request.form.get('kashmir_residence', '')
        village_city = request.form.get('village_city', '')
        
        if not name or not city or not country:
            flash('Please fill out all required fields', 'error')
            return render_template('add.html')
        
        # Geocode the address
        address = f"{city}, {country}"
        lat, lon = geocode(address)
        
        if lat is None or lon is None:
            flash('Could not determine the location. Please check the city and country names.', 'error')
            return render_template('add.html')
        
        # Add user to database with expanded info
        add_user_to_db(name, city, country, lat, lon, contact_info, kashmir_residence, village_city)
        flash('Your information has been added to the directory!', 'success')
        return redirect(url_for('index'))
    
    return render_template('add.html')

@app.route('/search', methods=['GET', 'POST'])
def search():
    """Search for users near a location."""
    if request.method == 'POST':
        city = request.form.get('city')
        country = request.form.get('country')
        radius_km = request.form.get('radius', 50, type=int)
        
        if not city or not country:
            flash('Please fill out city and country', 'error')
            return render_template('search.html')
        
        # Geocode the search location
        address = f"{city}, {country}"
        lat, lon = geocode(address)
        
        if lat is None or lon is None:
            flash('Could not determine the location. Please check the city and country names.', 'error')
            return render_template('search.html')
        
        # Find nearby users
        nearby_users = find_nearby_users(lat, lon, radius_km)
        
        return render_template('results.html', 
                              users=nearby_users, 
                              search_location=address,
                              radius=radius_km)
    
    return render_template('search.html')

# New route for Digital Village
@app.route('/digital_village', methods=['GET', 'POST'])
def digital_village():
    """Show users from the same village/city in Kashmir."""
    if request.method == 'POST':
        village_city = request.form.get('village_city')
        
        if not village_city:
            flash('Please enter a village or city name', 'error')
            return render_template('digital_village.html')
        
        # Search for users from the same village/city
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        # Case-insensitive search with LIKE
        c.execute('SELECT * FROM users WHERE LOWER(village_city) LIKE ?', 
                 ('%' + village_city.lower() + '%',))
        village_users = [dict(row) for row in c.fetchall()]
        conn.close()
        
        return render_template('digital_village.html', 
                              village_users=village_users, 
                              search_term=village_city)
    
    return render_template('digital_village.html')

# Events routes
@app.route('/events')
def events():
    """Show all upcoming events."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM events ORDER BY event_date')
    all_events = [dict(row) for row in c.fetchall()]
    conn.close()
    
    return render_template('events.html', events=all_events)

@app.route('/add_event', methods=['GET', 'POST'])
def add_event():
    """Add a new event."""
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        event_date = request.form.get('event_date')
        location = request.form.get('location')
        city = request.form.get('city')
        country = request.form.get('country')
        host_name = request.form.get('host_name')
        host_contact = request.form.get('host_contact')
        
        # Validate required fields
        if not title or not description or not event_date or not location or not city or not country or not host_name or not host_contact:
            flash('Please fill out all required fields', 'error')
            return render_template('add_event.html')
        
        # Geocode the event location
        address = f"{location}, {city}, {country}"
        lat, lon = geocode(address)
        
        if lat is None or lon is None:
            flash('Could not determine the location. Please check the address details.', 'error')
            return render_template('add_event.html')
        
        # Add event to database
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            INSERT INTO events (title, description, event_date, location, city, country, 
                              latitude, longitude, host_name, host_contact) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (title, description, event_date, location, city, country, lat, lon, host_name, host_contact))
        conn.commit()
        conn.close()
        
        flash('Your event has been added!', 'success')
        return redirect(url_for('events'))
    
    return render_template('add_event.html')

@app.route('/nearby_events', methods=['GET', 'POST'])
def nearby_events():
    """Find events near a location."""
    if request.method == 'POST':
        city = request.form.get('city')
        country = request.form.get('country')
        radius_km = request.form.get('radius', 50, type=int)
        
        if not city or not country:
            flash('Please fill out city and country', 'error')
            return render_template('nearby_events.html')
        
        # Geocode the search location
        address = f"{city}, {country}"
        lat, lon = geocode(address)
        
        if lat is None or lon is None:
            flash('Could not determine the location. Please check the city and country names.', 'error')
            return render_template('nearby_events.html')
        
        # Get all events
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM events')
        all_events = [dict(row) for row in c.fetchall()]
        conn.close()
        
        # Find nearby events
        nearby_events = []
        for event in all_events:
            # Calculate distance between the two points
            event_coords = (event['latitude'], event['longitude'])
            search_coords = (lat, lon)
            
            # Calculate the distance in kilometers
            distance = geodesic(search_coords, event_coords).kilometers
            
            if distance <= radius_km:
                event['distance'] = round(distance, 2)
                nearby_events.append(event)
        
        # Sort nearby events by distance
        nearby_events.sort(key=lambda x: x['distance'])
        
        return render_template('nearby_events_results.html', 
                              events=nearby_events, 
                              search_location=address,
                              radius=radius_km)
    
    return render_template('nearby_events.html')

if __name__ == '__main__':
    init_db()  # Initialize the database before starting the app
    app.run(debug=True)