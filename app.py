from flask import Flask, render_template, request, redirect, flash, session, url_for
from flask_session import Session
from helpers import apology, login_required, day
import sqlite3
from werkzeug.security import generate_password_hash,check_password_hash
from datetime import datetime, timedelta
from threading import Lock

# Configure applications
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["day"] = day

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# connecting to the database 
connection = sqlite3.connect("timesheet.db", check_same_thread=False)

# cursor  
c = connection.cursor() 

# Recursive use of cursors fix
lock = Lock()

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST (as by submiting a form via POST)
    if request.method == "POST":
        
        # Storing the username and password in a variable
        username = request.form.get("username")
        password = request.form.get("password")

        # Ensure a username was provided server side if JS was disable by user
        if not username:
            return apology("must provide username")

        # Query database for username
        c.execute("SELECT * FROM users WHERE username = :username", {"username": username})

        # Ensure username already doesn't exists
        rows = c.fetchone()
        if rows != None:
            return apology("username already exists!")
        
        # Password is not empty and passwords match
        if not password:
            return apology("must provide password")
        elif password != request.form.get("confirmation"):
            return apology("passwords do not match!")

        c.execute("INSERT INTO users (username, hash) VALUES (?, ?)",
                    (username, generate_password_hash(password)))

        # Save (commit) the changes
        connection.commit()
        

        # Remember which user has logged in
        c.execute("SELECT * FROM users WHERE username = :username", {"username": username})
        # Fetch the next row of the query result return a tuple
        rows = c.fetchone()
        # First element in the tuple is the id of the user
        session["user_id"] = rows[0]

        flash("Registered!")
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/")
@login_required
def index():
    # Show all the companies user works for
    c.execute("SELECT * FROM company WHERE user_id=:id",
             {"id":session.get('user_id')})

    # fetchall() to get all the rows returned instead of fetchone 
    rows = c.fetchall()

    # list of colors for different workplaces
    colors = ['#0074D9','#FF4136','#3D9970','#FF851B','#39CCCC','85144b','#F012BE','#AAAAA','#01FF70','#001f3f']

    return render_template("index.html", companies=rows, colors=colors)


