from pathlib import Path
import pickle
import re

import pandas as pd
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent


# ---------- Helpers ----------

def find_file(*names):
    """Find a file in the project folder, ignoring filename case."""
    for name in names:
        path = BASE_DIR / name
        if path.exists():
            return path

    wanted = {name.lower() for name in names}
    for path in BASE_DIR.iterdir():
        if path.is_file() and path.name.lower() in wanted:
            return path
    return None


def read_csv_safe(path):
    if path is None:
        return None
    for encoding in ("latin-1", "utf-8"):
        try:
            return pd.read_csv(path, encoding=encoding, low_memory=False)
        except Exception as exc:
            print(f"Could not read {path.name} using {encoding}: {exc}")
    return None


def find_column(df, candidates):
    if df is None:
        return None

    def normalize(value):
        return re.sub(r"[^a-z0-9]", "", str(value).lower())

    lookup = {normalize(c): c for c in df.columns}
    for candidate in candidates:
        if normalize(candidate) in lookup:
            return lookup[normalize(candidate)]
    return None


def clean_text(value):
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def get_cover(row):
    for key in ("cover", "image", "image_url", "image_url_m",
                "image_url_l", "Image-URL-M", "Image-URL-L", "Image-URL-S"):
        value = row.get(key)
        if value and str(value).startswith(("http://", "https://")):
            return str(value)

    isbn = clean_text(row.get("isbn", ""))
    if isbn:
        return f"https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg"
    return ""


# ---------- Load book data and ratings ----------

books_path = find_file("books_df.pkl", "Books.csv", "books.csv")
ratings_path = find_file(
    "Final_Book_Recommendation_Dataset.csv",
    "Ratings.csv",
    "ratings.csv"
)
similarity_path = find_file("book_similarity.pkl")

books_df = None
if books_path:
    try:
        if books_path.suffix.lower() == ".pkl":
            with books_path.open("rb") as file:
                books_df = pickle.load(file)
        else:
            books_df = read_csv_safe(books_path)
    except Exception as exc:
        print("Could not load books data:", exc)

ratings_df = read_csv_safe(ratings_path)

TITLE_CANDIDATES = ["Book-Title", "title", "book_title", "name"]
AUTHOR_CANDIDATES = ["Book-Author", "author", "book_author"]
ISBN_CANDIDATES = ["ISBN", "isbn", "book_id"]
USER_CANDIDATES = ["User-ID", "user_id", "userid", "user"]
RATING_CANDIDATES = ["Book-Rating", "rating", "book_rating", "score"]

title_col = find_column(books_df, TITLE_CANDIDATES)
author_col = find_column(books_df, AUTHOR_CANDIDATES)
isbn_col = find_column(books_df, ISBN_CANDIDATES)

if title_col is None:
    print("WARNING: Could not find a book title column in the books data.")
    books_df = None

rating_title_col = find_column(ratings_df, TITLE_CANDIDATES)
rating_isbn_col = find_column(ratings_df, ISBN_CANDIDATES)
user_col = find_column(ratings_df, USER_CANDIDATES)
rating_col = find_column(ratings_df, RATING_CANDIDATES)

if ratings_df is not None and rating_col:
    ratings_df[rating_col] = pd.to_numeric(ratings_df[rating_col], errors="coerce")
    ratings_df = ratings_df.dropna(subset=[rating_col])
    ratings_df = ratings_df[ratings_df[rating_col] > 0]

catalogue = pd.DataFrame()
if books_df is not None:
    catalogue["title"] = books_df[title_col].map(clean_text)
    catalogue["author"] = books_df[author_col].map(clean_text) if author_col else ""
    catalogue["isbn"] = books_df[isbn_col].map(clean_text) if isbn_col else ""

    # Preserve image URL columns from Book-Crossing.
    image_col = find_column(
        books_df,
        ["Image-URL-M", "Image-URL-L", "Image-URL-S",
         "image_url", "image_url_m", "image_url_l", "cover", "image"]
    )
    if image_col:
        catalogue["image_url"] = books_df[image_col].map(clean_text)

    catalogue = catalogue[catalogue["title"] != ""]
    catalogue = catalogue.drop_duplicates(subset=["isbn", "title"], keep="first")

if catalogue.empty and ratings_df is not None and rating_title_col:
    catalogue = pd.DataFrame({
        "title": ratings_df[rating_title_col].map(clean_text),
        "author": "",
        "isbn": ratings_df[rating_isbn_col].map(clean_text) if rating_isbn_col else ""
    })
    catalogue = catalogue[catalogue["title"] != ""].drop_duplicates(
        subset=["isbn", "title"]
    )

# Create quick rating summaries.
rating_summary = {}
if ratings_df is not None and rating_col:
    if rating_isbn_col:
        rating_summary = ratings_df.groupby(rating_isbn_col)[rating_col].agg(
            ["mean", "count"]
        ).to_dict("index")
    elif rating_title_col:
        temp = ratings_df.assign(_title=ratings_df[rating_title_col].map(clean_text))
        rating_summary = temp.groupby("_title")[rating_col].agg(
            ["mean", "count"]
        ).to_dict("index")


