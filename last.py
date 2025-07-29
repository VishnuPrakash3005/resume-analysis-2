
import streamlit as st
import google.generativeai as genai
import time
import os
import tempfile
from PyPDF2 import PdfReader
import logging
import json
import re
from datetime import datetime
import base64

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set the specific Gemini API key
GEMINI_API_KEY = "AIzaSyBUIMvCubeDxtKnWWjPlvHA6xGRn5NAPZQ"
genai.configure(api_key=GEMINI_API_KEY)

# Set page styling
def set_page_style():
    st.markdown("""
    <style>
        .main-header {
            font-size: 2.5rem;
            color: #1E88E5;
            margin-bottom: 0.5rem;
        }
        .subheader {
            font-size: 1.5rem;
            color: #424242;
            margin-bottom: 1rem;
        }
        .card {
            padding: 1rem;
            border-radius: 0.5rem;
            background-color: #f8f9fa;
            margin-bottom: 1rem;
            border-left: 4px solid #1E88E5;
        }
        .metric-card {
            text-align: center;
            padding: 1rem;
            background-color: #f1f8fe;
            border-radius: 0.5rem;
            box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        }
        .metric-value {
            font-size: 1.8rem;
            font-weight: bold;
            color: #1E88E5;
        }
        .metric-label {
            font-size: 0.9rem;
            color: #424242;
        }
        .keyword-tag {
            display: inline-block;
            background-color: #e3f2fd;
            color: #1565C0;
            padding: 0.3rem 0.6rem;
            border-radius: 1rem;
            margin: 0.2rem;
            font-size: 0.85rem;
            border: 1px solid #bbdefb;
        }
        .stButton>button {
            background-color: #1E88E5;
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 0.3rem;
        }
        .stButton>button:hover {
            background-color: #1565C0;
        }
        .section-divider {
            margin-top: 2rem;
            margin-bottom: 2rem;
            border-top: 1px solid #e0e0e0;
        }
        .download-button {
            display: inline-block;
            background-color: #1E88E5;
            color: white;
            padding: 0.5rem 1rem;
            border-radius: 0.3rem;
            text-decoration: none;
            margin-top: 1rem;
        }
        .download-button:hover {
            background-color: #1565C0;
            color: white;
        }
    </style>
    """, unsafe_allow_html=True)

