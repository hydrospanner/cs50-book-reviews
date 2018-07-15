import os
import requests
from flask import Flask, session, render_template, redirect, url_for, request
from flask_session import Session
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, FloatField
from wtforms.validators import InputRequired, Email, Length
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy  import SQLAlchemy

from secrets import GOODREADS_KEY


# Check for environment variable, prioritize URL from secrets.py
if not os.getenv("DATABASE_URL"):
    try:
        from secrets import DATABASE_URL
    except ImportError:
        raise ImportError("DATABASE_URL is not set and no secrets.py found")
else:
    DATABASE_URL = os.getenv("DATABASE_URL")

app = Flask(__name__)
Bootstrap(app)
app.config['SECRET_KEY'] = "I'M A SECRET"
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(15), unique=True)
    email = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(80))

    def __repr__(self):
        return '<User %r>' % self.username

class Reviews(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    isbn = db.Column(db.String(50))
    review_text = db.Column(db.String(10000), nullable=False)
    rating = db.Column(db.Float())

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class ReviewForm(FlaskForm):
    review_text = StringField('review_text', validators=[InputRequired(), Length(min=10, max=10000)])
    rating = FloatField('rating', validators=[InputRequired()])

class LoginForm(FlaskForm):
    username = StringField('username', validators=[InputRequired(), Length(min=4, max=15)])
    password = PasswordField('password', validators=[InputRequired(), Length(min=8, max=80)])
    remember = BooleanField('remember me')

class RegisterForm(FlaskForm):
    email = StringField('email', validators=[InputRequired(), Email(message='Invalid email'), Length(max=50)])
    username = StringField('username', validators=[InputRequired(), Length(min=4, max=15)])
    password = PasswordField('password', validators=[InputRequired(), Length(min=8, max=80)])

def c_dict_list(column_names, l):
    # return dictionary of rows with column keys
    return [{c_name: col for c_name, col in zip(column_names, row)} for row in l]

@app.route("/")
def index():
    books = db.session.execute('SELECT title, year, isbn FROM books ORDER BY RANDOM() LIMIT 15').fetchall()
    if current_user.is_anonymous:
        return render_template('home.html', books=books)
    return render_template('home.html', books=books, name=current_user.username)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            login_user(user, remember=form.remember.data)
            return redirect(url_for('search'))
        return '<h1>Invalid username or password</h1>'
    return render_template('login.html', form=form)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = RegisterForm()
    if form.validate_on_submit():
        new_user = User(username=form.username.data, email=form.email.data, password=form.password.data)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('signup.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

def add_wildcard_symbols(l):
    return (f'%{i}%' for i in l)

@app.route('/search', methods=['GET', 'POST'])
@login_required
def search():
    if request.method == 'GET':
        return render_template('search.html')
    isbn, title, author = add_wildcard_symbols([request.form['isbn'], request.form['title'], request.form['author']])
    l = db.session.execute('SELECT * FROM books WHERE isbn LIKE :isbn AND title LIKE :title AND author LIKE :author LIMIT 500',
                  {'isbn': isbn, 'title': title, 'author': author}).fetchall()
    l = [{'isbn': isbn, 'title': title, 'author': author, 'year': year} for isbn, title, author, year in l]
    return render_template('searchresults.html', books=l, name=current_user.username)

@app.route('/book/<isbn>', methods=['GET', 'POST'])
@login_required
def book_detail(isbn):
    form = ReviewForm()
    book = db.session.execute('SELECT title, author, year FROM books WHERE isbn = :isbn', {'isbn': isbn}).fetchone()
    if not book:
        return 'invalid ISBN'
    
    if request.method == 'POST':
        if not form.validate_on_submit():
            return 'invalid rating'
        new_review = Reviews(user_id=current_user.id, isbn=isbn, review_text=form.review_text.data,
                             rating=form.rating.data)
        db.session.add(new_review)
        db.session.commit()
    title, author, year = book
    d = {'isbn': isbn, 'title': title, 'author': author, 'year': year}
    good_reads = good_reads_data(isbn)
    reviews = Reviews.query.filter_by(isbn=isbn).all()
    return render_template('book.html', book=d, good_reads=good_reads, form=form, reviews=reviews,
                           name=current_user.username)

def good_reads_data(isbn):
    url = "https://www.goodreads.com/book/review_counts.json"
    res = requests.get(url, params={"key": GOODREADS_KEY, "isbns": isbn})
    if res.status_code == 200:
        return res.json()['books'][0]

if __name__ == '__main__':
    app.run(debug=True)
