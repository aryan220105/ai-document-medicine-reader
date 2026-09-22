# Architecture

FormSathi is a monorepo: a FastAPI backend and a React frontend.

## Layers

- **Routes** validate HTTP input and call services.
- **Services** own the document pipeline, guidance priority, and preview rendering.
- **Repositories** persist documents (SQLite) and knowledge (JSON + Chroma/lexical).
- **Providers** wrap Tesseract, embeddings, and the optional Groq LLM.

## Coordinate integrity

Every OCR word and detected field stores page index, pixel box, source image size, and a normalized 0–1 box produced by `app.utils.bounding_boxes.normalize_box`. The processed page is the authoritative display surface after preprocessing.

## Guidance priority

1. Exact known-form field guidance
2. Common-field dictionary
3. Retrieved related guidance above the similarity threshold
4. Groq interpretation of printed context when enabled and consented
5. Honest unavailable state

## No-LLM mode

The API starts without `GROQ_API_KEY`. Upload, OCR, detection, known-form help, answers, preview, and deletion remain available.
