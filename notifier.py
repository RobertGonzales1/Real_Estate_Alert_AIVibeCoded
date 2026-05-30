import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _format_price(price):
    return f"${price:,.0f}" if price else "N/A"


def _build_html(listings):
    rows = ""
    for L in listings:
        rows += f"""
        <tr style="border-bottom:1px solid #e0e0e0;">
          <td style="padding:12px 8px;">
            <a href="{L['url']}" style="color:#1a73e8;font-weight:600;text-decoration:none;">
              {L['address']}
            </a><br>
            <span style="font-size:12px;color:#666;">{L['source']} &bull; {L.get('search_area','')}</span>
          </td>
          <td style="padding:12px 8px;font-weight:700;color:#2e7d32;white-space:nowrap;">
            {_format_price(L['price'])}
          </td>
          <td style="padding:12px 8px;text-align:center;">{L['beds']} bd</td>
          <td style="padding:12px 8px;text-align:center;">{L['baths']} ba</td>
          <td style="padding:12px 8px;text-align:center;">
            {f"{int(L['sqft']):,} sqft" if L.get('sqft') else "N/A"}
          </td>
        </tr>
        """

    return f"""
    <html><body style="font-family:Arial,sans-serif;color:#333;max-width:900px;margin:auto;padding:20px;">
      <h2 style="color:#1a73e8;">&#127968; {len(listings)} New Condo Listing{'s' if len(listings)!=1 else ''} Found</h2>
      <p style="color:#555;">Matching your criteria: max $250,000 &bull; 2+ bed &bull; 2+ bath &bull; 1,000+ sqft &bull; Condo</p>
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <thead>
          <tr style="background:#f5f5f5;text-align:left;">
            <th style="padding:10px 8px;">Address</th>
            <th style="padding:10px 8px;">Price</th>
            <th style="padding:10px 8px;text-align:center;">Beds</th>
            <th style="padding:10px 8px;text-align:center;">Baths</th>
            <th style="padding:10px 8px;text-align:center;">Sqft</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      <p style="margin-top:24px;font-size:12px;color:#999;">
        Searching Dallas, TX and Las Vegas, NV within 50 miles &bull;
        Sources: Redfin, Zillow
      </p>
    </body></html>
    """


def send_alert_email(to_email, listings, gmail_user, gmail_app_password):
    if not listings:
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🏠 {len(listings)} New Condo Listing{'s' if len(listings)!=1 else ''} — Dallas & Las Vegas"
    msg["From"] = gmail_user
    msg["To"] = to_email

    plain = "\n".join(
        f"{L['address']} | {_format_price(L['price'])} | {L['beds']}bd {L['baths']}ba | {L['url']}"
        for L in listings
    )
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(_build_html(listings), "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_app_password)
        server.sendmail(gmail_user, to_email, msg.as_string())
