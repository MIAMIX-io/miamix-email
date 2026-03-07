import os
import smtplib
import requests
from email.message import EmailMessage
from email.utils import formataddr
from jinja2 import Environment, FileSystemLoader

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

def log(msg):
    print(msg, flush=True)

def notion_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

def main():
    log("🚀 SCRIPT INITIALIZING")

    NOTION_TOKEN = os.getenv("NOTION_TOKEN")
    DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
    EMAIL_USER = os.getenv("EMAIL_USER")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

    if not all([NOTION_TOKEN, DATABASE_ID, EMAIL_USER, EMAIL_PASSWORD]):
        raise RuntimeError("❌ Missing required environment variables")

    # --- Query Notion (RAW API) ---
    log("🔍 Querying Notion database")

    # UPDATED: Matches your exact Notion 'Status' column setting it to "Send Email"
    query_payload = {
        "filter": {
            "property": "Status",
            "status": {"equals": "Send Email"}
        }
    }

    res = requests.post(
        f"{NOTION_API}/databases/{DATABASE_ID}/query",
        headers=notion_headers(NOTION_TOKEN),
        json=query_payload,
        timeout=30
    )

    if not res.ok:
        raise RuntimeError(f"❌ Notion query failed: {res.text}")

    pages = res.json().get("results", [])
    log(f"📬 Found {len(pages)} contacts to email")

    if not pages:
        return

    # --- Email setup ---
    log("🔐 Connecting to Gmail SMTP")
    smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    smtp.login(EMAIL_USER, EMAIL_PASSWORD)

    env = Environment(loader=FileSystemLoader("emails"))
    template = env.get_template("email_template.html")

    with open("emails/OutreachAppDev-20260307.html", encoding="utf-8") as f:
        outreach_html = f.read()

    for page in pages:
        try:
            props = page["properties"]

            # UPDATED: Fetches from "Contact Name", falls back to "Brand Name" if empty
            contact_name_prop = props.get("Contact Name", {}).get("rich_text", [])
            brand_name_prop = props.get("Brand Name", {}).get("title", [])
            
            if contact_name_prop:
                name = contact_name_prop[0]["plain_text"]
            elif brand_name_prop:
                name = brand_name_prop[0]["plain_text"]
            else:
                name = "Partner"

            # UPDATED: Fetches from your "Contact Email" column
            email = props.get("Contact Email", {}).get("email")
            if not email:
                log(f"⚠ Skipping {name} - No email address found.")
                continue

            log(f"➡ Sending to {name} <{email}>")

            html = template.render(
                newsletter_title="MIAMIX App Beta - Sneak Peek",
                name=name,
                background_color="#F5F5F5",
                brand_color="#E136C4",
                email_content_from_file=outreach_html
            )

            msg = EmailMessage()
            msg["Subject"] = "Exclusive Sneak Peek: Test the New MIAMIX App"
            msg["From"] = formataddr(("MIAMIX", "no-reply@miamix.io"))
            msg["To"] = email
            msg["Reply-To"] = "info@miamix.io"

            msg.set_content(f"Hi {name}, please view this email in HTML format.")
            msg.add_alternative(html, subtype="html")

            smtp.send_message(msg)
            log("✅ Email sent")

            # --- Update Notion ---
            # UPDATED: Changes Status to "Sent" so they don't get emailed twice
            update_payload = {
                "properties": {
                    "Status": {"status": {"name": "Email Sent"}}
                }
            }

            upd = requests.patch(
                f"{NOTION_API}/pages/{page['id']}",
                headers=notion_headers(NOTION_TOKEN),
                json=update_payload,
                timeout=30
            )

            if not upd.ok:
                log(f"⚠ Notion update failed: {upd.text}")
            else:
                log("🔄 Notion Status updated to 'Sent'")

        except Exception as e:
            log(f"❌ ROW ERROR: {e}")

    smtp.quit()
    log("🏁 SCRIPT COMPLETE")

if __name__ == "__main__":
    main()
