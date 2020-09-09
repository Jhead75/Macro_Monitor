import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import date

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///fitness.db")

@app.route("/")
@login_required
def profile():
    """Show user profile"""
    profile = db.execute("SELECT * FROM macros WHERE id = :ident", ident = session["user_id"])

    if len(profile) == 0:
        user = db.execute("SELECT username FROM users WHERE id = :ident", ident = session["user_id"])
        return render_template("edit.html", user = user)

    return render_template("profile.html", profile = profile)

@app.route("/edit", methods=["GET", "POST"])
@login_required
def edit():

    if request.method == "GET":
        user = db.execute("SELECT username FROM users WHERE id = :ident", ident = session["user_id"])
        return render_template("edit.html", user = user)

    else:
        calories = request.form.get("calories")
        protein = request.form.get("protein")
        carbohydrates = request.form.get("carbohydrates")
        fat = request.form.get("fat")

        profile = db.execute("SELECT * FROM macros WHERE id = :ident", ident = session["user_id"])

        if len(profile) == 0:
            name = db.execute("SELECT username FROM users WHERE id = :ident", ident=session["user_id"])
            db.execute("INSERT INTO macros (id, name, calories, protein, carbohydrates, fat) VALUES (:ident, :name, :calories, :protein, :carbohydrates, :fat)"
                    , ident = session["user_id"], name = name[0]["username"], calories = calories, protein = protein, carbohydrates = carbohydrates, fat = fat)
            #update profile to include data just entered into 'macros' by user
            profile = db.execute("SELECT * FROM macros WHERE id = :ident", ident = session["user_id"])
        else:
            db.execute("UPDATE macros SET calories = ?, protein = ?, carbohydrates = ?, fat = ? WHERE id = ?"
                    , calories, protein, carbohydrates, fat, session["user_id"])
            #update profile to include data just entered into 'macros' by user
            profile = db.execute("SELECT * FROM macros WHERE id = :ident", ident = session["user_id"])

        return render_template("profile.html", profile = profile)

@app.route("/today", methods=["GET", "POST"])
@login_required
def today():
    """Enter food eaten today"""
    today = date.today()

    if request.method == "GET":
        log = db.execute("SELECT * FROM log JOIN food ON food.food_id = log.food_id WHERE id = :ident and date = :date",
                        ident = session["user_id"], date = today)
        goals = db.execute("SELECT protein, carbohydrates, fat FROM macros WHERE id = :ident", ident = session["user_id"])

        #initiate macros, percent, and angle
        macros = [0,0,0,0] #[calories, protein, carbs, fat]
        percent = [0,0,0,0,0,0] # calculate percentages used to determin angles for pie charts
                                # first three represent current metrics (protein, carbs, fat)
                                # second three represent goal metrics (protein, carbs, fat)
        angle = [0,0,0,0,0,0] # calculate angles for "Today" web page
                              # first three represent current metrics (protein, carbs, fat)
                              # second three represent goal metrics (protein, carbs, fat)

        #calculate macro totals for the day
        for row in log:
            macros[0] = macros[0] + row["calories"]*row["qty"]
            macros[1] = macros[1] + row["protein"]*row["qty"]
            macros[2] = macros[2] + row["carbohydrates"]*row["qty"]
            macros[3] = macros[3] + row["fat"]*row["qty"]

        #calculate angles for "Goal" pie chart
        percent[3] = (goals[0]["protein"]*4) / (goals[0]["protein"]*4 + goals[0]["carbohydrates"]*4 + goals[0]["fat"]*9)
        percent[4] = (goals[0]["carbohydrates"]*4) / (goals[0]["protein"]*4 + goals[0]["carbohydrates"]*4 + goals[0]["fat"]*9)
        percent[5] = (goals[0]["fat"]*9) / (goals[0]["protein"]*4 + goals[0]["carbohydrates"]*4 + goals[0]["fat"]*9)
        angle[3] = percent[3]*360
        angle[4] = percent[4]*360
        angle[5] = percent[5]*360

        if macros[0] == 0 or macros[1] == 0 or macros[2] == 0 or macros[3] == 0:
            angle[0] = 120
            angle[1] = 120
            angle[2] = 120
        else:
            #calculate percentages for the day
            percent[0] = (macros[1]*4) / (macros[1]*4 + macros[2]*4 + macros[3]*9)
            percent[1] = (macros[2]*4) / (macros[1]*4 + macros[2]*4 + macros[3]*9)
            percent[2] = (macros[3]*9) / (macros[1]*4 + macros[2]*4 + macros[3]*9)
            #Translate percentage into angle
            angle[0] = percent[0]*360
            angle[1] = percent[1]*360
            angle[2] = percent[2]*360

        #format percentages for use on "today.html"
        for i in range(6):
            percent[i] = round(percent[i]*100)

        return render_template("today.html", log = log, macros = macros, angle = angle, percent = percent)
    else:
        item = request.form.get("item").upper()
        #check food database for food_id
        food_id = db.execute("SELECT food_id FROM food WHERE item = :item  AND id = :ident",
                            item = item, ident = session["user_id"])
        #if food_id does not exist then food must be added to food database before being added to log
        if not food_id:
            return redirect("/food_add")

        qty = request.form.get("qty")
        #If food has already been entered for that day, return current quantity
        curQty = db.execute("SELECT qty FROM log WHERE food_id = :food_id and date = :date",
                            food_id = food_id[0]["food_id"], date = today)

        #if food_id has already been entered in log for the day, update qty and macro values for that day
        if curQty:
            newQty = int(qty) + curQty[0]["qty"]
            db.execute("UPDATE log SET qty = :newQty WHERE food_id = :food_id", newQty = newQty, food_id = food_id[0]["food_id"])
        #if food_id has not been entered for the day, create new record
        else:
            db.execute("INSERT INTO log (food_id, qty, date) VALUES (:food_id, :qty, :date)",
            food_id = food_id[0]["food_id"], qty = qty, date = today)

        return redirect("/today")

