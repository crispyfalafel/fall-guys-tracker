import os
import sqlalchemy
import psycopg2

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, percent

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
db = SQL("postgres://hzeqxftaqdqkoo:642486dee2042c4249b3a4a5d5f22a47af2d72ba31939910b044e0951550ef92@ec2-52-86-116-94.compute-1.amazonaws.com:5432/d5t0i8j478i083")
# sqlite:///fallguys.db


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Enter new wins/losses"""

    if request.method == "GET":

        # Get list of games
        finals = db.execute("SELECT * FROM fallguystracker.games WHERE mode='final'")
        nonfinals = db.execute("SELECT * FROM fallguystracker.games WHERE NOT mode='final'")
        return render_template("index.html", finals=finals, nonfinals=nonfinals)

    else:

        # Ensure all fields of form was submitted
        if not request.form.get("result"):
            flash("Results missing", "warning")
            return redirect("/")

        elif not request.form.get("game"):
            flash("Results missing", "warning")
            return redirect("/")

        elif not request.form.get("round"):
            flash("Results missing", "warning")
            return redirect("/")

        db.execute("INSERT INTO fallguystracker.history (id, result, game, round, datetime) VALUES (:id, :result, :game, :round, datetime('now'))",
                    id=session["user_id"], result=request.form.get("result"), game=request.form.get("game"), round=int(request.form.get("round")))

        flash("Match recorded!", "success")
        return redirect("/")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "GET":
        return render_template("login.html")

    else:
        # Ensure username was submitted
        if not request.form.get("username"):
            flash("Username not entered.", "warning")
            return render_template("login.html")

        # Ensure password was submitted
        elif not request.form.get("password"):
            flash("Must provide password.", "warning")
            return render_template("login.html")

        # Query database for username
        rows = db.execute("SELECT * FROM fallguystracker.users WHERE username = :username",
                          username=request.form.get("username").lower())

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            flash("Invalid username and/or password.", "warning")
            return render_template("login.html")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")

    else:
        # Ensure username was submitted
        if not request.form.get("username"):
            flash("Username not entered.", "warning")
            return redirect("/register")

        # Ensure password was submitted
        elif not request.form.get("password"):
            flash("Password not entered.", "warning")
            return redirect("/register")

        # Ensure password confirmation was submitted:
        elif not request.form.get("confirmation"):
            flash("Password not confirmed.", "warning")
            return redirect("/register")

         # Ensure passwords match
        if request.form.get("password") != request.form.get("confirmation"):
            flash("Passwords do not match.", "warning")
            return redirect("/register")

        # Check if username already taken
        rows = db.execute("SELECT * FROM fallguystracker.users WHERE username = :username",
                            username=request.form.get("username"))
        if len(rows) > 0:
            flash("Username already taken.", "warning")
            return redirect("/register")

        # Hash user's password
        password_hash = generate_password_hash(request.form.get("password"))

        # Add registration information to database
        id = db.execute("INSERT INTO fallguystracker.users (username, hash) VALUES (:username, :password)", username=request.form.get("username").lower(), password=password_hash)

        # Log user in
        session["user_id"] = id
        flash("Registered!")
        return redirect("/")

@app.route("/statistics")
@login_required
def statistics():
    """Display user statistics"""

    # Get username
    id=session["user_id"]
    user = db.execute("SELECT * FROM fallguystracker.users WHERE id=:id", id=session["user_id"])

    stats = {}

    # Check if user has games recorded
    rows = db.execute("SELECT * FROM fallguystracker.history WHERE id=:id", id=id)
    if not rows:
        return apology("record some games beech", 404)

    # Get dictionary of total win count for each finals map
    rows = db.execute("SELECT game, COUNT(game) FROM fallguystracker.history WHERE id = :id AND result = 'win' GROUP BY game",
                    id=id)
    wins = {}
    for row in rows:
        wins[row["game"]] = row["COUNT(game)"]

    # Get list of total losses on each map in descending order
    losses = db.execute("SELECT game, COUNT(game) FROM fallguystracker.history JOIN fallguystracker.games ON game = fallguystracker.games.name WHERE NOT mode= 'final' AND id = :id AND result = 'loss' GROUP BY game ORDER BY COUNT(game) DESC;",
                    id=id)

    # Get dictionary of total rounds played on each finals map and win rate for each map
    rows = db.execute("SELECT game, COUNT(game) FROM fallguystracker.history JOIN fallguystracker.games ON game = fallguystracker.games.name WHERE mode = 'final' AND id = :id GROUP BY game",
                    id=id)
    finals = {}
    finals_winrate = {}
    for row in rows:
        finals[row["game"]] = row["COUNT(game)"]

        # Add game to win rate dictionary if user has won on the game before
        if row["game"] in wins:
            finals_winrate[row["game"]] = percent(wins[row["game"]], finals[row["game"]])

        else:
            finals_winrate[row["game"]] = percent(0, finals[row["game"]])

    # Get total games played
    game_count = db.execute("SELECT COUNT(*) FROM fallguystracker.history WHERE id = :id", id=id)
    stats["game_count"] = game_count[0]["COUNT(*)"]

    # Get total wins
    win_count = db.execute("SELECT COUNT(game) FROM fallguystracker.history WHERE id = :id AND result = 'win'", id=id)
    stats["win_count"] = win_count[0]['COUNT(game)']

    # Get total rounds played
    round_count = db.execute("SELECT SUM(round) FROM fallguystracker.history WHERE id = :id", id=id)
    stats["round_count"] = round_count[0]["SUM(round)"]

    # Get finals made
    finals_count = db.execute("SELECT COUNT(game) FROM fallguystracker.history JOIN fallguystracker.games ON game = fallguystracker.games.name WHERE mode = 'final' AND id = :id",
                            id=id)
    stats["finals_count"] = finals_count[0]["COUNT(game)"]

    # Calculate total rounds qualified
    stats["rounds_won"] = stats["round_count"] - (stats["game_count"] - stats["win_count"])

    # Calculate win rate
    stats["win_rate"] = percent(stats["win_count"], stats["game_count"])

    # Calculate finals rate
    stats["finals_rate"] = percent(stats["finals_count"], stats["game_count"])

    # Calculate round qualification rate
    stats["rounds_rate"] = percent(stats["rounds_won"], stats["round_count"])

    # Calculate average rounds per game
    avg_round = db.execute("SELECT AVG(round) FROM fallguystracker.history WHERE id = :id", id=id)
    stats["avg_round"] = round(avg_round[0]["AVG(round)"], 2)

    # Calculate team game elimination rate
    team_count = db.execute("SELECT COUNT(game) FROM fallguystracker.history JOIN fallguystracker.games ON game = fallguystracker.games.name WHERE mode = 'team' AND id = :id",
                            id=id)
    team_wins = db.execute("SELECT COUNT(game) FROM fallguystracker.history JOIN fallguystracker.games ON game = fallguystracker.games.name WHERE mode = 'final' AND result = 'win' AND id = :id",
                            id=id)

    stats["team_winrate"] = percent(team_count[0]["COUNT(game)"] - team_wins[0]["COUNT(game)"], team_count[0]["COUNT(game)"])

    # Create lists for pie chart
    labels = []
    values = []
    for game in wins.keys():
        labels.append(game.title())

    for value in wins.values():
        values.append(value)



    return render_template("stats.html", username=user[0]["username"], losses=losses, stats=stats, wins=wins, finals=finals, finals_winrate=finals_winrate,
                            labels=labels, values=values)

@app.route("/collection", methods=["GET", "POST"])
@login_required
def collection():
    """Display or add to user's cosmetics collection"""
    users = db.execute("SELECT * FROM fallguystracker.users WHERE id = :id", id=session["user_id"])

    return render_template("collection.html")

