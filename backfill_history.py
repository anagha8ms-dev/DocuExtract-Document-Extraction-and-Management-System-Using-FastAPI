
from database import SessionLocal
import db_models

db = SessionLocal()

try:
    documents = db.query(db_models.Document).all()

    count = 0

    for doc in documents:

        activities = [
            ("Document Uploaded", "Completed")
        ]

        # Check extracted text
        extracted = db.query(
            db_models.ExtractedData
        ).filter(
            db_models.ExtractedData.document_id == doc.id
        ).first()

        if extracted:
            activities.append(
                ("Text Extracted", "Completed")
            )

        # Check summary
        summary = db.query(
            db_models.Summary
        ).filter(
            db_models.Summary.document_id == doc.id
        ).first()

        if summary:
            activities.append(
                ("Summary Generated", "Completed")
            )

        for action, status in activities:

            # Prevent duplicate entries
            existing = db.query(
                db_models.ProcessingActivity
            ).filter(
                db_models.ProcessingActivity.document_id == doc.id,
                db_models.ProcessingActivity.action == action
            ).first()

            if not existing:

                activity = db_models.ProcessingActivity(
                    user_id=doc.user_id,
                    document_id=doc.id,
                    filename=doc.filename,
                    action=action,
                    status=status
                )

                db.add(activity)
                count += 1

    db.commit()

    print("Processing History updated successfully!")
    print("New activities added:", count)

except Exception as e:
    db.rollback()
    print("Error:", e)

finally:
    db.close()
