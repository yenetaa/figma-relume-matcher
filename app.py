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

@app.route('/')
def hello_world():
    return 'Hello, World! Backend is running.'

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files: return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({'error': 'No selected file'}), 400

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
            else:
                height, width, channels = img_cv.shape
                print(f"Image loaded: {filename}, Dimensions: {height}x{width}")

                gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
                blurred = cv2.GaussianBlur(gray, (5, 5), 0)
                low_thresh = 50; high_thresh = 150
                edges = cv2.Canny(blurred, low_thresh, high_thresh)
                contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                min_contour_area = 500
                bounding_boxes = []
                for contour in contours:
                    area = cv2.contourArea(contour)
                    if area > min_contour_area:
                        x, y, w, h = cv2.boundingRect(contour)
                        bounding_boxes.append({'x': x, 'y': y, 'w': w, 'h': h, 'area': int(area)})
                bounding_boxes.sort(key=lambda b: b['area'], reverse=True)
                box_count = len(bounding_boxes)
                print(f"Geometric Analysis: Found {box_count} significant bounding boxes...")

                left_box_count = 0; right_box_count = 0
                widest_box = None; tallest_box = None
                max_width = 0; max_height = 0
                is_tall_dominant = False; is_wide_dominant = False
                center_x = width / 2
                if bounding_boxes:
                    for box in bounding_boxes:
                        if (box['x'] + box['w'] / 2) < center_x: left_box_count += 1
                        else: right_box_count += 1
                        if box['w'] > max_width: max_width = box['w']; widest_box = box
                        if box['h'] > max_height: max_height = box['h']; tallest_box = box
                    print(f"Layout Features: Left={left_box_count}, Right={right_box_count}")
                    tall_aspect_ratio_threshold = 1.5; wide_aspect_ratio_threshold = 1.5
                    if tallest_box and tallest_box['w'] > 0:
                        if (tallest_box['h'] / tallest_box['w']) > tall_aspect_ratio_threshold: is_tall_dominant = True; print("Detected TALL element.")
                    if widest_box and widest_box['h'] > 0:
                        if (widest_box['w'] / widest_box['h']) > wide_aspect_ratio_threshold: is_wide_dominant = True; print("Detected WIDE element.")
                else: print("Layout Features: No significant boxes found.")

                text_block_count = 0
                try:
                    img_rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
                    img_pil = Image.fromarray(img_rgb)
                    ocr_data = pytesseract.image_to_data(img_pil, output_type=pytesseract.Output.DICT, timeout=15)
                    detected_blocks = set()
                    num_items = len(ocr_data['level'])
                    min_ocr_confidence = 50
                    for i in range(num_items):
                        confidence = int(ocr_data['conf'][i])
                        text = ocr_data['text'][i].strip()
                        if confidence >= min_ocr_confidence and text:
                            block_num = ocr_data['block_num'][i]
                            detected_blocks.add(block_num)
                    text_block_count = len(detected_blocks)
                    print(f"OCR Analysis: Found {text_block_count} text blocks (conf >= {min_ocr_confidence}%).")
                except Exception as e_ocr: print(f"Error during OCR processing: {e_ocr}")

                guessed_dominant_side = "balanced"
                total_boxes = left_box_count + right_box_count
                if total_boxes > 0:
                    left_ratio = left_box_count / total_boxes
                    if left_ratio > 0.65: guessed_dominant_side = "left"
                    elif left_ratio < 0.35: guessed_dominant_side = "right"
                print(f"Guessed dominant side: {guessed_dominant_side}")

                best_match_component = None; best_score = -1
                for component in relume_components:
                    current_score = 0
                    component_side = component.get('dominant_side', 'unknown').lower()
                    min_boxes = component.get('min_boxes', 0)
                    max_boxes = component.get('max_boxes', 1000)
                    min_text_blocks = component.get('min_text_blocks', 0)
                    max_text_blocks = component.get('max_text_blocks', 100)

                    side_score = 0
                    if guessed_dominant_side == 'balanced' and component_side in ['center', 'balanced']: side_score = 1
                    elif guessed_dominant_side == component_side: side_score = 1
                    current_score += side_score

                    geo_box_score = 0
                    if min_boxes <= box_count <= max_boxes: geo_box_score = 1
                    current_score += geo_box_score

                    ocr_block_score = 0
                    if min_text_blocks <= text_block_count <= max_text_blocks: ocr_block_score = 2
                    current_score += ocr_block_score

                    print(f"  - Scoring '{component.get('name')}': Side='{component_side}'(Wt=1, Score={side_score}), GeoBoxRange=[{min_boxes}-{max_boxes}](In={min_boxes <= box_count <= max_boxes}, Wt=1, Score={geo_box_score}), OcrBoxRange=[{min_text_blocks}-{max_text_blocks}](In={min_text_blocks <= text_block_count <= max_text_blocks}, Wt=2, Score={ocr_block_score}). Total Score={current_score}")

                    if current_score > best_score:
                        best_score = current_score
                        best_match_component = component

                match_name = "No suitable match found"; match_link = "#"
                min_match_score_threshold = 1
                if best_match_component and best_score >= min_match_score_threshold:
                    print(f"Best Match Found (Score {best_score}): {best_match_component['name']}")
                    match_name = best_match_component['name']; match_link = best_match_component['link']
                else: print(f"No suitable match found (Best score: {best_score} < Threshold: {min_match_score_threshold})")


                analysis_result = {
                     'significant_box_count': box_count,
                     'layout_features': {
                         'left_box_count': left_box_count, 'right_box_count': right_box_count,
                         'widest_box_details': widest_box, 'tallest_box_details': tallest_box,
                         'is_tall_dominant': is_tall_dominant, 'is_wide_dominant': is_wide_dominant,
                         'guessed_dominant_side': guessed_dominant_side,
                         'ocr_text_block_count': text_block_count
                     },
                     'componentName': match_name,
                     'componentLink': match_link
                 }
                return jsonify({'message': 'Analysis complete', 'filename': filename, 'analysis': analysis_result }), 200

        except Exception as e:
            print(f"Error processing file: {e}")
            traceback.print_exc()
            return jsonify({'error': 'Failed to save or process file on server'}), 500
    else:
         return jsonify({'error': 'Invalid file object received'}), 500

if __name__ == '__main__':
    app.run(debug=True)