const fileInput = document.getElementById('fileInput');
const uploadLabel = document.querySelector('.upload-label');
const imagePreview = document.getElementById('imagePreview');
const analyseButton = document.getElementById('analyseButton');
const resultArea = document.getElementById('resultArea');

const allowedImageTypes = ['image/png', 'image/jpeg', 'image/jpg'];

let currentFile = null;

function resetUI() {
    console.log('Resetting UI to initial state.');
    uploadLabel.style.display = 'flex';
    imagePreview.style.display = 'none';
    imagePreview.src = '#';
    analyseButton.style.display = 'none';
    analyseButton.disabled = true;
    analyseButton.innerText = 'Analyse Design';
    resultArea.innerHTML = '';
    currentFile = null;
}

fileInput.addEventListener('change', handleFileSelect);

function handleFileSelect(event) {
    resetUI();

    const files = event.target.files;

    if (files.length === 0) {
        console.log('File selection cancelled.');
        fileInput.value = '';
        return;
    }

    const file = files[0];

    if (!allowedImageTypes.includes(file.type)) {
        alert('Invalid file type. Please upload a PNG or JPG image.');
        fileInput.value = '';
        return;
    }

    currentFile = file;

    const imageURL = URL.createObjectURL(file);
    imagePreview.src = imageURL;
    imagePreview.onload = () => {
         URL.revokeObjectURL(imagePreview.src);
    }

    imagePreview.style.display = 'block';
    uploadLabel.style.display = 'none';
    analyseButton.style.display = 'inline-block';
    analyseButton.disabled = false;
}


analyseButton.addEventListener('click', handleAnalyseClick);

function handleAnalyseClick(event) {
    event.preventDefault();

    if (analyseButton.innerText === 'Analyse another') {
        console.log('Resetting UI and triggering new file selection...');
        resetUI();
        fileInput.value = '';
        setTimeout(() => { fileInput.click(); }, 0);
        return;
    }


    if (!currentFile) {
         console.error('No file selected.');
         alert('Please select a file first.');
         return;
     }
     console.log('Uploading file:', currentFile.name);

    analyseButton.innerText = 'Uploading & Analysing...';
    analyseButton.disabled = true;
    resultArea.innerHTML = '';

    const formData = new FormData();
    formData.append('file', currentFile, currentFile.name);

    fetch('http://127.0.0.1:5000/upload', {
        method: 'POST',
        body: formData,
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => {
                throw new Error(err.error || `Server error: ${response.statusText}`);
             }).catch(() => {
                 throw new Error(`Server error: ${response.status} ${response.statusText}`);
             });
        }
        return response.json();
    })
    .then(data => {
        console.log('Parsed data successfully:', data);

        const componentName = data.analysis?.componentName || "Could not determine component";
        const componentLink = data.analysis?.componentLink || "#";

        resultArea.innerHTML = `
            <div class="result-content" style="text-align: left; max-width: 600px; margin: 0 auto;">
                <p><strong>Suggested Component:</strong></p>
                <p class="component-name" style="font-size: 1.1em; margin-bottom: 10px;">${componentName}</p>
                <p><strong>Link:</strong>
                   <a href="${componentLink}" target="_blank" rel="noopener noreferrer" style="word-break: break-all;">${componentLink}</a>
                </p>
                </div>
        `;

        imagePreview.style.display = 'none';
        analyseButton.innerText = 'Analyse another';
        analyseButton.disabled = false;

        currentFile = null;

    })
    .catch(error => {
        console.error('Error during fetch or processing:', error);
        resultArea.innerHTML = `<p style="color: red; text-align: center;">Error: ${error.message}</p>`;
        analyseButton.innerText = 'Analyse Design';
        analyseButton.disabled = false;
    });
}