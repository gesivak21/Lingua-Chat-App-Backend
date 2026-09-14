import time
import random
from fastapi import HTTPException, APIRouter, Depends
from auth import create_token, get_current_user
from db import get_connection

router = APIRouter()

# ============================================================
# DATABASE SETUP
# ============================================================

def init_db():
    with get_connection() as conn:
        with conn.cursor() as cursor:

            # ---------------- USERS ----------------
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    name TEXT DEFAULT 'Unknown',
                    mobile TEXT UNIQUE NOT NULL,
                    preferred_language TEXT DEFAULT 'en'
                )
            """)

            # ---------------- MESSAGES ----------------
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    sender_mobile TEXT NOT NULL,
                    receiver_mobile TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # ---------------- OTP ----------------
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS otp_store (
                    mobile TEXT PRIMARY KEY,
                    otp TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # ---------------- CONTACTS ----------------
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS contacts (
                    id SERIAL PRIMARY KEY,
                    owner_mobile TEXT NOT NULL,
                    contact_mobile TEXT NOT NULL,
                    contact_name TEXT NOT NULL,
                    UNIQUE(owner_mobile, contact_mobile)
                )
            """)

            # ---------------- BLOCKED USERS ----------------
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS blocked_users (
                    id SERIAL PRIMARY KEY,
                    owner_mobile TEXT NOT NULL,
                    blocked_mobile TEXT NOT NULL,
                    UNIQUE(owner_mobile, blocked_mobile)
                )
            """)

            # ---------------- INDEXES ----------------

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_conversation
                ON messages(sender_mobile, receiver_mobile)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_receiver
                ON messages(receiver_mobile)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_contacts_owner
                ON contacts(owner_mobile)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_blocked_owner
                ON blocked_users(owner_mobile)
            """)

        conn.commit()

    print("PostgreSQL database initialized successfully!")


# ============================================================
# USER FUNCTIONS
# ============================================================

def get_or_create_user(mobile: str, name: str = "Unknown"):
    with get_connection() as conn:
        with conn.cursor() as cursor:

            cursor.execute(
                "SELECT id, name FROM users WHERE mobile = %s",
                (mobile,)
            )

            user = cursor.fetchone()

            if user:
                user_id, current_name = user

                if name and current_name == "Unknown":
                    cursor.execute(
                        "UPDATE users SET name = %s WHERE id = %s",
                        (name, user_id)
                    )

                return user_id

            cursor.execute(
                """
                INSERT INTO users (mobile, name)
                VALUES (%s, %s)
                RETURNING id
                """,
                (mobile, name)
            )

            user_id = cursor.fetchone()[0]

        conn.commit()

    return user_id


def update_user_name(mobile: str, new_name: str):
    with get_connection() as conn:
        with conn.cursor() as cursor:

            cursor.execute(
                """
                UPDATE users
                SET name = %s
                WHERE mobile = %s
                """,
                (new_name, mobile)
            )

            updated = cursor.rowcount > 0

        conn.commit()

    return updated


def get_user_language(mobile: str) -> str:
    with get_connection() as conn:
        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT preferred_language
                FROM users
                WHERE mobile = %s
                """,
                (mobile,)
            )

            row = cursor.fetchone()

    return row[0] if row else "en"


# ============================================================
# MESSAGE FUNCTIONS
# ============================================================

def save_message(
    receiver_mobile: str,
    message: str,
    sender_mobile: str
):
    # Make sure receiver exists
    get_or_create_user(receiver_mobile)

    with get_connection() as conn:
        with conn.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO messages
                (
                    sender_mobile,
                    receiver_mobile,
                    message
                )
                VALUES (%s, %s, %s)
                """,
                (
                    sender_mobile,
                    receiver_mobile,
                    message
                )
            )

        conn.commit()


def get_last_message(mobile: str):
    with get_connection() as conn:
        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT sender_mobile, message
                FROM messages
                WHERE receiver_mobile = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (mobile,)
            )

            result = cursor.fetchone()

    if result:
        return {
            "sender_mobile": result[0],
            "message": result[1]
        }

    return None


