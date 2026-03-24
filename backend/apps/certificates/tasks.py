"""Certificates Celery task — async PDF generation via WeasyPrint."""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def generate_certificate_pdf(self, certificate_id: str):
    """Generate a PDF certificate and attach a URL to the DB record."""
    try:
        from apps.certificates.models import Certificate
        from services.external.weasyprint_cert import generate_certificate_pdf as _gen_pdf

        cert = Certificate.objects.select_related("user", "course").get(id=certificate_id)
        pdf_path = _gen_pdf(cert)
        logger.info("Certificate PDF generated: %s", pdf_path)
    except Exception as exc:
        logger.exception("generate_certificate_pdf failed: %s", exc)
        raise self.retry(exc=exc)
