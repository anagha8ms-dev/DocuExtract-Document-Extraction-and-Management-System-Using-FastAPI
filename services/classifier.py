
def classify_document(text: str, filename: str = ""):

    if not text or not text.strip():
        return "General"

    text = text.lower()
    filename = filename.lower()

    categories = {

        "Resume": [
            "resume",
            "curriculum vitae",
            "work experience",
            "professional skills",
            "technical skills",
            "education",
            "career objective",
            "professional summary",
            "python developer",
            "full stack developer",
            "projects",
            "certifications",
            "linkedin",
            "github",
            "b.tech",
            "computer science"
        ],

        "Invoice": [
            "invoice",
            "bill number",
            "total amount",
            "payment due",
            "tax",
            "quantity",
            "unit price",
            "invoice date",
            "subtotal"
        ],

        "Certificate": [
            "certificate",
            "certified",
            "successfully completed",
            "awarded to",
            "qualification",
            "certificate of completion",
            "has successfully completed"
        ],

        "Report": [
            "report",
            "introduction",
            "analysis",
            "findings",
            "conclusion",
            "recommendations",
            "executive summary",
            "methodology"
        ]
    }

    combined_text = filename + " " + text

    scores = {}

    for category, keywords in categories.items():

        score = sum(
            1 for word in keywords
            if word in combined_text
        )

        scores[category] = score

    best_category = max(scores, key=scores.get)

    if scores[best_category] < 2:
        return "General"

    return best_category
