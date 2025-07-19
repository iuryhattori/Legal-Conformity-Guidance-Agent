from crewai import Agent, Crew, Task, Process
from crewai.project import CrewBase, agent, task, crew
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.tools import BaseTool, tool
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Type
from langchain_openai import ChatOpenAI
from enum import Enum
import yaml
import pdfplumber
from datetime import datetime
import markdown
import pdfkit
import re
import subprocess
import tempfile
import os
import warnings
warnings.filterwarnings('ignore')

os.environ["OPENAI_API_KEY"] = ""  
llm = ChatOpenAI(model="gpt-4o-mini")

@tool("Line Break Adjustment")
def adjust_line_breaks_for_pdf(markdown_content: str, page_break_tag: str = '<div class="page-break"></div>') -> str:
    """
    Adjusts line breaks and inserts page break tags in Markdown to optimize PDF output.

    Args:
        markdown_content (str): The original Markdown report.
        page_break_tag (str, optional): The tag used for page breaks. Default is <div class="page-break"></div>.

    Returns:
        str: The adjusted Markdown content with strategic page breaks.
    """
    # List of patterns to identify the main titles/sections of the report
    sections = [ 
        r'^##\s*📌 Mandatory Procedural Acts',
        r'^##\s*⚠️ Points of Attention',
        r'^##\s*🛠️ Practical Roadmap for Regularization',
        r'^##\s*ℹ️ Doubts or Actions',
        r'^##\s*📝 Final Summary',
        r'^##\s*🤝 Contact Us'
    ]
    # Inserts page break before each new section (except the first)
    # ensures no unnecessary consecutive breaks
    content_lines = markdown_content.splitlines()
    output_lines = []
    last_was_break = False

    for i, line in enumerate(content_lines):
        found_section = any(re.match(sec, line) for sec in sections)
        if found_section and i != 0 and not last_was_break:
            output_lines.append(page_break_tag)
            last_was_break = True
        else:
            last_was_break = False
        output_lines.append(line)

    final_lines = []
    i = 0
    while i < len(output_lines):
        line = output_lines[i]
        if re.match(r'^\|', line):
            prev_line = output_lines[i-1] if i > 0 else ""   # Only insert break if not break/title before
            if not (prev_line.strip() == page_break_tag or prev_line.strip() == "" or prev_line.startswith("##")):
                final_lines.append(page_break_tag)
        final_lines.append(line)
        i += 1

    return '\n'.join(final_lines)

