import os
import cv2
import numpy as np
import json
import pytesseract
from PIL import Image
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
import traceback

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app = Flask(__name__)
CORS(app)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

RELUME_DATA_FILE = 'relume_data.json'
relume_components = []
try:
    with open(RELUME_DATA_FILE, 'r') as f:
        relume_components = json.load(f)
    print(f"Successfully loaded {len(relume_components)} components from {RELUME_DATA_FILE}")
except Exception as e:
    print(f"ERROR loading {RELUME_DATA_FILE}: {e}")


def find_best_match(components, layout_features, guessed_dominant_side):
    best_match_components = []
    best_score = -1
    min_match_score_threshold = 5.0  # Increased threshold for better quality matches

    print(f"Matching based on: Layout Features={layout_features}, GuessedSide='{guessed_dominant_side}'")

    for component in components:
        current_score = 0
        component_side = component.get('dominant_side', 'unknown').lower()
        component_type = component.get('layout_type', '').lower()
        
        # 1. Side Alignment Score (weight: 2.5)
        side_score = 0
        if guessed_dominant_side == 'balanced' and component_side in ['center', 'balanced']:
            side_score = 2.5
        elif guessed_dominant_side == component_side:
            side_score = 2.5
            # Extra bonus for exact side match on directional layouts
            if guessed_dominant_side in ['left', 'right'] and component_side == guessed_dominant_side:
                side_score += 0.5
        current_score += side_score

        # 2. Box Count Score (weight: 2)
        box_count = len(layout_features['bounding_boxes'])
        min_boxes = component.get('min_boxes', 0)
        max_boxes = component.get('max_boxes', 1000)
        
        geo_box_score = 0
        if min_boxes <= box_count <= max_boxes:
            geo_box_score = 2
            # Bonus for being closer to the expected range midpoint
            expected_mid = (min_boxes + max_boxes) / 2
            if abs(box_count - expected_mid) <= (max_boxes - min_boxes) / 4:
                geo_box_score += 0.5
                
            # Additional bonus for hero sections with more elements
            if 'hero' in component_type and box_count >= 8:
                geo_box_score += 0.5
        current_score += geo_box_score

        # 3. Text Block Score (weight: 2)
        text_block_count = len(layout_features['text_blocks'])
        min_text_blocks = component.get('min_text_blocks', 0)
        max_text_blocks = component.get('max_text_blocks', 100)
        
        ocr_block_score = 0
        if min_text_blocks <= text_block_count <= max_text_blocks:
            ocr_block_score = 2
            # Bonus for being closer to the expected range midpoint
            expected_mid = (min_text_blocks + max_text_blocks) / 2
            if abs(text_block_count - expected_mid) <= (max_text_blocks - min_text_blocks) / 4:
                ocr_block_score += 0.5
                
            # Additional bonus for matching text block expectations
            if 'hero' in component_type and text_block_count >= 2:
                ocr_block_score += 0.5
            elif 'cta' in component_type and text_block_count <= 2:
                ocr_block_score += 0.25
        current_score += ocr_block_score

        # 4. Grid Pattern Score (weight: 1.5)
        grid_score = 0
        if layout_features['spacing_patterns']:
            vertical_spacing = layout_features['spacing_patterns']['vertical']
            horizontal_spacing = layout_features['spacing_patterns']['horizontal']
            
            # Check for consistent spacing patterns
            if len(vertical_spacing) >= 2:
                vertical_consistency = all(abs(s - vertical_spacing[0]) < 10 for s in vertical_spacing)
                if vertical_consistency:
                    grid_score += 0.75
            
            if len(horizontal_spacing) >= 2:
                horizontal_consistency = all(abs(s - horizontal_spacing[0]) < 10 for s in horizontal_spacing)
                if horizontal_consistency:
                    grid_score += 0.75
                    
            # Extra bonus for grid components with consistent spacing
            if 'grid' in component_type and grid_score > 1:
                grid_score += 0.5
        current_score += grid_score

        # 5. Element Ratio Score (weight: 1.5)
        ratio_score = 0
        if layout_features['element_ratios']:
            avg_ratio = sum(layout_features['element_ratios']) / len(layout_features['element_ratios'])
            
            # Different ratio expectations for different component types
            if 'hero' in component_type:
                if 0.5 <= avg_ratio <= 2.0:  # Hero sections often have balanced ratios
                    ratio_score += 1.5
            elif 'cta' in component_type:
                if 1.0 <= avg_ratio <= 3.0:  # CTAs often have wider elements
                    ratio_score += 1.0
            elif 'grid' in component_type:
                if 0.8 <= avg_ratio <= 1.2:  # Grids often have square-like elements
                    ratio_score += 1.5
        current_score += ratio_score

        # 6. Component Type Specific Adjustments
        if 'hero' in component_type:
            # Penalize centered hero sections for left/right layouts
            if component_side == 'center' and guessed_dominant_side in ['left', 'right']:
                current_score -= 1.0
            # Bonus for hero sections with appropriate side alignment
            elif component_side == guessed_dominant_side:
                current_score += 0.5
        elif 'cta' in component_type:
            if box_count <= 5:  # CTAs typically have fewer elements
                current_score += 0.25
            # Penalize CTAs for directional layouts
            if guessed_dominant_side in ['left', 'right']:
                current_score -= 0.5
        elif 'grid' in component_type:
            if grid_score > 0:  # Grids should have consistent spacing
                current_score += 0.5
            if len(layout_features['bounding_boxes']) >= 3:  # Grids should have multiple elements
                current_score += 0.5

        print(f"  - Scoring '{component.get('name')}': Side='{component_side}'(Wt=2.5, Score={side_score}), "
              f"GeoBoxRange=[{min_boxes}-{max_boxes}](In={min_boxes <= box_count <= max_boxes}, Wt=2, Score={geo_box_score}), "
              f"OcrBoxRange=[{min_text_blocks}-{max_text_blocks}](In={min_text_blocks <= text_block_count <= max_text_blocks}, "
              f"Wt=2, Score={ocr_block_score}), GridScore={grid_score}, RatioScore={ratio_score}. Total Score={current_score}")

        # Update best matches
        if current_score > best_score:
            best_score = current_score
            best_match_components = [component]
        elif current_score == best_score:
            best_match_components.append(component)

    # No matches found
    if not best_match_components or best_score < min_match_score_threshold:
        print(f"No suitable match found (Best score: {best_score} < Threshold: {min_match_score_threshold})")
        return None

    # If multiple matches with same score, use tiebreakers
    if len(best_match_components) > 1:
        # Tiebreaker 1: Prefer components where the box_count is closer to the middle of their range
        best_match = min(best_match_components, 
                        key=lambda c: abs(box_count - ((c.get('min_boxes', 0) + c.get('max_boxes', 1000)) / 2)))
    else:
        best_match = best_match_components[0]

    print(f"Final Best Match (Score {best_score}): {best_match['name']}")
    return best_match


