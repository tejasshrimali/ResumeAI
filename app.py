from flask import Flask, render_template, request, session, redirect, url_for , jsonify
import firebase_admin
from firebase_admin import credentials, auth , firestore
import google.generativeai as genai
import docx
import PyPDF2
import os
import re

from dotenv import load_dotenv

load_dotenv()

# Initialize Firebase Admin SDK
cred = credentials.Certificate("diems-cse-firebase-adminsdk-148re-4fb00b91fc.json")
firebase_admin.initialize_app(cred)
db = firestore.client()
# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # Replace with your Gemini API key
genai.configure(api_key=GEMINI_API_KEY)

app = Flask(__name__)
app.secret_key = '5as4d12a3s1dqasagas'

# Helper function to extract text from .docx
def extract_text_from_docx(file):
    doc = docx.Document(file)
    return "\n".join([para.text for para in doc.paragraphs if para.text.strip()])

# Helper function to extract text from .pdf
def extract_text_from_pdf(file):
    reader = PyPDF2.PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text

@app.route('/')
def index():
    return render_template('index.html')

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/register")
def register():
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    session.pop("display_name", None)
    return redirect(url_for("login"))

@app.route("/submit", methods=["GET", "POST"])
def submit():
    if "user" not in session:
        return redirect(url_for("login"))
    
    if request.method == "POST":
        job_desc = request.form.get("job_desc")
        resume_file = request.files.get("resume")
        resume_text = ""

        # Extract text from resume if uploaded
        if resume_file and resume_file.filename:
            if resume_file.filename.endswith(".docx"):
                resume_text = extract_text_from_docx(resume_file)
            elif resume_file.filename.endswith(".pdf"):
                resume_text = extract_text_from_pdf(resume_file)

        # Call Gemini API
        try:
            model = genai.GenerativeModel("gemini-1.5-flash")  # Use appropriate Gemini model
            prompt = f"""
            You are a job description analyzer, your work is to extract the skills and knowledge 
            needed for the job and help the candidate by making his resume suitable for the job inform of html tags or markups ,
            make sure the resume is well formated and easy to read make sure to have points like resume header , skills , 
            experience (optional), achievments , education , profesional summary when needed also make sure to include a HTML Unordered list of suggestion point at the very end of the resume
            .
            do not include any other information or text.
            **Job Description**:
            {job_desc}
            **Resume** (if provided):
            {resume_text}
            Please provide suggestions in HTML format with clear headings and bullet points for easy reading.
            """
            response = model.generate_content(prompt)
            suggestions = response.text 
            cleaned = re.sub(r'^```html\s*', '', suggestions, flags=re.MULTILINE)
            # Remove optional whitespace followed by closing ```
            cleaned = re.sub(r'\s*```$', '', cleaned, flags=re.MULTILINE) # HTML-formatted suggestions
            session["suggestions"] = cleaned  # Store in session for result page
            return redirect(url_for("result"))
        except Exception as e:
            print(f"Gemini API error: {str(e)}")
            return render_template("submit.html", error=f"Failed to generate suggestions: {str(e)}")

    return render_template("submit.html")

@app.route("/result")
def result():
    if "user" not in session:
        return redirect(url_for("login"))
    suggestions = session.get("suggestions", "<p>No suggestions available.</p>")
    return render_template("result.html", suggestions=suggestions)

@app.route("/save_suggestions", methods=["POST"])
def save_suggestions():
    if "user" not in session:
        return jsonify({"message": "Unauthorized: Please log in"}), 401
    
    try:
        data = request.get_json()
        suggestions = data.get("suggestions")
        if not suggestions:
            return jsonify({"message": "No suggestions provided"}), 400
        
        # Save to Firestore under user's collection
        user_id = session["user"]
        db.collection("users").document(user_id).collection("suggestions").add({
            "suggestions": suggestions,
            "timestamp": firestore.SERVER_TIMESTAMP
        })
        return jsonify({"message": "Suggestions saved successfully"})
    except Exception as e:
        print(f"Error saving suggestions: {str(e)}")
        return jsonify({"message": f"Failed to save: {str(e)}"}), 500

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if request.method == "POST":
        id_token = request.form.get("id_token")
        display_name = request.form.get("display_name", "User")
        try:
            decoded_token = auth.verify_id_token(id_token)
            uid = decoded_token["uid"]
            session["user"] = uid
            session["display_name"] = display_name
        except auth.InvalidIdTokenError:
            print("Invalid ID token")
            return "Unauthorized: Invalid ID token", 401
        except auth.ExpiredIdTokenError:
            print("Expired ID token")
            return "Unauthorized: ID token expired", 401
        except Exception as e:
            print(f"Error verifying token: {str(e)}")
            return f"Unauthorized: {str(e)}", 401
    if "user" not in session:
        return redirect(url_for("login"))
    
    # Fetch saved suggestions from Firestore
    user_id = session["user"]
    suggestions_ref = db.collection("users").document(user_id).collection("suggestions")
    suggestions = [
        {"id": doc.id, "suggestions": doc.to_dict().get("suggestions"), "timestamp": doc.to_dict().get("timestamp")}
        for doc in suggestions_ref.order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
    ]
    display_name = session.get("display_name", "User")
    return render_template("dashboard.html", user_id=user_id, display_name=display_name, suggestions=suggestions)

@app.route("/view_suggestion/<suggestion_id>")
def view_suggestion(suggestion_id):
    if "user" not in session:
        return redirect(url_for("login"))
    
    try:
        user_id = session["user"]
        suggestion_doc = db.collection("users").document(user_id).collection("suggestions").document(suggestion_id).get()
        if not suggestion_doc.exists:
            return "Suggestion not found", 404
        suggestion_data = suggestion_doc.to_dict()
        return render_template("view_suggestion.html", suggestion=suggestion_data.get("suggestions"), suggestion_id=suggestion_id)
    except Exception as e:
        print(f"Error fetching suggestion: {str(e)}")
        return f"Error: {str(e)}", 500

@app.route("/delete_suggestion/<suggestion_id>", methods=["POST"])
def delete_suggestion(suggestion_id):
    if "user" not in session:
        return jsonify({"message": "Unauthorized: Please log in"}), 401
    
    try:
        user_id = session["user"]
        db.collection("users").document(user_id).collection("suggestions").document(suggestion_id).delete()
        return jsonify({"message": "Suggestion deleted successfully"})
    except Exception as e:
        print(f"Error deleting suggestion: {str(e)}")
        return jsonify({"message": f"Failed to delete: {str(e)}"}), 500

# ... (rest of your existing app.py code)
if __name__ == '__main__':
    app.run(debug=True)