# Accessing a variable url via <>
@app.route("/week/<cname>", methods=["GET","POST"])
@login_required
def week(cname):
    """Let user note down hours worked"""

    # if user provides a filter date
    filter_date = request.form.get("filter-date")

    if filter_date == None:
        today = datetime.now().date()
    else:
        # converting str into datetime object
        today = datetime.strptime(filter_date, '%Y-%m-%d')

    day = request.form.getlist('date')
    print(day)

    start_day = today - timedelta(days=today.weekday())
    end_day = start_day + timedelta(days=6)
    delta = timedelta(days=1)

    # Date range to pass in html
    date_range = start_day.strftime('%b %d'), end_day.strftime('%b %d')
    
    # Lock the cursor
    lock.acquire(True)
    # Get a tuple of the company's data user just clicked
    c.execute("SELECT * FROM company WHERE company_name = :cname AND user_id = :user_id",
              {"cname": cname, "user_id": session.get('user_id')})
    company = c.fetchone()
    # Release the cursor
    lock.release()

    
    # Get the start time, end time & pay of a week starting from the start day till the weeks end
    c.execute("SELECT start, end, pay FROM work_hours WHERE user_id=? AND company_id=? AND date BETWEEN ? AND ?", (session.get('user_id'), company[0], start_day.strftime('%Y-%m-%d'), end_day.strftime('%Y-%m-%d')))
    hours = c.fetchall()


    # Store the week in a list
    weeks = []
    while start_day <= end_day:
        # Format datetime as Mon 02/03 
        weeks.append([start_day])
        start_day += delta

    # Adding the hours(tuple) to a weeks(list)
    for i in range(len(hours)):
        weeks[i] += hours[i] 

    if request.method == "POST":
        # Get a list of user input for start and end time
        start = request.form.getlist('start')
        end = request.form.getlist('end')
        
        # If POST request came from the filter date 
        if start == [] and end == []:
            # if its not the current date your editing then diable it 
            today = datetime.now().date()
            start_day = today - timedelta(days=today.weekday())
            end_day = start_day + timedelta(days=6)
            delta = timedelta(days=1)

            while start_day <= end_day:
                if filter_date == start_day.strftime("%Y-%m-%d"):
                    print(filter_date)
                    print(start_day.strftime("%Y-%m-%d"))
                    print('hi')
                    disabled = False
                    break
                start_day += delta
                disabled = "disabled"

            c.execute("SELECT SUM(pay) FROM work_hours WHERE user_id=? AND company_id=? AND date BETWEEN ? AND ?", (session.get('user_id'), company[0], start_day, end_day))
            total = c.fetchone()[0]
            return render_template("week.html", weeks=weeks, cname=cname, company=company, total=total, date_range=date_range, disabled=disabled)
        else:
            for i in range(7):
                # Check if the weeks data is already in the db for that user and company
                lock.acquire(True)
                c.execute("SELECT end FROM work_hours WHERE date=:date AND user_id=:user_id AND company_id=:company_id", {'date':weeks[i][0], 'user_id':session.get('user_id'), 'company_id':company[0]})
                rows = c.fetchone()
                lock.release()

                # Calculating pay of each day
                fmt = "%H:%M"
                if start[i] != "" and end[i] != "":
                    # hours_worked.append(datetime.strptime(end[i], fmt) - datetime.strptime(start[i], fmt))
                    # pay = hours_worked[i].seconds * (company[3]/3600)
                    pay = (datetime.strptime(end[i], fmt) - datetime.strptime(start[i], fmt)).seconds * (company[3]/3600)
                else:
                    pay = 0

                # If the weeks data doesnot exist in the db
                if rows == None:
                    lock.acquire(True)
                    c.execute("INSERT INTO work_hours (user_id, company_id, date, start, end, pay) VALUES (?, ?, ?, ?, ?, ?)", (session.get('user_id'), company[0], weeks[i][0], start[i], end[i], pay))
                    connection.commit()
                    lock.release()

                # If the weeks data already exists then UPDATE
                else:
                    lock.acquire(True)
                    c.execute("UPDATE work_hours SET start=?, end=?, pay=? WHERE user_id=? AND company_id=? AND date=?",
                            (start[i], end[i], pay, session.get("user_id"), company[0], weeks[i][0]))
                    connection.commit()
                    lock.release() 
        

        return redirect(url_for('week', cname=cname))
    else:
        start_day = today - timedelta(days=today.weekday())
        # Fetch the total pay of a week
        c.execute("SELECT SUM(pay) FROM work_hours WHERE user_id=? AND company_id=? AND date BETWEEN ? AND ?", (session.get('user_id'), company[0], start_day, end_day))
        total = c.fetchone()[0]
        return render_template("week.html", weeks=weeks, cname=cname, company=company, total=total,date_range=date_range)


@app.route("/login", methods=["GET","POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username:
            return apology("must provide username")
        if not password:
            return apology("must provide password")
        
        c.execute("SELECT * FROM users WHERE username = :username",
                 {"username": username})
        rows = c.fetchone()

        # Ensure username exists and password is correct
        if rows == None or not check_password_hash(rows[2], password):
            return apology("invalid username and/or password")

        # Remember which user has logged in
        session['user_id'] = rows[0]

        return redirect("/")
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

@app.route("/workplace", methods=["GET", "POST"])
def workplace():
    if request.method == "POST":
        company = request.form.get("company")
        basepay = request.form.get("basepay")

        if not company:
            return apology("must provide company name")
        if not basepay:
            return apology("must provide base pay")

        # Check if company name is already in db
        c.execute("SELECT * FROM company WHERE company_name = :company",
                  {"company":company})
        
        if c.fetchone() == None:
            # Insert into company table the user id as a foreign key and other infos
            c.execute("INSERT INTO company (user_id, company_name, basepay) VALUES (?, ?, ?)",
                        (session.get("user_id"), company, basepay))
            connection.commit()
        else:
            return apology("already working on the company")

        return redirect("/")        
    else:
        pass
