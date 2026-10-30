# BookRecommender — green theme demo

A responsive Flask website inspired by the supplied reference image.

## Run locally (Windows)

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000/ in your browser.

## Important

- This version uses a small demo book catalogue to make the UI functional.
- It does not yet load your notebook's processed CSV or trained recommendation model.
- Replace the `BOOKS` list in `app.py` and the `/api/search` logic with your real dataset and recommendation function.
- Book covers are loaded from Open Library; genre backgrounds use Unsplash image URLs, so internet access is needed for those images.
- Only load trusted pickle files.
