import random
from flask import Flask, render_template, request, jsonify

# Initialize the Flask application
app = Flask(__name__)

def parse_list(text, delimiter_char):
    """Helper function to split text into a list."""
    if not text:
        return []
        
    # Split the text by the chosen delimiter
    items = text.split(delimiter_char)
    
    # Clean up: remove empty strings and whitespace
    cleaned_items = [item.strip() for item in items if item.strip()]
    return cleaned_items

@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

@app.route('/randomize', methods=['POST'])
def handle_randomize():
    """Handles the randomization logic."""
    data = request.get_json()
    
    text = data.get('list_text', '')
    delimiter = data.get('delimiter', '\n') # Default to newline
    num_to_select = data.get('num_selections', 0)
    
    items = parse_list(text, delimiter)
    
    if not items:
        return jsonify({'result_list': [], 'error': 'No items found in the list.'})
    
    # Shuffle the list in place
    random.shuffle(items)
    
    # If num_to_select is 0 or greater than list size, return all
    if num_to_select <= 0 or num_to_select >= len(items):
        result_list = items
    else:
        # Otherwise, pick the specified number of items
        result_list = items[:num_to_select]
        
    return jsonify({'result_list': result_list})

@app.route('/remove-duplicates', methods=['POST'])
def handle_remove_duplicates():
    """Handles removing duplicates."""
    data = request.get_json()
    
    text = data.get('list_text', '')
    delimiter = data.get('delimiter', '\n')
    
    items = parse_list(text, delimiter)
    
    # Use a dictionary to maintain order and uniqueness
    unique_items_ordered = list(dict.fromkeys(items))
    
    # Join back with newlines, as this will update the text area
    result_text = '\n'.join(unique_items_ordered)
    
    return jsonify({'result_text': result_text})

if __name__ == '__main__':
    app.run(debug=True)