"""Fictional regression documents, not hardcoded candidate outputs."""
from io import BytesIO
from pathlib import Path
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE
from reportlab.pdfgen import canvas
import pytest

from app.services.parser import ResumeParser, segment_sections
from app.services.extraction import InformationExtractor
from app.services.extraction.contacts import urls
from app.services.extraction.records import project_records, certification_records, education_records
from test_extraction import StubNER


def hyperlink(paragraph, label, url):
    relationship = paragraph.part.relate_to(url, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
    link=OxmlElement('w:hyperlink');link.set(qn('r:id'),relationship)
    run=OxmlElement('w:r');text=OxmlElement('w:t');text.text=label;run.append(text);link.append(run);paragraph._p.append(link)


def test_visible_technology_names_are_never_urls():
    assert urls('React.js Node.js Vue.js Next.js ASP.NET') == []
    assert urls('[GitHub]') == []
    assert urls('github.com/example/tool') == ['https://github.com/example/tool']


def test_projects_keep_bullets_wrapped_lines_and_labels():
    records=project_records('Resume-Insight Platform | Python, React.js\n[GitHub]\n- Developed a resume parser\nusing Python and machine learning.\n- Integrated document uploads.\nMarket-Data Dashboard\nAn interactive application that provides market summaries.\n- Built data charts.\n')
    assert [r.name for r in records] == ['Resume-Insight Platform','Market-Data Dashboard']
    assert 'parser using Python' in records[0].description
    assert 'JavaScript' not in records[0].technologies
    assert 'React' in records[0].technologies
    assert all('https://react.js' not in r.urls for r in records)


def test_certification_dates_issuers_and_activity_boundary():
    text='Certifications\nIndustrial Automation Certificate\nSiemens\nJul\n2024\n- Completed practical modules.\nSoftware Engineering Simulation by Forage\nDate: Aug 2023\nEXTRA CURRICULAR ACTIVITIES\n- Won a university football tournament.\n- Organized a sports event.\n'
    result=InformationExtractor(StubNER()).extract(text)
    certs=result.candidate.certifications
    assert len(certs)==2
    assert certs[0].issuer=='Siemens' and certs[0].date=='2024-07'
    assert certs[1].issuer=='Forage'
    assert len(result.candidate.activities)==1
    assert 'football' in result.candidate.activities[0].raw_text
    assert all('football' not in c.raw_text for c in certs)
    assert not result.candidate.work_experience
    assert result.work_experience_status=='not_detected'


def test_education_multiple_qualifications_grades_and_dates():
    records=education_records('Example Institute of Technology\nB.Tech in AI & ML\n2021 - 2025\nCGPA: 8.4/10\nExample Junior College\nHSC\n2019 - 2021\nGrade: 87%\nExample High School\nSSC\nGraduated 2019\n')
    assert len(records)==3
    assert records[0].institution=='Example Institute of Technology'
    assert records[0].field=='AI & ML'
    assert (records[0].start_date,records[0].end_date)==('2021','2025')
    assert records[0].grade=='CGPA: 8.4/10'
    assert records[1].degree=='HSC' and records[2].degree=='SSC'
    assert records[2].end_date=='2019'


def test_pdf_embedded_profile_and_project_links_are_anchored(tmp_path):
    path=tmp_path/'synthetic.pdf';pdf=canvas.Canvas(str(path),pagesize=(612,792))
    for text,y in [('Name: Alex Example',760),('[LinkedIn]',740),('Projects',710),('Project: First Tool',690),('[GitHub]',670),('- Built document APIs.',650),('Project: Second Tool',620),('[GitHub]',600),('- Built data charts.',580)]:
        pdf.drawString(40,y,text)
    pdf.linkURL('https://linkedin.com/in/alex-example',(40,738,100,750),relative=0)
    pdf.linkURL('https://github.com/example/first',(40,668,100,680),relative=0)
    pdf.linkURL('https://github.com/example/second',(40,598,100,610),relative=0)
    pdf.save()
    parsed=ResumeParser().parsefile(path)
    assert len(parsed['hyperlinks'])==3
    assert parsed['raw_text'] and parsed['layout_blocks']
    result=InformationExtractor(StubNER()).extract(parsed['text'],hyperlinks=parsed['hyperlinks'],layout_blocks=parsed['layout_blocks'])
    assert result.candidate.linkedin_urls==['https://linkedin.com/in/alex-example']
    assert [r.urls for r in result.candidate.projects]==[['https://github.com/example/first'],['https://github.com/example/second']]
    assert [r.github_url for r in result.candidate.projects] == ['https://github.com/example/first', 'https://github.com/example/second']


def test_docx_relationships_preserve_visible_labels_and_lists(tmp_path):
    path=tmp_path/'synthetic.docx';doc=Document();doc.add_paragraph('Name: Alex Example')
    hyperlink(doc.add_paragraph(),'GitHub','https://github.com/alex-example')
    doc.add_paragraph('Projects');doc.add_paragraph('Project: Document Tool')
    hyperlink(doc.add_paragraph(),'[GitHub]','https://github.com/example/document-tool')
    doc.add_paragraph('Built Python APIs.',style='List Bullet');doc.save(path)
    parsed=ResumeParser().parsefile(path)
    assert '[GitHub]' in parsed['text'] and '- Built Python' in parsed['text']
    result=InformationExtractor(StubNER()).extract(parsed['text'],hyperlinks=parsed['hyperlinks'],layout_blocks=parsed['layout_blocks'])
    assert 'https://github.com/alex-example' in result.candidate.github_urls
    assert result.candidate.projects[0].urls==['https://github.com/example/document-tool']
    assert result.candidate.projects[0].github_url == 'https://github.com/example/document-tool'


def test_conflicting_project_urls_remain_unresolved():
    record = project_records('Project: Document Tool\n- Built document APIs.\nhttps://github.com/example/first\nhttps://github.com/example/second\nLive demo: https://demo.example.test\n')[0]
    assert record.github_url is None
    assert record.live_url == 'https://demo.example.test'
    assert record.extraction_warnings and record.evidence


def test_unlabeled_website_is_not_invented_as_live_demo():
    record = project_records('Project: Document Tool\n- Built document APIs.\nhttps://docs.example.test\n')[0]
    assert record.live_url is None
    assert record.urls == ['https://docs.example.test']


def test_bare_stack_and_unbulleted_feature_sentence_stay_with_project():
    records = project_records('Project: Document Tool\nPython, React.js\nFeatures include secure document uploads\n- Built a parser.\nProject: Chart Tool\n- Built data charts.')
    assert [record.name for record in records] == ['Document Tool', 'Chart Tool']
    assert {'Python', 'React'} <= set(records[0].technologies)
    assert 'secure document uploads' in records[0].description


def test_pdf_annotation_spanning_projects_is_not_arbitrarily_assigned(tmp_path):
    path = tmp_path / 'ambiguous.pdf'
    pdf = canvas.Canvas(str(path))
    for index, line in enumerate(['Projects', 'Project: First Tool', '[GitHub]', '- Built APIs.', 'Project: Second Tool', '[GitHub]', '- Built charts.']):
        pdf.drawString(40, 760-index*20, line)
    pdf.linkURL('https://github.com/example/uncertain', (40, 650, 250, 740), relative=0)
    pdf.save()
    parsed = ResumeParser().parsefile(path)
    assert parsed['hyperlinks'][0]['ambiguous']
    result = InformationExtractor(StubNER()).extract(parsed['text'], hyperlinks=parsed['hyperlinks'], layout_blocks=parsed['layout_blocks'])
    assert len(result.candidate.projects) == 2
    assert all(project.github_url is None and not project.urls for project in result.candidate.projects)
    assert any('unresolved' in warning for warning in parsed['warnings'])


def test_two_columns_keep_sections_local_and_right_aligned_dates(tmp_path):
    path=tmp_path/'columns.pdf';pdf=canvas.Canvas(str(path),pagesize=(612,792))
    for x,lines in [(35,['Name: Alex Example','Skills','Python, SQL','Education','Example University','BSc in Physics','2018 - 2022']), (330,['Projects','Project: Document Tool','- Built document APIs.','Certifications','Certificate: Cloud Basics','Issuer: Example Board','2023'])]:
        for index,line in enumerate(lines):pdf.drawString(x,760-index*24,line)
    pdf.save();parsed=ResumeParser().parsefile(path)
    assert 'Example University' in parsed['sections']['education']
    assert 'Document Tool' in parsed['sections']['projects']
    assert 'Cloud Basics' not in parsed['sections']['education']
    assert any('Two-column' in w for w in parsed['warnings'])


def test_embedded_contact_schemes_and_unsafe_links():
    from app.services.document_links import normalize_document_target
    assert normalize_document_target('javascript:alert(1)') is None
    assert normalize_document_target('https://user:private@example.test') is None
    result=InformationExtractor(StubNER()).extract('Name: Alex Example',hyperlinks=[
        {'url':'mailto:alex@example.test','label':'Email','source':'docx_relationship'},
        {'url':'tel:+442079460018','label':'Phone','source':'docx_relationship'},
    ])
    assert result.candidate.emails==['alex@example.test']
    assert result.candidate.phones[0].e164=='+442079460018'


def test_strict_decorated_headings_and_project_stack_context():
    sections,_=segment_sections('1. E D U C A T I O N\nExample University\nBSc\nCERTIFICATIONS\nCertificate: Basics\nEXTRA-CURRICULAR ACTIVITIES\n- Football')
    assert 'education' in sections and 'activities' in sections
    record=project_records('Project: Data Tool\nTech Stack: Go, React.js\n- Built APIs.')[0]
    assert 'Go' in record.technologies and 'React' in record.technologies
    assert record.urls==[]


def test_compact_pdf_keeps_full_repeated_skill_evidence_only_in_json(docx_bytes):
    from fastapi.testclient import TestClient
    from app.core.config import Settings
    from app.main import create_app
    from pdfminer.high_level import extract_text
    document=Document(BytesIO(docx_bytes))
    document.add_paragraph('Skills')
    for _ in range(60):document.add_paragraph('Python')
    content=BytesIO();document.save(content)
    with TestClient(create_app(Settings(_env_file=None,app_mode='anonymous'))) as client:
        data=client.post('/api/v1/resumes/analyze',files={'file':('synthetic.docx',content.getvalue())}).json()
        skill=next(s for s in data['parsed']['skills'] if s['name']=='Python')
        assert len(skill['occurrences'])>=60
        pdf=client.post('/api/v1/reports',json={'snapshot':data,'format':'pdf'})
        assert pdf.status_code==200
        text=extract_text(BytesIO(pdf.content))
        assert text.count('Python') < 10
        assert 'JSON report' in text
