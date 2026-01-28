import io
import re
import pandas as pd
import streamlit as st
from pdf2image import convert_from_bytes
import pytesseract

# ------------ CONFIG ------------
st.set_page_config(page_title="PDF → brīvie Nr", layout="wide")

# Regex: Nr + X + Y (ķer arī ** un »)
ROW_RE = re.compile(
    r"(?:^|[^\d])(\d{1,7})\s*(?:\*{1,3}|»)?\s+"
    r"(\d{5,7}[.,]\d{1,3})\s+"
    r"(\d{5,7}[.,]\d{1,3})(?!\d)",
    re.MULTILINE
)

def norm_float(s: str) -> float:
    return float(s.replace(",", "."))

def extract_points_from_text(text: str, x_min: float, x_max: float, y_min: float, y_max: float, nr_max: int):
    points = {}
    for m in ROW_RE.finditer(text):
        nr = int(m.group(1))
        x = norm_float(m.group(2))
        y = norm_float(m.group(3))

        # Filtri pret datumiem / platībām / mērogiem
        if not (x_min <= x <= x_max and y_min <= y <= y_max):
            continue
        if not (1 <= nr <= nr_max):
            continue

        # unikāls pēc Nr
        points.setdefault(nr, (x, y))

    df = pd.DataFrame(
        [{"Nr": nr, "X": points[nr][0], "Y": points[nr][1]} for nr in sorted(points)]
    )
    return df

def find_free_numbers(used, how_many=50):
    free = []
    n = 1
    used = set(used)
    while len(free) < how_many:
        if n not in used:
            free.append(n)
        n += 1
    return free

# ------------ UI ------------
st.title("PDF → Nr brīvie (OCR + tabula)")

with st.sidebar:
    st.header("Iestatījumi")
    lang = st.selectbox("OCR valoda", ["lav+eng", "eng", "lav"], index=0)
    dpi = st.slider("DPI (kvalitāte)", 150, 400, 300, 50)
    max_pages = st.slider("Maks. lapas OCR", 1, 30, 10, 1)

    st.subheader("Koordinātu filtri (lai nesajauc ar datumiem u.c.)")
    x_min = st.number_input("X min", value=200000.0, step=1000.0)
    x_max = st.number_input("X max", value=800000.0, step=1000.0)
    y_min = st.number_input("Y min", value=200000.0, step=1000.0)
    y_max = st.number_input("Y max", value=800000.0, step=1000.0)
    nr_max = st.number_input("Nr max", value=20000000, step=100000)

    st.subheader("Brīvo numuru saraksts")
    how_many = st.slider("Cik brīvos rādīt", 10, 200, 50, 10)

uploaded = st.file_uploader("Iemet PDF (arī skenētu)", type=["pdf"])

# Windows: ja vajag norādīt tesseract ceļu, atķeksē un ieliec ceļu
with st.expander("Ja uz Windows nerunā OCR: iestati Tesseract ceļu"):
    tpath = st.text_input("Tesseract ceļš (piem.)", value=r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if tpath.strip():
        pytesseract.pytesseract.tesseract_cmd = tpath.strip()

if uploaded:
    pdf_bytes = uploaded.read()

    st.info("1) Pārvērš PDF lapas par attēliem…")
    images = convert_from_bytes(pdf_bytes, dpi=dpi)

    # limit pages
    images = images[:max_pages]

    st.info("2) OCR lasa tekstu… (tas var aizņemt 10–60s atkarībā no PDF)")
    all_text = []
    progress = st.progress(0)
    for i, img in enumerate(images, start=1):
        txt = pytesseract.image_to_string(img, lang=lang)
        all_text.append(txt)
        progress.progress(int(i / len(images) * 100))

    text = "\n".join(all_text)

    st.info("3) Izvelk Nr, X, Y no OCR teksta…")
    df_points = extract_points_from_text(text, x_min, x_max, y_min, y_max, int(nr_max))

    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("Atrasti punkti")
        st.write(f"Punktu skaits: **{len(df_points)}**")
        st.dataframe(df_points, use_container_width=True, height=420)

    with c2:
        st.subheader("Brīvie Nr")
        used = df_points["Nr"].tolist() if len(df_points) else []
        free = find_free_numbers(used, how_many=how_many)
        st.write(f"Mazākais brīvais: **{free[0] if free else '—'}**")
        st.dataframe(pd.DataFrame({"FreeNr": free}), use_container_width=True, height=420)

    # downloads
    st.subheader("Lejupielāde")
    points_csv = df_points.to_csv(index=False).encode("utf-8")
    free_csv = pd.DataFrame({"FreeNr": free}).to_csv(index=False).encode("utf-8")

    st.download_button("Lejupielādēt points.csv", data=points_csv, file_name="points.csv", mime="text/csv")
    st.download_button("Lejupielādēt free.csv", data=free_csv, file_name="free.csv", mime="text/csv")

    with st.expander("Debug: OCR teksts (pirmais gabals)"):
        st.text(text[:4000])