def book_to_json(row):
    isbn = clean_text(row.get("isbn", ""))
    title = clean_text(row.get("title", ""))
    author = clean_text(row.get("author", ""))

    stats = rating_summary.get(isbn, {}) if isbn else {}
    if not stats and title:
        stats = rating_summary.get(title, {})

    mean = stats.get("mean", 0)
    if pd.isna(mean):
        mean = 0

    # Book-Crossing ratings are usually 0-10; show them on a 0-5 scale.
    display_rating = round(float(mean) / 2, 1) if mean else 0

    return {
        "title": title,
        "author": author or "Unknown author",
        "rating": display_rating,
        "rating_count": int(stats.get("count", 0)),
        "genre": "Books",
        "isbn": isbn,
        "cover": clean_text(row.get("image_url", "")) or get_cover(row),
    }


# ---------- Load the saved book similarity model ----------

model_data = None
model_isbns = []
similarity_matrix = None

if similarity_path:
    try:
        with similarity_path.open("rb") as file:
            model_data = pickle.load(file)

        model_isbns = [clean_text(value) for value in model_data["isbns"]]
        similarity_matrix = model_data["similarity_matrix"]

        if len(model_isbns) != similarity_matrix.shape[0]:
            raise ValueError("ISBN list length does not match similarity matrix.")
        print(f"Loaded similarity model for {len(model_isbns)} books.")
    except Exception as exc:
        print("Could not load book similarity model:", exc)
        model_data = None
        model_isbns = []
        similarity_matrix = None
else:
    print("WARNING: book_similarity.pkl not found in", BASE_DIR)


# ---------- Search and recommendation functions ----------

def search_catalogue(query="", limit=30):
    if catalogue.empty:
        return []

    df = catalogue
    query = query.strip().casefold()
    if query:
        mask = (
            df["title"].astype(str).str.casefold().str.contains(query, regex=False)
            | df["author"].astype(str).str.casefold().str.contains(query, regex=False)
        )
        df = df[mask]

    return [book_to_json(row) for _, row in df.head(limit).iterrows()]


def recommend_similar_books(book_title, limit=6):
    """Use the saved cosine-similarity matrix to recommend similar books."""
    if similarity_matrix is None or catalogue.empty:
        return []

    matches = catalogue[
        catalogue["title"].astype(str).str.casefold()
        == book_title.strip().casefold()
    ]
    if matches.empty:
        matches = catalogue[
            catalogue["title"].astype(str).str.casefold().str.contains(
                book_title.strip().casefold(), regex=False
            )
        ]
    if matches.empty:
        return []

    # Try each matching ISBN until one is present in the model.
    target_index = None
    target_isbn = ""
    for isbn in matches["isbn"].astype(str):
        isbn = clean_text(isbn)
        try:
            target_index = model_isbns.index(isbn)
            target_isbn = isbn
            break
        except ValueError:
            continue

    if target_index is None:
        return []

    scores = similarity_matrix[target_index]
    ranked_indices = sorted(
        range(len(scores)), key=lambda idx: float(scores[idx]), reverse=True
    )

    recommended_isbns = []
    for idx in ranked_indices:
        isbn = model_isbns[idx]
        if isbn and isbn != target_isbn:
            recommended_isbns.append((isbn, float(scores[idx])))
        if len(recommended_isbns) >= limit * 4:
            break

    if not recommended_isbns:
        return []

    score_map = dict(recommended_isbns)
    recs = catalogue[catalogue["isbn"].astype(str).isin(score_map)].copy()
    recs["_similarity"] = recs["isbn"].astype(str).map(score_map)
    recs = recs.sort_values("_similarity", ascending=False)
    recs = recs.drop_duplicates(subset=["title"], keep="first")
    return [book_to_json(row) for _, row in recs.head(limit).iterrows()]


# ---------- Website routes ----------

@app.route("/")
def home():
    books = search_catalogue(limit=10)
    return render_template("index.html", books=books)


@app.get("/api/search")
def search():
    query = request.args.get("q", "").strip()
    return jsonify(search_catalogue(query=query, limit=30))


@app.get("/api/recommend")
def recommend():
    title = request.args.get("title", "").strip()
    if not title:
        return jsonify({
            "error": "Provide a book title using ?title=Book+Name",
            "results": []
        }), 400

    results = recommend_similar_books(title, limit=6)
    if not results:
        return jsonify({
            "message": (
                "No recommendations found for this title. The book may not be "
                "included in the saved similarity model, or its ISBN may not match."
            ),
            "results": []
        })

    return jsonify({"results": results})


@app.get("/api/health")
def health():
    return jsonify({
        "catalogue_loaded": not catalogue.empty,
        "book_count": int(len(catalogue)),
        "ratings_loaded": ratings_df is not None,
        "rating_count": int(len(ratings_df)) if ratings_df is not None else 0,
        "similarity_model_loaded": similarity_matrix is not None,
        "model_book_count": len(model_isbns),
        "recommendation_method": "item-based cosine similarity",
    })


if __name__ == "__main__":
    print("Project folder:", BASE_DIR)
    print("Book catalogue rows:", len(catalogue))
    print("Ratings rows:", len(ratings_df) if ratings_df is not None else 0)
    print("Similarity model loaded:", similarity_matrix is not None)
    app.run(debug=True)
