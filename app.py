import json
from flask import Flask, render_template, request, jsonify
from slugify import slugify

# Initialize the Flask application
app = Flask(__name__)

# --- Route 1: The Home Page ---
# This route just serves your HTML page to the user's browser.
@app.route('/')
def index():
    # Flask knows to look in the "templates" folder for this file.
    return render_template('index.html')

# --- Route 2: The Slug Generator API ---
# This is the "API" our front-end will send data to.
# It only accepts POST requests (we're sending data, not just getting a page).
@app.route('/generate-slug', methods=['POST'])
def generate_slug():
    # Get the JSON data sent from the front-end
    data = request.json
    
    # Get all the options from the data
    text = data.get('text', '')
    separator = data.get('separator', '-')
    remove_numbers = data.get('remove_numbers', False)
    lowercase = data.get('lowercase', True) # Get the lowercase option
    
    # Get the remove_special option
    remove_special = data.get('remove_special', True) 
    
    # --- The Core Logic ---
    # Create the slug using the python-slugify library
    final_slug = slugify(
        text, 
        separator=separator,
        lowercase=lowercase  # <-- THIS WAS THE FIX
    )

    # If the "Remove Numbers" checkbox is checked, we do an extra step.
    if remove_numbers:
        final_slug = "".join(c for c in final_slug if not c.isdigit())
        # Re-apply separator if numbers created double-separators
        final_slug = final_slug.replace(separator * 2, separator)


    # Send the generated slug back as a JSON response
    return jsonify({'slug': final_slug})

# This line allows you to run the app by just running "python app.py"
if __name__ == '__main__':
    app.run(debug=True)