@app.route("/history", methods=["GET", "POST"])
@login_required
def matchhistory():
    """Display user's recent match history"""

    matches = db.execute("SELECT * FROM fallguystracker.history WHERE id=:id ORDER BY datetime DESC LIMIT 15", id=session["user_id"])
    if not matches:
        return apology("No matches recorded", "404")

    return render_template("history.html", matches=matches)

@app.route("/search", methods=["GET", "POST"])
@login_required
def search():
    """Search for other players' match history"""

    # Display search bar
    if request.method == "GET":
        return render_template("search.html")

    # Return searched user's profile
    else:

        # Ensure user search was entered
        if not request.form.get("search"):
            flash("Search not entered.", "warning")
            return redirect(url_for("search"))

        return redirect(url_for("profile", username=request.form.get("search")))

@app.route("/profile/<username>")
@login_required
def profile(username):

    # Search for user
    user = db.execute("SELECT * FROM fallguystracker.users WHERE username= :username", username=username.lower())
    stats = {}

    # Redirect user to search page if username does not exist
    if not user:
        flash("User does not exist.", "warning")
        return redirect(url_for("search"))

    # Get searched user's id
    search_id = user[0]["id"]

    # Get number of wins
    win_count = db.execute("SELECT COUNT(game) FROM fallguystracker.history WHERE id = :id AND result = 'win'", id=search_id)
    stats["win_count"] = win_count[0]['COUNT(game)']

    # Get number of games played
    game_count = db.execute("SELECT COUNT(*) FROM fallguystracker.history WHERE id = :id", id=search_id)
    stats["game_count"] = game_count[0]["COUNT(*)"]

    # Get recent match history (last 10 games)
    matches = db.execute("SELECT * FROM fallguystracker.history WHERE id=:id ORDER BY datetime DESC LIMIT 10", id=search_id)

    return render_template("profile.html", username=username, matches=matches, stats=stats)






def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)


    # TO DO:

    # Error on stats page if no games recorded
    # Final games played on each map
    # Player profile search doesn't require login

    # Add wins per day ?
    # Add time zones?

if __name__ == '__main__':
    app.run(debug=True)