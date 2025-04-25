# tests/test_analysis.py
import sys
import os
import pytest # Often needed for more advanced features, good practice to import

# --- Allow importing 'app' from the parent directory ---
# Get the absolute path of the parent directory (project root)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# Add the project root to the Python path
sys.path.insert(0, project_root)
# --- End Path Setup ---

# Import the function we want to test from app.py
from app import find_best_match

# Define mock component data for testing (based on your relume_data.json)
# Using slightly adjusted ranges based on test results
MOCK_COMPONENTS = [
  { "id": "hero-TL-IR-1", "name": "Hero - Text Left, Image Right", "link": "#", "layout_type": "Text_Left_Image_Right", "dominant_side": "left", "min_boxes": 8, "max_boxes": 30, "min_text_blocks": 2, "max_text_blocks": 3 },
  { "id": "hero-TR-IL-1", "name": "Hero - Text Right, Image Left", "link": "#", "layout_type": "Text_Right_Image_Left", "dominant_side": "right", "min_boxes": 8, "max_boxes": 30, "min_text_blocks": 2, "max_text_blocks": 3 },
  { "id": "hero-centered-1", "name": "Hero - Centered Text", "link": "#", "layout_type": "Hero_Centered_Text", "dominant_side": "center", "min_boxes": 1, "max_boxes": 15, "min_text_blocks": 1, "max_text_blocks": 3 },
  { "id": "feature-3col-1", "name": "Feature Section - 3 Columns", "link": "#", "layout_type": "Feature_Grid_3_Col", "dominant_side": "balanced", "min_boxes": 2, "max_boxes": 15, "min_text_blocks": 6, "max_text_blocks": 20 },
  { "id": "cta-centered-1", "name": "CTA - Centered", "link": "#", "layout_type": "CTA_Centered", "dominant_side": "center", "min_boxes": 3, "max_boxes": 15, "min_text_blocks": 1, "max_text_blocks": 4 }
]

# Test function for various matching scenarios
def test_find_best_match_scenarios():
    # Case 1: Left Heavy (from logs)
    # Geo=22, OCR=2, Guess=left -> Expect TL-IR (Side=1, Geo=1, OCR=2 -> Score 4)
    result1 = find_best_match(MOCK_COMPONENTS, box_count=22, text_block_count=2, guessed_dominant_side='left')
    assert result1 is not None, "Test Case 1 Failed: Should find a match"
    assert result1['id'] == 'hero-TL-IR-1', f"Test Case 1 Failed: Expected hero-TL-IR-1, got {result1.get('id') if result1 else 'None'}"

    # Case 2: Right Heavy (from logs)
    # Geo=12, OCR=2, Guess=right -> Expect TR-IL (Side=1, Geo=1, OCR=2 -> Score 4)
    result2 = find_best_match(MOCK_COMPONENTS, box_count=12, text_block_count=2, guessed_dominant_side='right')
    assert result2 is not None, "Test Case 2 Failed: Should find a match"
    assert result2['id'] == 'hero-TR-IL-1', f"Test Case 2 Failed: Expected hero-TR-IL-1, got {result2.get('id') if result2 else 'None'}"

    # Case 3: Centered Hero (from logs)
    # Geo=2, OCR=1, Guess=balanced -> Expect Centered Hero (Side=1, Geo=1, OCR=2 -> Score 4)
    result3 = find_best_match(MOCK_COMPONENTS, box_count=2, text_block_count=1, guessed_dominant_side='balanced')
    assert result3 is not None, "Test Case 3 Failed: Should find a match"
    assert result3['id'] == 'hero-centered-1', f"Test Case 3 Failed: Expected hero-centered-1, got {result3.get('id') if result3 else 'None'}"

    # Case 4: 3-Column (from logs)
    # Geo=3, OCR=14, Guess=left -> Expect 3-Col (Side=0, Geo=1, OCR=2 -> Score 3)
    result4 = find_best_match(MOCK_COMPONENTS, box_count=3, text_block_count=14, guessed_dominant_side='left')
    assert result4 is not None, "Test Case 4 Failed: Should find a match"
    assert result4['id'] == 'feature-3col-1', f"Test Case 4 Failed: Expected feature-3col-1, got {result4.get('id') if result4 else 'None'}"

    # Case 5: Centered CTA (from logs)
    # Geo=3, OCR=3, Guess=right -> Expect CTA (Side=0, Geo=2, OCR=2 -> Score 4)
    result5 = find_best_match(MOCK_COMPONENTS, box_count=3, text_block_count=3, guessed_dominant_side='right')
    assert result5 is not None, "Test Case 5 Failed: Should find a match"
    assert result5['id'] == 'cta-centered-1', f"Test Case 5 Failed: Expected cta-centered-1, got {result5.get('id') if result5 else 'None'}"

    # Case 6: No Match (values outside expected ranges)
    result6 = find_best_match(MOCK_COMPONENTS, box_count=100, text_block_count=100, guessed_dominant_side='left')
    assert result6 is None, "Test Case 6 Failed: Should not find a match"