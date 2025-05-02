from flask import Flask, render_template, request, redirect, session, url_for
from auth import register_user, login_user
from invoices import get_open_invoices
from utils import berechne_monatsüberschuss

app = Flask(__name__)
app.secret_key = "supergeheim"

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        register_user(request.form['username'], request.form['password'])
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = login_user(request.form['username'], request.form['password'])
        if user_id:
            session['user_id'] = user_id
            return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    einkommen = None
    uebrig = None

    if request.method == 'POST':
        einkommen = float(request.form['einkommen'])
        uebrig = berechne_monatsüberschuss(session['user_id'], einkommen)

    rechnungen = get_open_invoices(session['user_id'])
    return render_template('dashboard.html', rechnungen=rechnungen, uebrig=uebrig)

if __name__ == '__main__':
    app.run(debug=True)
