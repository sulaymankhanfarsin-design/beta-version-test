// This code runs after the entire HTML page has loaded
document.addEventListener('DOMContentLoaded', () => {

    // --- Get all the interactive elements ---
    const listInput = document.getElementById('list-input');
    const randomizeButton = document.getElementById('randomize-btn');
    const removeDuplicatesButton = document.getElementById('remove-duplicates-btn');
    const resetButton = document.getElementById('reset-btn');
    const outputDiv = document.getElementById('randomized-list');

    // Options
    const formatDropdown = document.getElementById('list-format');
    const numSelectionsInput = document.getElementById('number-of-selections');

    // Stats
    const totalCountEl = document.getElementById('total-count');
    const uniqueCountEl = document.getElementById('unique-count');
    const duplicateCountEl = document.getElementById('duplicate-count');

    // --- Helper function to get delimiter character ---
    function getDelimiter() {
        // We stored the actual character (like '\n' or ',') in the value
        return formatDropdown.value;
    }

    // --- Helper function to parse list from textarea ---
    function getItemsFromInput() {
        const text = listInput.value;
        const delimiter = getDelimiter();
        
        if (!text.trim()) {
            return [];
        }

        return text.split(delimiter)
                   .map(item => item.trim())
                   .filter(item => item.length > 0);
    }

    // --- Helper function to update the stats display ---
    function updateStats() {
        const items = getItemsFromInput();
        const totalCount = items.length;
        
        const uniqueItems = new Set(items);
        const uniqueCount = uniqueItems.size;
        
        const duplicateCount = totalCount - uniqueCount;

        totalCountEl.textContent = totalCount;
        uniqueCountEl.textContent = uniqueCount;
        duplicateCountEl.textContent = duplicateCount;
    }

    // --- Event Listener: Update stats as user types ---
    listInput.addEventListener('input', updateStats);
    formatDropdown.addEventListener('change', updateStats);

    // --- Event Listener: "Randomize" Button ---
    randomizeButton.addEventListener('click', () => {
        const text = listInput.value;
        const delimiter = getDelimiter();
        const numSelections = parseInt(numSelectionsInput.value, 10) || 0;

        outputDiv.textContent = 'Randomizing...';

        // Send data to our Python backend
        fetch('/randomize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                'list_text': text,
                'delimiter': delimiter,
                'num_selections': numSelections
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.result_list) {
                // Join the shuffled array back into a string with new lines
                outputDiv.textContent = data.result_list.join('\n');
            } else {
                outputDiv.textContent = data.error || 'An unknown error occurred.';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            outputDiv.textContent = 'Error connecting to the server.';
        });
    });

    // --- Event Listener: "Remove Duplicates" Button ---
    removeDuplicatesButton.addEventListener('click', () => {
        const text = listInput.value;
        const delimiter = getDelimiter();

        fetch('/remove-duplicates', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                'list_text': text,
                'delimiter': delimiter
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.result_text || data.result_text === '') {
                // Update the *input* textarea with the cleaned list
                listInput.value = data.result_text;
                // Manually trigger the stat update
                updateStats();
                outputDiv.textContent = 'Duplicates removed. Your list in the text box has been updated.';
            } else {
                outputDiv.textContent = 'Could not remove duplicates.';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            outputDiv.textContent = 'Error connecting to the server.';
        });
    });

    // --- Event Listener: "Reset" Button ---
    resetButton.addEventListener('click', () => {
        listInput.value = '';
        outputDiv.textContent = '';
        numSelectionsInput.value = 0;
        formatDropdown.value = '\n'; // Reset to "One per line"
        updateStats(); // This will reset stats to 0
    });
});