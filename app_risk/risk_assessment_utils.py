# SecBoard/app_risk/risk_assessment_utils.py
import pytz
import logging
from decimal import Decimal
from django.utils import timezone
from django.utils.translation import gettext as _
from django.db.models import Q

from .models import RiskLevel, AcceptableRisk, AccessRisk

logger = logging.getLogger(__name__)


def get_company_risk_levels_queryset(company_id=None):
    qs = RiskLevel.objects.filter(is_active=True)
    if company_id:
        qs = qs.filter(Q(company__isnull=True) | Q(company_id=company_id))
    else:
        qs = qs.filter(company__isnull=True)
    return qs.order_by('min_value')


def get_acceptable_risk_for_asset(asset, language):
    """
    Get the acceptable risk level for a specific asset based on its company, asset group, asset type, and criticality
    """
    try:
        # Get the asset's criticality level
        criticality_level = None
        if asset.confidentiality and asset.confidentiality.cost >= max(
            asset.integrity.cost if asset.integrity else 0,
            asset.availability.cost if asset.availability else 0
        ):
            criticality_level = asset.confidentiality
        elif asset.integrity and asset.integrity.cost >= max(
            asset.confidentiality.cost if asset.confidentiality else 0,
            asset.availability.cost if asset.availability else 0
        ):
            criticality_level = asset.integrity
        elif asset.availability:
            criticality_level = asset.availability
        
        if not criticality_level:
            return None
        
        # Try to find acceptable risk setting with specific asset type first
        acceptable_risk = AcceptableRisk.objects.filter(
            company=asset.company,
            asset_group=asset.group,
            asset_type=asset.asset_type,
            criticality_level=criticality_level
        ).first()
        
        # If not found, try without asset type (general setting for the group)
        if not acceptable_risk:
            acceptable_risk = AcceptableRisk.objects.filter(
                company=asset.company,
                asset_group=asset.group,
                asset_type__isnull=True,
                criticality_level=criticality_level
            ).first()

        if acceptable_risk:
            return {
                'level_id': acceptable_risk.acceptable_risk_level.id,
                'name': acceptable_risk.get_acceptable_risk_level_name(language),
                'color': acceptable_risk.acceptable_risk_level.color,
                'max_value': acceptable_risk.acceptable_risk_level.max_value
            }

        return None
    except Exception as e:
        logger.error(f"Error getting acceptable risk for asset {asset.id}: {str(e)}")
        return None


def get_localized_criticality(asset, language):
    """Get localized criticality information for an asset"""
    levels = [
        (asset.confidentiality, asset.confidentiality.cost if asset.confidentiality else 0),
        (asset.integrity, asset.integrity.cost if asset.integrity else 0),
        (asset.availability, asset.availability.cost if asset.availability else 0)
    ]
    max_level = max(levels, key=lambda x: x[1])
    if max_level[0]:
        return {
            'name': getattr(max_level[0], f'critical_name_{language}', '') or max_level[0].critical_name_uk,
            'cost': max_level[0].cost,
            'color': max_level[0].color
        }
    return {'name': _("Undefined"), 'cost': 0, 'color': "#000000"}


def calculate_risk_level(value_of_risk, company_id=None):
    """
    Обчислює рівень ризику на основі значення ризику, використовуючи дані з моделі RiskLevel.
    """
    # logger.debug(f"calculate_risk_level - Input value: {value_of_risk}")
    
    # Отримуємо всі активні рівні ризику, відсортовані за мінімальним значенням
    risk_levels = get_company_risk_levels_queryset(company_id)
    logger.debug(f"Found {risk_levels.count()} risk levels in database")

    if value_of_risk == 0:
        absent_level = RiskLevel.get_by_display_name('Невизначено', company_id=company_id)
        if absent_level:
            logger.debug(f"Found undefined level: {absent_level}")
            return absent_level
        logger.debug("Undefined level not found, returning None")
        return None

    for level in risk_levels:
        logger.debug(f"Checking level: {level.get_name()} (min: {level.min_value}, max: {level.max_value})")
        if level.min_value <= value_of_risk <= level.max_value:
            logger.debug(f"Found matching level: {level.get_name()}")
            return level

    if value_of_risk < risk_levels.first().min_value:
        logger.debug(f"Value {value_of_risk} below minimum, returning first level: {risk_levels.first().get_name()}")
        return risk_levels.first()
    elif value_of_risk > risk_levels.last().max_value:
        logger.debug(f"Value {value_of_risk} above maximum, returning last level: {risk_levels.last().get_name()}")
        return risk_levels.last()
    else:
        closest_level = min(risk_levels, key=lambda x: min(abs(x.min_value - value_of_risk), abs(x.max_value - value_of_risk)))
        logger.debug(f"Value {value_of_risk} not in range, returning closest level: {closest_level.get_name()}")
        return closest_level


