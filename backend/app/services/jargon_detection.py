import spacy
from collections import Counter
from wordfreq import word_frequency, zipf_frequency

FREQUENCY_THRESHOLD = 4.0

nlp = spacy.load("en_core_sci_md")

def detect_medical_jargon(text):
    doc = nlp(text.lower())
    
    jargon_found = []
    
    for ent in doc.ents:
        ent_text = ent.text.lower().strip()
        zipf_score = zipf_frequency(ent_text, 'en')
        if zipf_score < FREQUENCY_THRESHOLD:
            jargon_found.append({
                'term': ent_text,
                'zipf_score': zipf_score,  # Optional: include score
                'start': ent.start_char,
                'end': ent.end_char
            })
    
    return jargon_found