def get_all_message(
    receiver_mobile: str,
    sender_mobile: str = None
):
    with get_connection() as conn:
        with conn.cursor() as cursor:

            if sender_mobile:

                # Conversation between two users
                cursor.execute(
                    """
                    SELECT sender_mobile, message
                    FROM messages
                    WHERE
                        (
                            sender_mobile = %s
                            AND receiver_mobile = %s
                        )
                        OR
                        (
                            sender_mobile = %s
                            AND receiver_mobile = %s
                        )
                    ORDER BY id ASC
                    """,
                    (
                        receiver_mobile,
                        sender_mobile,
                        sender_mobile,
                        receiver_mobile
                    )
                )

            else:

                # All messages received by user
                cursor.execute(
                    """
                    SELECT sender_mobile, message
                    FROM messages
                    WHERE receiver_mobile = %s
                    ORDER BY id ASC
                    """,
                    (receiver_mobile,)
                )

            results = cursor.fetchall()

    return [
        {
            "sender_mobile": row[0],
            "message": row[1]
        }
        for row in results
    ]


# ============================================================
# OTP FUNCTIONS
# ============================================================

def save_otp(mobile: str) -> str:

    otp = str(random.randint(100000, 999999))

    with get_connection() as conn:
        with conn.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO otp_store
                    (mobile, otp, created_at)
                VALUES
                    (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (mobile)
                DO UPDATE SET
                    otp = EXCLUDED.otp,
                    created_at = CURRENT_TIMESTAMP
                """,
                (mobile, otp)
            )

        conn.commit()

    return otp


def verify_otp(mobile: str, otp: str) -> bool:

    with get_connection() as conn:
        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT otp, created_at
                FROM otp_store
                WHERE mobile = %s
                """,
                (mobile,)
            )

            row = cursor.fetchone()

    if not row:
        return False

    stored_otp, created_at = row

    # OTP expires after 5 minutes
    age_seconds = time.time() - created_at.timestamp()

    if age_seconds > 300:
        return False

    if stored_otp != otp:
        return False

    # Delete OTP after successful verification
    with get_connection() as conn:
        with conn.cursor() as cursor:

            cursor.execute(
                """
                DELETE FROM otp_store
                WHERE mobile = %s
                """,
                (mobile,)
            )

        conn.commit()

    return True


# ============================================================
# CONTACT FUNCTIONS
# ============================================================

def add_contact(
    owner_mobile: str,
    contact_mobile: str,
    contact_name: str
):

    # Make sure contact exists as a user
    get_or_create_user(contact_mobile, contact_name)

    with get_connection() as conn:
        with conn.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO contacts
                    (
                        owner_mobile,
                        contact_mobile,
                        contact_name
                    )
                VALUES
                    (%s, %s, %s)
                ON CONFLICT (owner_mobile, contact_mobile)
                DO UPDATE SET
                    contact_name = EXCLUDED.contact_name
                """,
                (
                    owner_mobile,
                    contact_mobile,
                    contact_name
                )
            )

        conn.commit()


def get_contacts(owner_mobile: str):

    with get_connection() as conn:
        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT contact_mobile, contact_name
                FROM contacts
                WHERE owner_mobile = %s
                ORDER BY contact_name
                """,
                (owner_mobile,)
            )

            rows = cursor.fetchall()

    return [
        {
            "mobile": row[0],
            "name": row[1]
        }
        for row in rows
    ]


def update_contact_name(
    owner_mobile: str,
    contact_mobile: str,
    new_name: str
):

    with get_connection() as conn:
        with conn.cursor() as cursor:

            cursor.execute(
                """
                UPDATE contacts
                SET contact_name = %s
                WHERE
                    owner_mobile = %s
                    AND contact_mobile = %s
                """,
                (
                    new_name,
                    owner_mobile,
                    contact_mobile
                )
            )

            updated = cursor.rowcount > 0

        conn.commit()

    return updated


def delete_contact(
    owner_mobile: str,
    contact_mobile: str
):

    with get_connection() as conn:
        with conn.cursor() as cursor:

            cursor.execute(
                """
                DELETE FROM contacts
                WHERE
                    owner_mobile = %s
                    AND contact_mobile = %s
                """,
                (
                    owner_mobile,
                    contact_mobile
                )
            )

        conn.commit()


# ============================================================
# UNKNOWN SENDERS
# ============================================================

def get_unknown_senders(my_mobile: str):

    with get_connection() as conn:
        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT DISTINCT sender_mobile
                FROM messages
                WHERE
                    receiver_mobile = %s
                    AND sender_mobile != %s
                    AND sender_mobile NOT IN (
                        SELECT contact_mobile
                        FROM contacts
                        WHERE owner_mobile = %s
                    )
                """,
                (
                    my_mobile,
                    my_mobile,
                    my_mobile
                )
            )

            rows = cursor.fetchall()

    return [row[0] for row in rows]


# ============================================================
# BLOCK FUNCTIONS
# ============================================================

def block_user(
    owner_mobile: str,
    blocked_mobile: str
):

    with get_connection() as conn:
        with conn.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO blocked_users
                    (
                        owner_mobile,
                        blocked_mobile
                    )
                VALUES
                    (%s, %s)
                ON CONFLICT (owner_mobile, blocked_mobile)
                DO NOTHING
                """,
                (
                    owner_mobile,
                    blocked_mobile
                )
            )

        conn.commit()


