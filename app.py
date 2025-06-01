import json
import logging
import re
from flask import Flask, render_template, request, jsonify
from collections import defaultdict
import uuid
import os
import difflib

# Setup logging with more detailed format
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Load JSON data with detailed logging
try:
    logger.info("\n=== LOADING DATA ===")
    logger.info("Attempting to load kcet_cutoffs_master.json")
    with open('kcet_cutoffs_master.json', 'r', encoding='utf-8') as file:
        logger.debug("File opened successfully")
        master_data = json.load(file)
        logger.info("JSON data loaded successfully")
        
        # Extract cutoff data and metadata
        cutoff_data = master_data['cutoffs']
        metadata = master_data['metadata']
        
        # Print first few entries to see the structure
        logger.info("\n=== SAMPLE DATA ENTRIES ===")
        for entry in cutoff_data[:3]:
            logger.info(json.dumps(entry, indent=2))
        
        # Print unique values for each field
        logger.info("\n=== UNIQUE VALUES IN DATA ===")
        logger.info(f"Years: {sorted(set(entry['year'] for entry in cutoff_data))}")
        logger.info(f"Categories: {sorted(set(entry['category'] for entry in cutoff_data))}")
        logger.info(f"Rounds: {sorted(set(entry['round'] for entry in cutoff_data))}")
        logger.info(f"Sample Courses: {sorted(set(entry['course'] for entry in cutoff_data))[:10]}")
        logger.info("===========================\n")
        
        # Print counts
        logger.info("\n=== DATA STATISTICS ===")
        logger.info(f"Total entries: {len(cutoff_data)}")
        logger.info(f"Unique years: {len(set(entry['year'] for entry in cutoff_data))}")
        logger.info(f"Unique categories: {len(set(entry['category'] for entry in cutoff_data))}")
        logger.info(f"Unique rounds: {len(set(entry['round'] for entry in cutoff_data))}")
        logger.info(f"Unique courses: {len(set(entry['course'] for entry in cutoff_data))}")
        logger.info("=======================\n")
        
        # Print available values
        years = sorted(set(entry['year'] for entry in cutoff_data))
        rounds = sorted(set(entry['round'] for entry in cutoff_data))
        categories = sorted(set(entry['category'] for entry in cutoff_data))
        courses = sorted(set(entry['course'] for entry in cutoff_data))
        
        logger.info("\n=== AVAILABLE DATA VALUES ===")
        logger.info(f"Years available: {years}")
        logger.info(f"Rounds available: {rounds}")
        logger.info(f"Categories available: {categories}")
        logger.info(f"Courses available: {courses}")
        logger.info("===========================\n")
        
        # Print some sample entries
        logger.info("\n=== SAMPLE ENTRIES ===")
        for entry in cutoff_data[:3]:
            logger.info(json.dumps(entry, indent=2))
        logger.info("====================\n")
        
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
    'AD': 'Artificial Intelligence And Data Science',
    'AE': 'Aeronautical Engineering',
    'AI': 'Artificial Intelligence and Machine Learning',
    'AM': 'B TECH IN COMP SCI & ENGG (AI & ML)',
    'AR': 'Architecture',
    'AT': 'Automotive Engineering',
    'AU': 'Automobile Engineering',
    'BA': 'B.Tech(Agri.Engg)',
    'BB': 'B TECH IN ELECTRONICS & COMMUNICATION ENGINEERING',
    'BC': 'BTech Computer Technology',
    'BD': 'Computer Science Engineering-Big Data',
    'BE': 'Bio-Electronics Engineering',
    'BF': 'B TECH (HONS) COMP SCI AND ENGG(DATA SCIENCE)',
    'BG': 'B TECH IN ARTIFICIAL INTELLI AND DATA SCIENCE',
    'BH': 'B TECH IN ARTIFICIAL INTELLIGENCE AND ML',
    'BI': 'Information Technology and Engineering',
    'BJ': 'B TECH IN ELECTRICAL & ELECTRONICS ENGINEERING',
    'BK': 'B TECH IN ENERGY ENGINEERING',
    'BL': 'B TECH IN AERO SPACE ENGINEERING',
    'BM': 'Bio Medical Engineering',
    'BN': 'B TECH IN COMPUTER SCIENCE AND TECH(BIG DATA)',
    'BO': 'B TECH IN BIO-TECHNOLOGY',
    'BP': 'B TECH IN CIVIL ENGINEERING',
    'BQ': 'B TECH IN COMPUTER SCIENCE AND TECHNOLOGY',
    'BR': 'BioMedical and Robotic Engineering',
    'BS': 'Bachelor of Science (Honours)',
    'BT': 'Bio Technology',
    'BU': 'B TECH IN COMPUTER SCIENCE AND INFO TECH',
    'BV': 'B TECH IN COMPUTER ENGINEERING',
    'BW': 'B TECH IN COMPUTER SCIENCE AND ENGINEERING',
    'BX': 'B TECH IN COMP SCIENCE AND ENGG(CYBER SECURITY)',
    'BY': 'B TECH IN COMP SCIENCE AND TECHNOLOGY(DEV OPS)',
    'BZ': 'B TECH IN COMPUTER SCIENCE AND ENGG(DATA SCIENCE)',
    'CA': 'Computer Science Engineering-AI, Machine Learning',
    'CB': 'Computer Science and Business Systems',
    'CC': 'Computer and Communication Engineering',
    'CD': 'Computer Science and Design',
    'CE': 'Civil Engineering',
    'CF': 'B TECH IN COMPUTER SCIENCE AND ENGINEERING',
    'CG': 'Computer Science and Technology',
    'CH': 'Chemical Engineering',
    'CI': 'Computer Science and Information Technology',
    'CK': 'Civil Engineering (Kannada Medium)',
    'CL': 'B TECH IN ELECTRONICS & COMPUTER ENGINEERING',
    'CM': 'ELECTRONICS ENGINEERING(VLSI DESIGN & TECH)',
    'CN': 'B TECH IN COMP SCI AND ENGG(IOT AND BLOCK CHAIN)',
    'CO': 'Computer Engineering',
    'CP': 'Civil Engineering and Planning',
    'CQ': 'B TECH IN COMPUTER SCIENCE AND ENGINEERING(IOT)',
    'CR': 'Ceramics and Cement Technology',
    'CS': 'Computers Science And Engineering',
    'CT': 'Construction Technology and Management',
    'CU': 'B TECH IN INFORMATION SCIENCE ENGINEERING',
    'CV': 'Civil Environmental Engineering',
    'CW': 'B TECH IN INFORMATION TECHNOLOGY',
    'CX': 'B TECH IN INFORMATION SCIENCE & TECHNOLOGY',
    'CY': 'Computer Science Engineering-Cyber Security',
    'CZ': 'B TECH IN COMPUTER SCIENCE AND ENGG(BLOCK CHAIN)',
    'DA': 'B TECH IN MATHAMATICS AND COMPUTING',
    'DB': 'B TECH IN MECHANICAL ENGINEERING',
    'DC': 'Data Sciences',
    'DD': 'B TECH IN MECHATRONICS ENGINEERING',
    'DE': 'B TECH IN PETROLEUM ENGINEERING',
    'DF': 'B TECH IN ROBOTICS AND AUTOMATION',
    'DG': 'DESIGN',
    'DH': 'B Tech in ROBOTICS AND ARTIFICIAL INTELLIGENCE',
    'DI': 'B TECH IN ROBOTIC ENGINEERING',
    'DJ': 'B TECH IN ROBOTICS',
    'DK': 'B TECH IN COMPUTER SCIENCE AND SYSTEM ENGG',
    'DL': 'B TECH IN COMPUTER SCIENCE',
    'DM': 'COMPUTER SCIENCE ENGINEERING (NETWORKS)',
    'DN': 'B Tech in VLSI',
    'DS': 'Computer Science Engineering-Data Sciences',
    'EA': 'Agriculture Engineering',
    'EB': 'ELECTRONICS AND COMMUNICATION (ADV COMM TECH)',
    'EC': 'Electronics and Communication Engineering',
    'EE': 'Electrical And Electronics Engineering',
    'EG': 'Energy Engineering',
    'EI': 'Electronics and Instrumentation Engineering',
    'EL': 'Electronics and Instrumentation Tech.',
    'EN': 'Environmental Engineering',
    'EP': 'BTech Technology and Entrepreneurship',
    'ER': 'Electrical and Computer Engineering',
    'ES': 'Electronics and Computer Engineering',
    'ET': 'Electronics and Telecommunication Engineering',
    'EV': 'Electronics Engineering(VLSI Design Technology)',
    'IB': 'Computer Science Engg-IoT including Block Chain',
    'IC': 'CS-Internet of things, Cyber Security(Block Chain)',
    'IE': 'Information Science and Engineering',
    'IG': 'Information Technology',
    'II': 'Elec. and Communication- Industrial Integrated',
    'IM': 'Industrial Engineering and Management',
    'IO': 'Computer Science Engineering-Internet of Things',
    'IP': 'Industrial and Production Engineering',
    'IS': 'Information Science and Technology',
    'IT': 'Instrumentation Technology',
    'IY': 'CS - Information Technology-Cyber Security',
    'LA': 'B Plan',
    'LC': 'Computer Science Engineering-Block Chain',
    'MC': 'Mathematics and Computing',
    'MD': 'Medical Electronics',
    'ME': 'Mechanical Engineering',
    'MK': 'Mechanical Engineering (Kannada Medium)',
    'MM': 'Mechanical and Smart Manufacturing',
    'MR': 'Marine Engineering',
    'MS': 'Manufacturing Science and Engineering',
    'MT': 'Mechatronics',
    'NT': 'Nano Technology',
    'OP': 'Computer Science Engineering-Dev Ops',
    'OT': 'Industrial IOT',
    'PE': 'Petrochem Engineering',
    'PL': 'Petroleum Engineering',
    'PM': 'Precision Manufacturing',
    'PT': 'Polymer Science and Technology',
    'RA': 'Robotics and Automation',
    'RB': 'Robotics',
    'RI': 'Robotics and Artificial Intelligence',
    'RM': 'Computer Science - Robotic Engineering-AI and ML',
    'RO': 'Automation and Robotics Engineering',
    'SA': 'Smart Agritech',
    'SE': 'Aero Space Engineering',
    'SS': 'Computer Science and System Engineering',
    'ST': 'Silk Technology',
    'TC': 'Telecommunication Engineering',
    'TE': 'Tool Engineering',
    'TI': 'Industrial IoT',
    'TX': 'Textile Technology',
    'UP': 'Planning',
    'UR': 'Planning',
    'ZC': 'COMPUTER SCIENCE',
    'mn': 'Mining Engineering'
}

