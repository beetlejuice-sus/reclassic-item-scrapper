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
    """Reads item IDs from a published Google Sheet CSV (Column A)."""
    items = []
    try:
        resp = requests.get(GOOGLE_SHEET_URL, timeout=10)
        resp.raise_for_status()
        
        # Read the CSV line by line
        for line in resp.text.splitlines():
            # Split by comma and take the first column
            first_col = line.split(',')[0].strip()
            
            # If it's a valid number, add it to our list
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
        except:
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
    embed_fields = []
    trigger_loud_alert = False
    
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
                # 1. Scrape Current Prices & Item Name
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

                # 2. API 30d Average
                avg_30d = 0
                try:
                    api_resp = session.get(url_api, timeout=10)
                    if api_resp.json().get("success"):
                        avg_30d = int(api_resp.json()["stats"]["avg_price"])
                except: 
                    pass

                # 3. Stateful Logic
                item_highlights = []
                item_triggered_alert = False

                if item_id_str not in state:
                    state[item_id_str] = {"cash": cash_price, "zeny": zeny_price}
                    if cash_price > 0 or zeny_price > 0:
                        item_triggered_alert = True
                        item_highlights.append("✨ Initial listing detected")
                else:
                    prev = state[item_id_str]
                    
                    if cash_price > 0 and prev["cash"] == 0:
                        item_triggered_alert = True
                        item_highlights.append("🆕 **New Cash listing!**")
                    elif cash_price > 0 and cash_price < prev["cash"]:
                        item_triggered_alert = True
                        item_highlights.append(f"📉 **Cash Drop:** ~~{prev['cash']:,}~~ ➔ **{cash_price:,} Cash**")
                        
                    if zeny_price > 0 and prev["zeny"] == 0:
                        item_triggered_alert = True
                        item_highlights.append("🆕 **New Zeny listing!**")
                    elif zeny_price > 0 and zeny_price < prev["zeny"]:
                        item_triggered_alert = True
                        item_highlights.append(f"📉 **Zeny Drop:** ~~{prev['zeny']:,}z~~ ➔ **{zeny_price:,}z**")
                        
                    if zeny_price > 0 and avg_30d > 0 and zeny_price <= (avg_30d * DEAL_THRESHOLD):
                        item_triggered_alert = True
                        item_highlights.append(f"🔥 **Super Deal!** (Under 85% of 30d avg)")

                    state[item_id_str] = {"cash": cash_price, "zeny": zeny_price}

                # 4. Format Discord Message (ONLY for items with alerts)
                if item_triggered_alert:
                    trigger_loud_alert = True
                    
                    enc_name = urllib.parse.quote_plus(item_name)
                    prices = []
                    if cash_price > 0: prices.append(f"[**{cash_price:,} Cash**](https://reclassic.com.br/?to=marketplace&busca={enc_name})")
                    if zeny_price > 0: prices.append(f"[**{zeny_price:,}z**](https://reclassic.com.br/?to=comercio&busca={enc_name}) *(Avg: {avg_30d:,}z)*")
                    
                    lines = [" > " + "\n > ".join(item_highlights)]
                    if prices: lines.append(" | ".join(prices))
                    
                    embed_fields.append({
                        "name": f"🚨 {item_name} (ID: {item_id})",
                        "value": "\n".join(lines),
                        "inline": False
                    })
                    
            except Exception as e:
                print(f"Failed ID {item_id}: {e}")

    # Save new state back to the file so GitHub Actions can commit it
    save_state(state)

    # 5. Send Webhook (Only if there are deals)
    if embed_fields:
        payload = {
            "content": "🔥 **Market Alert: Price Drop / New Offer!**",
            "embeds": [{"color": 16711680, "fields": embed_fields}]
        }
        requests.post(DISCORD_WEBHOOK_URL, json=payload)
        print("Discord alert sent (silent)!")
    else:
        print("No new deals or price drops found.")

if __name__ == "__main__":
    main()