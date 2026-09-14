# Lingua — Language-Aware Chat App

Lingua is a real-time chat application designed to let people communicate across languages. Messages are delivered through a FastAPI WebSocket backend and translated into the receiver's preferred language before being pushed to an online recipient.

## Features

- Mobile-number login with demo OTP verification.
- JWT-based authentication for protected API requests and WebSocket connections.
- Real-time messaging over WebSockets.
- Automatic language detection and translation with `googletrans`.
- Per-user preferred-language selection.
- Contact management: add, edit, list, and delete contacts.
- Unknown-sender handling with options to add or block a sender.
- Block/unblock users.
- Conversation history and conversation deletion.
- Light/dark frontend theme.
- PostgreSQL persistence.
- GZip response compression and CORS middleware in the API.

## Architecture

```text
lingua-chatapp/
├── backend/
│   ├── auth.py
│   ├── database.py
│   ├── db.py
│   ├── main.py
│   ├── translate.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   └── index.html
├── .gitignore
└── README.md
```

### Backend

The backend uses FastAPI. `main.py` exposes the `/ws` WebSocket endpoint and mounts the database and translation routers. The server defaults to port `8080` when `PORT` is not set.

The WebSocket flow is:

1. Client connects to `/ws?token=<JWT>`.
2. The token is validated and the user's mobile number identifies the connection.
3. Incoming messages contain `receiver` and `message`.
4. Blocked recipients are rejected.
5. The original message is stored in PostgreSQL.
6. If the recipient is online, their preferred language is loaded and the message is translated before delivery.

### Frontend

The frontend is a single `index.html` application. It currently calls the backend at `http://127.0.0.1:8000` and opens a WebSocket at `ws://127.0.0.1:8000/ws`.

For deployment, change those hard-coded development URLs to your deployed API/WebSocket origin. For HTTPS deployments, use `wss://` for the WebSocket connection.

## Database

The application uses PostgreSQL through `psycopg`. The database layer creates these tables automatically:

- `users`
- `messages`
- `otp_store`
- `contacts`
- `blocked_users`

It also creates indexes for conversation, receiver, contacts, and blocked-user lookups.

The application can connect using `DATABASE_URL`. If that variable is not set, `db.py` falls back to PostgreSQL connection parameters and a Cloud SQL Unix socket using `INSTANCE_CONNECTION_NAME`.

## Authentication

The application uses JWTs signed with `JWT_SECRET` and the HS256 algorithm. Tokens expire after 7 days.

The OTP flow is:

```text
POST /database/send_otp
        ↓
POST /database/verify_otp
        ↓
JWT returned
        ↓
Authenticated REST requests + WebSocket connection
```

> **Demo limitation:** OTPs are currently generated server-side and printed to the backend console rather than sent through an SMS provider. Do not use this OTP implementation as-is for production authentication.

## API Overview

### Health check

```text
GET /api_checker
```

Returns `API Test Successful` when the API is running.

### Authentication

```text
POST /database/send_otp
POST /database/verify_otp
```

### User and language

```text
GET  /database/me
POST /database/update_name
POST /database/set_language
POST /database/get_language
```

### Contacts and conversations

```text
GET  /database/get_contacts
POST /database/add_contact
POST /database/update_contact_name
POST /database/delete_contact
POST /database/last_message
POST /database/all_message
POST /database/delete_conversation
GET  /database/unknown_senders
```

### Blocking

```text
POST /database/block_user
GET  /database/blocked_users
POST /database/unblock_user
```

### Translation

```text
POST /translate/chat_message_translate
```

The translation endpoint returns the original message, detected language, target language, and translated message.

### WebSocket

```text
/ws?token=<JWT>
```

Client message:

```json
{
  "receiver": "9876543210",
  "message": "Hello!"
}
```

Server delivery to an online recipient follows this shape:

```json
{
  "sender_mobile": "9876543210",
  "message": "<translated message>",
  "type": "new",
  "is_unknown_sender": false
}
```

## Supported UI Languages

The current frontend includes selections for:

- English (`en`)
- Tamil (`ta`)
- Hindi (`hi`)
- French (`fr`)
- German (`de`)
- Arabic (`ar`)
- Spanish (`es`)

Additional languages may be possible through the translation library, but the current UI only exposes the languages listed above.

## Local Development

### 1. Prerequisites

- Python 3.11+
- PostgreSQL
- A modern web browser

### 2. Configure the backend

```bash
cd backend
python -m venv .venv

# macOS/Linux
source .venv/bin/activate

# Windows PowerShell
# .venv\Scripts\Activate.ps1

pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with a valid PostgreSQL connection and a secure `JWT_SECRET`.

### 3. Start the API

```bash
cd backend
python main.py
```

The API listens on `0.0.0.0:8080` by default. If you want to match the current frontend's development configuration, run the API on port `8000` instead:

```bash
PORT=8000 python main.py
```

### 4. Open the frontend

Serve the `frontend` directory with a local static server rather than relying on `file://` URLs:

```bash
cd frontend
python -m http.server 5500
```

Then open `http://127.0.0.1:5500` in your browser.

Because the current frontend is configured for `127.0.0.1:8000`, use the backend on port `8000` for the simplest local setup.

## Docker

Build the backend image:

```bash
cd backend
docker build -t lingua-backend .
```

Run it with your environment file:

```bash
docker run --env-file .env -p 8080:8080 lingua-backend
```

The container exposes port `8080` and starts the FastAPI application with `python main.py`.

## Production Considerations

Before deploying Lingua publicly, address the following:

- Replace demo OTP generation with a real SMS/OTP provider.
- Restrict CORS instead of allowing all origins.
- Use HTTPS and `wss://` for production traffic.
- Store a strong random JWT secret in a secret manager/environment configuration.
- Validate and rate-limit OTP requests and verification attempts.
- Consider a production-grade translation API rather than relying on `googletrans`.
- Add structured logging, monitoring, and error reporting.
- Add database migrations rather than relying only on startup table creation.
- Consider Redis or another shared connection/presence layer if the backend is horizontally scaled; the current WebSocket connection map is process-local.
- Add automated tests for authentication, messaging, translation, contacts, blocking, and database behavior.

## Development Status

This repository is organized from the current Lingua source provided for the project. It is suitable as a development/demo starting point; production hardening is still required.

## License

No license was provided with the source. Add a license before publishing the repository for public reuse.
