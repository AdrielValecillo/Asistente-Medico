from sqlalchemy.orm import Session
from .db import models, schemas

def get_user_by_cedula(db: Session, cedula: str):
    return db.query(models.User).filter(models.User.cedula == cedula).first()

def get_reports_by_user_id(db: Session, user_id: int):
    return db.query(models.Report).filter(models.Report.user_id == user_id).all()

def get_report_by_hash_for_user(db: Session, user_id: int, file_hash: str):
    return db.query(models.Report).filter(models.Report.user_id == user_id, models.Report.file_hash == file_hash).first()

def create_user(db: Session, user: schemas.UserCreate):
    db_user = models.User(cedula=user.cedula, full_name=user.full_name)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def create_report_for_user(db: Session, report: schemas.ReportCreate, user_id: int, file_hash: str):
    db_report = models.Report(report_content=report.report_content, user_id=user_id, file_hash=file_hash)
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report

def delete_report_by_id(db: Session, report_id: int):
    db_report = db.query(models.Report).filter(models.Report.id == report_id).first()
    if db_report:
        db.delete(db_report)
        db.commit()
        return True
    return False 