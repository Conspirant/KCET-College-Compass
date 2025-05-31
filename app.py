import json
import logging
import re
from flask import Flask, render_template, request, jsonify
from collections import defaultdict
import uuid
import os

# Setup logging with more detailed format
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Load JSON data with detailed logging
try:
    logger.info("Attempting to load kcet_cutoffs_master.json")
    with open('kcet_cutoffs_master.json', 'r', encoding='utf-8') as file:
        logger.debug("File opened successfully")
        master_data = json.load(file)
        logger.info("JSON data loaded successfully")
        
        # Extract cutoff data and metadata
        cutoff_data = master_data['cutoffs']
        metadata = master_data['metadata']
        
        # Convert to old format for compatibility
        data = {'kcet_cutoff': {}}
        
        # Group by year and round
        for entry in cutoff_data:
            year = entry['year']
            round_name = entry['round'].lower().replace(' ', '_')
            
            if year not in data['kcet_cutoff']:
                data['kcet_cutoff'][year] = {}
            
            if round_name not in data['kcet_cutoff'][year]:
                data['kcet_cutoff'][year][round_name] = {}
            
            college_key = entry['institute_code']
            if college_key not in data['kcet_cutoff'][year][round_name]:
                data['kcet_cutoff'][year][round_name][college_key] = {
                    'institute_name': entry['institute'],
                    'institute_code': entry['institute_code'],
                    'courses': {}
                }
            
            if entry['course'] not in data['kcet_cutoff'][year][round_name][college_key]['courses']:
                data['kcet_cutoff'][year][round_name][college_key]['courses'][entry['course']] = {}
            
            data['kcet_cutoff'][year][round_name][college_key]['courses'][entry['course']][entry['category']] = entry['cutoff_rank']
        
        logger.info("Successfully converted master JSON to app format")
        logger.debug(f"Years available: {list(data['kcet_cutoff'].keys())}")
        
