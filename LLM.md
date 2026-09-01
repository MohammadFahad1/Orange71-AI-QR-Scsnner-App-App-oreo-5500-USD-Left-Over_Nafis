I'd keep it focused on the business features and user flows like this.

# Orange71 / Amore Rings - Feature & User Flow Overview

## Core Concept

Amore Rings is a private social networking app exclusive to customers who purchase a ring from the Amore Rings WooCommerce website.

Instead of exchanging phone numbers, users exchange QR codes. Scanning another user's QR code starts a private chat inside the app.

---

# Feature 1: Ring Purchase & App Access

### Flow

1. User purchases a ring from the WooCommerce website.
2. User's email is stored in the system.
3. A corresponding account is created (or made available) in the Django backend.
4. User logs into the mobile app using that email.
5. User gains access to app features.

---

# Feature 2: QR Code Identity

Each user has a unique QR code.

### Flow

1. User opens "My QR Code".
2. App displays the user's personal QR.
3. Another app user scans the QR.
4. The scanner is taken directly to a chat with that user.

Purpose:

* Replace exchanging phone numbers.
* Only works between registered app users.

---

# Feature 3: Private Messaging

Users can privately chat after scanning each other's QR code.

### Flow

1. Scan QR.
2. Conversation is created (or existing conversation opens).
3. Users exchange messages.

Current UI shows:

* Conversation list
* Chat screen
* Block / Unblock user

---

# Feature 4: Message Credits

Sending messages requires credits.

Receiving messages is free.

### Flow

1. User has available credits.
2. User sends message.
3. Credit is deducted.
4. Recipient receives message.

If user has no credits:

* Show purchase credits popup.
* User purchases more credits.
* Sending resumes after purchase.

---

# Feature 5: Ring Exchange

Allows customers to exchange their purchased ring.

### Flow

1. User opens Ring Exchange.
2. User enters desired replacement ring size.
3. User pays exchange/shipping fee.
4. User ships original ring to Amore Rings.
5. Company receives ring.
6. Replacement ring is sent.
7. Exchange request is completed.

UI includes:

* Exchange instructions
* Ring size input
* Payment form
* Success screen

---

# Feature 6: Refund

Allows customers to return their ring.

### Flow

1. User opens Refund.
2. User sees refund deadline.
3. User mails original ring.
4. Company receives ring.
5. Refund is processed.

UI currently shows:

* Instructions
* Shipping address
* Return deadline

---

# Feature 7: Brand Ambassador

Users can become brand ambassadors.

### Flow

1. User selects "Become Brand Ambassador."
2. User watches orientation/training video.
3. After completing orientation, ambassador features become available.

---

# Feature 8: Affiliate Links

Brand ambassadors can generate referral links.

### Flow

1. Ambassador generates affiliate link.
2. Link is shared with others.
3. Someone purchases through the link.
4. Referral is tracked.
5. Ambassador earns commission.

UI includes:

* Generate affiliate link
* Share link

---

# Feature 9: Fundraiser QR

Users can generate a fundraiser QR code.

### Flow

1. User creates fundraiser QR.
2. QR is shared.
3. Others scan the QR.
4. QR directs users to the fundraiser/purchase flow.

(Current business logic needs verification.)

---

# Feature 10: QR Sharing

Generated QR codes can be shared outside the app.

### Flow

1. Generate QR.
2. Share via native share sheet.
3. Another user scans it.
4. Desired action is performed (chat or fundraiser).

---

# Feature 11: User Profile

Current screenshots suggest users have:

* Personal QR code
* Ring exchange
* Refund
* Brand ambassador access
* Messaging access

---

# Overall User Journey

```text
Purchase Ring (WooCommerce)
        │
        ▼
Account Created
        │
        ▼
Login to Mobile App
        │
        ▼
Receive Personal QR Code
        │
        ▼
Meet Someone
        │
        ▼
Scan Each Other's QR
        │
        ▼
Private Conversation Starts
        │
        ▼
Purchase Message Credits (when needed)
        │
        ▼
Continue Chatting
```

## Additional Features Available

* Ring Exchange
* Refund Requests
* Brand Ambassador Program
* Affiliate Link Generation
* Fundraiser QR Generation
* QR Sharing
