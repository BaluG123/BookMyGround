# PythonAnywhere Env Setup

Create a `.env` file in your project root on PythonAnywhere.

Path example:

```bash
/home/yourusername/BookMyGround/.env
```

Add:

```env
DEBUG=False
ALLOWED_HOSTS=yourusername.pythonanywhere.com
CORS_ALLOWED_ORIGINS=https://your-react-native-web-domain.com
CSRF_TRUSTED_ORIGINS=https://yourusername.pythonanywhere.com

FIREBASE_CREDENTIALS=/home/yourusername/BookMyGround/firebase-admin.json

RAZORPAY_KEY_ID=rzp_test_xxxxx
RAZORPAY_KEY_SECRET=your_razorpay_secret
RAZORPAY_WEBHOOK_SECRET=your_razorpay_webhook_secret
```

Then:

1. Upload your Firebase Admin SDK JSON file to:
   `/home/yourusername/BookMyGround/firebase-admin.json`
2. Pull latest code.
3. Activate venv.
4. Run:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

5. Reload the PythonAnywhere web app.

Razorpay dashboard values:

- `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`: Developers -> API Keys
- `RAZORPAY_WEBHOOK_SECRET`: Webhooks -> create webhook -> set same secret here

Webhook URL to add in Razorpay:

```text
https://yourusername.pythonanywhere.com/api/v1/bookings/razorpay/webhook/
```
