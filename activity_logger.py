
import db_models
from sqlalchemy.orm import Session


def log_activity(
    db: Session,
    user_id: int,
    document_id: int,
    filename: str,
    action: str,
    status: str
):

    activity = db_models.ProcessingActivity(
        user_id=user_id,
        document_id=document_id,
        filename=filename,
        action=action,
        status=status
    )

    db.add(activity)
    db.commit()

    return activity
