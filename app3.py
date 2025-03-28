import os
import uuid
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from itertools import combinations
from flask import Flask, render_template, request, redirect, url_for, session, send_file
from scipy.stats import mannwhitneyu
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'inclusive-key'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['RESULT_FOLDER'] = 'results'
app.config['PLOT_FOLDER'] = 'static/plots'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULT_FOLDER'], exist_ok=True)
os.makedirs(app.config['PLOT_FOLDER'], exist_ok=True)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files["file"]
        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(filepath)
            session['uploaded_file'] = filepath
            df = pd.read_excel(filepath) if filename.endswith(".xlsx") else pd.read_csv(filepath)
            session['columns'] = df.columns.tolist()
            return redirect(url_for('select_columns'))
    return render_template("index.html")

@app.route("/select-columns", methods=["GET", "POST"])
def select_columns():
    columns = session.get('columns', [])
    if request.method == "POST":
        session['module_col'] = request.form["module_col"]
        session['mark_col'] = request.form["mark_col"]
        session['demo_cols'] = request.form.getlist("demo_cols")
        return redirect(url_for('results'))
    return render_template("select_columns.html", columns=columns)

@app.route("/results")
def results():
    filepath = session.get('uploaded_file')
    module_col = session.get('module_col')
    mark_col = session.get('mark_col')
    demo_cols = session.get('demo_cols')

    df = pd.read_excel(filepath) if filepath.endswith(".xlsx") else pd.read_csv(filepath)
    df[mark_col] = pd.to_numeric(df[mark_col], errors='coerce')
    df.dropna(subset=[module_col, mark_col] + demo_cols, inplace=True)

    all_results = []
    grouped_output = []

    for module in df[module_col].unique():
        module_data = df[df[module_col] == module]
        module_result = {"module": module, "demographics": []}
        for demo in demo_cols:
            sub_results = []
            groups = module_data[demo].dropna().unique()
            if len(groups) < 2:
                continue
            for g1, g2 in combinations(groups, 2):
                a = module_data[module_data[demo] == g1][mark_col]
                b = module_data[module_data[demo] == g2][mark_col]
                if len(a) < 5 or len(b) < 5:
                    continue
                stat, p = mannwhitneyu(a, b, alternative='two-sided')
                row = {
                    "Module": module,
                    "Demographic": demo,
                    "Group A": g1,
                    "Group B": g2,
                    "Median A": round(a.median(), 2),
                    "Median B": round(b.median(), 2),
                    "U Statistic": round(stat, 3),
                    "p-value": round(p, 4),
                    "Significant": "Yes" if p < 0.05 else "No"
                }
                all_results.append(row)
                sub_results.append(row)

            if sub_results:
                # Plot
                plt.figure(figsize=(8, 5))
                sns.boxplot(x=demo, y=mark_col, data=module_data)
                plt.title(f"{module} by {demo}")
                plt.xticks(rotation=45)
                plot_filename = f"{module}_{demo}.png".replace("/", "_")
                plt.tight_layout()
                plt.savefig(os.path.join(app.config["PLOT_FOLDER"], plot_filename))
                plt.close()

                df_demo = pd.DataFrame(sub_results)
                module_result["demographics"].append({
                    "name": demo,
                    "table": df_demo.to_html(classes="table table-bordered", index=False),
                    "plot": plot_filename
                })

        if module_result["demographics"]:
            grouped_output.append(module_result)

    results_df = pd.DataFrame(all_results)
    result_filename = f"results_{uuid.uuid4().hex}.csv"
    result_path = os.path.join(app.config["RESULT_FOLDER"], result_filename)
    results_df.to_csv(result_path, index=False)

    return render_template("results.html",
                           grouped_results=grouped_output,
                           download_link=result_filename)

@app.route("/download/<filename>")
def download(filename):
    filepath = os.path.join(app.config["RESULT_FOLDER"], filename)
    return send_file(filepath, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)