@tool("PDF Generator")
def pdf_generator_tool(markdown_text: str, output_path: Optional[str] = None) -> str:
    """
    Converts Markdown text to a PDF file with improved formatting.

    Args:
        markdown_text: The Markdown text to convert
        output_path: Optional path to save the PDF

    Returns:
        The path to the generated PDF file or an error message
    """
    try:
        import subprocess
        import datetime
        import tempfile
        import os
        import markdown
        import pdfkit

        try:
            subprocess.run(['wkhtmltopdf', '--version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            return ("Error: wkhtmltopdf is not installed. "
                    "Install with: apt-get install wkhtmltopdf (Ubuntu) or brew install wkhtmltopdf (Mac)")
        # Custom CSS for better client PDF appearance
        css_styles = """
        <style>
            body {
                font-family: 'Arial', 'Helvetica', sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
            }
            h1, h2, h3, h4, h5, h6 {
                color: #2c3e50;
                margin-top: 30px;
                margin-bottom: 10px;
                page-break-after: avoid !important;
                break-after: avoid;
            }
            h1 { font-size: 2.5em; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
            h2 { font-size: 2em; border-bottom: 2px solid #3498db; padding-bottom: 8px; margin-bottom: 0px; }
            h3 { font-size: 1.5em; color: #34495e; }
            p { margin-bottom: 15px; text-align: justify; }
            code {
                background-color: #f8f9fa;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: 'Courier New', monospace;
                color: #e74c3c;
            }
            pre {
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 5px;
                padding: 15px;
                overflow-x: auto;
                margin: 20px 0;
            }
            blockquote {
                border-left: 4px solid #3498db;
                margin: 20px 0;
                padding-left: 20px;
                font-style: italic;
                color: #555;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin: 0;
                table-layout: auto;
                page-break-inside: avoid !important;
            }
            thead, tr, th, td {
                page-break-inside: avoid !important;
                background: #fff;
            }
            th, td {
                border: 1px solid #ddd;
                padding: 12px;
                text-align: left;
                vertical-align: top;
                white-space: normal !important;
                overflow-wrap: anywhere !important;
                font-size: 13px;
            }
            th {
                background-color: #3498db;
                color: white;
                font-weight: bold;
            }
            tr:nth-child(even) {
                background-color: #f2f2f2;
            }
            td:last-child, th:last-child {
                min-width: 160px;
            }
            ul, ol {
                margin: 15px 0;
                padding-left: 30px;
                page-break-inside: avoid !important;
                break-inside: avoid;
            }
            li {
                margin-bottom: 8px;
                page-break-inside: avoid !important;
            }
            .keep-together {
                page-break-inside: avoid !important;
                break-inside: avoid;
            }
            a {
                color: #3498db;
                text-decoration: none;
            }
            a:hover {
                text-decoration: underline;
            }
            .page-break {
                page-break-before: always;
            }
        </style>
        """

        try:
            html = markdown.markdown(
                markdown_text,
                extensions=[
                    'tables',
                    'fenced_code',
                    'nl2br',
                    'codehilite',
                    'toc',
                    'attr_list'
                ]
            )
        except Exception as e:
            return f"Error converting Markdown to HTML: {str(e)}"

        html = re.sub(r'(</h2>|</h3>)\s*<table', r'\1<table', html)

        def keep_together_blocks(html):
            html = re.sub(
                r'(<h2[^>]*>.*?</h2>\s*)(<ul>.*?</ul>)',
                r'<div class="keep-together">\1\2</div>',
                html,
                flags=re.DOTALL
            )
            html = re.sub(
                r'(<h2[^>]*>.*?</h2>\s*)(<ol>.*?</ol>)',
                r'<div class="keep-together">\1\2</div>',
                html,
                flags=re.DOTALL
            )
            html = re.sub(
                r'(<h2[^>]*>.*?</h2>\s*)(<table.*?>.*?</table>)',
                r'<div class="keep-together">\1\2</div>',
                html,
                flags=re.DOTALL
            )
            return html

        html = keep_together_blocks(html)

        full_html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>PDF Document</title>
            {css_styles}
        </head>
        <body>
            {html}
        </body>
        </html>
        """

        if not output_path:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            fd, output_path = tempfile.mkstemp(suffix=f"_document_{timestamp}.pdf")
            os.close(fd)  
        options = {
            'encoding': 'UTF-8',
            'enable-local-file-access': None,
            'page-size': 'A4',
            'margin-top': '20mm',
            'margin-bottom': '20mm',
            'margin-left': '15mm',
            'margin-right': '15mm',
            'orientation': 'Portrait',
            'no-outline': None,
            'enable-smart-shrinking': None,
            'print-media-type': None,
            'disable-smart-shrinking': None,
            'zoom': 1.0,
            'dpi': 300,
            'image-quality': 100,
            'javascript-delay': 1000,
            'no-stop-slow-scripts': None,
        }
        try:
            pdfkit.from_string(full_html, output_path, options=options)
            return f"PDF successfully generated at: {output_path}"
        except Exception as e:
            return f"Error generating PDF: {str(e)}"

    except ImportError as e:
        return f"Error: Dependency not found - {str(e)}. Install with: pip install markdown pdfkit"
    except Exception as e:
        return f"Error generating PDF: {str(e)}"

@tool("PDF Reader")
def pdf_reader_tool(file_path: str) -> str:
    """Reads a PDF file and returns all extracted text."""
    try:
        with pdfplumber.open(file_path) as pdf:
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text
    except Exception as e:
        return f"Error reading PDF: {str(e)}"

@CrewBase
class Juriscrew():
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o-mini")
    """
======================================================================================================================
    NOTE: - Max_iter and max_retry_limit received higher values in agents executing tasks
                where omission may strongly harm the reliability of the final result

                - Respect_context_window was used to automate very robust tasks, or those with
                a very long input
======================================================================================================================
"""
                    
    @agent # Extracts general process information, including parties, claims, decisions, dates, attachments, and doubts.
    def generalExtractor(self)->Agent:
        return Agent(
            config=self.agents_config['generalExtractor'],
            verbose=False,
            max_iter=30, 
            max_retry_limit=3, 
            respect_context_window=True,
            tools =[pdf_reader_tool],
            llm=self.llm
        )
    @agent  # Extracts deadlines, procedural dates, and risks of non-compliance.
    def deadlineSpecialist(self)->Agent:
        return Agent(
            config=self.agents_config['deadlineSpecialist'],
            max_iter= 15,
            max_retry_limit= 2,
            verbose=False,
            llm=self.llm
        )
    @agent # Maps possible procedural nullities.
    def nullitySpecialist(self)->Agent:
        return Agent(
            config=self.agents_config['nullitySpecialist'],
            verbose=False,
            max_iter= 15,
            max_retry_limit= 2,
            llm=self.llm
        )
    @agent # Detects formal and territorial jurisdiction irregularities.
    def irregularitySpecialist(self)->Agent:
        return Agent(
            config=self.agents_config['irregularitySpecialist'],
            verbose=False,
            max_iter= 15,
            max_retry_limit= 2,
            llm=self.llm
        )
    @agent # Identifies textual ambiguities, interpretation doubts, and suggests improvements.
    def ambiguitySpecialist(self)->Agent:
        return Agent(
            config=self.agents_config['ambiguitySpecialist'],
            verbose=False,
            max_iter= 15,
            max_retry_limit= 2,
            llm=self.llm
        )
    @agent  # Explains the process context
    def contextExplainer(self)->Agent:
        return Agent(
            config=self.agents_config['contextExplainer'],
            verbose=False,
            max_iter= 25,
            max_retry_limit= 2,
            respect_context_window=True,
            llm=self.llm
        )
    @agent # Attests procedural regularity for each category (deadlines, nullities, etc).
    def processRegularityAttestor(self)->Agent:
        return Agent(
            config=self.agents_config['processRegularityAttestor'],
            verbose=False,
            max_iter= 25,
            max_retry_limit= 2,
            respect_context_window=True,
            llm=self.llm
        )
    @agent # Consolidates and organizes technical findings into a unique, traceable report.
    def synthesisSpecialist(self)->Agent:
        return Agent(
            config=self.agents_config['synthesisSpecialist'],
            verbose=False,
            max_iter= 30,
            max_retry_limit= 3,
            respect_context_window=True,
            llm=self.llm
        )
    @agent # Provides detailed legal reasoning for each procedural category.
    def legalGroundsSpecialist(self)->Agent:
        return Agent(
            config=self.agents_config['legalGroundsSpecialist'],
            max_iter=30,
            max_retry_limit= 3,
            respect_context_window=True,
            verbose=False,
            llm=self.llm
        )
    @agent # Lists all mandatory formal acts for process regularization.
    def formalActsSpecialist(self)->Agent:
        return Agent(
            config=self.agents_config['formalActsSpecialist'],
            verbose=False,
            max_iter= 30,
            max_retry_limit= 3,
            respect_context_window=False,
            llm=self.llm
        )
    @agent # Assigns the main responsible to each detected formal act.
    def formalActsResponsiblesSpecialist(self)->Agent:
        return Agent(
            config=self.agents_config['formalActsResponsiblesSpecialist'],
            verbose=False,
            max_iter= 30,
            max_retry_limit= 3,
            respect_context_window=False,
            llm=self.llm
        )
    @agent # Associates individual legal basis to each mandatory formal act.
    def legalBasisForActsSpecialist(self)->Agent:
        return Agent(
            config=self.agents_config['legalBasisForActsSpecialist'],
            verbose=False,
            max_iter= 30,
            max_retry_limit=3,
            respect_context_window=False,
            llm=self.llm
        )
    @agent  # Prioritizes acts, indicating deadline and technical justification for each.
    def actsPrioritizationAndDeadlinesSpecialist(self)->Agent:
        return Agent(
            config=self.agents_config['actsPrioritizationAndDeadlinesSpecialist'],
            verbose=False,
            max_iter= 30,
            max_retry_limit= 3,
            respect_context_window=False,
            llm=self.llm
        )
    @agent  # Records doubts, gaps, and actions for each act.
    def actsDoubtsAndGapsSpecialist(self)->Agent:
        return Agent(
            config=self.agents_config['actsDoubtsAndGapsSpecialist'],
            verbose=False,
            max_iter= 30,
            max_retry_limit= 3,
            respect_context_window=False,
            llm=self.llm
        )

    @agent # Consolidates all acts and pending information for the final report.
    def formalActsClientReportBuilderSpecialist(self)->Agent:
        return Agent(
            config=self.agents_config['formalActsClientReportBuilderSpecialist'],
            verbose=False,
            max_iter=30,
            max_retry_limit= 3,
            respect_context_window=True,
            llm=self.llm
        )
    @agent # Formats the consolidated report in professional markdown for the client.
    def formalActsClientReportFormatterSpecialist(self)->Agent:
        return Agent(
            config=self.agents_config['formalActsClientReportFormatterSpecialist'],
            verbose=False,
            max_iter=8,
            max_retry_limit= 3,
            respect_context_window=False,
            llm=self.llm
        )
    @agent # Optimizes line/page breaks in markdown for PDF readability.
    def lineBreakAdjustmentSpecialist(self)->Agent:
        return Agent(
            config=self.agents_config['lineBreakAdjustmentSpecialist'],
            verbose=False,
            max_iter=10,
            max_retry_limit=2,
            respect_context_window=False,
            llm=self.llm
        )
    @agent # Generates the final PDF report with all formatting preserved.
    def formalActsClientReportPDFGeneratorSpecialist(self)->Agent:
        return Agent(
            config=self.agents_config['formalActsClientReportPDFGeneratorSpecialist'],
            verbose=False,
            max_iter=8,
            max_retry_limit= 3,
            respect_context_window=False,
            tools=[pdf_generator_tool],
            llm=self.llm
        )
    @task # Executes general extraction from the legal document.
    def generalExtraction(self)->Task:
        return Task(
            config=self.tasks_config['generalExtraction'],
            agent=self.generalExtractor(),
        )
    @task # Analyzes and explains the legal context of extracted data.
    def contextExplainerTask(self)->Task:
        return Task(
            config=self.tasks_config['contextExplainerTask'],
            agent=self.contextExplainer(),
            async_execution=True
        )
    @task # Performs thorough analysis of procedural deadlines.
    def deadlineAnalysis(self)->Task:
        return Task(
            config=self.tasks_config['deadlineAnalysis'],
            agent=self.deadlineSpecialist(),
            async_execution=True
        )
    @task # Detects procedural nullities from extracted data.
    def nullityAnalysis(self)->Task:
        return Task(
            config=self.tasks_config['nullityAnalysis'],
            agent=self.nullitySpecialist(),
            async_execution=True
        )
    @task  # Identifies formal and territorial irregularities.
    def analyzeIrregularities(self)->Task:
        return Task(
            config=self.tasks_config['analyzeIrregularities'],
            agent=self.irregularitySpecialist(),
            async_execution=True
        )
    
    @task  # Maps textual ambiguities and 
    def ambiguityAnalysis(self)->Task:
        return Task(
            config=self.tasks_config['ambiguityAnalysis'],
            agent=self.ambiguitySpecialist(),
            async_execution=True
        )
    @task # Consolidates procedural findings for technical consultation and automation.
    def synthesizeProcessualInformation(self)->Task:
        return Task(
            config = self.tasks_config['synthesizeProcessualInformation'],
            agent=self.synthesisSpecialist(),
        )
    @task # Identifies applicable legal grounds.
    def legalGroundsAnalysisTask(self)->Task:
        return Task(
            config=self.tasks_config['legalGroundsAnalysisTask'],
            agent=self.legalGroundsSpecialist()
        )
    @task
    def attestProcessualRegularity(self)->Task:
        return Task(
            config=self.tasks_config['attestProcessualRegularity'],
            agent=self.processRegularityAttestor()
        )
    @task # Detects all mandatory formal acts.
    def detectFormalActsTask(self)->Task:
        return Task(
            config=self.tasks_config['detectFormalActsTask'],
            agent=self.formalActsSpecialist()
        )
    @task # Assigns responsibles to each identified formal act.
    def assignFormalActResponsiblesTask(self)->Task:
        return Task(
            config=self.tasks_config['assignFormalActResponsiblesTask'],
            agent=self.formalActsResponsiblesSpecialist()
        )
    @task # Associates individual legal basis to mandatory acts.
    def legalBasisForActsTask(self)->Task:
        return Task(
            config=self.tasks_config['legalBasisForActsTask'],
            agent=self.legalBasisForActsSpecialist()
        )
    @task # Prioritizes acts and defines deadlines/technical justification.
    def actsPrioritizationAndDeadlinesTask(self)->Task:
        return Task(
            config=self.tasks_config['actsPrioritizationAndDeadlinesTask'],
            agent=self.actsPrioritizationAndDeadlinesSpecialist()
        )
    @task # Lists doubts, gaps, and actions for each act.
    def actsDoubtsAndGapsTask(self)->Task:
        return Task(
            config=self.tasks_config['actsDoubtsAndGapsTask'],
            agent=self.actsDoubtsAndGapsSpecialist()
        )

    @task # Builds the final consolidated report of procedural acts.
    def formalActsClientReportBuilder(self)->Task:
        return Task(
            config=self.tasks_config['formalActsClientReportBuilder'],
            agent=self.formalActsClientReportBuilderSpecialist()
        )
    @task # Formats report for the client in visually pleasant markdown.
    def formalActsClientReportFormatter(self)->Task:
        return Task(
            config=self.tasks_config['formalActsClientReportFormatter'],
            agent=self.formalActsClientReportFormatterSpecialist(),
            markdown=True
        )
    @task # Optimizes line/page breaks for ideal PDF visualization.
    def lineBreakAdjustmentTask(self)->Task:
        return Task(
        config=self.tasks_config['lineBreakAdjustmentTask'],
        agent=self.lineBreakAdjustmentSpecialist(),
        tools=[adjust_line_breaks_for_pdf])
    @task # Generates the final procedural PDF report.
    def formalActsClientReportPDFGenerationTask(self)->Task:
        return Task(
            config=self.tasks_config['formalActsClientReportPDFGenerationTask'],
            agent=self.formalActsClientReportPDFGeneratorSpecialist(),
        )

    @crew # Orchestrates all agents and tasks in sequential workflow
    def crew(self)->Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
        )