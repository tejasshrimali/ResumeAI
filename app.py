from flask import Flask, render_template, request, session
import firebase_admin
from firebase_admin import credentials, auth  # Import auth explicitly

# Initialize Firebase Admin SDK
cred = credentials.Certificate("diems-cse-firebase-adminsdk-148re-4fb00b91fc.json")
firebase_admin.initialize_app(cred)

app = Flask(__name__)
app.secret_key = '5as4d12a3s1dqasagas' 

@app.route('/')
def index():
    return render_template('index.html')

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/register")
def register():
    return render_template("register.html")  # Ensure this matches your signup.html or rename accordingly

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if request.method == "POST":
        id_token = request.form.get("id_token")
        try:
            # Verify the ID token using Firebase Admin SDK
            decoded_token = auth.verify_id_token(id_token)
            uid = decoded_token["uid"]
            session["user"] = uid  # Store UID in session
            return render_template("dashboard.html", user_id=uid)
        except auth.InvalidIdTokenError:
            print("Invalid ID token")
            return "Unauthorized: Invalid ID token", 401
        except auth.ExpiredIdTokenError:
            print("Expired ID token")
            return "Unauthorized: ID token expired", 401
        except Exception as e:
            print(f"Error verifying token: {str(e)}")
            return f"Unauthorized: {str(e)}", 401
    else:  # GET request
        if "user" in session:
            # User is authenticated, render dashboard
            return render_template("dashboard.html", user_id=session["user"])
        else:
            # User is not authenticated, redirect to login
            return redirect(url_for("login"))

@app.route('/submit', methods=['POST'])
def submit():
    job_desc = request.form['job_desc']
    resume = request.form['resume']
    # Add your logic here (AI suggestions, .docx generation, etc.)
    return render_template('result.html', job_desc=job_desc, resume=resume)

if __name__ == '__main__':
    app.run(debug=True)