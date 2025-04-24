const fileInput = document.getElementById('fileInput');
const uploadLabel = document.querySelector('.upload-label');
const imagePreview = document.getElementById('imagePreview');
const analyseButton = document.getElementById('analyseButton');
const resultArea = document.getElementById('resultArea');

const allowedImageTypes = ['image/png', 'image/jpeg', 'image/jpg'];

let currentFile = null;

fileInput.addEventListener('change', handleFileSelect);

function handleFileSelect(event) {
    const files = event.target.files;
    currentFile = null;
    analyseButton.disabled = true;
    analyseButton.innerText = 'Analyse Design';

    if (files.length === 0) {
        console.log('File selection cancelled.');
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

    imagePreview.style.display = 'block';
    uploadLabel.style.display = 'none';
    analyseButton.style.display = 'inline-block';
    analyseButton.disabled = false;

    resultArea.innerHTML = '';
}

analyseButton.addEventListener('click', handleAnalyseClick);

function handleAnalyseClick() {
    if (!currentFile) {
        console.error('Error: Analyse button clicked but no valid file is selected.');
        alert('Something went wrong, please select a file again.');
        return;
    }

    console.log('Analyse button clicked! Simulating analysis for:', currentFile.name);

    analyseButton.innerText = 'Analysing...';
    analyseButton.disabled = true;
    resultArea.innerHTML = '';

    setTimeout(() => {
        const mockResult = {
            componentName: 'Relume - Header 1 Example',
            componentLink: '#'
        };

        resultArea.innerHTML = `
            <p><strong>Suggested Component:</strong> ${mockResult.componentName}</p>
            <p><strong>Link:</strong> <a href="${mockResult.componentLink}" target="_blank" rel="noopener noreferrer">${mockResult.componentLink}</a></p>
        `;

        imagePreview.style.display = 'none';

        analyseButton.innerText = 'Analyse another';
        analyseButton.disabled = false;

    }, 2000);
}