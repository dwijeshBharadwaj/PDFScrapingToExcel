from django.shortcuts import render, redirect
import os
from PyPDF2 import PdfReader
import concurrent.futures
import logging
import io
from django.shortcuts import render
from .forms import DocumentForm
import pandas as pd
from django.http import FileResponse
from django.http import HttpResponse
import mimetypes
from django.http import HttpResponseServerError
from django.urls import reverse
from django.conf import settings
import zipfile
import re


LOG_FILE_PATH = os.path.join(settings.BASE_DIR, 'logs')
logging.basicConfig(filename=LOG_FILE_PATH, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def extract_text_from_pdf(pdf_file):
    try:
        reader = PdfReader(pdf_file)
        text = []
        for page in reader.pages:
            text.extend(page.extract_text().split("\n"))
        return text
    except Exception as e:
        logging.error(f"Error extracting text from PDF: {e}")
        return []

# Function to process multiple PDFs and store their texts in a dictionary
def extract_texts_from_pdfs(pdf_files):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_idx = {executor.submit(extract_text_from_pdf, pdf_file): idx for idx, pdf_file in enumerate(pdf_files, start=1)}
        for future in concurrent.futures.as_completed(future_to_idx):
            idx = future_to_idx[future]
            yield f"text{idx}", future.result()

# Function to extract column headings from text
def extract_column_headings(text):
    QuestionHeading_Start = [i for i, a in enumerate(text) if a == "1D"][0]
    QuestionHeading_End = [i for i, b in enumerate(text) if b == "Pct"][3]
    QuestionHeading = text[QuestionHeading_Start: QuestionHeading_End + 1]

    # Remove the repeated "Med" string from the "Grp Med" columns
    indexes_to_remove = [i for i, x in enumerate(QuestionHeading) if x == 'Med']
    for index in sorted(indexes_to_remove, reverse=True):
        del QuestionHeading[index]

    # Remove "Dev" from "Std Dev"
    QuestionHeading.remove('Dev')

    # Insert elements at the beginning in reverse order
    
    QuestionHeading.insert(0, "Questions")
    QuestionHeading.insert(0, "Question Number")
    QuestionHeading.insert(0, "responseRate")
    QuestionHeading.insert(0, "Section")
    QuestionHeading.insert(0, "Course")
    QuestionHeading.insert(0, "Name")

    return QuestionHeading

# Mention all the identifiers with the same data span as the label
question_identifiers = ["Q3", "Q5", "Q7", "Q9", "Q11", "Q13", "Q15", "Q17"]
# Put the data span, meaning the number of columns including the identifier
data_span = 21

# Function to extract the identifiers from each text file
def extract_question_data_from_text(text):
    questions_data_dict = {}
    for question in question_identifiers:
        start_indexes = [i for i, x in enumerate(text) if x == question]
        if start_indexes:
            start_index = start_indexes[0]
            end_index = start_index + data_span
            question_data = text[start_index:end_index + 1]
            questions_data_dict[question] = question_data
        else:
            questions_data_dict[question] = []
    return questions_data_dict



def find_elements(list_, keyword):
    found = False
    for element in list_:
        if found:
            if element.strip():  # Check if the line isn't just whitespace
                return element
        if keyword in element:
            found = True
    return None

def extract_percentage(text):
    if text:
        match = re.search(r'(\d+(\.\d+)?%)', text)
        return match.group(0) if match else None
    return None

def extract_name_course_section(text):
    faculty_name = find_elements(text, "Responsible Faculty:")
    course_code_and_section = find_elements(text, "Course:")
    response_rate_line = find_elements(text, "Responses / Expected:")

    if course_code_and_section:
        parts = course_code_and_section.split()
        course_code = parts[0] if len(parts) > 0 else None
        section_number = parts[1] if len(parts) > 1 else None
    else:
        course_code = section_number = None

    # Extracting the percentage from the response rate line
    response_rate = extract_percentage(response_rate_line)

    return [faculty_name, course_code, section_number, response_rate]


# Function to integrate faculty details into the questions data
def integrate_faculty_details_ordered(pdf_questions_data, pdf_name_course_section_data):
    ordered_faculty_details = list(pdf_name_course_section_data.values())
    
    for (pdf_key, questions_data), faculty_details in zip(pdf_questions_data.items(), ordered_faculty_details):
        for question_key in questions_data:
            pdf_questions_data[pdf_key][question_key] = faculty_details + pdf_questions_data[pdf_key][question_key]



def home(request):
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_files = request.FILES.getlist('files')
            texts_dict = dict(extract_texts_from_pdfs(uploaded_files))
            pdf_questions_data = {}

            for key, text in texts_dict.items():
                questions_data = extract_question_data_from_text(text)
                pdf_questions_data[key] = questions_data

            pdf_name_course_section_data = {key: extract_name_course_section(text) for key, text in texts_dict.items()}

            integrate_faculty_details_ordered(pdf_questions_data, pdf_name_course_section_data)  # Integrate faculty details

            # Extract column headings (assuming 'text1' is the key for the first PDF)
            column_headings = extract_column_headings(texts_dict['text1'])

            # Create dataframe for question set 1
            rows = []
            for text_key, questions in pdf_questions_data.items():
                for q_key, q_data in questions.items():
                    row = q_data[:len(column_headings)]
                    rows.append(row)

            df1 = pd.DataFrame(rows, columns=column_headings)

            # Export to Excel
            excel_file = io.BytesIO()
            try:
                with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
                    df1.to_excel(writer, sheet_name='Sheet1')
            except Exception as e:
                logger.error(f"Error exporting to Excel: {e}")
                return HttpResponseServerError("An error occurred while exporting to Excel.")

            excel_file.seek(0)

            # Log the successful completion before reading the log file
            logger.info("Excel file and log file successfully generated and downloaded")
            # Ensure the logger has processed all messages
            for handler in logger.handlers:
                handler.flush()

            # Create a zip file including the latest log content
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                zip_file.writestr('QuestionPair.xlsx', excel_file.getvalue())
                with open(LOG_FILE_PATH, 'r') as log_file:
                    log_content = log_file.read()
                zip_file.writestr('logs.log', log_content)

            zip_buffer.seek(0)

            # Set the response headers for file download
            response = HttpResponse(zip_buffer, content_type='application/zip')
            response['Content-Disposition'] = 'attachment; filename="QuestionPair.zip"'

            return response
    else:
        form = DocumentForm()
    return render(request, 'blog/home.html', {'form': form})



















