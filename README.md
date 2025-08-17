# ScentFinder: A Personalized Cologne Recommendation System

![ScentFinder Banner](ScentFinder.png)

## 👃 Project Overview

ScentFinder is a data science project designed to recommend colognes based on scent profile similarity. Inspired by my personal passion for fragrance and driven by my background in data science, this project integrates web scraping, data engineering, machine learning, and full-stack deployment to help users discover new colognes tailored to their olfactory preferences.

> “I wanted to build a system that tells me: ‘If you love Dior Sauvage and Bleu de Chanel, here’s what you should try next.’”

---

## 🎯 Goals

- Scrape structured fragrance data from sources like Fragrantica
- Build a scalable SQL + MongoDB database of perfumes
- Engineer meaningful features from scent notes and metadata
- Implement a content-based recommendation engine
- Deploy a Streamlit app for user-friendly recommendations
- Produce a professional report analyzing dataset trends and modelling outcomes

---

## 🧠 Key Features

| Feature                  | Description                                                                 |
|--------------------------|-----------------------------------------------------------------------------|
| 🕸️ Web Scraping          | Extracts cologne metadata, notes, brands, etc. from Fragrantica             |
| 🧹 Data Cleaning         | Normalizes scent notes, classifies longevity/sillage, price ranges          |
| 🧱 Database Architecture | SQL schema + optional MongoDB for document storage                          |
| 🧬 Feature Engineering   | One-hot encoding, note richness, profile vectors                            |
| 🧠 Recommendation Engine | Cosine similarity on scent profiles for personalized suggestions            |
| 🌐 Web App (Streamlit)   | User selects colognes and gets recommendations with visual explanations     |
| 📊 Report & EDA          | Note co-occurrence, seasonal analysis, scent clustering                     |

---

## 🔧 Technologies Used

- **Python 3.9+**
- **BeautifulSoup / Requests** for scraping
- **pandas / numpy / scikit-learn** for data processing & modeling
- **PostgreSQL + SQLAlchemy** for relational database
- **MongoDB** (optional) for document-based scent storage
- **joblib / pickle** for caching models
- **Streamlit** for web app deployment
- **Matplotlib / Seaborn / Plotly** for visualizations

---

## 📁 Folder Structure

```bash
scentfinder/
├── data/            # Raw, interim, and processed datasets
├── notebooks/       # EDA and modelling notebooks
├── src/             # Scraping, Data Cleaning, modelling, and app modules
├── config/          # Pipeline settings, database schema
├── cache/           # Cached models and similarity matrices
├── reports/         # Visualizations and final report
├── requirements.txt
└── README.md
```

## Project Timeline 
| Week        | Focus           | 
| ------------- |:-------------:|
| 1      | Project setup, environment, schema design |
| 2     | Web scraping and raw data collection      |
| 3  | Data cleaning + database loading     |
| 4  | Exploratory data analysis & visualization     |
| 5  | Modeling & similarity logic     |
| 6  | App deployment via Streamlit     |
| 7  | Reporting, documentation, and polish     |

## Getting Started

1.	Clone the repo:
```bash
git clone https://github.com/ethanbobrik/scentfinder.git
cd scentfinder
```

2.	Set up your Python environment:
```bash
python -m venv env
source env/bin/activate
pip install -r requirements.txt
```

3.	Run the app (when ready):
```bash
streamlit run src/app/main.py
```

## 👤 Author
Ethan Bobrik
2nd-Year Data Science Student
Western University

## 📌 Acknowledgments
- Fragrantica.com — For being the best source of fragrance metadata
- The data science community — For open tools and generous documentation
