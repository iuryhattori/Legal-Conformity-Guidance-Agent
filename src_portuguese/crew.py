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



@tool("Ajuste de quebra de linhas") 
def adjust_line_breaks_for_pdf(conteudo_markdown: str, tag_quebra_pagina: str = '<div class="page-break"></div>') -> str:
    """
    Ajusta quebras de linha e insere tags de quebra de página no Markdown para otimizar a saída em PDF.

    Args:
        conteudo_markdown (str): O relatório Markdown original.
        tag_quebra_pagina (str, opcional): A tag usada para quebras de página. Padrão é <div class="page-break"></div>.

    Retorna:
        str: O conteúdo Markdown ajustado com quebras de página estratégicas.
    """
    #Lista de padrões para identificar os principais titulos/seções do relatório
    secoes = [ 
        r'^##\s*📌 Atos Obrigatórios do Processo',
        r'^##\s*⚠️ Pontos de Atenção',
        r'^##\s*🛠️ Roteiro Prático para Regularização',
        r'^##\s*ℹ️ Dúvidas ou Ações',
        r'^##\s*📝 Resumo Final',
        r'^##\s*🤝 Fale Conosco'
    ]
    #Insere quebra de página antes de cada nova seção (exceto a primeira)
    #garante que não haja quebras consecutivas desnecessárias
    linhas_conteudo = conteudo_markdown.splitlines()
    linhas_saida = []
    ultima_foi_quebra = False

    for i, linha in enumerate(linhas_conteudo):
        encontrou_secao = any(re.match(sec, linha) for sec in secoes) # Insere quebra de página antes de uma nova seção, exceto na primeira linha/seção
        if encontrou_secao and i != 0 and not ultima_foi_quebra:
            linhas_saida.append(tag_quebra_pagina)
            ultima_foi_quebra = True
        else:
            ultima_foi_quebra = False
        linhas_saida.append(linha)

    linhas_finais = []
    i = 0
    while i < len(linhas_saida):
        linha = linhas_saida[i]
        if re.match(r'^\|', linha):
            linha_anterior = linhas_saida[i-1] if i > 0 else ""   # Só insere quebra se não houver quebra/título antes
            if not (linha_anterior.strip() == tag_quebra_pagina or linha_anterior.strip() == "" or linha_anterior.startswith("##")):
                linhas_finais.append(tag_quebra_pagina)
        linhas_finais.append(linha)
        i += 1

    return '\n'.join(linhas_finais)

@tool("Gerador de PDF")
def pdf_generator_tool(markdown_text: str, output_path: Optional[str] = None) -> str:
    """
    Converte um texto em Markdown para um arquivo PDF com formatação aprimorada.

    Args:
        markdown_text: O texto em formato Markdown a ser convertido
        output_path: Caminho opcional onde salvar o PDF

    Retorna:
        O caminho do arquivo PDF gerado ou uma mensagem de erro
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
            return ("Erro: wkhtmltopdf não está instalado. "
                    "Instale com: apt-get install wkhtmltopdf (Ubuntu) ou brew install wkhtmltopdf (Mac)")
        #CSS customizado para deixar o pdf mais agradável ao cliente
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
                margin: 0; /* Remover espaçamento extra acima da tabela */
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

        try: #conversão do markdown para HTML, utiliza extensões para suportar tabelas, listas, codigos, TOC e atributos
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
            return f"Erro ao converter Markdown para HTML: {str(e)}"

        #ajuste para evitar quebra indesejada entre o titulo e a tabela

        html = re.sub(r'(</h2>|</h3>)\s*<table', r'\1<table', html)

        def keep_together_blocks(html):
            # Tem como função evitar quebra de linhas.
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

        #Montagem do HTML final para PDF
        full_html = f"""
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Documento PDF</title>
            {css_styles}
        </head>
        <body>
            {html}
        </body>
        </html>
        """

        #Define o caminho de saída do pdf
        if not output_path:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            fd, output_path = tempfile.mkstemp(suffix=f"_document_{timestamp}.pdf")
            os.close(fd)  
        #Controla como o pdf será gerado, garantindo um visual mais agradável
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
        #Geração do PDF
        try:
            pdfkit.from_string(full_html, output_path, options=options)
            return f"PDF gerado com sucesso em: {output_path}"
        except Exception as e:
            return f"Erro ao gerar o PDF: {str(e)}"

    except ImportError as e:
        return f"Erro: Dependência não encontrada - {str(e)}. Instale com: pip install markdown pdfkit"
    except Exception as e:
        return f"Erro ao gerar o PDF: {str(e)}"

@tool("Leitor de PDF")
def pdf_reader_tool(file_path: str) -> str:
    """Lê um arquivo PDF e retorna todo o texto extraído."""
    try:
        with pdfplumber.open(file_path) as pdf:
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text
    except Exception as e:
        return f"Erro ao ler o PDF: {str(e)}"

@CrewBase
class Juriscrew():
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o-mini")
    """
