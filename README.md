# Paper Radar

**Team Infinite Loopers** | Team ID: DEX 26094 | Theme: AI & Machine Learning | Category: Software

Paper Radar transforms past exam papers from static PDFs into a targeted, gamified study strategy. Instead of guessing what to study, students can upload a subject's past papers to instantly extract every question, map it to an official syllabus topic, and visualize exact exam patterns.

> This is **pattern analysis, not a prediction**. Every count shows how many papers it rests on, and every topic links back to its source paper and year.

## How it works

1. **Upload** past papers (PDF or photo) for one subject and one regulation
2. **Extract**: `pdfplumber` reads text PDFs, Tesseract OCR handles scans
3. **Tag**: an LLM reads each question and picks a topic from the official syllabus list only
4. **Count**: plain pandas code counts topics by paper and marks (the LLM never counts)
5. **Rank**: heatmap plus a study-first list, with a "check and fix tags" step before you trust it

## Project structure

```
app.py            Streamlit web page
extractor.py      PDF/image to text (with OCR fallback)
tagger.py         LLM tagging, restricted to syllabus topics
analyzer.py       counting and ranking (pandas)
syllabus.py       syllabus loader
syllabus/         syllabus JSON files (edit this for your subject)
data/             demo data (synthetic)
make_demo_data.py regenerates the synthetic demo CSV
```

## Setup

```bash
git clone <your-repo-link>
cd paper-radar
python -m venv venv
venv\Scripts\activate          # Windows   (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and paste your Anthropic API key (or type it in the app sidebar).

**For scanned papers only**, install the OCR tools:
- Tesseract: https://github.com/UB-Mannheim/tesseract/wiki (Windows installer; add it to PATH)
- Poppler (for `pdf2image`): https://github.com/oschwartzer/poppler-windows/releases (add its `bin` folder to PATH)

## Run

```bash
streamlit run app.py
```

- **Demo data** mode works with no API key. It uses made-up questions only to show the UI.
- **Upload my papers** mode needs the API key.

## Using your real subject

1. Copy `syllabus/sample_syllabus.json` to a new file, e.g. `syllabus/my_subject.json`
2. Replace subject, regulation, units and topics with the **official** syllabus names
3. Upload that JSON from the app sidebar
4. Put the year in each paper's filename (e.g. `CS3301_Nov_2022.pdf`) so the year is picked up

## Papers used

Fill this in before submitting: exact subject, regulation, years, and where each paper came from.

| Subject | Regulation | Years | Source |
|---|---|---|---|
| TODO | TODO | TODO | TODO |

## Known limits (honest list)

- The LLM can tag a question with the wrong topic. That is why the app has an editable check step.
- Messy scans can break OCR. Demo on clean papers first.
- Only same-regulation papers should be analyzed together, because syllabi change.
- Few papers means weak patterns. The app warns when there are fewer than 5.
- Tag accuracy has not been measured yet. Spot-check a sample and write the real number here.

## Tech

Python, pandas, Streamlit, pdfplumber, Tesseract OCR, Anthropic API. No model training.
