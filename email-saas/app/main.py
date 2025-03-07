import logging
from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from .database import init_db, SessionLocal, Email
from .email_client import fetch_emails, update_email_metrics, archive_email, connect_to_email
from .model import train_model, load_model, predict_email_urgency
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("email-saas")

app = FastAPI(title="Automated Email Relevance Filtering SaaS")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class Credentials(BaseModel):
    email: str
    token: str

class EmailMetrics(BaseModel):
    email_id: str
    is_read: bool
    reading_duration: float

class ProcessEmailsRequest(Credentials):
    pass

@app.on_event("startup")
def startup_event():
    init_db()
    logger.info("Database initialized.")

@app.post("/ingest_emails")
def ingest_emails(creds: Credentials, db: Session = Depends(get_db)):
    try:
        emails_data = fetch_emails(creds.email, creds.token)
        for email_data in emails_data:
            update_email_metrics(db, creds.email, email_data, is_read=False, reading_duration=0.0)
        return {"status": "success", "message": f"Ingested {len(emails_data)} emails."}
    except Exception as e:
        logger.exception("Error ingesting emails for %s", creds.email)
        raise HTTPException(status_code=500, detail="Error ingesting emails.")

@app.post("/update_metrics")
def update_metrics(creds: Credentials, metrics: EmailMetrics, db: Session = Depends(get_db)):
    try:
        record = db.query(Email).filter(Email.email_id == metrics.email_id, Email.user_email == creds.email).first()
        if not record:
            raise HTTPException(status_code=404, detail="Email record not found.")
        record.is_read = metrics.is_read
        record.reading_duration = metrics.reading_duration
        db.commit()
        return {"status": "success", "message": "Metrics updated."}
    except Exception as e:
        logger.exception("Error updating metrics for %s", creds.email)
        raise HTTPException(status_code=500, detail="Error updating metrics.")

@app.post("/train_model")
def train_model_endpoint(creds: Credentials, db: Session = Depends(get_db)):
    try:
        model_data = train_model(db, creds.email)
        if not model_data:
            raise HTTPException(status_code=400, detail="Not enough data to train model.")
        return {"status": "success", "message": "Model trained successfully."}
    except Exception as e:
        logger.exception("Error training model for %s", creds.email)
        raise HTTPException(status_code=500, detail="Error training model.")

@app.post("/process_and_archive")
def process_and_archive(creds: Credentials, db: Session = Depends(get_db)):
    try:
        model_data = load_model(creds.email)
        if not model_data:
            raise HTTPException(status_code=400, detail="Model not found. Train the model first.")
        
        emails_to_process = db.query(Email).filter(Email.user_email == creds.email, Email.is_urgent == None).all()
        if not emails_to_process:
            return {"status": "success", "message": "No new emails to process."}
        
        mail_conn = connect_to_email(creds.email, creds.token)
        for email_record in emails_to_process:
            urgent = predict_email_urgency(
                model_data, 
                email_record.subject, 
                email_record.body, 
                email_record.reading_duration, 
                email_record.is_read
            )
            email_record.is_urgent = urgent
            db.commit()
            if not urgent:
                try:
                    archive_email(creds.email, creds.token, email_record.email_id)
                except Exception as archive_err:
                    logger.exception("Error archiving email %s", email_record.email_id)
        return {"status": "success", "message": "Processed emails and archived non-urgent ones."}
    except Exception as e:
        logger.exception("Error processing emails for %s", creds.email)
        raise HTTPException(status_code=500, detail="Error processing emails.")

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