======================================================================================================================
    OBSERVAÇÃO: - Max_iter e max_retry_limit Receberam valores maiores em agentes que executam tasks
                nas quais a omissão pode prejudicar fortemente a confiabilidade do resultado final

                - Respect_context_window foi usado para automatizar tasks muito robustas, ou que possuem
                um input muito longo
======================================================================================================================
"""
                    
    @agent #Extrai informações gerais do processo, inclusive partes, pedidos, decisões, datas, anexos e dúvidas.
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
    @agent  # Extrai prazos processuais, datas de atos e riscos de descumprimento.
    def deadlineSpecialist(self)->Agent:
        return Agent(
            config=self.agents_config['deadlineSpecialist'],
            max_iter= 15,
            max_retry_limit= 2,
            verbose=False,
            llm=self.llm
        )
    @agent # Mapeia possíveis nulidades processuais.
    def nullitySpecialist(self)->Agent:
        return Agent(
            config=self.agents_config['nullitySpecialist'],
            verbose=False,
            max_iter= 15,
            max_retry_limit= 2,
            llm=self.llm
        )
    @agent # Detecta irregularidades formais e de competência territorial.
    def irregularitySpecialist(self)->Agent:
        return Agent(
            config=self.agents_config['irregularitySpecialist'],
            verbose=False,
            max_iter= 15,
            max_retry_limit= 2,
            llm=self.llm
        )
    @agent # Identifica ambiguidades textuais, dúvidas de interpretação e sugere melhorias.
    def ambiguitySpecialist(self)->Agent:
        return Agent(
            config=self.agents_config['ambiguitySpecialist'],
            verbose=False,
            max_iter= 15,
            max_retry_limit= 2,
            llm=self.llm
        )
    @agent  # Explica o contexto do processo
    def contextExplainer(self)->Agent:
        return Agent(
            config=self.agents_config['contextExplainer'],
            verbose=False,
            max_iter= 25,
            max_retry_limit= 2,
            respect_context_window=True,
            llm=self.llm
        )
    @agent # Faz o atestado de regularidade processual para cada categoria (prazos, nulidades etc).
    def processRegularityAttestor(self)->Agent:
        return Agent(
            config=self.agents_config['processRegularityAttestor'],
            verbose=False,
            max_iter= 25,
            max_retry_limit= 2,
            respect_context_window=True,
            llm=self.llm
        )
    @agent # Consolida e organiza achados técnicos em relatório único e rastreável.
    def synthesisSpecialist(self)->Agent:
        return Agent(
            config=self.agents_config['synthesisSpecialist'],
            verbose=False,
            max_iter= 30,
            max_retry_limit= 3,
            respect_context_window=True,
            llm=self.llm
        )
    @agent # Realiza fundamentação jurídica detalhada para cada categoria processual.
    def legalGroundsSpecialist(self)->Agent:
        return Agent(
            config=self.agents_config['legalGroundsSpecialist'],
            max_iter=30,
            max_retry_limit= 3,
            respect_context_window=True,
            verbose=False,
            llm=self.llm
        )
    @agent # Lista todos os atos formais obrigatórios para regularização do processo.
    def formalActsSpecialist(self)->Agent:
        return Agent(
            config=self.agents_config['formalActsSpecialist'],
            verbose=False,
            max_iter= 30,
            max_retry_limit= 3,
            respect_context_window=False,
            llm=self.llm
        )
    @agent # Atribui o responsável principal a cada ato formal detectado.
    def formalActsResponsiblesSpecialist(self)->Agent:
        return Agent(
            config=self.agents_config['formalActsResponsiblesSpecialist'],
            verbose=False,
            max_iter= 30,
            max_retry_limit= 3,
            respect_context_window=False,
            llm=self.llm
        )
    @agent # Associa fundamento legal individual a cada ato formal obrigatório.
    def legalBasisForActsSpecialist(self)->Agent:
        return Agent(
            config=self.agents_config['legalBasisForActsSpecialist'],
            verbose=False,
            max_iter= 30,
            max_retry_limit=3,
            respect_context_window=False,
            llm=self.llm
        )
    @agent  # Prioriza atos, indicando prazo e justificativa técnica para cada um.
    def actsPrioritizationAndDeadlinesSpecialist(self)->Agent:
        return Agent(
            config=self.agents_config['actsPrioritizationAndDeadlinesSpecialist'],
            verbose=False,
            max_iter= 30,
            max_retry_limit= 3,
            respect_context_window=False,
            llm=self.llm
        )
    @agent  # Registra dúvidas, lacunas e providências para cada ato.
    def actsDoubtsAndGapsSpecialist(self)->Agent:
        return Agent(
            config=self.agents_config['actsDoubtsAndGapsSpecialist'],
            verbose=False,
            max_iter= 30,
            max_retry_limit= 3,
            respect_context_window=False,
            llm=self.llm
        )

    @agent # Consolida todas as informações dos atos e pendências para o relatório final.
    def formalActsClientReportBuilderSpecialist(self)->Agent:
        return Agent(
            config=self.agents_config['formalActsClientReportBuilderSpecialist'],
            verbose=False,
            max_iter=30,
            max_retry_limit= 3,
            respect_context_window=True,
            llm=self.llm
        )
    @agent # Formata o relatório consolidado em markdown profissional para o cliente.
    def formalActsClientReportFormatterSpecialist(self)->Agent:
        return Agent(
            config=self.agents_config['formalActsClientReportFormatterSpecialist'],
            verbose=False,
            max_iter=8,
            max_retry_limit= 3,
            respect_context_window=False,
            llm=self.llm
        )
    @agent # Otimiza quebras de linha/página no markdown para garantir legibilidade no PDF.
    def lineBreakAdjustmentSpecialist(self)->Agent:
        return Agent(
            config=self.agents_config['lineBreakAdjustmentSpecialist'],
            verbose=False,
            max_iter=10,
            max_retry_limit=2,
            respect_context_window=False,
            llm=self.llm
        )
    @agent # Gera o PDF do relatório final com toda formatação preservada.
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
    @task # Executa extração geral do documento jurídico.
    def generalExtraction(self)->Task:
        return Task(
            config=self.tasks_config['generalExtraction'],
            agent=self.generalExtractor(),
        )
    @task # Analisa e explica o contexto jurídico dos dados extraídos.
    def contextExplainerTask(self)->Task:
        return Task(
            config=self.tasks_config['contextExplainerTask'],
            agent=self.contextExplainer(),
            async_execution=True
        )
    @task # Faz análise minuciosa dos prazos processuais.
    def deadlineAnalysis(self)->Task:
        return Task(
            config=self.tasks_config['deadlineAnalysis'],
            agent=self.deadlineSpecialist(),
            async_execution=True
        )
    @task # Detecta nulidades processuais a partir dos dados extraídos.
    def nullityAnalysis(self)->Task:
        return Task(
            config=self.tasks_config['nullityAnalysis'],
            agent=self.nullitySpecialist(),
            async_execution=True
        )
    @task  # Identifica irregularidades formais e territoriais.
    def analyzeIrregularities(self)->Task:
        return Task(
            config=self.tasks_config['analyzeIrregularities'],
            agent=self.irregularitySpecialist(),
            async_execution=True
        )
    
    @task  # Mapeia ambiguidades textuais e 
    def ambiguityAnalysis(self)->Task:
        return Task(
            config=self.tasks_config['ambiguityAnalysis'],
            agent=self.ambiguitySpecialist(),
            async_execution=True
        )
    @task # Consolida achados processuais para consulta técnica e automação.
    def synthesizeProcessualInformation(self)->Task:
        return Task(
            config = self.tasks_config['synthesizeProcessualInformation'],
            agent=self.synthesisSpecialist(),
        )
    @task # Identifica fundamentos jurídicos aplicáveis.
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
    @task # Detecta todos os atos formais obrigatórios.
    def detectFormalActsTask(self)->Task:
        return Task(
            config=self.tasks_config['detectFormalActsTask'],
            agent=self.formalActsSpecialist()
        )
    @task # Atribui responsáveis a cada ato formal identificado.
    def assignFormalActResponsiblesTask(self)->Task:
        return Task(
            config=self.tasks_config['assignFormalActResponsiblesTask'],
            agent=self.formalActsResponsiblesSpecialist()
        )
    @task # Associa fundamentação legal individual aos atos obrigatórios.
    def legalBasisForActsTask(self)->Task:
        return Task(
            config=self.tasks_config['legalBasisForActsTask'],
            agent=self.legalBasisForActsSpecialist()
        )
    @task # Prioriza atos e define prazos/justificativas técnicas.
    def actsPrioritizationAndDeadlinesTask(self)->Task:
        return Task(
            config=self.tasks_config['actsPrioritizationAndDeadlinesTask'],
            agent=self.actsPrioritizationAndDeadlinesSpecialist()
        )
    @task # Lista dúvidas, lacunas e providências para cada ato.
    def actsDoubtsAndGapsTask(self)->Task:
        return Task(
            config=self.tasks_config['actsDoubtsAndGapsTask'],
            agent=self.actsDoubtsAndGapsSpecialist()
        )

    @task # Constrói relatório final consolidado dos atos processuais.
    def formalActsClientReportBuilder(self)->Task:
        return Task(
            config=self.tasks_config['formalActsClientReportBuilder'],
            agent=self.formalActsClientReportBuilderSpecialist()
        )
    @task # Formata relatório para o cliente em markdown visualmente agradável.
    def formalActsClientReportFormatter(self)->Task:
        return Task(
            config=self.tasks_config['formalActsClientReportFormatter'],
            agent=self.formalActsClientReportFormatterSpecialist(),
            markdown=True
        )
    @task # Otimiza quebras de linha/página para visual ideal no PDF.
    def lineBreakAdjustmentTask(self)->Task:
        return Task(
        config=self.tasks_config['lineBreakAdjustmentTask'],
        agent=self.lineBreakAdjustmentSpecialist(),
        tools=[adjust_line_breaks_for_pdf])
    @task # Gera PDF final do relatório processual.
    def formalActsClientReportPDFGenerationTask(self)->Task:
        return Task(
            config=self.tasks_config['formalActsClientReportPDFGenerationTask'],
            agent=self.formalActsClientReportPDFGeneratorSpecialist(),
        )

        agent=self.formalActsClientReportPDFGeneratorSpecialist(),
    
    @crew # Orquestra todos os agentes e tarefas em workflow sequencial
    def crew(self)->Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
        )


    
