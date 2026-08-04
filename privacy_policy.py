from datetime import date

from config import config

_LAST_UPDATED = date.today().isoformat()

PRIVACY_POLICY_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Privacy Policy - {config.STORE_NAME}</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body {{ font-family: -apple-system, Segoe UI, Arial, sans-serif; max-width: 720px; margin: 40px auto; padding: 0 20px; color: #222; line-height: 1.6; }}
  h1 {{ font-size: 1.5em; margin-bottom: 4px; }}
  .updated {{ color: #666; font-size: 0.85em; margin-bottom: 1.5em; }}
  h2 {{ font-size: 1.1em; margin-top: 1.8em; }}
  ul {{ padding-left: 22px; }}
  li {{ margin-bottom: 6px; }}
</style>
</head>
<body>
<h1>Privacy Policy</h1>
<p class="updated">Last updated: {_LAST_UPDATED}</p>

<p>This Privacy Policy explains how {config.STORE_NAME} ("we", "us", "our") collects, uses, and protects your
information when you interact with our WhatsApp ordering assistant ("the Service"). By messaging us on WhatsApp,
you agree to the practices described here.</p>

<h2>1. Information we collect</h2>
<p>When you message us on WhatsApp, we collect and store:</p>
<ul>
  <li><b>Your WhatsApp phone number</b>, used to identify you and reply to your messages.</li>
  <li><b>The content of your messages</b>, including text, voice notes, and photos you send us.</li>
  <li><b>Your name</b>, if you tell us or if it's available from your WhatsApp profile.</li>
  <li><b>Delivery location</b>, only when you explicitly share it via WhatsApp's location-sharing feature.</li>
  <li><b>Order details</b> - items ordered, quantities, prices, delivery/pickup preference, and order status.</li>
</ul>

<h2>2. Voice notes and photos</h2>
<p>If you send a voice note, we transcribe it to text using a third-party speech-to-text service (Groq) so our
assistant can understand your order; the audio is sent to that provider for transcription and is not stored by
us beyond what's needed to process your message. If you send a photo (e.g. of a dish you'd like to order or
identify), it is analyzed by a third-party AI vision service (via OpenRouter) to help match it to a menu item -
photos are used only for that purpose and are not shared for any other reason.</p>

<h2>3. How we use your information</h2>
<p>We use the information above only to:</p>
<ul>
  <li>Respond to your messages and answer questions about our menu.</li>
  <li>Take, confirm, and prepare your food order.</li>
  <li>Calculate delivery fees and coordinate delivery or pickup.</li>
  <li>Send order status updates (e.g. when your order is picked up or delivered).</li>
  <li>Offer to reuse a previously shared delivery address to speed up future orders - you can always decline and
share a new location instead.</li>
  <li>Understand order history and preferences (e.g. frequently ordered items) so we can serve you better.</li>
</ul>
<p>We do not use your information for advertising, and we do not sell your data.</p>

<h2>4. Who we share information with</h2>
<p>We share information only as needed to operate the Service:</p>
<ul>
  <li><b>Our own staff and delivery riders</b>, who see your order details and delivery address to fulfill your order.</li>
  <li><b>Meta / WhatsApp</b>, which transmits messages between you and us as the messaging platform.</li>
  <li><b>OpenRouter</b> (AI text and image processing) and <b>Groq</b> (voice transcription), which process
message content, photos, and voice notes as needed to generate a reply or extract order details.</li>
</ul>
<p>We do not share your information with any other third party, and we never sell your data.</p>

<h2>5. Data retention</h2>
<p>We retain your conversation history and order records for as long as needed to provide the Service, respond to
you, and keep business records (e.g. for accounting). You may ask us to delete your data at any time - see
"Your rights" below.</p>

<h2>6. Your rights</h2>
<p>You can ask us to:</p>
<ul>
  <li>Tell you what information we hold about you.</li>
  <li>Correct inaccurate information (e.g. an outdated delivery address).</li>
  <li>Delete your information, subject to any records we're legally required to keep.</li>
  <li>Stop contacting you - simply block our number on WhatsApp, or tell us to stop.</li>
</ul>
<p>To exercise any of these, contact us using the details below.</p>

<h2>7. Security</h2>
<p>We take reasonable technical and organizational measures to protect your information, including restricting
access to our order-management system to authorized staff only.</p>

<h2>8. Children's privacy</h2>
<p>This Service is intended for adults placing food orders and is not directed at children. We do not knowingly
collect information from children.</p>

<h2>9. Changes to this policy</h2>
<p>We may update this policy from time to time. The "Last updated" date at the top will reflect the most recent
changes. Continued use of the Service after a change means you accept the updated policy.</p>

<h2>10. Contact us</h2>
<p>For questions about this policy or your data, contact {config.STORE_NAME} at
{config.STORE_PHONE or "our restaurant number"}.</p>
</body>
</html>"""