@app.route("/history")
@login_required
def history():
    """Show history of food and drink logs"""
    log = db.execute("SELECT * FROM log JOIN food ON food.food_id = log.food_id WHERE id = :ident ORDER BY date DESC",
                        ident = session["user_id"])
    return render_template("history.html", log = log)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            flag = 1;
            return render_template("login.html", flag = flag)

        # Ensure password was submitted
        elif not request.form.get("password"):
            flag = 2;
            return render_template("login.html", flag = flag)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            flag = 3;
            return render_template("login.html", flag = flag)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/food", methods=["GET", "POST"])
@login_required
def food():
    """Enter Food Information"""
    if request.method == "GET":
        return render_template("food.html")
    else:
        item = request.form.get("item").upper()
        entry = db.execute("SELECT * FROM food WHERE item = :item AND id = :ident", item = item, ident = session["user_id"])
        #make item name accessible by other routes ("food_edit" and "food_add")
        session['item'] = item

        if entry:
            return render_template ("food_data.html", food = entry)
        else:
            return render_template ("food_add.html", food = entry)

@app.route("/food_edit", methods=["GET", "POST"])
@login_required
def food_edit():
    """Edit Food Information"""

    #Display form to edit a selected food
    if request.method == "GET":
        item = session.get('item',None)
        return render_template("food_edit.html", item = item)
    else:
        item = session.get('item', None)
        calories = request.form.get("calories")
        protein = request.form.get("protein")
        carbohydrates = request.form.get("carbohydrates")
        fat = request.form.get("fat")

        db.execute("""UPDATE food SET calories = :calories, protein = :protein, carbohydrates = :carbohydrates, fat = :fat
                WHERE item = :item AND id = :ident""", calories = calories, protein = protein, carbohydrates = carbohydrates, fat = fat,
                item = item, ident = session["user_id"])
        entry = db.execute("SELECT * FROM food WHERE item = :item AND id = :ident", item = item, ident = session["user_id"])
        return render_template ("food_data.html", food = entry)

