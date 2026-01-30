from docling.document_converter import DocumentConverter

source = "Dummy_CV_as_PDF.pdf"
converter = DocumentConverter()
doc = converter.convert(source).document
output=doc.export_to_markdown()
#print(output)


# the text now is extracted but it need to be parse-friendly  for better handling 
#----------------------------------------
#parsing phase : 
# in the parsing phase the extracted data should be defined into sections  
#   1. HEADER (identity + contacts + links)
#	2.	SUMMARY
#	3.	SKILLS
#	4.	EXPERIENCE
#	5.	EDUCATION
#	6.	PROJECTS 
#	7.	CERTIFICATIONS 
#	8.	LANGUAGES 
#	9.	OTHER
#---------------------------------------- 

import re

def clean_header(line: str) -> str:
    s = line.strip()    
    s = re.sub(r"^#{1,6}\s+", "", s)
    s = re.sub(r"^\*\*(.+)\*\*$", r"\1", s)
    s = s.rstrip(":").strip()

    s = re.sub(r"\s+", " ", s).lower()
    return s

def output_parsing(output: str) -> dict:
    #Split Docling markdown output into section buckets.

   # How it works:
    #1) Start in HEADER.
    #2) Read markdown line by line.
    #3) When a line looks like a section header (e.g. '## Skills', '**Skills**', 'Skills:'),
     #  switch `current_section` to the right bucket.
    #4) Otherwise, append the line to the current section.

    # Returns: dict[str, str] where each value is the text captured for that section.


    # 1) Buckets you want to produce (stable contract)
    sections = {
        "HEADER": [],
        "SUMMARY": [],
        "SKILLS": [],
        "EXPERIENCE": [],
        "EDUCATION": [],
        "PROJECTS": [],
        "CERTIFICATIONS": [],
        "LANGUAGES": [],
        "OTHER": [],
    }

    # 2) Header aliases: many possible titles -> one bucket
    
    aliases = {
        "SUMMARY": ["summary", "profile", "about", "profil", "résumé", "resume", "a propos", "à propos", "objectif"],
        "SKILLS": ["skills", "technical skills", "core skills", "competencies", "competences", "compétences", "compétences techniques", "technologies", "stack"],
        "EXPERIENCE": ["experience", "work experience", "employment", "professional experience", "expérience", "expériences", "expérience professionnelle", "parcours", "stage", "stages", "internship", "internships"],
        "EDUCATION": ["education", "academic background", "formation", "éducation", "parcours académique", "diplômes", "diplomes"],
        "PROJECTS": ["projects", "project", "personal projects", "academic projects", "projets", "projet", "projets académiques", "projets personnels"],
        "CERTIFICATIONS": ["certifications", "certification", "certificates", "certificate", "attestations", "attestation"],
        "LANGUAGES": ["languages", "language", "langues", "langue"],
    }

    # 3) Helper: decide whether a line is *probably* a header line
    def looks_like_header(raw_line: str) -> bool:
        line = raw_line.strip()
        if not line:
            return False

        low = line.lower()
        # Don't treat contact lines as section headers
        if ("@" in low) or ("http://" in low) or ("https://" in low) or ("linkedin" in low) or ("github" in low):
            return False

        # Strong header formats in markdown
        if re.match(r"^#{1,6}\s+\S+", line):
            return True
        if re.match(r"^\*\*[^*]{1,80}\*\*$", line):
            return True

        # Weak header format: short line that ends with ':'
        if line.endswith(":"):
            title = clean_header(line)
            return len(title.split()) <= 6

        return False

    # 4) Helper: map a header line -> section name (or None if unknown)
    def section_for_header(raw_line: str):
        if not looks_like_header(raw_line):
            return None

        title = clean_header(raw_line)

        # Try exact matches first
        for section_name, words in aliases.items():
            for w in words:
                if title == w:
                    return section_name

        # Then try containment (e.g., 'skills & tools')
        for section_name, words in aliases.items():
            for w in words:
                if w in title:
                    return section_name

        return None

    # 5) Main loop: build the buckets
    current_section = "HEADER"
    for raw_line in output.splitlines():
        # Keep markdown structure: remove only trailing spaces
        line = raw_line.rstrip()

        # Detect and switch section
        new_section = section_for_header(line)
        if new_section is not None:
            current_section = new_section
            continue  # don't store the header line itself

        # Store content
        sections[current_section].append(line)

    # 6) Join list-of-lines -> final strings
    final_sections = {}
    for name, lines in sections.items():
        text = "\n".join(lines)
        # collapse huge blank gaps
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        final_sections[name] = text

    # 7) Safety: if we detected no real section headers, don't lose data
    # Move everything from HEADER to OTHER so you know sectioning failed.
    any_non_header = any(final_sections[k].strip() for k in final_sections if k != "HEADER")
    if not any_non_header:
        final_sections["OTHER"] = final_sections["HEADER"]
        final_sections["HEADER"] = ""

    return final_sections









parsed = output_parsing(output)
print("\n--- Parsed Sections ---\n")
for k, v in parsed.items():
    print(f"{k}: {v} ")
    