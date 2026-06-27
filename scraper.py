from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import time

# =========================
# INSTELLINGEN
# =========================
BASE_URL = "https://basketball.realgm.com/international/stats/"
POSITIONS = ["PG", "SG", "SF", "PF", "C"]
STAT_TYPES = ["Averages", "Advanced Stats"]

# Harde safeguard voor runaway pagination
MAX_PAGES_DEFAULT = 50
MAX_PAGES_PER_POSITION = {
    "C": 19   # tijdelijke fix, gebaseerd op wat jij op de site zag
}

# =========================
# BROWSER SETUP
# =========================
driver = webdriver.Chrome()
wait = WebDriverWait(driver, 20)

driver.get(BASE_URL)

# =========================
# COOKIE CONSENT
# =========================
try:
    consent_button = wait.until(
        EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "button.fc-button.fc-cta-consent.fc-primary-button")
        )
    )
    consent_button.click()
    print("✅ Consent geklikt")
except:
    print("⚠️ Geen consent nodig")

time.sleep(2)

# =========================
# DROPDOWNS VINDEN
# =========================
def find_dropdowns():
    selects = driver.find_elements(By.TAG_NAME, "select")

    season = None
    position = None
    stat = None

    for el in selects:
        sel = Select(el)
        options = [o.text.strip() for o in sel.options]

        if "2025-2026" in options and "2026-2027" in options:
            season = sel

        if "PG" in options and "SG" in options and "C" in options:
            position = sel

        if "Averages" in options and "Advanced Stats" in options:
            stat = sel

    return season, position, stat

# =========================
# FILTERS ZETTEN
# =========================
def apply_filters(position_value, stat_type_value):
    season, position, stat = find_dropdowns()

    if season is None:
        raise Exception("Season dropdown niet gevonden")
    if position is None:
        raise Exception("Position dropdown niet gevonden")
    if stat is None:
        raise Exception("Stat Type dropdown niet gevonden")

    season.select_by_visible_text("2025-2026")
    time.sleep(1)

    season, position, stat = find_dropdowns()
    position.select_by_visible_text(position_value)
    time.sleep(1)

    season, position, stat = find_dropdowns()
    stat.select_by_visible_text(stat_type_value)
    time.sleep(2)

# =========================
# JUISTE TABEL PAKKEN
# =========================
def extract_best_table_from_page():
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")

    tables = soup.find_all("table")
    if not tables:
        return None, None

    best_table = max(tables, key=lambda t: len(t.find_all("tr")))
    rows = best_table.find_all("tr")

    if not rows:
        return None, None

    headers = []
    data = []

    for i, row in enumerate(rows):
        cols = [col.get_text(strip=True) for col in row.find_all(["td", "th"])]

        if i == 0:
            headers = cols
        else:
            if cols:
                data.append(cols)

    if not headers or not data:
        return headers, pd.DataFrame()

    df = pd.DataFrame(data, columns=headers)
    return headers, df

# =========================
# NEXT-KNOP KLIKKEN
# =========================
def click_next_page(previous_table_signature):
    """
    Probeert de zichtbare › knop te klikken.
    Stop als de tabel niet wijzigt.
    """
    try:
        next_buttons = driver.find_elements(By.XPATH, "//a[contains(text(),'›')]")

        visible_next = None
        for btn in next_buttons:
            try:
                if btn.is_displayed():
                    visible_next = btn
                    break
            except:
                pass

        if visible_next is None:
            return False

        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", visible_next)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", visible_next)

        # wacht een beetje
        time.sleep(2)

        # check of tabel veranderd is
        _, new_df = extract_best_table_from_page()
        if new_df is None or new_df.empty:
            return False

        new_signature = tuple(new_df.iloc[0].astype(str).tolist())

        if new_signature == previous_table_signature:
            return False

        return True

    except:
        return False

# =========================
# NUMERIEKE KOLOMMEN
# =========================
def convert_numeric(df):
    df = df.copy()

    for col in df.columns:
        if df[col].dtype == object:
            try:
                # percentages / decimalen zoals .453 of 27,4 of 27.4
                cleaned = (
                    df[col]
                    .astype(str)
                    .str.replace("%", "", regex=False)
                    .str.replace(",", ".", regex=False)
                )

                # alleen converteren als het kan
                converted = pd.to_numeric(cleaned, errors="coerce")

                # alleen overschrijven als niet alles NaN wordt
                if converted.notna().sum() > 0:
                    df[col] = converted
            except:
                pass

    return df

# =========================
# SCRAPING LOOP
# =========================
results = {
    "Averages": [],
    "Advanced Stats": []
}

for stat_type in STAT_TYPES:
    for pos in POSITIONS:
        print(f"\n🚀 {pos} - {stat_type}")

        # Start altijd opnieuw op de hoofdpagina
        driver.get(BASE_URL)
        time.sleep(2)

        # consent soms opnieuw
        try:
            consent_button = driver.find_element(
                By.CSS_SELECTOR, "button.fc-button.fc-cta-consent.fc-primary-button"
            )
            if consent_button.is_displayed():
                consent_button.click()
                time.sleep(1)
        except:
            pass

        apply_filters(pos, stat_type)

        page = 1
        max_pages = MAX_PAGES_PER_POSITION.get(pos, MAX_PAGES_DEFAULT)

        while True:
            print(f"➡️ Pagina {page}")

            headers, df = extract_best_table_from_page()

            if df is None or df.empty:
                print("✅ Stop: geen data meer")
                break

            # metadata toevoegen
            df["Position"] = pos
            df["StatType"] = stat_type

            results[stat_type].append(df)

            # signature eerste rij, om herhaling te detecteren
            first_row_signature = tuple(df.iloc[0].astype(str).tolist())

            # safeguard
            if page >= max_pages:
                print(f"✅ Stop: max pagina's bereikt voor {pos} ({max_pages})")
                break

            moved = click_next_page(first_row_signature)

            if not moved:
                print("✅ Stop: geen volgende unieke pagina")
                break

            page += 1

# =========================
# DATA COMBINEREN
# =========================
avg_df = pd.concat(results["Averages"], ignore_index=True).drop_duplicates()
adv_df = pd.concat(results["Advanced Stats"], ignore_index=True).drop_duplicates()

print(f"\n✅ Averages totaal: {len(avg_df)} rijen")
print(f"✅ Advanced totaal: {len(adv_df)} rijen")

# numeriek maken
avg_df = convert_numeric(avg_df)
adv_df = convert_numeric(adv_df)

# =========================
# MERGEN PER SPELER
# =========================
# Voor nu mergen we op Player + Team + GP
# Als later blijkt dat dit te streng of te los is, kunnen we dit tunen.
merge_keys = ["Player", "Team"]

merged_df = pd.merge(
    avg_df,
    adv_df,
    on=merge_keys,
    suffixes=("_avg", "_adv"),
    how="inner"
).drop_duplicates()

print(f"✅ Merged totaal: {len(merged_df)} rijen")

# =========================
# OPSLAAN IN EXCEL
# =========================
output_file = "basketball_FULL_dataset_2025_2026.xlsx"

with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
    merged_df.to_excel(writer, sheet_name="Merged", index=False)
    avg_df.to_excel(writer, sheet_name="Averages_Raw", index=False)
    adv_df.to_excel(writer, sheet_name="Advanced_Raw", index=False)

print(f"\n✅ Excel opgeslagen als: {output_file}")

driver.quit()