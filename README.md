# 🎯 ReClassic Market Sniper

An automated, serverless Discord bot that monitors the ReClassic marketplace for new listings and price drops. 

This bot runs entirely in the cloud using GitHub Actions (zero server costs) and is controlled by a simple Google Sheet, allowing anyone in the guild to manage the snipe list without needing to touch the code.

---

## ⚡ Features
* **Lightning Fast:** Pings the market exactly every 5 minutes using a dedicated API trigger.
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

*(Note: When you add a brand new item to the sheet, the bot will immediately send an "✨ Initial listing detected" alert to Discord on its next run to establish the baseline price).*

---

## ⏱️ Why We Use an External Trigger (cron-job.org)

While GitHub Actions has a built-in schedule feature, it acts as a "best-effort" queue. During periods of high platform load, GitHub can delay scheduled runs by 15 to 45 minutes. In a market sniper bot, a 30-minute delay means you lose the deal.

To guarantee an **exact 5-minute interval**, this repository is configured to only run on demand via its API (`workflow_dispatch`). We use a free external service, **cron-job.org**, to send an authenticated API request to GitHub exactly every 5 minutes, bypassing GitHub's queue completely.

---

## 🚀 Setting up the 5-Minute Trigger (cron-job.org)

If you need to set up the external trigger from scratch, follow these steps:

### 1. Generate a GitHub Token
1. Go to **Settings > Developer Settings > Personal access tokens (classic)** on GitHub.
2. Generate a new token. Check the **`workflow`** and **`repo`** scopes.
3. Copy the token (it starts with `ghp_` or `github_pat_`).

### 2. Configure cron-job.org
1. Create a free account on https://cron-job.org.
2. Create a new cron job with the schedule set to **Every 5 minutes**.
3. **URL:** `https://api.github.com/repos/YOUR_USERNAME/YOUR_REPOSITORY/actions/workflows/run.yml/dispatches`
4. **Method:** `POST`
5. **Request Body:** `{"ref": "main"}`
6. **Headers (Crucial):** Add these 4 headers exactly:
   * `Content-Type`: `application/json`
   * `Accept`: `application/vnd.github+json`
   * `Authorization`: `Bearer YOUR_GITHUB_TOKEN` *(Include the word Bearer and a space)*
   * `User-Agent`: `cron-job-bot`

Save the job, and it will run instantly and precisely every 5 minutes.

---

## 🔑 Renewing Your GitHub Token

For security, GitHub Personal Access Tokens (PATs) expire. If your bot suddenly stops updating and sending messages, your token likely expired. When this happens, GitHub returns a `401 Unauthorized` error, which you can see in your cron-job.org history.

**How to fix an expired token:**
1. Go to your GitHub Developer Settings (https://github.com/settings/tokens).
2. Generate a new token with **`workflow`** and **`repo`** permissions. (You can set the expiration up to 1 year).
3. Copy the new token.
4. Log into https://cron-job.org, edit your job, and open the **Headers** tab.
5. Replace the old token in the `Authorization` header with the new one: `Bearer YOUR_NEW_TOKEN`.
6. Save and click "Test Run" to verify it works!
