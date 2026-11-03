import re
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="NZ Price Compare", page_icon="🔎", layout="wide")
st.title("🔎 Trade Me + Facebook Marketplace price compare")

TM_URL = "https://api.trademe.co.nz/v1/Search/General.json"


def trademe_search(query, price_min, price_max, rows):
    key = st.secrets["TRADEME_KEY"]
    secret = st.secrets["TRADEME_SECRET"]
    headers = {
        "Authorization": (
            f'OAuth oauth_consumer_key="{key}", '
            f'oauth_signature_method="PLAINTEXT", '
            f'oauth_signature="{secret}&"'
        )
    }
    params = {"search_string": query, "rows": rows}
    if price_min:
        params["price_min"] = price_min
    if price_max:
        params["price_max"] = price_max
    r = requests.get(TM_URL, headers=headers, params=params, timeout=20)
    r.raise_for_status()
    out = []
    for item in r.json().get("List", []):
        price = item.get("BuyNowPrice") or item.get("StartPrice")
        out.append(
            {
                "Source": "Trade Me",
                "Title": item.get("Title"),
                "Price": price,
                "Location": item.get("Region") or item.get("Suburb") or "",
                "Link": f"https://www.trademe.co.nz/a/listing/{item.get('ListingId')}",
            }
        )
    return out


def parse_fb_paste(text):
    """Each line like: '$450 Samsung TV 55 inch - Albany'. Takes first $ amount as price."""
    out = []
    for line in text.splitlines():
        m = re.search(r"\$\s?([\d,]+(?:\.\d+)?)", line)
        if not m:
            continue
        price = float(m.group(1).replace(",", ""))
        title = re.sub(r"\$\s?[\d,]+(?:\.\d+)?", "", line).strip(" -–|")
        out.append(
            {
                "Source": "Facebook",
                "Title": title or "(no title)",
                "Price": price,
                "Location": "",
                "Link": "",
            }
        )
    return out


with st.sidebar:
    st.header("Search")
    query = st.text_input("What are you looking for?", placeholder="e.g. Nintendo Switch")
    c1, c2 = st.columns(2)
    price_min = c1.number_input("Min $", min_value=0, value=0, step=10)
    price_max = c2.number_input("Max $", min_value=0, value=0, step=10)
    rows = st.slider("Trade Me results", 10, 100, 50, step=10)
    go = st.button("Search", type="primary", use_container_width=True)

if not query:
    st.info("Enter what you want in the sidebar and tap Search.")
    st.stop()

# Facebook link
fb_url = f"https://www.facebook.com/marketplace/auckland/search?query={quote(query)}"
if price_min:
    fb_url += f"&minPrice={price_min}"
if price_max:
    fb_url += f"&maxPrice={price_max}"

st.subheader("1. Facebook Marketplace")
st.link_button("Open this search on Facebook Marketplace", fb_url)
st.caption(
    "Facebook doesn't allow automated scraping, so copy the listings you want "
    "to compare and paste them here, one per line, with the price (e.g. '$450 Samsung TV - Albany')."
)
fb_text = st.text_area("Paste Facebook listings", height=150)

rows_out = []
if go or query:
    st.subheader("2. Trade Me")
    try:
        tm = trademe_search(query, price_min, price_max, rows)
        rows_out += tm
        st.write(f"Found {len(tm)} Trade Me listings.")
    except KeyError:
        st.error("Trade Me keys not set yet. See the setup steps for adding TRADEME_KEY and TRADEME_SECRET.")
    except Exception as e:
        st.error(f"Trade Me search failed: {e}")

rows_out += parse_fb_paste(fb_text)

if rows_out:
    df = pd.DataFrame(rows_out).dropna(subset=["Price"])
    df = df[df["Price"] > 0].sort_values("Price")

    st.subheader("3. Price comparison")
    summary = (
        df.groupby("Source")["Price"]
        .agg(Listings="count", Lowest="min", Median="median", Average="mean", Highest="max")
        .round(0)
    )
    st.dataframe(summary, use_container_width=True)
    st.bar_chart(summary[["Lowest", "Median", "Highest"]])

    st.subheader("All listings (cheapest first)")
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Price": st.column_config.NumberColumn(format="$%.0f"),
            "Link": st.column_config.LinkColumn("Link", display_text="Open"),
        },
    )
    st.download_button("Download CSV", df.to_csv(index=False), "price_compare.csv", "text/csv")