def is_blocked(
    receiver_mobile: str,
    sender_mobile: str
) -> bool:

    with get_connection() as conn:
        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT 1
                FROM blocked_users
                WHERE
                    owner_mobile = %s
                    AND blocked_mobile = %s
                """,
                (
                    receiver_mobile,
                    sender_mobile
                )
            )

            return cursor.fetchone() is not None


def get_blocked_users(owner_mobile: str):

    with get_connection() as conn:
        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT blocked_mobile
                FROM blocked_users
                WHERE owner_mobile = %s
                """,
                (owner_mobile,)
            )

            rows = cursor.fetchall()

    return [row[0] for row in rows]


def unblock_user(
    owner_mobile: str,
    blocked_mobile: str
):

    with get_connection() as conn:
        with conn.cursor() as cursor:

            cursor.execute(
                """
                DELETE FROM blocked_users
                WHERE
                    owner_mobile = %s
                    AND blocked_mobile = %s
                """,
                (
                    owner_mobile,
                    blocked_mobile
                )
            )

        conn.commit()


# ============================================================
# DELETE CONVERSATION
# ============================================================

def delete_conversation(
    my_mobile: str,
    other_mobile: str
):

    with get_connection() as conn:
        with conn.cursor() as cursor:

            cursor.execute(
                """
                DELETE FROM messages
                WHERE
                    (
                        sender_mobile = %s
                        AND receiver_mobile = %s
                    )
                    OR
                    (
                        sender_mobile = %s
                        AND receiver_mobile = %s
                    )
                """,
                (
                    my_mobile,
                    other_mobile,
                    other_mobile,
                    my_mobile
                )
            )

        conn.commit()


# ============================================================
# FASTAPI ENDPOINTS
# ============================================================

@router.post("/create_data")
def create_data(
    request: dict,
    user_mobile: str = Depends(get_current_user)
):

    mobile = request.get("mobile")
    name = request.get("name") or "Unknown"
    message = request.get("message") or ""

    if not mobile:
        raise HTTPException(
            status_code=400,
            detail="Mobile required"
        )

    user_id = get_or_create_user(mobile, name)

    save_message(
        mobile,
        message,
        user_mobile
    )

    return {
        "status": "success",
        "user_id": user_id,
        "receiver_mobile": mobile,
        "sender_mobile": user_mobile,
        "message": message
    }


@router.post("/update_name")
def update_name(
    request: dict,
    user_mobile: str = Depends(get_current_user)
):

    name = request.get("name")

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Name required"
        )

    updated = update_user_name(
        user_mobile,
        name
    )

    if not updated:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return {
        "status": "success",
        "mobile": user_mobile,
        "name": name
    }


@router.get("/get_contacts")
def get_contacts_endpoint(
    user_mobile: str = Depends(get_current_user)
):

    return {
        "contacts": get_contacts(user_mobile)
    }


@router.post("/add_contact")
def add_contact_endpoint(
    request: dict,
    user_mobile: str = Depends(get_current_user)
):

    contact_mobile = request.get("contact_mobile")
    contact_name = request.get(
        "contact_name",
        "Unknown"
    )

    if not contact_mobile:
        raise HTTPException(
            status_code=400,
            detail="contact_mobile required"
        )

    add_contact(
        user_mobile,
        contact_mobile,
        contact_name
    )

    return {
        "status": "success"
    }


@router.post("/update_contact_name")
def update_contact_name_endpoint(
    request: dict,
    user_mobile: str = Depends(get_current_user)
):

    contact_mobile = request.get("contact_mobile")
    name = request.get("name")

    if not contact_mobile or not name:
        raise HTTPException(
            status_code=400,
            detail="Contact mobile and name required"
        )

    updated = update_contact_name(
        user_mobile,
        contact_mobile,
        name
    )

    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Contact not found"
        )

    return {
        "status": "success"
    }


