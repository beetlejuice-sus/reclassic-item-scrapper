# 🎯 ReClassic Market Sniper

An automated, serverless Discord bot that monitors the ReClassic marketplace for new listings and price drops. 

This bot runs entirely in the cloud using GitHub Actions (zero server costs) and is controlled by a simple Google Sheet, allowing anyone in the guild to manage the snipe list without needing to touch the code.

---

## ⚡ Features
* **24/7 Monitoring:** Automatically checks the market every 5 minutes.
* **Stateful Tracking:** Remembers previous prices to detect exact price drops and new undercuts.
* **Smart Alerts:** Only pings Discord when an item is newly listed, drops in price, or falls below 85% of its 30-day average.
* **Guild-Friendly UI:** Controlled entirely via a shared Google Sheet.

---

## 📝 How to Add or Remove Items

You do not need to edit the code to change what the bot is looking for. The bot reads directly from a published Google Sheet.

**To update the list:**
1. Open the shared Google Sheet.
2. Add your items using this exact format:
   * **Column A (Required):** The exact Item ID number (e.g., `40004`).
   * **Column B (Optional):** The Item Name (e.g., `Orbe do Abismo III`). The bot completely ignores Column B, so you can type whatever you want here just to help humans remember what the ID means!
3. **You're done!** Close the sheet. 

Google automatically updates the background data, and the bot will start tracking your new items on its next 5-minute cycle.

*(Note: When you add a brand new item to the sheet, the bot will immediately send an "Initial listing detected" alert to Discord on its next run to establish the baseline price).*

---

## 🛠️ How it Works (Under the Hood)

1. **The Trigger:** A GitHub Actions cron job wakes up every 5 minutes (`.github/workflows/run.yml`).
2. **The Fetch:** The script (`sniper.py`) downloads the latest item list from the Google Sheet CSV.
3. **The Scrape:** It checks the ReClassic website and API for current Cash/Zeny prices and the 30-day average.
4. **The Comparison:** It compares the current prices against its memory file (`state.json`).
5. **The Alert:** If a deal is found, it securely pulls the Discord Webhook URL from GitHub Secrets and sends the alert.
6. **The Memory:** It saves the new prices to `state.json` and pushes the updated file back to this repository so it's ready for the next run.
