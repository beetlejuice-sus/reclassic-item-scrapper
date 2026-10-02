import os
import re
import json
import requests
import urllib.parse
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
DEAL_THRESHOLD = 0.85 
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTwRbfWdvjKN_60Y5biQ5rJR0hEw5jc4eYAG9tty_niP1RrmHv4NQV1wsR7tYT4aeACX19W0zgjFXMY/pub?output=csv" # published items CSV link
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")
STATE_FILE = "state.json"

def clean_number(text):
    cleaned = re.sub(r'[^\d]', '', text)
    return int(cleaned) if cleaned else 0

def get_items():
    items = []
    try:
        resp = requests.get(GOOGLE_SHEET_URL, timeout=10)
        resp.raise_for_status()
        for line in resp.text.splitlines():
            first_col = line.split(',')[0].strip()
            if first_col.isdigit():
                items.append(int(first_col))
    except Exception as e:
        print(f"Error reading Google Sheet: {e}")
    return items

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)

def main():
    if not DISCORD_WEBHOOK_URL:
        print("No Webhook URL found in environment variables!")
        return

    items = get_items()
    if not items:
        print("No items found in Google Sheet.")
        return

    state = load_state()
    active_items = []
    any_alert_triggered = False
    
    with requests.Session() as session:
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        })
        
        for item_id in items:
            item_id_str = str(item_id)
            url_page = f"https://reclassic.com.br/?to=veritem&id={item_id}"
            url_api = f"https://reclassic.com.br/api/item-price-history.php?id={item_id}&period=30d"
            
            try:
                # 1. Scrape Current Market Prices
                page_resp = session.get(url_page, timeout=10)
                soup = BeautifulSoup(page_resp.text, 'html.parser')
                
                item_name = f"Item {item_id}"
                title_tag = soup.find('title')
                if title_tag:
                    item_name = title_tag.text.replace(" | ReClassic", "").strip()

                cash_price, zeny_price = 0, 0
                venda_section = soup.find(lambda tag: tag.name == "h3" and "À Venda Agora" in tag.text)
                if venda_section and venda_section.find_next_sibling("div"):
                    for card in venda_section.find_next_sibling("div").find_all(class_="onsale-card"):
                        lbl = card.find(class_="onsale-label")
                        prc = card.find(class_="onsale-price")
                        if lbl and prc:
                            if "cash" in lbl.text.lower(): cash_price = clean_number(prc.text)
                            elif "zeny" in lbl.text.lower(): zeny_price = clean_number(prc.text)

                # 2. Extract Average and Last Sold (HTML First, API as Fallback)
                avg_30d = 0
                last_sold = 0
                
                # Attempt to pull directly from the HTML IDs you found
                stat_avg_tag = soup.find(id="stat-avg")
                if stat_avg_tag:
                    avg_30d = clean_number(stat_avg_tag.text)
                    
                stat_last_tag = soup.find(id="stat-last-price")
                if stat_last_tag:
                    last_sold = clean_number(stat_last_tag.text)
                
                # Fallback to API if HTML was empty (e.g. if loaded via javascript later)
                if avg_30d == 0 or last_sold == 0:
                    try:
                        api_resp = session.get(url_api, timeout=10)
                        data = api_resp.json()
                        if data.get("success"):
                            stats = data.get("stats", {})
                            if avg_30d == 0 and "avg_price" in stats and stats["avg_price"]:
                                avg_30d = int(float(stats["avg_price"]))
                            if last_sold == 0:
                                if "last_price" in stats and stats["last_price"]: 
                                    last_sold = int(float(stats["last_price"]))
                                elif "latest_price" in stats and stats["latest_price"]: 
                                    last_sold = int(float(stats["latest_price"]))
                                elif "history" in data and isinstance(data["history"], list) and len(data["history"]) > 0:
                                    last_entry = data["history"][-1]
                                    if isinstance(last_entry, dict) and "price" in last_entry:
                                        last_sold = int(float(last_entry["price"]))
                    except Exception:
                        pass

                # 3. Stateful Evaluation
                item_changes = []
                item_triggered_alert = False
                price_increased = False

                if item_id_str not in state:
                    state[item_id_str] = {"cash": cash_price, "zeny": zeny_price}
                    if cash_price > 0 or zeny_price > 0:
                        item_triggered_alert = True
                        item_changes.append("✨ Initial listing detected")
                else:
                    prev = state[item_id_str]
                    
                    # Cash tracking
                    if cash_price > 0:
                        if prev.get("cash", 0) == 0:
                            item_triggered_alert = True
                            item_changes.append("🆕 **New Cash listing!**")
                        elif cash_price < prev.get("cash", 0):
                            item_triggered_alert = True
                            item_changes.append(f"📉 **Cash Drop:** ~~{prev['cash']:,}~~ ➔ **{cash_price:,} Cash**")
                        elif cash_price > prev.get("cash", 0):
                            price_increased = True
                            item_changes.append(f"🔺 **Cash Up:** ~~{prev['cash']:,}~~ ➔ **{cash_price:,} Cash**")
                            
                    # Zeny tracking
                    if zeny_price > 0:
                        if prev.get("zeny", 0) == 0:
                            item_triggered_alert = True
                            item_changes.append("🆕 **New Zeny listing!**")
                        elif zeny_price < prev.get("zeny", 0):
                            item_triggered_alert = True
                            item_changes.append(f"📉 **Zeny Drop:** ~~{prev['zeny']:,}z~~ ➔ **{zeny_price:,}z**")
                        elif zeny_price > prev.get("zeny", 0):
                            price_increased = True
                            item_changes.append(f"🔺 **Zeny Up:** ~~{prev['zeny']:,}z~~ ➔ **{zeny_price:,}z**")
                            
                    # Super Deal tracking (Now accurately compares Cash price vs Cash Average)
                    if cash_price > 0 and avg_30d > 0 and cash_price <= (avg_30d * DEAL_THRESHOLD):
                        item_triggered_alert = True
                        item_changes.append("🔥 **Super Deal!** (Cash under 85% of 30d avg)")

                    state[item_id_str] = {"cash": cash_price, "zeny": zeny_price}

                if item_triggered_alert:
                    any_alert_triggered = True

                # Only include in Discord overview if it actually has active listings
                if cash_price > 0 or zeny_price > 0:
                    active_items.append({
                        "id": item_id,
                        "name": item_name,
                        "cash": cash_price,
                        "zeny": zeny_price,
                        "avg_30d": avg_30d,
                        "last_sold": last_sold,
                        "triggered": item_triggered_alert,
                        "increased": price_increased,
                        "changes": item_changes
                    })
                    
            except Exception as e:
                print(f"Failed ID {item_id}: {e}")

    # Always persist updated prices for memory tracking
    save_state(state)

    # 4. Only send if at least one item triggered an actual alert
    if not any_alert_triggered:
        print("No price drops or new listings. Sleeping silently.")
        return

    # Put alerted items at the top (0), increased items middle (1), stable items bottom (2)
    sorted_items = sorted(active_items, key=lambda x: 0 if x["triggered"] else (1 if x["increased"] else 2))
    embed_fields = []

    for item in sorted_items:
        enc_name = urllib.parse.quote_plus(item["name"])
        prices = []
        
        # Format Cash string (with Avg and Last Sold)
        if item["cash"] > 0:
            avg_str = ""
            if item["avg_30d"] > 0 and item["last_sold"] > 0:
                avg_str = f" *(Avg: {item['avg_30d']:,} | Last: {item['last_sold']:,})*"
            elif item["avg_30d"] > 0:
                avg_str = f" *(Avg: {item['avg_30d']:,})*"
            prices.append(f"[**{item['cash']:,} Cash**](https://reclassic.com.br/?to=marketplace&busca={enc_name}){avg_str}")
            
        # Format Zeny string
        if item["zeny"] > 0:
            prices.append(f"[**{item['zeny']:,}z**](https://reclassic.com.br/?to=comercio&busca={enc_name})")

        if item["triggered"]:
            field_name = f"🚨 {item['name']} (ID: {item['id']})"
        elif item["increased"]:
            field_name = f"🔺 {item['name']} (ID: {item['id']})"
        else:
            field_name = f"• {item['name']} (ID: {item['id']})"

        if item["changes"]:
            field_val = " > " + "\n > ".join(item["changes"]) + "\n" + " | ".join(prices)
        else:
            field_val = " | ".join(prices)

        embed_fields.append({
            "name": field_name,
            "value": field_val,
            "inline": False
        })

    # Chunk fields into batches of 25 to respect Discord embed limits
    embed_chunks = [embed_fields[i:i + 25] for i in range(0, len(embed_fields), 25)]
    embeds = []
    for idx, chunk in enumerate(embed_chunks):
        embeds.append({
            "title": "🔥 Market Update & Current Active Offers" if idx == 0 else None,
            "color": 16711680 if idx == 0 else 0x2B2D31,
            "fields": chunk
        })

    payload = {
        "content": "🔥 **Market Alert: Price Drop / New Offer!**",
        "embeds": embeds
    }
    requests.post(DISCORD_WEBHOOK_URL, json=payload)
    print("Discord alert sent with full active offer list!")

if __name__ == "__main__":
    main()