except FileNotFoundError:
    logger.error("kcet_cutoffs_master.json not found, trying original file")
    with open('kcet_cutoffs.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
        logger.info("Loaded original JSON file")
except json.JSONDecodeError as e:
    logger.error("JSON file is malformed: %s", e)
    logger.error("Error occurred at line %d, column %d", e.lineno, e.colno)
    raise
except Exception as e:
    logger.error("Unexpected error loading JSON: %s", str(e))
    raise

# Initialize institutes list
institutes = []
institute_set = set()

# Build institutes list from cutoff data
if 'metadata' in data and 'cutoffs' in data:
    # New JSON format
    logger.info("Using new JSON format with metadata")
    cutoff_data = data['cutoffs']
    metadata = data['metadata']
    
    # Extract unique institutes
    for entry in cutoff_data:
        institute_key = f"{entry['institute_code']}_{entry['institute']}"
        if institute_key not in institute_set:
            institutes.append({
                'key': institute_key,
                'name': entry['institute'],
                'code': entry['institute_code']
            })
            institute_set.add(institute_key)
    
elif 'kcet_cutoff' in data:
    # Old JSON format
    logger.info("Using old JSON format")
    # Extract institutes from old format
    for year_data in data['kcet_cutoff'].values():
        for round_data in year_data.values():
            for college_key, college_data in round_data.items():
                institute_key = f"{college_data['institute_code']}_{college_data['institute_name']}"
                if institute_key not in institute_set:
                    institutes.append({
                        'key': institute_key,
                        'name': college_data['institute_name'],
                        'code': college_data['institute_code']
                    })
                    institute_set.add(institute_key)
else:
    logger.error("Invalid JSON structure")
    raise ValueError("Invalid JSON structure: missing required keys")

# Sort institutes by name
institutes.sort(key=lambda x: x['name'])
logger.info(f"Processed {len(institutes)} institutes")

# Update round name mapping based on actual data
round_name_map = defaultdict(dict)
for entry in cutoff_data:
    year = entry['year']
    round_info = entry['round']
    round_key = round_info.lower().replace(' ', '_')
    round_name_map[year][round_key] = f"{year} {round_info}"

logger.info("Available rounds by year:")
for year, rounds in round_name_map.items():
    logger.info(f"{year}: {list(rounds.values())}")

# Update the course name mappings
COURSE_FULL_NAMES = {
    # Computer Science & IT Group
    'CSE': 'Computer Science & Engineering',
    'AI & ML': 'Artificial Intelligence & Machine Learning',
    'ISE': 'Information Science & Engineering',
    'DS': 'Data Science & Engineering',
    'CY': 'Computer Science & Engineering (Cyber Security)',
    'CA': 'Computer Science & Engineering (AI & ML)',
    'CB': 'Computer Science & Business Systems',
    'CD': 'Computer Science & Design Engineering',
    'IC': 'Computer Science & Engineering (IoT & Cyber Security)',
    'LE': 'Computer Science & Engineering (AI & ML)',
    'LK': 'Computer Science & Engineering (IoT)',
    'YA': 'Computer Science & Engineering (Robotics)',
    'YB': 'Computer Science & Engineering (Data Analytics)',
    'CU': 'Information Science & Engineering',
    'LG': 'Computer Science & Engineering',
    'LH': 'Information Science & Engineering',
    'ZC': 'Computer Science & Engineering',
    'CF': 'Computer Science & Engineering (AI)',
    'BW': 'Computer Science & Engineering',
    'ZO': 'Computer Science & Business Systems',
    'CW': 'Information Technology Engineering',

    # Electronics & Communication Group
    'ECE': 'Electronics & Communication Engineering',
    'EEE': 'Electrical & Electronics Engineering',
    'EI': 'Electronics & Instrumentation Engineering',
    'ET': 'Electronics & Telecommunication Engineering',
    'EV': 'Electronics & Communication (VLSI Design)',
    'ES': 'Electronics & Computer Engineering',
    'TC': 'Telecommunication Engineering',
    'MD': 'Medical Electronics Engineering',
    'YC': 'Electronics & Communication (Embedded Systems & VLSI)',
    'YG': 'Electronics & Communication (VLSI & Embedded)',
    'BB': 'Electronics & Communication Engineering',
    'YF': 'Electrical & Computer Engineering',

    # Mechanical & Manufacturing Group
    'MECH': 'Mechanical Engineering',
    'MM': 'Mechanical Engineering (Smart Manufacturing)',
    'AU': 'Automobile Engineering',
    'AM': 'Additive Manufacturing Engineering',
    'DB': 'Mechanical Engineering',
    'YI': 'Mechanical Engineering',
    'ZT': 'Mechanical Engineering (Smart Manufacturing)',

    # Aerospace & Aviation Group
    'AERO': 'Aerospace Engineering',
    'AE': 'Aeronautical Engineering',
    'SE': 'Aerospace Engineering',
    'ZA': 'Aeronautical Engineering',

    # Civil & Architecture Group
    'CIVIL': 'Civil Engineering',
    'CE': 'Civil Engineering',
    'CV': 'Civil & Environmental Engineering',
    'AR': 'Architecture',
    'YE': 'Civil Engineering (Construction & Sustainability)',
    'CK': 'Civil Engineering (Kannada Medium)',

    # Biotechnology & Medical Group
    'BT': 'Biotechnology Engineering',
    'BR': 'Biomedical & Robotics Engineering',
    'BO': 'Biotechnology Engineering',

    # Chemical & Mining Group
    'CHEM': 'Chemical Engineering',
    'CH': 'Chemical Engineering',
    'MI': 'Mining Engineering',
    'ZN': 'Pharmaceutical Engineering',

    # Robotics & AI Group
    'RA': 'Robotics & Automation Engineering',
    'AI': 'Artificial Intelligence Engineering',
    'AD': 'Artificial Intelligence & Data Science Engineering',
    'RI': 'Robotics & Artificial Intelligence Engineering',
    'DF': 'Robotics & Automation Engineering',
    'DH': 'Robotics & AI Engineering',
    'BG': 'Artificial Intelligence & Data Science Engineering',
    'BZ': 'Data Science Engineering',
    'DC': 'Data Science Engineering',
    'BF': 'Data Science Engineering',
    'DI': 'Robotics Engineering',

    # Industrial & Management Group
    'IM': 'Industrial Engineering & Management',
    'OT': 'Industrial IoT Engineering',
    'EB': 'Engineering Analysis & Technology',

    # Other Specializations
    'YH': 'Engineering Design',
    'LJ': 'Biomedical Systems Engineering',
    'ST': 'Silk Technology Engineering',
    'TX': 'Textile Engineering'
}

# Update course descriptions
COURSE_DESCRIPTIONS = {
    # Computer Science & IT Group
    'CSE': 'Core computer science focusing on software development, algorithms, and system design',
    'AI & ML': 'Advanced artificial intelligence concepts, machine learning algorithms, and data analytics',
    'ISE': 'Information systems, databases, and enterprise software development',
    'DS': 'Data science, big data analytics, statistical modeling, and data visualization',
    'CY': 'Network security, cryptography, and cyber defense systems',
    'CA': 'AI/ML applications in computer science',
    'CB': 'Computer science with business applications',
    'CD': 'Computer science with design principles',
    'IC': 'IoT systems and cybersecurity',
    'LE': 'AI/ML applications in computer science',
    'LK': 'IoT applications in computer science',
    'YA': 'Robotics applications in computer science',
    'YB': 'Data analytics and computer science',

    # Electronics & Communication Group
    'ECE': 'Digital electronics, communication systems, and signal processing',
    'EEE': 'Power systems, control systems, and electrical machines',
    'EI': 'Electronic instrumentation and control',
    'ET': 'Telecommunications and electronic systems',
    'EV': 'VLSI design and embedded systems',
    'ES': 'Electronics and computer systems integration',
    'TC': 'Telecommunication systems and networks',
    'MD': 'Medical electronics and instrumentation',
    'YC': 'Embedded systems and VLSI design',

    # Mechanical & Manufacturing Group
    'MECH': 'Machine design, thermal engineering, and manufacturing processes',
    'MM': 'Smart manufacturing systems and automation',
    'AU': 'Automotive systems and design',
    'AM': 'Advanced manufacturing and 3D printing',

    # Aerospace & Aviation Group
    'AERO': 'Aircraft design, aerodynamics, and aerospace systems',
    'AE': 'Aircraft and aerospace systems engineering',
    'SE': 'Space and aircraft engineering',
    'ZA': 'Aeronautical and aviation engineering',

    # Civil & Architecture Group
    'CIVIL': 'Structural engineering, construction technology, and infrastructure design',
    'CE': 'Civil infrastructure and construction engineering',
    'CV': 'Civil engineering with environmental focus',
    'AR': 'Architectural design and planning',
    'YE': 'Sustainable civil engineering',

    # Biotechnology & Medical Group
    'BT': 'Genetic engineering, biochemistry, and bioprocess technology',
    'BR': 'Biomedical instrumentation and robotics',
    'BO': 'Biotechnology and bioprocessing',

    # Chemical & Mining Group
    'CHEM': 'Chemical processes, reactor design, and industrial chemistry',
    'CH': 'Chemical process engineering',
    'MI': 'Mining technology and operations',
    'ZN': 'Pharmaceutical process engineering',

    # Robotics & AI Group
    'RA': 'Robot design, control systems, and industrial automation',
    'AI': 'Artificial intelligence systems and applications',
    'AD': 'AI and data science applications',
    'RI': 'Robotics with AI applications',
    'DF': 'Advanced robotics and automation',

    # Industrial & Management Group
    'IM': 'Industrial processes and management',
    'OT': 'Industrial Internet of Things',
    'EB': 'Engineering analysis and technology'
}

# Update course groupings
COURSE_GROUPS = {
    # Computer Science & IT
    'CSE': 'Computer Science & IT',
    'AI & ML': 'Computer Science & IT',
    'ISE': 'Computer Science & IT',
    'DS': 'Computer Science & IT',
    'CY': 'Computer Science & IT',
    'CA': 'Computer Science & IT',
    'CB': 'Computer Science & IT',
    'CD': 'Computer Science & IT',
    'IC': 'Computer Science & IT',
    'LE': 'Computer Science & IT',
    'LK': 'Computer Science & IT',
    'YA': 'Computer Science & IT',
    'YB': 'Computer Science & IT',
    'CU': 'Computer Science & IT',
    'LG': 'Computer Science & IT',
    'LH': 'Computer Science & IT',
    'ZC': 'Computer Science & IT',
    'CF': 'Computer Science & IT',
    'BW': 'Computer Science & IT',
    'ZO': 'Computer Science & IT',
    'CW': 'Computer Science & IT',

    # Electronics & Communication
    'ECE': 'Electronics & Communication',
    'EEE': 'Electronics & Communication',
    'EI': 'Electronics & Communication',
    'ET': 'Electronics & Communication',
    'EV': 'Electronics & Communication',
    'ES': 'Electronics & Communication',
    'TC': 'Electronics & Communication',
    'MD': 'Electronics & Communication',
    'YC': 'Electronics & Communication',
    'YG': 'Electronics & Communication',
    'BB': 'Electronics & Communication',
    'YF': 'Electronics & Communication',

    # Mechanical & Manufacturing
    'MECH': 'Mechanical & Manufacturing',
    'MM': 'Mechanical & Manufacturing',
    'AU': 'Mechanical & Manufacturing',
    'AM': 'Mechanical & Manufacturing',
    'DB': 'Mechanical & Manufacturing',
    'YI': 'Mechanical & Manufacturing',
    'ZT': 'Mechanical & Manufacturing',

    # Aerospace & Aviation
    'AERO': 'Aerospace & Aviation',
    'AE': 'Aerospace & Aviation',
    'SE': 'Aerospace & Aviation',
    'ZA': 'Aerospace & Aviation',

    # Civil & Architecture
    'CIVIL': 'Civil & Architecture',
    'CE': 'Civil & Architecture',
    'CV': 'Civil & Architecture',
    'AR': 'Civil & Architecture',
    'YE': 'Civil & Architecture',
    'CK': 'Civil & Architecture',

    # Biotechnology & Medical
    'BT': 'Biotechnology & Medical',
    'BR': 'Biotechnology & Medical',
    'BO': 'Biotechnology & Medical',
    'LJ': 'Biotechnology & Medical',

    # Chemical & Mining
    'CHEM': 'Chemical & Mining',
    'CH': 'Chemical & Mining',
    'MI': 'Chemical & Mining',
    'ZN': 'Chemical & Mining',

    # Robotics & AI
    'RA': 'Robotics & AI',
    'AI': 'Robotics & AI',
    'AD': 'Robotics & AI',
    'RI': 'Robotics & AI',
    'DF': 'Robotics & AI',
    'DH': 'Robotics & AI',
    'BG': 'Robotics & AI',
    'BZ': 'Robotics & AI',
    'DC': 'Robotics & AI',
    'BF': 'Robotics & AI',
    'DI': 'Robotics & AI',

    # Industrial & Management
    'IM': 'Industrial & Management',
    'OT': 'Industrial & Management',
    'EB': 'Industrial & Management',

    # Other Specializations
    'YH': 'Other Specializations',
    'ST': 'Other Specializations',
    'TX': 'Other Specializations'
}

@app.route('/')
def index():
    """
    Renders the main HTML page for the KCET College Predictor.
    Passes the extracted years and institutes to the Jinja2 template.
    """
    # Extract years from the data and sort in reverse order (newest first)
    years = sorted(list(data['kcet_cutoff'].keys()), reverse=True)
    logger.info(f"Passing years to template: {years}")
    
    return render_template('college.html', years=years, institutes=institutes)

@app.route('/predict', methods=['POST'])
def predict():
    try:
        logger.debug("Received POST request to /predict")
        user_input = request.get_json()
        logger.debug(f"Received input data: {user_input}")
        
        # Validate required fields
        required_fields = ['rank', 'category', 'round_name']
        missing_fields = [field for field in required_fields if field not in user_input or user_input[field] is None]
        
        if missing_fields:
            error_msg = f"Missing required fields: {', '.join(missing_fields)}"
            logger.error(error_msg)
            return jsonify({'error': error_msg}), 400
            
        rank = int(user_input.get('rank'))
        category = user_input.get('category')
        course = user_input.get('course', '')
        round_name = user_input.get('round_name')
        include_nearby = user_input.get('include_nearby', False)
        selected_institute = user_input.get('institute', '')

        logger.debug(f"Processing request: Rank={rank}, Category={category}, Course='{course}', Round='{round_name}'")

        # Extract year from round_name
        year = round_name.split()[0]
        
        # Calculate rank range based on include_nearby flag
        rank_margin = 0.10 if include_nearby else 0  # 10% margin if include_nearby is True, 0% otherwise
        min_rank = int(rank * (1 - rank_margin))
        max_rank = int(rank * (1 + rank_margin))
        
        # Filter cutoffs based on criteria
        matching_colleges = []
        seen_combinations = set()  # To prevent duplicates
        
        for entry in cutoff_data:
            # Skip if year doesn't match (unless "All Rounds" is selected)
            if not round_name.endswith('All Rounds') and entry['year'] != year:
                continue
                
            # Skip if category doesn't match
            if entry['category'] != category:
                continue
                
            # Skip if course doesn't match (when a course is selected)
            if course and entry['course'] != course:
                continue
                
            # Skip if institute doesn't match (when an institute is selected)
            if selected_institute and f"{entry['institute_code']}_{entry['institute']}" != selected_institute:
                continue

            # Include colleges based on rank criteria
            if include_nearby:
                # If nearby ranks included, use the calculated range
                if not (min_rank <= entry['cutoff_rank'] <= max_rank + 50000):
                    continue
            else:
                # If nearby ranks not included, only show colleges with cutoff higher than user's rank
                if entry['cutoff_rank'] < rank:
                    continue

            # Create a unique key for this combination to prevent duplicates
            # Include all relevant fields to ensure uniqueness
            combo_key = (
                f"{entry['institute_code']}_"
                f"{entry['course']}_"
                f"{entry['category']}_"
                f"{entry['cutoff_rank']}_"
                f"{entry['year']}_"
                f"{entry['round']}"
            )
            
            # Skip if we've already seen this exact combination
            if combo_key in seen_combinations:
                continue
            seen_combinations.add(combo_key)
                
            # Calculate rank difference percentage
            rank_diff_percent = ((entry['cutoff_rank'] - rank) / rank) * 100
            
            # All colleges with higher cutoff rank are considered "good match"
            is_likely = entry['cutoff_rank'] >= rank
            
            # Get full course name
            course_code = entry['course']
            course_full_name = COURSE_FULL_NAMES.get(course_code, course_code)
            
            # Format round name to include year if "All Rounds" is selected
            display_round = f"{entry['year']} {entry['round']}" if round_name.endswith('All Rounds') else entry['round']
            
            matching_colleges.append({
                'institute': entry['institute'],
                'institute_code': entry['institute_code'],
                'cutoff_rank': entry['cutoff_rank'],
                'course': course_full_name,
                'course_code': course_code,
                'category': entry['category'],
                'round': display_round,
                'year': entry['year'],
                'likely': is_likely,
                'rank_diff': rank_diff_percent
            })
        
        if not matching_colleges:
            return jsonify({'message': 'No colleges found matching your criteria. Try adjusting your filters or including nearby ranks.'})
        
        # Sort by cutoff rank (ascending) and likelihood
        matching_colleges.sort(key=lambda x: (not x['likely'], x['cutoff_rank']))
        
        # Log some debugging information
        logger.debug(f"Found {len(matching_colleges)} matching colleges after filtering")
        logger.debug(f"First few matches: {matching_colleges[:3]}")
        
        return jsonify(matching_colleges)

    except Exception as e:
        logger.error(f"Error in predict route: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/get_courses')
def get_courses():
    """Returns a list of all available courses that exist in the data."""
    available_courses = set()
    
    try:
        if 'metadata' in data and 'cutoffs' in data:
            # New JSON format
            for entry in cutoff_data:
                if entry['course']:
                    available_courses.add(entry['course'])
        else:
            # Old JSON format - iterate through the nested structure
            for year_data in data['kcet_cutoff'].values():
                for round_data in year_data.values():
                    for college in round_data.values():
                        if 'courses' in college:
                            available_courses.update(college['courses'].keys())
        
        # Convert to list and sort
        course_list = sorted(list(available_courses))
        logger.debug(f"Found {len(course_list)} available courses")
        return jsonify(course_list)
        
    except Exception as e:
        logger.error(f"Error in get_courses route: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
