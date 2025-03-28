
import os
import uuid
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from itertools import combinations
from flask import Flask, render_template, request, redirect, url_for, session, send_file
from scipy.stats import mannwhitneyu
from statsmodels.stats.multitest import multipletests
from werkzeug.utils import secure_filename

def cliffs_delta(a, b):
    from numpy import array
    a, b = array(a), array(b)
    n, m = len(a), len(b)
    more = sum([1 for x in a for y in b if x > y])
    less = sum([1 for x in a for y in b if x < y])
    return (more - less) / (n * m)

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

    raw_results = []

    for module in df[module_col].unique():
        module_data = df[df[module_col] == module]
        for demo in demo_cols:
            groups = module_data[demo].dropna().unique()
            if len(groups) < 2:
                continue
            for g1, g2 in combinations(groups, 2):
                a = module_data[module_data[demo] == g1][mark_col]
                b = module_data[module_data[demo] == g2][mark_col]
                if len(a) < 5 or len(b) < 5:
                    continue
                stat, p = mannwhitneyu(a, b, alternative='two-sided')
                effect = cliffs_delta(a, b)
                raw_results.append({
                    "Module": module,
                    "Demographic": demo,
                    "Group A": g1,
                    "Group B": g2,
                    "Median A": round(a.median(), 2),
                    "Median B": round(b.median(), 2),
                    "U Statistic": round(stat, 3),
                    "p-value": p,
                    "Effect Size": round(effect, 3),
                    "Size Warning": "Yes" if len(a) < 10 or len(b) < 10 else "No"
                })

    p_values = [r["p-value"] for r in raw_results]
    _, corrected, _, _ = multipletests(p_values, alpha=0.05, method='fdr_bh')
    for i, row in enumerate(raw_results):
        row["Corrected p-value"] = round(corrected[i], 4)
        row["Significant"] = "Yes" if corrected[i] < 0.05 else "No"
        row["p-value"] = round(row["p-value"], 4)

    results_df = pd.DataFrame(raw_results)
    grouped_output = []

    for module in results_df["Module"].unique():
        module_df = results_df[results_df["Module"] == module]
        module_result = {"module": module, "demographics": []}

        top = module_df.loc[module_df["Effect Size"].abs().idxmax()]
        module_result["summary"] = {
            "total": len(module_df),
            "significant": module_df["Significant"].value_counts().get("Yes", 0),
            "top_demo": top["Demographic"],
            "group_a": top["Group A"],
            "group_b": top["Group B"],
            "effect_size": top["Effect Size"]
        }

        for demo in module_df["Demographic"].unique():
            df_demo = module_df[module_df["Demographic"] == demo].copy()

            styled = df_demo.style.applymap(
                lambda v: 'background-color: #fdd' if isinstance(v, str) and v == "Yes" else '',
                subset=["Significant"]
            ).applymap(
                lambda v: 'background-color: #ffd' if isinstance(v, str) and v == "Yes" else '',
                subset=["Size Warning"]
            ).format(precision=3)

            violin_plot = f"{module}_{demo}_violin.png".replace("/", "_")
            if not os.path.exists(os.path.join(app.config["PLOT_FOLDER"], violin_plot)):
                plt.figure(figsize=(8, 5))
                sns.violinplot(x=demo, y=mark_col, data=df[df[module_col] == module], inner="box")
                plt.title(f"{module} - Violin Plot by {demo}")
                plt.xticks(rotation=45)
                plt.tight_layout()
                plt.savefig(os.path.join(app.config["PLOT_FOLDER"], violin_plot))
                plt.close()

            swarm_plot = f"{module}_{demo}_swarm.png".replace("/", "_")
            if not os.path.exists(os.path.join(app.config["PLOT_FOLDER"], swarm_plot)):
                plt.figure(figsize=(8, 5))
                sns.swarmplot(x=demo, y=mark_col, data=df[df[module_col] == module], size=4)
                plt.title(f"{module} - Swarm Plot by {demo}")
                plt.xticks(rotation=45)
                plt.tight_layout()
                plt.savefig(os.path.join(app.config["PLOT_FOLDER"], swarm_plot))
                plt.close()

            module_result["demographics"].append({
                "name": demo,
                "table": styled.to_html(classes="table table-bordered", index=False),
                "violin_plot": violin_plot,
                "swarm_plot": swarm_plot
            })

        if module_result["demographics"]:
            grouped_output.append(module_result)

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