# Update course descriptions
COURSE_DESCRIPTIONS = {
    # Computer Science & IT Group
    'AD': 'AI and data science applications',
    'AI': 'Advanced artificial intelligence and machine learning',
    'AM': 'Computer science with AI and ML specialization',
    'BD': 'Big data analytics and processing',
    'BF': 'Honors program in data science',
    'BG': 'AI and data science integration',
    'BH': 'Advanced AI and ML technologies',
    'BI': 'IT systems and engineering',
    'BN': 'Big data technologies',
    'BQ': 'Computer science fundamentals',
    'BU': 'CS and IT integration',
    'BV': 'Computer engineering fundamentals',
    'BW': 'Standard CSE program',
    'BX': 'Cyber security focus',
    'BY': 'DevOps and deployment focus',
    'BZ': 'Data science specialization',
    'CA': 'AI and ML integration',
    'CB': 'Business-focused CS',
    'CC': 'Computer and communication systems',
    'CD': 'Design-focused CS',
    'CF': 'AI specialization',
    'CG': 'Core computer science',
    'CI': 'Information technology focus',
    'CN': 'IoT and blockchain technologies',
    'CO': 'Computer systems engineering',
    'CQ': 'IoT specialization',
    'CS': 'Core computer science',
    'CU': 'Information science focus',
    'CW': 'Information technology systems',
    'CX': 'Information science and technology',
    'CY': 'Cyber security specialization',
    'CZ': 'Blockchain technology focus',
    'DK': 'Systems engineering approach',
    'DL': 'Core computer science',
    'DM': 'Network specialization',
    'DS': 'Data science focus',
    'IB': 'IoT and blockchain integration',
    'IC': 'IoT and cybersecurity',
    'IE': 'Information systems',
    'IG': 'Information technology',
    'IO': 'Internet of Things focus',
    'IS': 'Information systems',
    'IY': 'Cybersecurity focus',
    'LC': 'Blockchain specialization',
    'OP': 'DevOps focus',
    'SS': 'Systems engineering',
    'ZC': 'Computer science core',

    # Electronics & Communication Group
    'BB': 'Electronics and communication',
    'BE': 'Bioelectronics systems',
    'BJ': 'Electrical and electronics',
    'CL': 'Electronics and computer integration',
    'CM': 'VLSI design focus',
    'DN': 'VLSI technology',
    'EB': 'Advanced communication',
    'EC': 'Core electronics and communication',
    'EE': 'Electrical and electronic systems',
    'EI': 'Electronics and instrumentation',
    'EL': 'Instrumentation technology',
    'ER': 'Electrical and computer systems',
    'ES': 'Electronics and computer integration',
    'ET': 'Telecommunication systems',
    'EV': 'VLSI design specialization',
    'II': 'Industrial electronics',
    'IT': 'Instrumentation systems',
    'MD': 'Medical electronics',
    'TC': 'Telecommunication engineering',

    # Mechanical & Manufacturing Group
    'AT': 'Automotive systems design',
    'AU': 'Automobile engineering',
    'DB': 'Mechanical engineering',
    'ME': 'Core mechanical engineering',
    'MK': 'Mechanical engineering (Kannada)',
    'MM': 'Smart manufacturing systems',
    'MS': 'Manufacturing processes',
    'PM': 'Precision engineering',
    'TE': 'Tool engineering',

    # Civil & Architecture Group
    'AR': 'Architectural design',
    'BP': 'Civil engineering',
    'CE': 'Core civil engineering',
    'CK': 'Civil engineering (Kannada)',
    'CP': 'Civil planning',
    'CT': 'Construction technology',
    'CV': 'Environmental focus',
    'LA': 'Planning and design',
    'UP': 'Urban planning',
    'UR': 'Rural planning',

    # Chemical & Biotechnology Group
    'BM': 'Biomedical systems',
    'BO': 'Biotechnology',
    'BR': 'Biomedical robotics',
    'BT': 'Biotechnology',
    'CH': 'Chemical processes',
    'CR': 'Ceramics technology',
    'PE': 'Petrochemical engineering',
    'PL': 'Petroleum engineering',
    'PT': 'Polymer technology',

    # Aerospace & Aviation Group
    'AE': 'Aeronautical systems',
    'BL': 'Aerospace engineering',
    'MR': 'Marine systems',
    'SE': 'Space engineering',

    # Robotics & Automation Group
    'DF': 'Robotics and automation',
    'DH': 'AI-powered robotics',
    'DI': 'Robotic systems',
    'DJ': 'Robotics engineering',
    'RA': 'Automation systems',
    'RB': 'Core robotics',
    'RI': 'AI and robotics',
    'RM': 'Robotics with AI/ML',
    'RO': 'Industrial automation',

    # Other Specialized Programs
    'BA': 'Agricultural engineering',
    'BC': 'Computer technology',
    'BK': 'Energy systems',
    'BS': 'Science honors',
    'DA': 'Mathematical computing',
    'DC': 'Data sciences',
    'DD': 'Mechatronics systems',
    'DE': 'Petroleum engineering',
    'DG': 'Design engineering',
    'EA': 'Agricultural systems',
    'EG': 'Energy engineering',
    'EN': 'Environmental systems',
    'EP': 'Technology entrepreneurship',
    'IM': 'Industrial management',
    'IP': 'Production engineering',
    'MC': 'Mathematical computing',
    'MT': 'Mechatronics systems',
    'NT': 'Nanotechnology',
    'OT': 'Industrial IoT',
    'SA': 'Smart agriculture',
    'ST': 'Silk technology',
    'TI': 'Industrial IoT systems',
    'TX': 'Textile engineering',
    'mn': 'Mining engineering'
}

