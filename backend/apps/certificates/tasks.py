"""Certificates — Background task: async PDF generation via WeasyPrint."""
import logging
import time

logger = logging.getLogger(__name__)


def generate_certificate_pdf(certificate_id: str):
    """Generate a PDF certificate and attach a URL to the DB record."""
    MAX_RETRIES = 2
    RETRY_DELAY = 30

    for attempt in range(MAX_RETRIES):
        try:
            from apps.certificates.models import Certificate
            from services.external.weasyprint_cert import generate_certificate_pdf as _gen_pdf

            cert = Certificate.objects.select_related("user", "course").get(id=certificate_id)
            pdf_path = _gen_pdf(cert)
            logger.info("Certificate PDF generated: %s", pdf_path)
            break  # Success
        except Exception as exc:
            if attempt == MAX_RETRIES - 1:
                logger.exception("generate_certificate_pdf failed after %d retries: %s", MAX_RETRIES, exc)
                raise
            logger.warning("generate_certificate_pdf attempt %d failed, retrying in %ds: %s", attempt + 1, RETRY_DELAY, exc)
            time.sleep(RETRY_DELAY)
