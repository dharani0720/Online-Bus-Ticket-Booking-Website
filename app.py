from flask import Flask, render_template, request, redirect,url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bus_booking.db'
app.config['SECRET_KEY'] = 'your_secret_key'
db = SQLAlchemy(app)

# User Model (Admin & Passenger)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(10), nullable=False)  

# Bus Model
class Bus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    source = db.Column(db.String(50), nullable=False)
    destination = db.Column(db.String(50), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    price = db.Column(db.Float, nullable=False)
    total_seats = db.Column(db.Integer, nullable=False)
    available_seats = db.Column(db.Integer, nullable=False)


# Booking Model - Added 'status' field to track canceled bookings
class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    bus_id = db.Column(db.Integer, nullable=False)
    seats_booked = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default="Booked")  

#  Home Page
@app.route('/')
def home():
    return render_template("home.html")

#  Registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        if role=='admin':
            existing_admin=User.query.filter_by(role='admin').first()
            if existing_admin:
                flash("Admin already exists.Only one admin can be registered.",'danger')
                return redirect(url_for('register'))
        hashed_password=generate_password_hash(password,method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password, role=role)
        db.session.add(new_user)
        db.session.commit()
        flash(f'Registration successful as {role}! You can now login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

#  Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
                session['user_id'] = user.id
                session['role'] = user.role
            
                if user.role == 'admin':
                    return redirect(url_for('admin'))
                elif user.role == 'passenger':
                    return redirect(url_for('passenger'))
        else:
            flash('Invalid credentials', 'danger')
    
    return render_template('login.html')


# Admin Dashboard (Manage Buses)
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        bus = Bus(
            name=request.form['name'],
            source=request.form['source'],
            destination=request.form['destination'],
            date=request.form['date'],
            price=float(request.form['price']),
            total_seats=int(request.form['total_seats']),
            available_seats=int(request.form['total_seats']),
        )
        db.session.add(bus)
        db.session.commit()
        flash('Bus added successfully!', 'success')
        return(redirect(url_for('bus_details')))
    buses = Bus.query.all()
    return render_template('admin.html',buses=buses)

#  Admin Dashboard (To Show & Delete Buses)
@app.route('/bus_details')
def bus_details():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    buses = Bus.query.all()
    return render_template('bus_details.html', buses=buses)

#  Delete Bus
@app.route('/delete_bus/<int:bus_id>', methods=['POST'])
def delete_bus(bus_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    bus = Bus.query.get(bus_id)
    if bus:
        db.session.delete(bus)
        db.session.commit()
        flash('Bus deleted successfully!', 'success')
    
    return redirect(url_for('admin'))

@app.route('/view_bookings')
def view_bookings():
    if 'role' not in session or session['role'] != 'admin':
        flash("Access denied! Admins only.", "danger")
        return redirect(url_for('login'))

    # Fetch all bookings with user details and passenger details
    bookings = db.session.query(
        Booking.id, User.username, Bus.name.label("bus_name"), Bus.source, 
        Bus.destination, Bus.date, Bus.price, Booking.seats_booked, 
        Booking.status, (Bus.price * Booking.seats_booked).label('total_price')
    ).join(User, Booking.user_id == User.id) \
     .join(Bus, Booking.bus_id == Bus.id) \
     .all()

    return render_template('view_bookings.html', bookings=bookings)



#  Passenger Dashboard (Search & Book Bus)
@app.route('/passenger', methods=['GET', 'POST'])
def passenger():
    if 'role' not in session or session['role'] != 'passenger':
        return redirect(url_for('login'))

    buses = Bus.query.all()  # Show all buses by default
    if request.method == 'POST':
        source = request.form['source']
        destination = request.form['destination']
        buses = Bus.query.filter_by(source=source, destination=destination).all()
    return render_template('passenger.html', buses=buses)



#  Booking with Payment Confirmation
@app.route('/book_bus/<int:bus_id>',methods=['GET','POST'])
def book_bus(bus_id):
    if 'role' not in session or session['role'] != 'passenger':
        return redirect(url_for('login'))

    bus = Bus.query.get(bus_id)
    
    if request.method=='POST':
        seats_requested=request.form.get('seats',type=int,default=1)
        if bus and bus.available_seats >= seats_requested:
            bus.available_seats -= seats_requested
            booking = Booking(user_id=session['user_id'], bus_id=bus.id, seats_booked=seats_requested)
            db.session.add(booking)
            db.session.commit()

            # Store booking details in session
            session['booking_details'] = {
                'total_price': bus.price * seats_requested
            }
            
            flash(f'Booking successful for {seats_requested} seat(s)!!! ', 'success')
            return redirect(url_for('payment_success'))
    return render_template('book_bus.html',bus= bus)


#  View & Cancel Bookings (Passenger)
@app.route('/my_bookings')
def my_bookings():
    if 'role' not in session or session['role'] != 'passenger':
        return redirect(url_for('login'))

    user_id = session['user_id']
    
    bookings = db.session.query(
        Booking.id, Bus.name, Bus.source, Bus.destination, 
        Bus.date, Bus.price, Booking.seats_booked, Booking.bus_id,
        Booking.status, (Bus.price * Booking.seats_booked).label('total_price')
    ).join(Bus, Booking.bus_id == Bus.id).filter(Booking.user_id == user_id).all()

    return render_template('my_bookings.html', bookings=bookings)
    
@app.route('/cancel_booking/<int:booking_id>', methods=['POST'])
def cancel_booking(booking_id):
    if 'role' not in session or session['role'] != 'passenger':
        return redirect(url_for('login'))

    booking = Booking.query.get(booking_id)

    if booking and booking.user_id == session['user_id']:
        # Update status instead of deleting the row
        booking.status = "Cancelled"
        
        # Refund seats to the bus
        bus = Bus.query.get(booking.bus_id)
        if bus:
            bus.available_seats += booking.seats_booked

        db.session.commit()
        flash('Booking canceled successfully!', 'success')
    
    return redirect(url_for('my_bookings'))



#  Payment Success Page
@app.route('/payment_success')
def payment_success():
    if 'booking_details' not in session:
        return redirect(url_for('passenger'))  # Redirect if no booking details found

    booking_details = session.pop('booking_details', None)  # Get and clear session data
    return render_template('payment_success.html', booking=booking_details)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/edit_bus/<int:bus_id>', methods=['GET', 'POST'])
def edit_bus(bus_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    bus = Bus.query.get(bus_id)

    if request.method == 'POST':
        bus.name = request.form['name']
        bus.source = request.form['source']
        bus.destination = request.form['destination']
        bus.date = request.form['date']
        bus.price = float(request.form['price'])
        bus.total_seats = int(request.form['total_seats'])
        bus.available_seats = int(request.form['available_seats'])

        db.session.commit()
        flash('Bus updated successfully!', 'success')
        return redirect(url_for('bus_details'))

    return render_template('edit_bus.html', bus=bus)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