# Update course groupings
COURSE_GROUPS = {
    # Computer Science & IT
    'AD': 'Computer Science & IT',
    'AI': 'Computer Science & IT',
    'AM': 'Computer Science & IT',
    'BD': 'Computer Science & IT',
    'BF': 'Computer Science & IT',
    'BG': 'Computer Science & IT',
    'BH': 'Computer Science & IT',
    'BI': 'Computer Science & IT',
    'BN': 'Computer Science & IT',
    'BQ': 'Computer Science & IT',
    'BU': 'Computer Science & IT',
    'BV': 'Computer Science & IT',
    'BW': 'Computer Science & IT',
    'BX': 'Computer Science & IT',
    'BY': 'Computer Science & IT',
    'BZ': 'Computer Science & IT',
    'CA': 'Computer Science & IT',
    'CB': 'Computer Science & IT',
    'CC': 'Computer Science & IT',
    'CD': 'Computer Science & IT',
    'CF': 'Computer Science & IT',
    'CG': 'Computer Science & IT',
    'CI': 'Computer Science & IT',
    'CN': 'Computer Science & IT',
    'CO': 'Computer Science & IT',
    'CQ': 'Computer Science & IT',
    'CS': 'Computer Science & IT',
    'CU': 'Computer Science & IT',
    'CW': 'Computer Science & IT',
    'CX': 'Computer Science & IT',
    'CY': 'Computer Science & IT',
    'CZ': 'Computer Science & IT',
    'DK': 'Computer Science & IT',
    'DL': 'Computer Science & IT',
    'DM': 'Computer Science & IT',
    'DS': 'Computer Science & IT',
    'IB': 'Computer Science & IT',
    'IC': 'Computer Science & IT',
    'IE': 'Computer Science & IT',
    'IG': 'Computer Science & IT',
    'IO': 'Computer Science & IT',
    'IS': 'Computer Science & IT',
    'IY': 'Computer Science & IT',
    'LC': 'Computer Science & IT',
    'OP': 'Computer Science & IT',
    'SS': 'Computer Science & IT',
    'ZC': 'Computer Science & IT',

    # Electronics & Communication
    'BB': 'Electronics & Communication',
    'BE': 'Electronics & Communication',
    'BJ': 'Electronics & Communication',
    'CL': 'Electronics & Communication',
    'CM': 'Electronics & Communication',
    'DN': 'Electronics & Communication',
    'EB': 'Electronics & Communication',
    'EC': 'Electronics & Communication',
    'EE': 'Electronics & Communication',
    'EI': 'Electronics & Communication',
    'EL': 'Electronics & Communication',
    'ER': 'Electronics & Communication',
    'ES': 'Electronics & Communication',
    'ET': 'Electronics & Communication',
    'EV': 'Electronics & Communication',
    'II': 'Electronics & Communication',
    'IT': 'Electronics & Communication',
    'MD': 'Electronics & Communication',
    'TC': 'Electronics & Communication',

    # Mechanical & Manufacturing
    'AT': 'Mechanical & Manufacturing',
    'AU': 'Mechanical & Manufacturing',
    'DB': 'Mechanical & Manufacturing',
    'ME': 'Mechanical & Manufacturing',
    'MK': 'Mechanical & Manufacturing',
    'MM': 'Mechanical & Manufacturing',
    'MS': 'Mechanical & Manufacturing',
    'PM': 'Mechanical & Manufacturing',
    'TE': 'Mechanical & Manufacturing',

    # Civil & Architecture
    'AR': 'Civil & Architecture',
    'BP': 'Civil & Architecture',
    'CE': 'Civil & Architecture',
    'CK': 'Civil & Architecture',
    'CP': 'Civil & Architecture',
    'CT': 'Civil & Architecture',
    'CV': 'Civil & Architecture',
    'LA': 'Civil & Architecture',
    'UP': 'Civil & Architecture',
    'UR': 'Civil & Architecture',

    # Chemical & Biotechnology
    'BM': 'Chemical & Biotechnology',
    'BO': 'Chemical & Biotechnology',
    'BR': 'Chemical & Biotechnology',
    'BT': 'Chemical & Biotechnology',
    'CH': 'Chemical & Biotechnology',
    'CR': 'Chemical & Biotechnology',
    'PE': 'Chemical & Biotechnology',
    'PL': 'Chemical & Biotechnology',
    'PT': 'Chemical & Biotechnology',

    # Aerospace & Aviation
    'AE': 'Aerospace & Aviation',
    'BL': 'Aerospace & Aviation',
    'MR': 'Aerospace & Aviation',
    'SE': 'Aerospace & Aviation',

    # Robotics & Automation
    'DF': 'Robotics & Automation',
    'DH': 'Robotics & Automation',
    'DI': 'Robotics & Automation',
    'DJ': 'Robotics & Automation',
    'RA': 'Robotics & Automation',
    'RB': 'Robotics & Automation',
    'RI': 'Robotics & Automation',
    'RM': 'Robotics & Automation',
    'RO': 'Robotics & Automation',

    # Other Specialized Programs
    'BA': 'Other Specialized Programs',
    'BC': 'Other Specialized Programs',
    'BK': 'Other Specialized Programs',
    'BS': 'Other Specialized Programs',
    'DA': 'Other Specialized Programs',
    'DC': 'Other Specialized Programs',
    'DD': 'Other Specialized Programs',
    'DE': 'Other Specialized Programs',
    'DG': 'Other Specialized Programs',
    'EA': 'Other Specialized Programs',
    'EG': 'Other Specialized Programs',
    'EN': 'Other Specialized Programs',
    'EP': 'Other Specialized Programs',
    'IM': 'Other Specialized Programs',
    'IP': 'Other Specialized Programs',
    'MC': 'Other Specialized Programs',
    'MT': 'Other Specialized Programs',
    'NT': 'Other Specialized Programs',
    'OT': 'Other Specialized Programs',
    'SA': 'Other Specialized Programs',
    'ST': 'Other Specialized Programs',
    'TI': 'Other Specialized Programs',
    'TX': 'Other Specialized Programs',
    'mn': 'Other Specialized Programs'
}

