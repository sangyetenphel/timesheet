# Create empty test.db 
# open("test.db","w").close()

from flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/week")
def week():
    return render_template("week.html")

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/register")
def register():
    return render_template("register.html")
    
# if __name__ == "__main__":
#     app.run(debug=True)