@app.route("/suggest")
@login_required
def suggest():
    """Determine Best Food for User to Eat"""
    today = date.today()
    log = db.execute("SELECT * FROM log JOIN food ON food.food_id = log.food_id WHERE id = :ident and date = :date",
                    ident = session["user_id"], date = today)
    goal = db.execute("SELECT * FROM macros WHERE id = :ident", ident = session["user_id"])

    #initiate macros and differnce (holds the differenc between current and goal for each macro)
    macros = [0,0,0,0] #[calories, protein, carbs, fat]
    diff = [0,0,0,0] #[calories, protein, carbs, fat]

    #calculate macro totals for the day
    for row in log:
        macros[0] = macros[0] + row["calories"]*row["qty"]
        macros[1] = macros[1] + row["protein"]*row["qty"]
        macros[2] = macros[2] + row["carbohydrates"]*row["qty"]
        macros[3] = macros[3] + row["fat"]*row["qty"]

    #calculate differences between goal and current for each macro
    diff[0] = goal[0]["calories"] - macros[0]
    diff[1] = goal[0]["protein"] - macros[1]
    diff[2] = goal[0]["carbohydrates"] - macros[2]
    diff[3] = goal[0]["fat"] - macros[3]

    #Return message if user is far from 200 calories from goal
    if (diff[0] > 200):
        message = "You have plenty of options! Check back later"
        return render_template("suggest.html", message = message)
    elif (diff[0] < 0):
        message = "You have have surpassed your calorie goal for the day"
        return render_template("suggest.html", message = message)
    else:
        options = db.execute("SELECT * FROM food WHERE id = :ident", ident = session["user_id"])

        #cycle through user's food library looking for item that will bring user closest to goals
        i = 0 #initiate a counter so that optimal food index can be recorded
        index = 0 #will be used to store "i" that corresponds to optimal food
        best = 1000 #create variable to store lowest error achieved.
        qty = 0 #create variable to store quantity of recommended food

        for row in options:
            #determines QTY of entry that will get the user closest to calory goals. Note: allows user to go over goal.
            multiple = round(diff[0] / row["calories"])
            if multiple <  1:
                multiple = 1
            print("multiple " + str(multiple))
            protein = multiple*row["protein"]
            carbs = multiple*row["carbohydrates"]
            fat = multiple*row["fat"]

            #Calculate total error due to selecting food
            error = abs(diff[1]-protein) + abs(diff[2]-carbs) + abs(diff[3]-fat)
            print("diff 1 " + str(diff[1]))
            print(protein)
            print("diff 2 " + str(diff[2]))
            print(carbs)
            print("diff 3 " + str(diff[3]))
            print(fat)
            print("error " + str(error))
            if error < best:
                best = error
                index = i
                qty = multiple
            #increase index by one
            i = i + 1
            print(index)

        message = "Try "+ str(qty) + " " + options[index]["item"]
        return render_template("suggest.html", message = message)

@app.route("/food_add", methods=["GET", "POST"])
@login_required
def food_add():
    """Enter Food Information"""

    if request.method == "GET":
        return render_template("food_add.html")
    else:
        item = request.form.get("item").upper()
        calories = request.form.get("calories")
        protein = request.form.get("protein")
        carbohydrates = request.form.get("carbohydrates")
        fat = request.form.get("fat")

        entry = db.execute("SELECT * FROM food WHERE item = :item AND id = :ident", item = item, ident = session["user_id"])

        if entry:
            return render_template ("food_data.html", food = entry)
        else:
            db.execute("""INSERT INTO food (item, id, calories, protein, carbohydrates, fat)
                    VALUES (:item, :ident, :calories, :protein, :carbohydrates, :fat)""", item = item, ident = session["user_id"],
                    calories = calories, protein = protein, carbohydrates = carbohydrates, fat = fat)
            entry = db.execute("SELECT * FROM food WHERE item = :item AND id = :ident", item = item, ident = session["user_id"])
            session['item'] = item
            return render_template ("food_data.html", food = entry)



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")
    else:
        name = request.form.get("username")
        password = request.form.get("password")
        confirm = request.form.get("confirm")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :name", name = request.form.get("username"))

        if len(rows) != 0 or name == '':
            flag = 1;
            return render_template("register.html", flag = flag)

        # Check that passwords match
        if password != confirm or password == '':
            flag = 2;
            return render_template("register.html", flag = flag)

        # Hash user's password
        hashPass = generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)

        # Enter user into user database
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hashPass)", username = name, hashPass = hashPass)

        # Get id of new user so you can log in
        login = db.execute("SELECT id FROM users WHERE username = :name", name = request.form.get("username"))

        # Remember which user has logged in
        session["user_id"] = login[0]["id"]

        return redirect("/")

@app.route("/password", methods=["GET", "POST"])
def password():
    """Allow User to Change Password"""
    if request.method=="GET":
        return render_template("password.html")
    else:
        name = request.form.get("username")
        password = request.form.get("password")
        new = request.form.get("new")
        confirm = request.form.get("confirm")

         # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :name", name = name)

        if len(rows) != 1 or name == '':
            flag = 1;
            return render_template("password.html", flag = flag)

        # Check that user entered correct current password
        if not check_password_hash(rows[0]["hash"], request.form.get("password")):
            flag = 1;
            return render_template("password.html", flag = flag)

        # Check that new passwords match
        if new != confirm or new == '':
            flag = 1;
            return render_template("password.html", flag = flag)

        # Hash user's new password
        hashPass = generate_password_hash(new, method='pbkdf2:sha256', salt_length=8)

        # Enter user into database
        db.execute("UPDATE users SET hash = ? WHERE username = ?", hashPass, name)

        return redirect("/login")

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