# Create reverse mapping for course names to codes
COURSE_CODES = {full_name: code for code, full_name in COURSE_FULL_NAMES.items()}

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
        logger.info("\n=== NEW PREDICTION REQUEST ===")
        
        # Log raw request data
        logger.info("Raw request data:")
        logger.info(f"Content-Type: {request.content_type}")
        logger.info(f"Raw data: {request.get_data(as_text=True)}")
        
        try:
            user_input = request.get_json()
            logger.info(f"Parsed JSON input: {json.dumps(user_input, indent=2)}")
        except Exception as e:
            logger.error(f"Failed to parse JSON: {str(e)}")
            return jsonify({
                'error': 'Invalid JSON data',
                'details': str(e)
            }), 400
        
        if not user_input:
            logger.error("Empty request body")
            return jsonify({
                'error': 'Empty request body',
                'help': 'Request must include rank, category, and round_name'
            }), 400
            
        # Validate required fields
        required_fields = ['rank', 'category', 'round_name']
        missing_fields = [field for field in required_fields if field not in user_input or user_input[field] is None]
        
        if missing_fields:
            error_msg = f"Missing required fields: {', '.join(missing_fields)}"
            logger.error(error_msg)
            return jsonify({
                'error': error_msg,
                'required_fields': required_fields,
                'received_fields': list(user_input.keys())
            }), 400
            
        # Log the values we received
        logger.info("Received values:")
        logger.info(f"rank: {user_input.get('rank')}")
        logger.info(f"category: {user_input.get('category')}")
        logger.info(f"round_name: {user_input.get('round_name')}")
        logger.info(f"course: {user_input.get('course', '')}")
        
        try:
            rank = int(user_input.get('rank'))
        except ValueError:
            return jsonify({
                'error': 'Invalid rank value',
                'received': user_input.get('rank'),
                'help': 'Rank must be a valid number'
            }), 400
            
        category_input = user_input.get('category', '')
        course_input = user_input.get('course', '')
        round_name = user_input.get('round_name')
        include_nearby = user_input.get('include_nearby', False)
        selected_institute = user_input.get('institute', '')

        # Log available values for comparison
        logger.info("\n=== Available Values in Database ===")
        logger.info(f"Categories: {sorted(set(entry['category'] for entry in cutoff_data))}")
        logger.info(f"Rounds: {sorted(set(entry['round'] for entry in cutoff_data))}")
        if course_input:
            logger.info(f"Courses: {sorted(set(entry['course'] for entry in cutoff_data))}")
        logger.info("================================")

        # Forgiving matching for category
        def best_match(val, options):
            matches = difflib.get_close_matches(val, options, n=1, cutoff=0.6)
            return matches[0] if matches else None
        
        # Normalize all available values for matching
        norm = lambda s: s.strip().lower().replace(' ', '').replace('&', 'and') if isinstance(s, str) else s
        norm_categories = {norm(cat): cat for cat in sorted(set(entry['category'] for entry in cutoff_data))}
        norm_courses = {norm(c): c for c in sorted(set(entry['course'] for entry in cutoff_data))}
        norm_rounds = {norm(r): r for r in sorted(set(entry['round'] for entry in cutoff_data))}
        
        # Match category
        category_norm = norm(category_input)
        category = norm_categories.get(category_norm) or best_match(category_norm, list(norm_categories.keys()))
        if category:
            category = norm_categories.get(category, category)
        else:
            return jsonify({'error': f"Category '{category_input}' not found.", 'suggestions': sorted(norm_categories.keys())}), 400
        
        # Match course
        course_norm = norm(course_input)
        course = norm_courses.get(course_norm) or best_match(course_norm, list(norm_courses.keys()))
        if course:
            course = norm_courses.get(course, course)
        else:
            return jsonify({'error': f"Course '{course_input}' not found.", 'suggestions': sorted(norm_courses.keys())}), 400
        
        # Extract year and round information
        try:
            if ' ' not in round_name:
                if not sorted(set(entry['year'] for entry in cutoff_data)):
                    return jsonify({'error': 'No year data available'}), 400
                year_from_input_round_name = sorted(set(entry['year'] for entry in cutoff_data))[-1]  # Latest year
                specific_round_text_from_input = round_name
            else:
                parts = round_name.split(' ', 1)
                year_from_input_round_name = parts[0]
                specific_round_text_from_input = parts[1]
            is_all_rounds_selected_for_year = 'all rounds' in round_name.lower()
            input_round_norm = norm(specific_round_text_from_input)
            round_match = norm_rounds.get(input_round_norm) or best_match(input_round_norm, list(norm_rounds.keys()))
            if round_match:
                round_match = norm_rounds.get(round_match, round_match)
            else:
                return jsonify({'error': f"Round '{specific_round_text_from_input}' not found.", 'suggestions': sorted(norm_rounds.keys())}), 400
        except Exception as e:
            logger.error(f"Error parsing round name '{round_name}': {str(e)}")
            return jsonify({'error': f"Invalid round format: {round_name}"}), 400
        
        # Calculate rank range based on include_nearby flag
        rank_margin = 0.15 if include_nearby else 0  # Changed from 0.10 to 0.15 for ±15%
        min_rank = int(rank * (1 - rank_margin))
        max_rank = int(rank * (1 + rank_margin))
        
        # Pre-filter the data based on year and category
        filtered_data = []
        for entry in cutoff_data:
            if entry['year'] != year_from_input_round_name:
                continue
            if entry['category'] != category:
                continue
            if course and entry['course'] != course:
                continue
            if selected_institute and f"{entry['institute_code']}_{entry['institute']}" != selected_institute:
                continue
            if not is_all_rounds_selected_for_year and norm(entry['round']) != input_round_norm:
                continue
            filtered_data.append(entry)
        if not filtered_data:
            return jsonify({'error': 'No colleges found matching your criteria.', 'debug': {
                'year': year_from_input_round_name,
                'category': category,
                'course': course,
                'round': round_match,
                'available_years': sorted(set(e['year'] for e in cutoff_data)),
                'available_categories': sorted(set(e['category'] for e in cutoff_data)),
                'available_courses': sorted(set(e['course'] for e in cutoff_data)),
                'available_rounds': sorted(set(e['round'] for e in cutoff_data))
            }}), 404
        
        # Filter cutoffs based on remaining criteria
        matching_colleges = []
        seen_combinations = set()
        
        for entry in filtered_data:
            try:
                # Handle round filtering if specific round is selected
                if not is_all_rounds_selected_for_year:
                    entry_round_normalized = ' '.join(entry['round'].lower().split())
                    if entry_round_normalized != input_round_norm:
                        continue

                # Handle rank criteria with more lenient matching
                if include_nearby:
                    # Allow ranks within ±15% range and up to 75000 ranks higher
                    if not (min_rank <= entry['cutoff_rank'] <= max_rank + 75000):
                        continue
                else:
                    # For non-nearby matches, still allow some flexibility
                    if entry['cutoff_rank'] < rank - 1000:  # Allow slightly lower ranks
                        continue

                # Create a unique key for this combination
                combo_key = f"{entry['institute_code']}_{entry['course']}_{entry['category']}_{entry['cutoff_rank']}_{entry['year']}_{entry['round']}"
                
                if combo_key in seen_combinations:
                    continue
                seen_combinations.add(combo_key)
                
                # Calculate rank difference percentage
                rank_diff_percent = ((entry['cutoff_rank'] - rank) / rank) * 100
                
                # Get full course name (use dict.get with default to avoid extra lookups)
                course_full_name = COURSE_FULL_NAMES.get(entry['course'], entry['course'])
                
                matching_colleges.append({
                    'institute': entry['institute'],
                    'institute_code': entry['institute_code'],
                    'cutoff_rank': entry['cutoff_rank'],
                    'course': course_full_name,
                    'course_code': entry['course'],
                    'category': entry['category'],
                    'round': entry['round'],
                    'year': entry['year'],
                    'likely': entry['cutoff_rank'] >= rank,
                    'rank_diff': rank_diff_percent
                })
                
            except Exception as e:
                logger.error(f"Error processing entry: {str(e)}")
                continue
        
        if not matching_colleges:
            return jsonify({
                'message': 'No colleges found matching your criteria. Try adjusting your filters or including nearby ranks.',
                'criteria': {
                    'year': year_from_input_round_name,
                    'round': round_match,
                    'is_all_rounds': is_all_rounds_selected_for_year,
                    'category': category,
                    'course': course,
                    'institute': selected_institute,
                    'rank_range': f"{min_rank} to {max_rank + 75000 if include_nearby else rank - 1000}"
                },
                'available_values': {
                    'years': sorted(set(e['year'] for e in cutoff_data)),
                    'categories': sorted(set(e['category'] for e in cutoff_data)),
                    'rounds': sorted(set(e['round'] for e in cutoff_data))
                }
            })
        
        # Sort by cutoff rank and likelihood
        matching_colleges.sort(key=lambda x: (not x['likely'], x['cutoff_rank']))
        
        return jsonify(matching_colleges)
    except Exception as e:
        logger.error(f"Unexpected error in predict route: {str(e)}", exc_info=True)
        return jsonify({'error': f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/get_courses')
def get_courses():
    """Returns a list of all available courses."""
    try:
        # Define course groups
        GROUPS = {
            'CS_IT': 'Computer Science & IT',
            'ECE': 'Electronics & Communication',
            'MECH': 'Mechanical & Manufacturing',
            'CIVIL': 'Civil & Architecture',
            'CHEM_BIO': 'Chemical & Biotechnology',
            'AERO': 'Aerospace & Aviation',
            'ROBOTICS': 'Robotics & Automation',
            'OTHERS': 'Other Specialized Programs'
        }

        # Define courses with their groups
        courses = [
            # Computer Science & IT
            {'code': 'CS', 'name': 'Computer Science And Engineering', 'group': GROUPS['CS_IT']},
            {'code': 'IS', 'name': 'Information Science and Technology', 'group': GROUPS['CS_IT']},
            {'code': 'AI', 'name': 'Artificial Intelligence and Machine Learning', 'group': GROUPS['CS_IT']},
            {'code': 'DS', 'name': 'Data Science', 'group': GROUPS['CS_IT']},

            # Electronics & Communication
            {'code': 'EC', 'name': 'Electronics and Communication Engineering', 'group': GROUPS['ECE']},
            {'code': 'EE', 'name': 'Electrical and Electronics Engineering', 'group': GROUPS['ECE']},

            # Mechanical & Manufacturing
            {'code': 'ME', 'name': 'Mechanical Engineering', 'group': GROUPS['MECH']},
            {'code': 'AU', 'name': 'Automobile Engineering', 'group': GROUPS['MECH']},

            # Civil & Architecture
            {'code': 'CE', 'name': 'Civil Engineering', 'group': GROUPS['CIVIL']},
            {'code': 'AR', 'name': 'Architecture', 'group': GROUPS['CIVIL']},

            # Chemical & Biotechnology
            {'code': 'CH', 'name': 'Chemical Engineering', 'group': GROUPS['CHEM_BIO']},
            {'code': 'BT', 'name': 'Biotechnology', 'group': GROUPS['CHEM_BIO']},

            # Aerospace & Aviation
            {'code': 'AE', 'name': 'Aeronautical Engineering', 'group': GROUPS['AERO']},
            {'code': 'SE', 'name': 'Aerospace Engineering', 'group': GROUPS['AERO']},

            # Robotics & Automation
            {'code': 'RO', 'name': 'Robotics and Automation', 'group': GROUPS['ROBOTICS']},
            {'code': 'RI', 'name': 'Robotics and AI', 'group': GROUPS['ROBOTICS']},

            # Other Programs
            {'code': 'MT', 'name': 'Mechatronics', 'group': GROUPS['OTHERS']},
            {'code': 'NT', 'name': 'Nanotechnology', 'group': GROUPS['OTHERS']}
        ]

        # Add descriptions
        for course in courses:
            course['description'] = course['name']

        return jsonify(courses)
        
    except Exception as e:
        logger.error(f"Error in get_courses route: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
