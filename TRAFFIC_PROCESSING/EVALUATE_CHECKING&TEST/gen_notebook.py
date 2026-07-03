"""
generate_notebook.py — Tao file Notebook Jupyter cho phan EDA va danh gia mo hinh ITS Traffic LOS.
"""

import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
NOTEBOOK_DIR = SCRIPT_DIR
NOTEBOOK_PATH = NOTEBOOK_DIR / "Evaluate.ipynb"

notebook = {
    "cells": [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# Phan tich Kham pha Du lieu (EDA) & Tien Xu Ly\n",
                "\n",
                "## Gioi thieu Tong quan\n",
                "Day la buoc dau tien trong du an **Nghien cuu mo hinh Stacking Ensemble cho bai toan phan loai muc do phuc vu giao thong (LOS)**.\n",
                "Muc tieu cua phan nay la khao sat chat luong cua tap du lieu giao thong tho (Raw Data), sau do chay Pipeline tien xu ly de lam sach, gan nhan LOS va kiem tra lai chat luong dau ra.\n"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "import os\n",
                "import sys\n",
                "import subprocess\n",
                "import pandas as pd\n",
                "import numpy as np\n",
                "import matplotlib.pyplot as plt\n",
                "import seaborn as sns\n",
                "from pathlib import Path\n",
                "from IPython.display import display\n",
                "\n",
                "sns.set_theme(style='whitegrid', palette='muted')\n",
                "plt.rcParams['figure.figsize'] = (10, 6)\n",
                "\n",
                "SCRIPT_DIR = Path('.').resolve()\n",
                "TRAFFIC_DIR = SCRIPT_DIR.parent\n",
                "DATA_DIR = TRAFFIC_DIR / 'data_traffic'\n"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 1. Kham pha Du lieu Tho (Raw Data)\n",
                "Chung ta se doc cac bang du lieu goc tu thu muc `data_traffic` de xem hinh hai cua chung."
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "print('--- Dang tai du lieu tho ---')\n",
                "nodes = pd.read_csv(DATA_DIR / 'nodes.csv')\n",
                "segments = pd.read_csv(DATA_DIR / 'segments.csv')\n",
                "streets = pd.read_csv(DATA_DIR / 'streets.csv')\n",
                "segment_status = pd.read_csv(DATA_DIR / 'segment_status.csv')\n",
                "train_data = pd.read_csv(DATA_DIR / 'train.csv')\n",
                "\n",
                "print(f'Nodes: {nodes.shape}')\n",
                "print(f'Segments: {segments.shape}')\n",
                "print(f'Streets: {streets.shape}')\n",
                "print(f'Segment Status: {segment_status.shape}')\n",
                "print(f'Train Data: {train_data.shape}')\n",
                "\n",
                "display(segment_status.head())\n"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Tong quan ve Cau truc (Schema) va Dung luong Du lieu\n",
                "Truoc khi di vao truc quan hoa, chung ta can nắm rat bo du lieu co tong cong bao nhieu dong, cu nhu kieu du lieu (data types) cua tung bang. Dieu nay giup phat hien som cac truong du lieu bi sai kieu hay cac cot chua nhieu gia tri rong (Null).\n"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "total_rows = len(nodes) + len(segments) + len(streets) + len(segment_status) + len(train_data)\n",
                "print(f'\\nTONG SO HANG DU LIEU THO (RAW DATA): {total_rows:,} dong')\n",
                "print('='*60)\n",
                "\n",
                "datasets = {'Nodes': nodes, 'Segments': segments, 'Streets': streets, 'Segment Status': segment_status, 'Train': train_data}\n",
                "for name, df in datasets.items():\n",
                "    print(f'\\nSCHEMA BANG [{name.upper()}]')\n",
                "    df.info()\n",
                "    print('-'*60)\n"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "fig, axes = plt.subplots(1, 2, figsize=(16, 6))\n",
                "\n",
                "table_names = ['Nodes', 'Segments', 'Streets', 'Status', 'Train']\n",
                "table_sizes = [len(nodes), len(segments), len(streets), len(segment_status), len(train_data)]\n",
                "sns.barplot(x=table_names, y=table_sizes, ax=axes[0], palette='viridis')\n",
                "axes[0].set_title('So luong ban ghi cua cac bang du lieu tho', fontsize=14)\n",
                "axes[0].set_ylabel('So luong row')\n",
                "for i, v in enumerate(table_sizes):\n",
                "    axes[0].text(i, v + 1000, f'{v:,}', ha='center', fontweight='bold')\n",
                "\n",
                "sns.histplot(segment_status['velocity'].dropna(), bins=50, kde=True, color='crimson', ax=axes[1])\n",
                "axes[1].set_title('Phan bo Van toc (Velocity) ban dau', fontsize=14)\n",
                "axes[1].set_xlabel('Van toc (km/h)')\n",
                "axes[1].set_ylabel('Tan suat')\n",
                "\n",
                "plt.tight_layout()\n",
                "plt.show()\n"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Nhan xet ve du lieu tho:\n",
                "- **Missing Values**: Cot `velocity` trong `segment_status` doi khi bi rong (NaN) hoac co gia tri bang 0 bat thuong.\n",
                "- **Outliers**: Co cac dai toc do vot len tren 80 km/h o duong noi do hoac gia tri am, can phai got bo (Outlier Detection).\n",
                "- **Thieu Nhan (No Labels)**: Du lieu hien tai **chua co nhan LOS**. Can phai tinh toan V/C ratio de tu dong gan nhan.\n",
                "- **Reverse Duplicates**: Cac doan duong co su trung lap do xe chay haichieu (A->B va B->A).\n"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 2. So do Luong Tien Xu Ly (Data Pipeline)\n",
                "```mermaid\n",
                "flowchart TD\n",
                "    A[(Raw Data CSV)] --> B{Data Cleaning}\n",
                "    B --> |Xoa Null, Fix Type| C[Deduplication]\n",
                "    C --> |Xoa Reverse A-B/B-A| D[Outlier Detection]\n",
                "    D --> |IQR + Z-score| E[LOS Labeling]\n",
                "    E --> |Tinh V/C Ratio -> A,B,C,D,E,F| F[Merge Master Dataset]\n",
                "    F --> G[Extract Time Features]\n",
                "    G --> H[Normalization & Encoding]\n",
                "    H --> I[(train_features_base.csv)]\n",
                "```\n"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 3. Thuc thi Tien Xu Ly\n",
                "Chung ta se kich hoat script `preprocessing.py` thong qua moi truong hien tai."
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "print('Dang tien hanh chay script preprocessing.py...')\n",
                "script_path = str((TRAFFIC_DIR / 'scripts' / 'data_processing' / 'preprocessing.py').resolve())\n",
                "result = subprocess.run([sys.executable, script_path], capture_output=True, text=True)\n",
                "print(result.stdout)\n",
                "if result.stderr:\n",
                "    print('STDERR:', result.stderr)\n"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 4. Truc quan Du lieu Sau Xu Ly\n",
                "File `train_features_base.csv` vua duoc sinh ra. Chung ta se load no len va kiem tra xem nhan LOS da duoc gan chinh xac hay chua."
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "PROCESSED_PATH = TRAFFIC_DIR / 'scripts' / 'outputs' / 'train_features_base.csv'\n",
                "df_processed = pd.read_csv(PROCESSED_PATH)\n",
                "\n",
                "display(df_processed[['segment_id', 'date', 'hist_vel_last', 'max_velocity', 'vc_ratio', 'LOS']].head(10))\n"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "fig, axes = plt.subplots(1, 2, figsize=(16, 6))\n",
                "\n",
                "los_counts = df_processed['LOS'].value_counts().sort_index()\n",
                "colors = ['#1a9850', '#91cf60', '#d9ef8b', '#fee08b', '#fc8d59', '#d73027']\n",
                "axes[0].pie(los_counts, labels=los_counts.index, autopct='%1.1f%%',\n",
                "            colors=colors, startangle=140, explode=[0.05]*len(los_counts), shadow=True)\n",
                "axes[0].set_title('Phan bo Nhan Muc do Phuc vu (LOS)', fontsize=14, fontweight='bold')\n",
                "\n",
                "sns.boxplot(x='LOS', y='hist_vel_last', data=df_processed,\n",
                "            order=['A', 'B', 'C', 'D', 'E', 'F'], palette=colors, ax=axes[1])\n",
                "axes[1].set_title('Toc do thuc te (Velocity) phan bo theo muc do LOS', fontsize=14, fontweight='bold')\n",
                "axes[1].set_xlabel('LOS (A: Thong thoang -> F: Tac nghen)')\n",
                "axes[1].set_ylabel('Van toc (km/h)')\n",
                "\n",
                "plt.tight_layout()\n",
                "plt.show()\n"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Tong ket\n",
                "- **Chat luong du lieu**: Tu 5 file roi rac, nhieu loi, chung ta da gop thanh 1 tap Master duy nhat.\n",
                "- **Gan nhan**: Thuat toan da gan nhan rat thanh cong dua tren V/C ratio.\n",
                "- **San sang cho mo hinh**: Tap du lieu da du sach, san sang cho buoc Feature Engineering.\n"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "---\n",
                "## 5. Truc quan hoa qua trinh Feature Engineering\n",
                "### Cac nhom Dac trung (Features) duoc xay dung:\n",
                "- **Temporal Features**: Ma hoa `hour`, `minute`, `period` duoi dang `sine`/`cosine`.\n",
                "- **Spatial & Infrastructure Features**: Mat do duong (radius density), so lan xe (lanes), gioi han toc do (speed limit).\n",
                "- **Network Features**: Bac vao/ra cua doan duong, do luong muc do giao cat.\n",
                "- **Rolling & Lag Features**: Van toc qua khu (`velocity_lag_1` den `12`), trung binh truot (`rolling_mean`).\n",
                "- **Interaction Features**: Ti le `vc_ratio`, nang luc luu thong.\n",
                "- **Neighbor Features**: Do tre van toc tu cac doan duong lan can.\n"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "print('Dang tien hanh chay script feature_engineering.py...')\n",
                "fe_script_path = str((TRAFFIC_DIR / 'scripts' / 'feature_engineering' / 'feature_engineering.py').resolve())\n",
                "result_fe = subprocess.run([sys.executable, fe_script_path], capture_output=True, text=True)\n",
                "print('Da chay xong Feature Engineering!')\n",
                "print('\\n'.join(result_fe.stdout.split('\\n')[-10:]))\n"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Kham pha Du lieu sau Feature Engineering\n",
                "Tap du lieu luc nay da duoc mo rong len gan 200 cot dac trung."
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "FEATURES_PATH = TRAFFIC_DIR / 'scripts' / 'outputs' / 'train_features.csv'\n",
                "df_features = pd.read_csv(FEATURES_PATH)\n",
                "print(f'Kich thuoc du lieu sau Feature Engineering: {df_features.shape}')\n",
                "display(df_features[['segment_id', 'LOS', 'hour_sin', 'velocity_lag_1', 'hist_vel_mean', 'velocity_roll_mean_3', 'vc_ratio']].head())\n"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "import json\n",
                "\n",
                "cols_to_plot = ['LOS', 'velocity_lag_1', 'hist_vel_mean', 'velocity_roll_mean_3', 'vc_ratio', 'speed_limit_category_enc', 'est_lane_count']\n",
                "plot_df = df_features[cols_to_plot].copy()\n",
                "\n",
                "los_map = {k: v for v, k in enumerate(['A', 'B', 'C', 'D', 'E', 'F'])}\n",
                "plot_df['LOS_encoded'] = plot_df['LOS'].map(los_map)\n",
                "plot_df = plot_df.drop('LOS', axis=1)\n",
                "\n",
                "plt.figure(figsize=(10, 8))\n",
                "corr = plot_df.corr()\n",
                "sns.heatmap(corr, annot=True, cmap='coolwarm', fmt='.2f', linewidths=0.5)\n",
                "plt.title('Ma tran Tuong quan giua Dac trung moi va LOS (A=0 ... F=5)', fontsize=14, fontweight='bold')\n",
                "plt.tight_layout()\n",
                "plt.show()\n"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "---\n",
                "## 6. Toi uu hoa Sieu tham so (Hyperparameter Tuning)\n",
                "Quy trinh nay duoc xu ly trong file `tune_hyperparameters.py`, su dung thu vien **Optuna**.\n",
                "\n",
                "### Cac chi so duoc toi uu:\n",
                "- `n_estimators`: So luong cay quyet dinh (Decision Trees).\n",
                "- `max_depth`: Do sau toi da cua moi cay.\n",
                "- `num_leaves`: So luong la (nut cuoi) toi da tren moi cay.\n",
                "- `learning_rate`: Toc do hoc (Buoc nhay).\n",
                "- `subsample`: Ty le lay mau ngau nhien du lieu de huan luyen moi cay.\n"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Hien thi cau hinh toi uu da tim duoc\n"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "PARAMS_PATH = TRAFFIC_DIR / 'models' / 'best_optuna_params.json'\n",
                "if PARAMS_PATH.exists():\n",
                "    with open(PARAMS_PATH, 'r') as f:\n",
                "        best_params = json.load(f)\n",
                "    print('CAU HINH SIEU THAM SO TOI UU (Best Hyperparameters):\\n')\n",
                "    print('='*50)\n",
                "    for key, value in best_params.items():\n",
                "        print(f'   {str(key).ljust(15)} : {value}')\n",
                "    print('='*50)\n",
                "else:\n",
                "    print('Chua tim thay cau hinh toi uu. Vui long chay tune_hyperparameters.py truoc!')\n"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "---\n",
                "## 7. Huan luyen Mo hinh Stacking Ensemble\n",
                "### Co che Chia Du lieu (Data Splitting)\n",
                "Tap du lieu duoc che doc theo **Truc thoi gian (Time-based split)** voi ty le **80/10/10**.\n",
                "\n",
                "### Kien truc Stacking Ensemble\n",
                "- **Base Learners**: Random Forest, XGBoost, LightGBM, CatBoost.\n",
                "- **Meta Learner**: Logistic Regression (kem class_weight='balanced').\n"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Truc quan hoa Danh gia Cheo (Cross-Validation)\n"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "import json\n",
                "\n",
                "METRICS_PATH = TRAFFIC_DIR / 'models' / 'training_metrics.json'\n",
                "if METRICS_PATH.exists():\n",
                "    with open(METRICS_PATH, 'r') as f:\n",
                "        metrics = json.load(f)\n",
                "    \n",
                "    cv_acc = metrics.get('cv_accuracy_per_fold', [])\n",
                "    cv_f1 = metrics.get('cv_macro_f1_per_fold', [])\n",
                "    \n",
                "    if cv_acc and cv_f1:\n",
                "        fig, ax = plt.subplots(figsize=(10, 5))\n",
                "        folds = range(1, len(cv_acc) + 1)\n",
                "        ax.plot(folds, cv_acc, marker='o', lw=2.5, label=f\"Accuracy (Mean: {metrics['cv_accuracy_mean']:.4f})\", color='blue')\n",
                "        ax.plot(folds, cv_f1, marker='s', lw=2.5, label=f\"Macro F1 (Mean: {metrics['cv_macro_f1_mean']:.4f})\", color='green')\n",
                "        \n",
                "        ax.set_title('Cross-Validation Score Progression', fontsize=14, fontweight='bold')\n",
                "        ax.set_xlabel('Fold Index', fontsize=12)\n",
                "        ax.set_ylabel('Score', fontsize=12)\n",
                "        ax.set_xticks(folds)\n",
                "        ax.set_ylim(min(min(cv_acc), min(cv_f1)) - 0.05, 1.05)\n",
                "        ax.legend(loc='lower right')\n",
                "        ax.grid(True, linestyle='--', alpha=0.7)\n",
                "        plt.tight_layout()\n",
                "        plt.show()\n",
                "else:\n",
                "    print('Khong tim thay training_metrics.json. Vui long chay train_stacking.py truoc.')\n"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "---\n",
                "## 8. Danh gia Chuyen sau tren Tap Test Doc lap (Evaluation & XAI)\n",
                "\n",
                "### Cac Bieu do Truc quan:\n",
                "- **Confusion Matrix**: Ma tran Nham lan thuc te tren Test Set.\n",
                "- **Precision-Recall Curve**: Duong cong Precision - Recall.\n",
                "- **Feature Importance**: Diem trung binh nhung dac trung quan trong nhat.\n"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "import joblib\n",
                "from sklearn.metrics import classification_report, confusion_matrix, precision_recall_curve, average_precision_score\n",
                "from sklearn.preprocessing import label_binarize\n",
                "\n",
                "MODEL_PATH = TRAFFIC_DIR / 'models' / 'stacking_ensemble_ITS.joblib'\n",
                "TEST_PATH = TRAFFIC_DIR / 'scripts' / 'data_after_split' / 'test' / 'test.csv'\n",
                "\n",
                "if MODEL_PATH.exists() and TEST_PATH.exists():\n",
                "    print('Dang tai mo hinh va tap Test Set...')\n",
                "    pipeline = joblib.load(MODEL_PATH)\n",
                "    test_df = pd.read_csv(TEST_PATH)\n",
                "    \n",
                "    feature_names_path = TRAFFIC_DIR / 'models' / 'feature_names_used.json'\n",
                "    with open(feature_names_path, 'r') as f:\n",
                "        feature_names = json.load(f)['feature_names']\n",
                "        \n",
                "    X_test = test_df[feature_names]\n",
                "    y_test_raw = test_df['LOS']\n",
                "    \n",
                "    classes = ['A', 'B', 'C', 'D', 'E', 'F']\n",
                "    y_test = y_test_raw.values\n",
                "    \n",
                "    print('Dang du bao ket qua tren Test Set...')\n",
                "    y_pred = pipeline.predict(X_test)\n",
                "    try:\n",
                "        y_probs = pipeline.predict_proba(X_test)\n",
                "    except:\n",
                "        y_probs = None\n",
                "    \n",
                "    print('\\n================ CLASSIFICATION REPORT (TEST SET) ================')\n",
                "    print(classification_report(y_test, y_pred, target_names=[f'LOS {c}' for c in classes]))\n",
                "    \n",
                "    fig, axes = plt.subplots(1, 2, figsize=(18, 8))\n",
                "    \n",
                "    cm = confusion_matrix(y_test, y_pred)\n",
                "    sns.heatmap(cm, annot=True, fmt='d', cmap='OrRd', xticklabels=classes, yticklabels=classes, ax=axes[0], annot_kws={'size': 13})\n",
                "    axes[0].set_title('Ma tran Nham lan (Confusion Matrix) - Test Set', fontsize=15, fontweight='bold')\n",
                "    axes[0].set_ylabel('Nhan Thuc Te (True)', fontsize=12)\n",
                "    axes[0].set_xlabel('Nhan Du Bao (Predicted)', fontsize=12)\n",
                "    \n",
                "    if y_probs is not None:\n",
                "        y_test_bin = label_binarize(y_test, classes=range(len(classes)))\n",
                "        colors = ['blue', 'green', 'red', 'cyan', 'magenta', 'orange']\n",
                "        for i in range(len(classes)):\n",
                "            if i >= y_test_bin.shape[1]: break\n",
                "            precision, recall, _ = precision_recall_curve(y_test_bin[:, i], y_probs[:, i])\n",
                "            ap = average_precision_score(y_test_bin[:, i], y_probs[:, i])\n",
                "            axes[1].plot(recall, precision, color=colors[i], lw=2.5, label=f'LOS {classes[i]} (AP = {ap:.2f})')\n",
                "            \n",
                "        axes[1].set_xlabel('Recall', fontsize=12)\n",
                "        axes[1].set_ylabel('Precision', fontsize=12)\n",
                "        axes[1].set_title('Duong cong Precision-Recall da lop', fontsize=15, fontweight='bold')\n",
                "        axes[1].legend(loc='lower left')\n",
                "        axes[1].grid(True, alpha=0.3)\n",
                "    \n",
                "    plt.tight_layout()\n",
                "    plt.show()\n",
                "    \n",
                "    FI_PATH = TRAFFIC_DIR / 'models' / 'feature_importance_mean.csv'\n",
                "    if FI_PATH.exists():\n",
                "        df_fi = pd.read_csv(FI_PATH).head(20)\n",
                "        plt.figure(figsize=(14, 8))\n",
                "        sns.barplot(x='importance', y='feature', data=df_fi, palette='magma')\n",
                "        plt.title('Top 20 Dac trung Quan trong nhat', fontsize=15, fontweight='bold')\n",
                "        plt.xlabel('Do quan trong trung binh (Mean Importance)', fontsize=12)\n",
                "        plt.ylabel('Dac trung (Feature)', fontsize=12)\n",
                "        plt.tight_layout()\n",
                "        plt.show()\n",
                "else:\n",
                "    print('Khong tim thay file mo hinh hoac tap test. Dam bao da Train thanh cong!')\n"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "---\n",
                "## 9. Kham pha Ket qua Du bao Cuoi cung (Inference Results)\n",
                "Ket qua cua hang ngan phan doan duong duoc xuat ra file `prediction_result.csv`.\n",
                "\n",
                "### Y nghia cac truong du lieu dau ra:\n",
                "- **`LOS_pred`**: Nhan du bao muc do un tac (tu A: Thong thoang den F: Tac nghen nghiem trong).\n",
                "- **`confidence_score`**: Do tin cay cua du bao (tu 0.0 den 1.0).\n",
                "- **`prob_LOS_A` den `prob_LOS_F`**: Xac suat chi tiet cho tung nhan.\n"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "PRED_PATH = TRAFFIC_DIR / 'scripts' / 'outputs' / 'prediction_result.csv'\n",
                "if PRED_PATH.exists():\n",
                "    df_pred = pd.read_csv(PRED_PATH)\n",
                "    print(f'Da nap {len(df_pred):,} dong ket qua du bao tu prediction_result.csv!')\n",
                "    display(df_pred.sample(5, random_state=42))\n",
                "else:\n",
                "    print('Chua co ket qua du bao. Vui long chay prediction_ITS.py truoc!')\n"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "if PRED_PATH.exists():\n",
                "    fig, axes = plt.subplots(1, 2, figsize=(16, 6))\n",
                "    \n",
                "    sns.countplot(data=df_pred, x='LOS_pred', order=['A', 'B', 'C', 'D', 'E', 'F'], palette='coolwarm', ax=axes[0])\n",
                "    axes[0].set_title('Phan bo Cap do Giao thong (LOS) Du bao', fontsize=15, fontweight='bold')\n",
                "    axes[0].set_xlabel('Muc do LOS (A -> F)', fontsize=12)\n",
                "    axes[0].set_ylabel('So luong phan doan (Segments)', fontsize=12)\n",
                "    \n",
                "    for p in axes[0].patches:\n",
                "        axes[0].annotate(f'{int(p.get_height())}', (p.get_x() + p.get_width() / 2., p.get_height()),\n",
                "                         ha='center', va='center', xytext=(0, 8), textcoords='offset points', fontsize=11)\n",
                "    \n",
                "    sns.histplot(data=df_pred, x='confidence_score', bins=20, kde=True, color='teal', ax=axes[1])\n",
                "    axes[1].set_title('Mat do Phan bo Do Tin Cay (Confidence Score)', fontsize=15, fontweight='bold')\n",
                "    axes[1].set_xlabel('Do tin cay (0.0 -> 1.0)', fontsize=12)\n",
                "    axes[1].set_ylabel('Tan suat', fontsize=12)\n",
                "    \n",
                "    plt.tight_layout()\n",
                "    plt.show()\n",
                "    \n",
                "    sample = df_pred.iloc[0]\n",
                "    probs = [sample[f'prob_LOS_{c}'] for c in ['A', 'B', 'C', 'D', 'E', 'F']]\n",
                "    plt.figure(figsize=(8, 4))\n",
                "    sns.barplot(x=['LOS A', 'LOS B', 'LOS C', 'LOS D', 'LOS E', 'LOS F'], y=probs, palette='viridis')\n",
                "    plt.title(f\"Vi du Xac suat Du bao cho doan duong\", fontsize=13, fontweight='bold')\n",
                "    plt.ylabel('Xac suat (Probability)')\n",
                "    plt.ylim(0, 1.1)\n",
                "    for i, v in enumerate(probs):\n",
                "        plt.text(i, v + 0.02, f\"{v:.2f}\", ha='center', fontweight='bold')\n",
                "    plt.tight_layout()\n",
                "    plt.show()\n"
            ]
        }
    ],
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "codemirror_mode": {"name": "ipython", "version": 3},
            "file_extension": ".py",
            "mimetype": "text/x-python",
            "name": "python",
            "nbconvert_exporter": "python",
            "pygments_lexer": "ipython3",
            "version": "3.10.0"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 4
}

with open(NOTEBOOK_PATH, 'w', encoding='utf-8') as f:
    json.dump(notebook, f, ensure_ascii=False, indent=2)

print(f"Notebook da duoc tao thanh cong tai: {NOTEBOOK_PATH}")