def get_risk_level_name(risk_level, language):
    """Get localized name for a risk level"""
    if isinstance(risk_level, RiskLevel):
        return risk_level.get_name_by_language(language) or risk_level.get_name() or risk_level.name or _("Unnamed")
    return _("Undefined")


def calculate_value_of_risk(asset, vulnerability):
    """Calculate the value of risk for an asset-vulnerability combination"""
    criticality = asset.get_criticality()
    criticality_cost = criticality['cost']  # Get the cost from the criticality dict

    # Debug logging
    logger.debug(f"calculate_value_of_risk - Asset: {asset.name}, Vulnerability: {vulnerability.get_name()[:50]}...")
    logger.debug(f"Criticality: {criticality}, Cost: {criticality_cost}")

    highest_value_of_risk = Decimal('0')

    for threat in vulnerability.threats.all():
        # Calculate threat impact
        threat_impact_value = calculate_threat_impact_value(threat.probability, threat.impact)
        threat_impact_level = calculate_threat_impact_level(threat_impact_value)
        value_of_risk = Decimal(criticality_cost) * Decimal(threat_impact_level)

        # Debug logging for each threat
        logger.debug(f"Threat: {threat.get_name()}, Probability: {threat.probability}, Impact: {threat.impact}")
        logger.debug(f"Threat impact value: {threat_impact_value}, Threat impact level: {threat_impact_level}")
        logger.debug(f"Calculated risk value: {value_of_risk}")

        if value_of_risk > highest_value_of_risk:
            highest_value_of_risk = value_of_risk

    logger.debug(f"Final highest risk value: {highest_value_of_risk}")
    return highest_value_of_risk


def calculate_threat_impact_value(probability, impact):
    """Calculate threat impact value: Probability (L) × Overall Impact (E) × 100 for percentage format"""
    result = Decimal(probability) * Decimal(impact) * 100
    logger.debug(f"calculate_threat_impact_value - Probability: {probability}, Impact: {impact}, Result: {result}")
    return result


def calculate_threat_impact_level(value):
    """Calculate threat impact level based on value"""
    # logger.debug(f"calculate_threat_impact_level - Input value: {value}")
    
    if value == 0:
        result = 0
    elif 0 < value <= Decimal('0.054'):
        result = 1
    elif Decimal('0.054') < value <= Decimal('0.27'):
        result = 2
    elif Decimal('0.27') < value <= Decimal('0.55'):
        result = 3
    elif Decimal('0.55') < value <= Decimal('3.3'):
        result = 4
    elif Decimal('3.3') < value <= Decimal('14'):
        result = 6
    elif Decimal('14') < value <= Decimal('34'):
        result = 8
    elif Decimal('34') < value <= Decimal('45'):
        result = 10
    elif Decimal('45') < value <= Decimal('55'):
        result = 12
    elif Decimal('55') < value <= Decimal('70'):
        result = 14
    elif Decimal('70') < value <= Decimal('80'):
        result = 16
    elif Decimal('80') < value <= Decimal('90'):
        result = 18
    elif Decimal('90') < value <= Decimal('100'):
        result = 20
    elif value > Decimal('100'):
        # For values above 100, cap at the maximum level (20)
        result = 20
    else:
        result = 0
    
    # logger.debug(f"calculate_threat_impact_level - Output level: {result}")
    return result


def get_risk_level(value, company_id=None):
    """Get risk level object for a given value"""
    return get_company_risk_levels_queryset(company_id).filter(min_value__lte=value, max_value__gte=value).first()


def get_status_color(status):
    """Get color code for a treatment status"""
    status_colors = {
        'Undefined': '#808080',  # Gray
        'Planned': '#FFA500',    # Orange
        'In Progress': '#1E90FF', # Dodger Blue
        'Completed': '#32CD32',  # Lime Green
        'Overdue': '#FF0000'     # Red
    }
    return status_colors.get(status, '#000000')  # Default to black if status not found


def get_risk_level_from_name(name, company_id=None):
    """Get risk level object by name (default name or any translation name_local)."""
    return RiskLevel.get_by_display_name(name, company_id=company_id)


def get_user_risk_assessment_permissions(user):
    """Get user permissions for risk assessment"""
    access = AccessRisk.objects.filter(group__in=user.groups.all(), has_access_assessment=True)
    return {
        'companies': set(company.id for access_obj in access for company in access_obj.companies.all()),
        'can_edit': access.filter(can_edit_assessment=True).exists(),
        'show_link': access.exists(),
    }


def format_time(datetime_obj):
    """Format datetime object to string in Kyiv timezone"""
    if datetime_obj:
        kyiv_tz = pytz.timezone('Europe/Kiev')
        if timezone.is_naive(datetime_obj):
            datetime_obj = timezone.make_aware(datetime_obj, timezone.utc)
        kyiv_time = datetime_obj.astimezone(kyiv_tz)
        return kyiv_time.strftime('%Y-%m-%d %H:%M:%S')
    return ''
