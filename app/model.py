import os
import logging
import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer
from sqlalchemy.orm import Session
from .database import Email
from .config import MODEL_STORAGE_DIR

logger = logging.getLogger(__name__)

def get_model_path(user_email: str):
    safe_email = user_email.replace("@", "_at_").replace(".", "_")
    user_dir = os.path.join(MODEL_STORAGE_DIR, safe_email)
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)
    return os.path.join(user_dir, "email_classifier.joblib")

def train_model(db: Session, user_email: str):
    emails = db.query(Email).filter(Email.user_email == user_email).all()
    if not emails:
        logger.info("No emails found for training for %s", user_email)
        return None

    texts = []
    additional_features = []
    labels = []
    duration_threshold = 5.0  # seconds
    for email_obj in emails:
        combined_text = f"{email_obj.subject} {email_obj.body}"
        texts.append(combined_text)
        additional_features.append([email_obj.reading_duration, 1 if email_obj.is_read else 0])
        label = 1 if (email_obj.is_read and email_obj.reading_duration > duration_threshold) else 0
        labels.append(label)
    
    vectorizer = TfidfVectorizer(max_features=1000)
    X_text = vectorizer.fit_transform(texts)
    import scipy
    X_additional = np.array(additional_features)
    X = scipy.sparse.hstack([X_text, X_additional])
    
    clf = LogisticRegression(max_iter=1000)
    clf.fit(X, labels)
    
    model_data = {
        "vectorizer": vectorizer,
        "classifier": clf
    }
    model_path = get_model_path(user_email)
    joblib.dump(model_data, model_path)
    logger.info("Trained and saved model for %s at %s", user_email, model_path)
    return model_data

def load_model(user_email: str):
    model_path = get_model_path(user_email)
    if os.path.exists(model_path):
        return joblib.load(model_path)
    return None

def predict_email_urgency(model_data, subject: str, body: str, reading_duration: float, is_read: bool):
    combined_text = f"{subject} {body}"
    vectorizer = model_data["vectorizer"]
    classifier = model_data["classifier"]
    X_text = vectorizer.transform([combined_text])
    import scipy
    X_additional = np.array([[reading_duration, 1 if is_read else 0]])
    X = scipy.sparse.hstack([X_text, X_additional])
    prediction = classifier.predict(X)
    return bool(prediction[0])
