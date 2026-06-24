from .telegram_link import get_public_telegram_bot_link


def footer_telegram_bot(request):
    """Active Telegram bot link from app_integration for site footer (base.html)."""
    try:
        company_id = None
        if request.user.is_authenticated:
            cabinet = getattr(request.user, 'cabinet', None)
            if cabinet and cabinet.company_id:
                company_id = cabinet.company_id
        return {
            'footer_telegram_bot': get_public_telegram_bot_link(company_id=company_id),
        }
    except Exception:
        return {
            'footer_telegram_bot': None,
        }
