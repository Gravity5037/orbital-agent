import os
import json
import re
import hashlib
import uuid

USERS_DB_PATH = r"C:\Orbital\users\users_db.json"

def load_users_db():
    if not os.path.exists(USERS_DB_PATH):
        os.makedirs(os.path.dirname(USERS_DB_PATH), exist_ok=True)
        default_db = {
            "users": {
                "Gravity": {
                    "role": "admin",
                    "email": "admin@orbital.local",
                    "phone": "+10000000000",
                    "password_hash": hashlib.sha256("gravity_master_key".encode()).hexdigest(),
                    "email_validated": True,
                    "phone_validated": True,
                    "account_status": "active",
                    "permissions": ["all_access", "hive_override", "remote_inspect"],
                    "bound_hive_devices": ["MASTER-NODE-UUID"]
                }
            },
            "trusted_hive_nodes": ["MASTER-NODE-UUID"]
        }
        with open(USERS_DB_PATH, "w", encoding="utf-8") as f:
            json.dump(default_db, f, indent=4)
        return default_db
    with open(USERS_DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users_db(db):
    with open(USERS_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4)

def mask_email(email):
    if "@" not in email:
        return email
    name, domain = email.split("@", 1)
    if len(name) <= 2:
        masked_name = name[0] + "*"
    else:
        masked_name = name[0] + "*" * (len(name) - 2) + name[-1]
    return f"{masked_name}@{domain}"

def mask_phone(phone):
    digits = re.sub(r"\D", "", phone)
    if len(digits) >= 4:
        return f"+* (***) ***-{digits[-4:]}"
    return "+* (***) ***-****"

def register_user(username, email, phone, password):
    db = load_users_db()
    users = db.get("users", {})
    
    # Check uniqueness
    for u, data in users.items():
        if u.lower() == username.lower():
            return False, "Username already registered."
        if data.get("email", "").lower() == email.lower():
            return False, "Email already registered."
        if data.get("phone") == phone:
            return False, "Phone number already registered."

    pass_hash = hashlib.sha256(password.encode()).hexdigest()
    email_token = str(uuid.uuid4())[:8]
    phone_code = str(uuid.uuid4())[:6].upper()

    users[username] = {
        "role": "user",
        "email": email,
        "phone": phone,
        "password_hash": pass_hash,
        "email_validated": False,
        "phone_validated": False,
        "email_token": email_token,
        "phone_code": phone_code,
        "account_status": "pending_verification",
        "permissions": ["isolated_workspace"],
        "bound_hive_devices": []
    }
    db["users"] = users
    save_users_db(db)
    
    print(f"[📡 VALIDATION LINK SENT] Email to {mask_email(email)} | Link Token: {email_token}")
    print(f"[📱 VALIDATION CODE SENT] SMS to {mask_phone(phone)} | Code: {phone_code}")
    return True, f"Validation link sent to {mask_email(email)} and code texted to {mask_phone(phone)}."

def validate_user_account(username_or_email, email_token, phone_code):
    db = load_users_db()
    users = db.get("users", {})
    
    target_user = None
    target_data = None
    for u, data in users.items():
        if u.lower() == username_or_email.lower() or data.get("email", "").lower() == username_or_email.lower():
            target_user = u
            target_data = data
            break

    if not target_user:
        return False, "User account not found."

    if target_data.get("email_token") == email_token:
        target_data["email_validated"] = True
    if target_data.get("phone_code") == phone_code:
        target_data["phone_validated"] = True

    if target_data["email_validated"] and target_data["phone_validated"]:
        target_data["account_status"] = "active"
        save_users_db(db)
        return True, "Account fully validated & activated!"
    
    save_users_db(db)
    return False, "Partial validation complete. Both Email link and SMS code are required."

def authenticate_user(identifier, password):
    db = load_users_db()
    users = db.get("users", {})
    pass_hash = hashlib.sha256(password.encode()).hexdigest()

    for u, data in users.items():
        # Match by Username, Email, OR Phone Number
        if identifier.lower() in [u.lower(), data.get("email", "").lower(), data.get("phone", "")]:
            if data.get("password_hash") == pass_hash:
                if data.get("account_status") == "pending_verification":
                    return False, "Account pending verification. Please validate Email & Phone first.", None
                if data.get("account_status") == "blocked":
                    return False, "Account has been suspended by Admin Governance.", None
                return True, "Authentication Successful", {
                    "username": u,
                    "role": data.get("role"),
                    "data": data
                }
    return False, "Invalid Credentials", None

def handle_forgot_password(identifier):
    db = load_users_db()
    users = db.get("users", {})

    for u, data in users.items():
        if identifier.lower() in [u.lower(), data.get("email", "").lower(), data.get("phone", "")]:
            m_email = mask_email(data.get("email", ""))
            m_phone = mask_phone(data.get("phone", ""))
            print(f"[🔒 PASSWORD RESET LINK DISPATCHED] Link sent to {m_email} and SMS sent to {m_phone}")
            return True, f"An Email was sent to {m_email} and SMS sent to {m_phone}. Check your inbox."

    # Privacy-preserving generic response
    return True, "If an account matches that identifier, password reset instructions have been sent."