class SimpleJobAnalyzer:
    def __init__(self):
        try:
            # Use the gemini-1.5-flash model instead of pro
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            # Test if the model works
            test_response = self.model.generate_content("Test")
            logger.info(f"Initialized model: {self.model._model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize model: {str(e)}")
            raise e
        
    def extract_text_from_pdf(self, uploaded_file):
        """Extract text from PDF using PyPDF2 (simpler than OCR)"""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
                temp_pdf.write(uploaded_file.read())
                temp_pdf_path = temp_pdf.name
                
            text = ""
            with open(temp_pdf_path, 'rb') as file:
                reader = PdfReader(file)
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                
            os.remove(temp_pdf_path)
            return text.strip()
            
        except Exception as e:
            logger.error(f"Error extracting PDF: {str(e)}")
            return f"Error extracting PDF: {str(e)}"
    
    def _call_api_safely(self, prompt):
        """Make API call with improved retry mechanism and better error handling"""
        max_retries = 3  # Increased retries
        backoff_factor = 2  # For exponential backoff
        
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(prompt)
                return response.text
            except Exception as e:
                error_str = str(e)
                wait_time = backoff_factor * (attempt + 1)
                
                # Check for specific error types
                if "429" in error_str:  # Rate limit error
                    if attempt < max_retries - 1:
                        logger.warning(f"Rate limit hit, retry {attempt+1} in {wait_time}s")
                        time.sleep(wait_time)
                        continue
                    return "Sorry, the API is currently experiencing high traffic. Please try again in a few minutes."
                
                logger.error(f"API error: {error_str}")
                return f"Error: Unable to process request. Please try again later."
        
        return "Error: API calls failed after multiple retries. Please try again later."
    
    def quick_resume_analysis(self, resume_text):
        """Simplified resume analysis with fewer details"""
        prompt = f"""
        Analyze this resume briefly:
        
        {resume_text}
        
        Provide a VERY CONCISE analysis (maximum 200 words):
        1. Resume Score (0-100)
        2. Top 5 skills identified
        3. One-line experience summary
        4. Three quick improvement suggestions
        """
        return self._call_api_safely(prompt)
    
    def quick_job_match(self, resume_text, job_description):
        """Simplified job compatibility analysis"""
        # Use a shorter prompt with fewer details requested
        prompt = f"""
        Compare this resume and job description quickly:
        
        RESUME:
        {resume_text}
        
        JOB DESCRIPTION:
        {job_description}
        
        Provide a VERY BRIEF analysis (maximum 250 words):
        1. Match Score (0-100)
        2. Top 3 matching skills
        3. Top 3 missing skills
        4. Three specific improvement tips
        """
        return self._call_api_safely(prompt)
    
    def quick_resume_optimization(self, resume_text, job_description):
        """Generate key bullet points to add to resume"""
        prompt = f"""
        Based on this resume and job description, provide ONLY 5-7 key bullet points
        that should be added to the resume to better match the job.
        
        RESUME:
        {resume_text}
        
        JOB DESCRIPTION:
        {job_description}
        
        Format as bullet points (•).
        """
        return self._call_api_safely(prompt)

    def extract_keywords_from_job(self, job_description):
        """Extract key skills and keywords from job description"""
        prompt = f"""
        Extract the most important skills, technologies, and qualifications from this job description:
        
        {job_description}
        
        Return ONLY a JSON array of strings containing the top 10-15 keywords/phrases.
        Format: ["keyword1", "keyword2", "keyword3", ...]
        """
        try:
            response = self._call_api_safely(prompt)
            # Clean the response to ensure it's valid JSON
            json_str = re.search(r'\[.*\]', response.replace('\n', ' '), re.DOTALL)
            if json_str:
                return json.loads(json_str.group(0))
            else:
                return ["Error: Could not parse keywords"]
        except Exception as e:
            logger.error(f"Error extracting keywords: {str(e)}")
            return ["Error extracting keywords"]

    def create_cover_letter(self, resume_text, job_description, company_name):
        """Generate a customized cover letter based on resume and job"""
        prompt = f"""
        Create a professional cover letter based on this resume and job description:
        
        RESUME:
        {resume_text}
        
        JOB DESCRIPTION:
        {job_description}
        
        COMPANY:
        {company_name}
        
        Write a concise, compelling cover letter that:
        1. Highlights relevant experience from the resume
        2. Shows enthusiasm for the specific company
        3. Addresses key requirements from the job description
        4. Maintains a professional but personable tone
        5. Is properly formatted with today's date and appropriate salutation/closing
        
        Use today's date: {datetime.now().strftime('%B %d, %Y')}
        """
        return self._call_api_safely(prompt)

    def identify_skill_gaps(self, resume_text, job_description):
        """Identify detailed skill gaps and suggest learning resources"""
        prompt = f"""
        Analyze the skill gaps between this resume and job description:
        
        RESUME:
        {resume_text}
        
        JOB DESCRIPTION:
        {job_description}
        
        Provide:
        1. A list of specific skills/qualifications missing from the resume but required in the job
        2. For each missing skill, suggest a specific learning resource (course, certification, or practice project)
        3. Estimate the time investment needed to acquire each skill (in weeks/months)
        
        Format as a clear, structured list with main skills as headings.
        """
        return self._call_api_safely(prompt)
    
    def generate_elevator_pitch(self, resume_text, job_description):
        """Generate a personalized elevator pitch for the application"""
        prompt = f"""
        Create a compelling 30-second elevator pitch based on this resume and job description:
        
        RESUME:
        {resume_text}
        
        JOB DESCRIPTION:
        {job_description}
        
        The elevator pitch should:
        1. Highlight the candidate's most relevant skills and experience
        2. Align with the specific job requirements
        3. Include a unique value proposition
        4. Be conversational and engaging (approximately 100 words)
        5. End with a strong closing statement
        
        Write this in first person as if the candidate is speaking.
        """
        return self._call_api_safely(prompt)
    
    def salary_research(self, job_title, experience_years, location="United States"):
        """Provide salary range information for the job"""
        prompt = f"""
        Provide salary information for:
        
        JOB TITLE: {job_title}
        EXPERIENCE: {experience_years} years
        LOCATION: {location}
        
        Include:
        1. Estimated salary range (low, median, high)
        2. Factors that might affect compensation
        3. Additional benefits commonly offered for this position
        
        Note: This is general information only, based on industry averages.
        """
        return self._call_api_safely(prompt)
    
    def analyze_company_culture(self, company_name, industry=""):
        """Research and provide insights about company culture"""
        prompt = f"""
        Provide a brief analysis of company culture for preparation:
        
        COMPANY: {company_name}
        INDUSTRY: {industry}
        
        Include:
        1. Key values the company likely emphasizes
        2. Work environment characteristics
        3. How to align your application materials with their culture
        
        Note: This is general guidance based on industry trends and publicly available information.
        """
        return self._call_api_safely(prompt)