@router.get("/me")
def get_me(
    user_mobile: str = Depends(get_current_user)
):

    with get_connection() as conn:
        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT name
                FROM users
                WHERE mobile = %s
                """,
                (user_mobile,)
            )

            row = cursor.fetchone()

    return {
        "mobile": user_mobile,
        "name": row[0] if row else "Unknown"
    }


@router.post("/last_message")
def last_message(
    request: dict,
    user_mobile: str = Depends(get_current_user)
):

    message = get_last_message(user_mobile)

    if not message:
        raise HTTPException(
            status_code=404,
            detail="No messages found"
        )

    return {
        "mobile": user_mobile,
        "last_message": message
    }


@router.post("/all_message")
def all_message(
    request: dict,
    user_mobile: str = Depends(get_current_user)
):

    sender_mobile = request.get("sender_mobile")

    messages = get_all_message(
        user_mobile,
        sender_mobile
    )

    return {
        "mobile": user_mobile,
        "messages": messages
    }


@router.post("/delete_conversation")
def delete_conversation_endpoint(
    request: dict,
    user_mobile: str = Depends(get_current_user)
):

    other_mobile = request.get("other_mobile")

    if not other_mobile:
        raise HTTPException(
            status_code=400,
            detail="other_mobile required"
        )

    delete_conversation(
        user_mobile,
        other_mobile
    )

    return {
        "status": "success"
    }


@router.post("/delete_contact")
def delete_contact_endpoint(
    request: dict,
    user_mobile: str = Depends(get_current_user)
):

    contact_mobile = request.get("contact_mobile")

    if not contact_mobile:
        raise HTTPException(
            status_code=400,
            detail="contact_mobile required"
        )

    delete_contact(
        user_mobile,
        contact_mobile
    )

    return {
        "status": "success"
    }


@router.get("/unknown_senders")
def unknown_senders_endpoint(
    user_mobile: str = Depends(get_current_user)
):

    senders = get_unknown_senders(user_mobile)

    return {
        "unknown_senders": senders
    }


@router.post("/set_language")
def set_language(
    request: dict,
    user_mobile: str = Depends(get_current_user)
):

    language = request.get("language", "en")

    with get_connection() as conn:
        with conn.cursor() as cursor:

            cursor.execute(
                """
                UPDATE users
                SET preferred_language = %s
                WHERE mobile = %s
                """,
                (
                    language,
                    user_mobile
                )
            )

        conn.commit()

    return {
        "status": "success",
        "mobile": user_mobile,
        "language": language
    }


# ============================================================
# OTP ENDPOINTS
# ============================================================

@router.post("/send_otp")
def send_otp(request: dict):

    mobile = request.get("mobile")

    if not mobile:
        raise HTTPException(
            status_code=400,
            detail="Mobile required"
        )

    # Make sure user exists
    get_or_create_user(mobile)

    otp = save_otp(mobile)

    # DEMO ONLY
    print(f"[OTP] {mobile} -> {otp}")

    return {
        "status": "OTP sent",
        "mobile": mobile,
        "otp":otp
    }


@router.post("/verify_otp")
def verify_otp_endpoint(request: dict):

    mobile = request.get("mobile")
    otp = request.get("otp")

    if not mobile or not otp:
        raise HTTPException(
            status_code=400,
            detail="Mobile and OTP required"
        )

    if not verify_otp(mobile, otp):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired OTP"
        )

    token = create_token(mobile)

    return {
        "status": "verified",
        "token": token
    }


@router.post("/get_language")
def get_language(
    user_mobile: str = Depends(get_current_user)
):

    language = get_user_language(user_mobile)

    return {
        "mobile": user_mobile,
        "language": language
    }


# ============================================================
# BLOCK ENDPOINTS
# ============================================================

@router.post("/block_user")
def block_user_endpoint(
    request: dict,
    user_mobile: str = Depends(get_current_user)
):

    other_mobile = request.get("other_mobile")

    if not other_mobile:
        raise HTTPException(
            status_code=400,
            detail="other_mobile required"
        )

    block_user(
        user_mobile,
        other_mobile
    )

    # Delete conversation after blocking
    delete_conversation(
        user_mobile,
        other_mobile
    )

    return {
        "status": "blocked"
    }


@router.get("/blocked_users")
def blocked_users_endpoint(
    user_mobile: str = Depends(get_current_user)
):

    return {
        "blocked": get_blocked_users(user_mobile)
    }


@router.post("/unblock_user")
def unblock_user_endpoint(
    request: dict,
    user_mobile: str = Depends(get_current_user)
):

    mobile = request.get("mobile")

    if not mobile:
        raise HTTPException(
            status_code=400,
            detail="mobile required"
        )

    unblock_user(
        user_mobile,
        mobile
    )

    return {
        "status": "unblocked"
    }


# ============================================================
# INITIALIZE DATABASE
# ============================================================

init_db()