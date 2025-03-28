
# Inclusive Gap Checker 🧮🎓

This Flask web application helps educators and analysts detect **attainment gaps** in student assessments across different demographic groups (e.g., gender, ethnicity).

## 🔍 Features

- Upload `.xlsx` or `.csv` files with student data
- Select:
  - **Module column**
  - **Mark column**
  - **Demographic columns**
- Perform:
  - **Mann-Whitney U test**
  - **Cliff's Delta** (effect size)
  - **Multiple testing correction (FDR)**
  - **Sample size warnings**
- View:
  - Interactive tables (color-coded)
  - Violin and swarm plots per demographic
  - Summary per module

## 🚀 How to Run

```bash
pip install -r requirements.txt
python app.py
```

Visit: `http://127.0.0.1:5000/`

## 📁 Input Format

Your file should contain:
- One column for **module names**
- One column for **numerical marks**
- One or more columns with **categorical demographic values**

## 📤 Output

- Color-coded HTML tables showing statistical results
- Auto-generated plots (stored in `/static/plots`)
- CSV file with full results (downloadable)

---

Made with ❤️ to promote fair and inclusive education.