def analyze_image(img_cv):
    height, width, _ = img_cv.shape
    
    # Convert to grayscale and apply preprocessing
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Adaptive thresholding for better edge detection
    thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                 cv2.THRESH_BINARY_INV, 11, 2)
    
    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Analyze layout features
    layout_features = {
        'bounding_boxes': [],
        'text_blocks': [],
        'grid_patterns': [],
        'spacing_patterns': [],
        'element_ratios': []
    }
    
    # Process significant contours
    min_contour_area = 500
    for contour in contours:
        area = cv2.contourArea(contour)
        if area > min_contour_area:
            x, y, w, h = cv2.boundingRect(contour)
            box = {'x': x, 'y': y, 'w': w, 'h': h, 'area': int(area)}
            layout_features['bounding_boxes'].append(box)
            
            # Calculate aspect ratio
            aspect_ratio = w / h if h > 0 else 0
            layout_features['element_ratios'].append(aspect_ratio)
    
    # Sort boxes by area
    layout_features['bounding_boxes'].sort(key=lambda b: b['area'], reverse=True)
    
    # Analyze grid patterns
    if len(layout_features['bounding_boxes']) >= 3:
        # Check for vertical alignment
        vertical_centers = [b['x'] + b['w']/2 for b in layout_features['bounding_boxes']]
        vertical_centers.sort()
        vertical_spacing = [vertical_centers[i+1] - vertical_centers[i] 
                          for i in range(len(vertical_centers)-1)]
        
        # Check for horizontal alignment
        horizontal_centers = [b['y'] + b['h']/2 for b in layout_features['bounding_boxes']]
        horizontal_centers.sort()
        horizontal_spacing = [horizontal_centers[i+1] - horizontal_centers[i] 
                            for i in range(len(horizontal_centers)-1)]
        
        # Store spacing patterns
        layout_features['spacing_patterns'] = {
            'vertical': vertical_spacing,
            'horizontal': horizontal_spacing
        }
    
    # Perform OCR with improved settings
    try:
        img_rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
        img_pil = Image.fromarray(img_rgb)
        
        # Configure Tesseract for better text detection
        custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,!?()[]{}:;"\''
        ocr_data = pytesseract.image_to_data(img_pil, config=custom_config, output_type=pytesseract.Output.DICT)
        
        # Process OCR results
        detected_blocks = set()
        min_ocr_confidence = 50
        for i in range(len(ocr_data['level'])):
            confidence = int(ocr_data['conf'][i])
            text = ocr_data['text'][i].strip()
            if confidence >= min_ocr_confidence and text:
                block_num = ocr_data['block_num'][i]
                detected_blocks.add(block_num)
                
                # Store text block information
                text_block = {
                    'text': text,
                    'confidence': confidence,
                    'position': {
                        'x': ocr_data['left'][i],
                        'y': ocr_data['top'][i],
                        'w': ocr_data['width'][i],
                        'h': ocr_data['height'][i]
                    }
                }
                layout_features['text_blocks'].append(text_block)
    except Exception as e_ocr:
        print(f"Error during OCR processing: {e_ocr}")
    
    return layout_features