def create_download_link(content, filename, link_text):
    """Create a download link for text content"""
    b64 = base64.b64encode(content.encode()).decode()
    href = f'<a href="data:file/txt;base64,{b64}" download="{filename}" class="download-button">{link_text}</a>'
    return href

def main():
    st.set_page_config(
        page_title="CareerBoost - Smart Job Application Assistant",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    set_page_style()
    
    # Sidebar with logo and info
    with st.sidebar:
        st.markdown('<div class="main-header">🚀 CareerBoost</div>', unsafe_allow_html=True)
        st.markdown('<div class="subheader">AI-Powered Career Assistant</div>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        st.markdown("### How it works")
        st.info("""
        1. Upload your resume
        2. Add job descriptions
        3. Get AI-powered insights to boost your application
        """)
        
        st.markdown("---")
        
        # Track analytics
        if 'session_data' not in st.session_state:
            st.session_state.session_data = {
                'analyses_run': 0,
                'jobs_matched': 0,
                'improvements_made': 0
            }
        
        # Display metrics
        st.markdown("### Your Stats")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{st.session_state.session_data['analyses_run']}</div>
                <div class="metric-label">Analyses</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{st.session_state.session_data['jobs_matched']}</div>
                <div class="metric-label">Jobs Matched</div>
            </div>
            """, unsafe_allow_html=True)
    
    # Initialize the analyzer
    if 'analyzer' not in st.session_state:
        try:
            with st.spinner("Initializing AI models..."):
                st.session_state.analyzer = SimpleJobAnalyzer()
                st.session_state.api_connected = True
        except Exception as e:
            st.error(f"❌ Error initializing the AI model: {str(e)}")
            st.session_state.api_connected = False
            st.stop()
    
    # If API is not connected, display error and stop
    if not st.session_state.get('api_connected', False):
        st.error("❌ Unable to connect to the Gemini API. Please check your internet connection or try again later.")
        st.stop()
    
    # Initialize session state variables
    if 'resume_text' not in st.session_state:
        st.session_state.resume_text = None
    if 'last_job_description' not in st.session_state:
        st.session_state.last_job_description = ""
    
    # Main header
    st.markdown('<div class="main-header">Smart Job Application Assistant</div>', unsafe_allow_html=True)
    st.markdown("Get AI-powered insights to match and optimize your job applications")
    
    # Navigation tabs - more professional names
    tab1, tab2, tab3 = st.tabs(["📄 Resume Analysis", "🎯 Job Matching", "🛠️ Application Tools"])
    
    # Resume Analysis tab
    with tab1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="subheader">Upload Your Resume</div>', unsafe_allow_html=True)
        
        # Two columns for upload methods
        col1, col2 = st.columns([1, 1])
        
        with col1:
            uploaded_file = st.file_uploader("Upload resume (PDF format)", type="pdf")
            if uploaded_file:
                extract_button = st.button("📥 Extract Resume Content", use_container_width=True)
                if extract_button:
                    with st.spinner("Reading and processing your resume..."):
                        st.session_state.resume_text = st.session_state.analyzer.extract_text_from_pdf(uploaded_file)
                        if st.session_state.resume_text and not st.session_state.resume_text.startswith("Error"):
                            st.success("✅ Resume successfully extracted!")
                            st.session_state.session_data['analyses_run'] += 1
                        else:
                            st.error(st.session_state.resume_text or "Failed to extract text from PDF")
        
        with col2:
            st.markdown("### Or enter text manually")
            manual_resume = st.text_area("Paste your resume text:", height=150)
            if manual_resume and st.button("Use This Text", use_container_width=True):
                st.session_state.resume_text = manual_resume
                st.success("✅ Resume text saved!")
                st.session_state.session_data['analyses_run'] += 1
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Only show next sections if resume is loaded
        if st.session_state.resume_text and not st.session_state.resume_text.startswith("Error"):
            # Resume verification and editing
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="subheader">Review & Edit Resume</div>', unsafe_allow_html=True)
            
            resume_text_area = st.text_area(
                "Edit your resume text if needed:", 
                st.session_state.resume_text, 
                height=200
            )
            st.session_state.resume_text = resume_text_area

            analyze_button = st.button("🔍 Analyze Resume", use_container_width=True)
            
            if analyze_button:
                with st.spinner("Analyzing your resume..."):
                    analysis = st.session_state.analyzer.quick_resume_analysis(st.session_state.resume_text)
                    if not analysis.startswith("Error"):
                        st.success("✅ Analysis complete!")
                        st.markdown('<div class="subheader">Resume Analysis Results</div>', unsafe_allow_html=True)
                        st.markdown(analysis)
                        st.session_state.session_data['analyses_run'] += 1
                    else:
                        st.error(analysis)
            
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("👆 Please upload or enter your resume above to continue")
    
    # Job matching tab with improved design
    with tab2:
        if st.session_state.resume_text and not st.session_state.resume_text.startswith("Error"):
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="subheader">Job Position Analysis</div>', unsafe_allow_html=True)
            
            job_description = st.text_area(
                "Paste the job description here:", 
                value=st.session_state.last_job_description,
                height=200
            )
            st.session_state.last_job_description = job_description
            
            # Improved layout with two columns
            if job_description:
                col1, col2 = st.columns(2)
                
                with col1:
                    match_button = st.button("🔄 Calculate Match Score", use_container_width=True)
                    if match_button:
                        with st.spinner("Analyzing compatibility with job..."):
                            match_analysis = st.session_state.analyzer.quick_job_match(
                                st.session_state.resume_text, 
                                job_description
                            )
                            if not match_analysis.startswith("Error"):
                                st.success("✅ Match analysis complete!")
                                st.markdown('<div class="subheader">Job Match Results</div>', unsafe_allow_html=True)
                                st.markdown(match_analysis)
                                st.session_state.session_data['jobs_matched'] += 1
                            else:
                                st.error(match_analysis)
                
                with col2:
                    tips_button = st.button("💡 Get Improvement Tips", use_container_width=True)
                    if tips_button:
                        with st.spinner("Generating resume optimization tips..."):
                            optimization_tips = st.session_state.analyzer.quick_resume_optimization(
                                st.session_state.resume_text, 
                                job_description
                            )
                            if not optimization_tips.startswith("Error"):
                                st.success("✅ Tips generated!")
                                st.markdown('<div class="subheader">Resume Improvement Tips</div>', unsafe_allow_html=True)
                                st.markdown(optimization_tips)
                                st.session_state.session_data['improvements_made'] += 1
                            else:
                                st.error(optimization_tips)
            
                # Add keyword extraction with better styling
                keywords_button = st.button("🔑 Extract Key Skills", use_container_width=True)
                if keywords_button:
                    with st.spinner("Identifying key skills from job posting..."):
                        keywords = st.session_state.analyzer.extract_keywords_from_job(job_description)
                        if isinstance(keywords, list) and not keywords[0].startswith("Error"):
                            st.success("✅ Keywords extracted!")
                            st.markdown('<div class="subheader">Key Skills & Requirements</div>', unsafe_allow_html=True)
                            
                            # Better keyword display with custom styling
                            keyword_html = '<div style="display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px;">'
                            for keyword in keywords:
                                keyword_html += f'<div class="keyword-tag">{keyword}</div>'
                            keyword_html += '</div>'
                            st.markdown(keyword_html, unsafe_allow_html=True)
                        else:
                            st.error("Error extracting keywords")
            
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("📝 Please upload or enter your resume in the Resume Analysis tab first")
    
    # Application Tools tab - redesigned without interview prep
    with tab3:
        if st.session_state.resume_text and not st.session_state.resume_text.startswith("Error"):
            # Cover Letter Generator - improved layout
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="subheader">Cover Letter Generator</div>', unsafe_allow_html=True)
            st.markdown("Create a customized cover letter for your job application")
            
            col1, col2 = st.columns([3, 1])
            with col1:
                job_description_cl = st.text_area(
                    "Job description:", 
                    value=st.session_state.last_job_description, 
                    height=120, 
                    key="jd_cl"
                )
            with col2:
                company_name = st.text_input("Company name:")
            
            cover_letter_button = st.button("✉️ Generate Cover Letter", use_container_width=True)
            
            if cover_letter_button and job_description_cl and company_name:
                with st.spinner("Creating your personalized cover letter..."):
                    cover_letter = st.session_state.analyzer.create_cover_letter(
                        st.session_state.resume_text,
                        job_description_cl,
                        company_name
                    )
                    if not cover_letter.startswith("Error"):
                        st.success("✅ Cover letter created!")
                        
                        # Show cover letter with option to download
                        with st.expander("Preview Your Cover Letter", expanded=True):
                            st.markdown(cover_letter)
                            st.markdown(
                                create_download_link(
                                    cover_letter, 
                                    f"Cover_Letter_{company_name}.txt", 
                                    "📥 Download Cover Letter"
                                ), 
                                unsafe_allow_html=True
                            )
                    else:
                        st.error(cover_letter)
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Skill Gap Analysis - improved layout
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="subheader">Skill Gap Analysis</div>', unsafe_allow_html=True)
            st.markdown("Identify missing skills and how to acquire them")
            
            job_description_sg = st.text_area(
                "Job description:", 
                value=st.session_state.last_job_description, 
                height=120, 
                key="jd_sg"
            )
            
            skill_gaps_button = st.button("🧩 Analyze Skill Gaps", use_container_width=True)
            
            if skill_gaps_button and job_description_sg:
                with st.spinner("Analyzing skill gaps and creating learning plan..."):
                    skill_gaps = st.session_state.analyzer.identify_skill_gaps(
                        st.session_state.resume_text,
                        job_description_sg
                    )
                    if not skill_gaps.startswith("Error"):
                        st.success("✅ Skill gap analysis complete!")
                        
                        with st.expander("View Skill Gap Analysis", expanded=True):
                            st.markdown('<div class="subheader">Skills Gap Analysis & Learning Plan</div>', unsafe_allow_html=True)
                            st.markdown(skill_gaps)
                    else:
                        st.error(skill_gaps)
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Elevator Pitch Generator - new feature replacing interview prep
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="subheader">Elevator Pitch Generator</div>', unsafe_allow_html=True)
            st.markdown("Create a compelling 30-second pitch highlighting your value")
            
            job_description_ep = st.text_area(
                "Job description:", 
                value=st.session_state.last_job_description, 
                height=120, 
                key="jd_ep"
            )
            
            pitch_button = st.button("🎤 Generate Elevator Pitch", use_container_width=True)
            
            if pitch_button and job_description_ep:
                with st.spinner("Crafting your personalized elevator pitch..."):
                    elevator_pitch = st.session_state.analyzer.generate_elevator_pitch(
                        st.session_state.resume_text,
                        job_description_ep
                    )
                    if not elevator_pitch.startswith("Error"):
                        st.success("✅ Elevator pitch created!")
                        
                        with st.expander("View Your Elevator Pitch", expanded=True):
                            st.markdown('<div class="subheader">Your 30-Second Elevator Pitch</div>', unsafe_allow_html=True)
                            st.markdown(f'<div style="background-color: #e3f2fd; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #1565C0;">{elevator_pitch}</div>', unsafe_allow_html=True)
                            st.markdown(
                                create_download_link(
                                    elevator_pitch, 
                                    "Elevator_Pitch.txt", 
                                    "📥 Download Elevator Pitch"
                                ), 
                                unsafe_allow_html=True
                            )
                    else:
                        st.error(elevator_pitch)
            
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("📝 Please upload or enter your resume in the Resume Analysis tab first")

if __name__ == "__main__":
    main()
