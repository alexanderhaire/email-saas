import imaplib
import email
from email.header import decode_header
import logging
from .config import IMAP_SERVER
from .database import SessionLocal, Email
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

def connect_to_email(user_email: str, token: str, imap_server: str = IMAP_SERVER):
    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(user_email, token)
        logger.info("Connected to email account: %s", user_email)
        return mail
    except Exception as e:
        logger.exception("Failed to connect to email for %s", user_email)
        raise e

def extract_email_body(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition"))
            if content_type == "text/plain" and "attachment" not in disposition:
                try:
                    return part.get_payload(decode=True).decode("utf-8", errors="ignore")
                except Exception:
                    continue
    else:
        try:
            return msg.get_payload(decode=True).decode("utf-8", errors="ignore")
        except Exception:
            return ""
    return ""

def fetch_emails(user_email: str, token: str, folder="INBOX"):
    try:
        mail = connect_to_email(user_email, token)
        mail.select(folder)
        result, data = mail.search(None, "ALL")
        email_ids = data[0].split()
        emails = []
        for e_id in email_ids:
            result, msg_data = mail.fetch(e_id, "(RFC822)")
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            subject_parts = decode_header(msg.get("Subject", "No Subject"))
            subject = ""
            for part, encoding in subject_parts:
                if isinstance(part, bytes):
                    subject += part.decode(encoding if encoding else "utf-8", errors="ignore")
                else:
                    subject += part
            body = extract_email_body(msg)
            emails.append({
                "email_id": e_id.decode() if isinstance(e_id, bytes) else str(e_id),
                "subject": subject,
                "body": body,
            })
        logger.info("Fetched %d emails for %s", len(emails), user_email)
        return emails
    except Exception as e:
        logger.exception("Error fetching emails for %s", user_email)
        raise e

def archive_email(user_email: str, token: str, email_uid: str, folder="Archive"):
    try:
        mail = connect_to_email(user_email, token)
        mail.select("INBOX")
        mail.copy(email_uid, folder)
        mail.store(email_uid, "+FLAGS", "\\Deleted")
        mail.expunge()
        logger.info("Archived email %s for %s", email_uid, user_email)
    except Exception as e:
        logger.exception("Error archiving email %s for %s", email_uid, user_email)
        raise e

def update_email_metrics(db: Session, user_email: str, email_data: dict, is_read: bool, reading_duration: float):
    try:
        record = db.query(Email).filter(Email.email_id == email_data["email_id"]).first()
        if not record:
            record = Email(
                user_email=user_email,
                email_id=email_data["email_id"],
                subject=email_data["subject"],
                body=email_data["body"],
                is_read=is_read,
                reading_duration=reading_duration
            )
            db.add(record)
        else:
            record.is_read = is_read
            record.reading_duration = reading_duration
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("Error updating email metrics for %s", email_data["email_id"])
        raise e