@app.route('/')
def hello_world():
    return 'Hello, World! Backend is running.'

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file:
        filename = secure_filename(file.filename)
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        try:
            file.save(save_path)
            print(f"File saved: {filename}")
            img_cv = cv2.imread(save_path)

            if img_cv is None:
                print(f"Error: OpenCV could not load image: {save_path}")
                return jsonify({'error': 'Failed to process image file on server'}), 500
            
            # Enhanced image analysis
            layout_features = analyze_image(img_cv)
            
            # Calculate dominant side
            left_box_count = 0
            right_box_count = 0
            center_x = img_cv.shape[1] / 2
            
            for box in layout_features['bounding_boxes']:
                if (box['x'] + box['w'] / 2) < center_x:
                    left_box_count += 1
                else:
                    right_box_count += 1
            
            total_boxes = left_box_count + right_box_count
            guessed_dominant_side = "balanced"
            if total_boxes > 0:
                left_ratio = left_box_count / total_boxes
                if left_ratio > 0.65:
                    guessed_dominant_side = "left"
                elif left_ratio < 0.35:
                    guessed_dominant_side = "right"

            # Find best matching component using enhanced matching
            match_info = find_best_match(
                relume_components,
                layout_features,
                guessed_dominant_side
            )

            match_name = "No suitable match found"
            match_link = "#"
            if match_info:
                match_name = match_info.get('name', match_name)
                match_link = match_info.get('link', match_link)

            analysis_result = {
                'significant_box_count': len(layout_features['bounding_boxes']),
                'layout_features': {
                    'left_box_count': left_box_count,
                    'right_box_count': right_box_count,
                    'text_block_count': len(layout_features['text_blocks']),
                    'spacing_patterns': layout_features['spacing_patterns'],
                    'element_ratios': layout_features['element_ratios'],
                    'guessed_dominant_side': guessed_dominant_side
                },
                'componentName': match_name,
                'componentLink': match_link
            }
            
            return jsonify({'message': 'Analysis complete', 'filename': filename, 'analysis': analysis_result}), 200

        except Exception as e:
            print(f"Error processing file: {e}")
            traceback.print_exc()
            return jsonify({'error': 'Failed to save or process file on server'}), 500
    else:
        return jsonify({'error': 'Invalid file object received'}), 500

if __name__ == '__main__':
    app.run(debug=True)