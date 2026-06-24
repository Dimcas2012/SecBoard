# SecBoard\SecBoard\app_cabinet\backends.py
"""
LDAP/AD authentication backend for Cabinet.
No manual sync: first successful bind creates User + CabinetUser for that company.
"""
import logging
from datetime import datetime, timedelta, timezone as dt_timezone
from django.contrib.auth.backends import ModelBackend
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Q

from .models import CabinetADConnection, CabinetUser, CabinetGroup

logger = logging.getLogger(__name__)

# Extra AD attributes to fetch and store (General, Address, Telephones, Organization, Security)
AD_EXTRA_ATTRS = [
    "description", "displayName", "physicalDeliveryOfficeName", "initials", "wWWHomePage",
    "streetAddress", "postOfficeBox", "l", "st", "postalCode", "c", "co",
    "mobile", "facsimileTelephoneNumber", "ipPhone",
    "title", "department", "company",
    "memberOf",  # user's AD groups (Security block)
]


def _normalize_ldap_value_for_json(v):
    """Convert LDAP attribute value to JSON-serializable string or list of strings."""
    if v is None:
        return None
    if isinstance(v, bytes):
        try:
            return v.decode("utf-8", errors="replace")
        except Exception:
            return None
    if isinstance(v, list):
        out = []
        for x in v:
            y = _normalize_ldap_value_for_json(x)
            if y is not None and str(y).strip():
                out.append(str(y))
        return out[0] if len(out) == 1 else (out if out else None)
    s = str(v).strip()
    return s if s else None


# Windows FILETIME: 100-nanosecond intervals since 1601-01-01 UTC. accountExpires uses this.
_WIN_FILETIME_EPOCH = datetime(1601, 1, 1, tzinfo=dt_timezone.utc)
_WIN_FILETIME_NEVER = 9223372036854775807


def _parse_ldap_date(value):
    """Parse LDAP date to timezone-aware datetime or None.
    Supports: generalized time (YYYYMMDDHHMMSS.0Z), YYYY-MM-DD, YYYYMMDD,
    and Windows FILETIME (e.g. accountExpires: 100-nanosecond intervals since 1601-01-01 UTC).
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return timezone.make_aware(value) if timezone.is_naive(value) else value
    raw = value[0] if isinstance(value, list) and value else value
    if raw is None:
        return None
    # Windows FILETIME (integer or long digit string) - e.g. accountExpires; only if value is large
    try:
        if isinstance(raw, int):
            n = raw
        else:
            s = str(raw).strip()
            if not s or s in ("0", "9223372036854775807", str(_WIN_FILETIME_NEVER)):
                return None
            n = int(s)
        if n > 100000000000000 and n < _WIN_FILETIME_NEVER:  # typical accountExpires range
            # 100-nanosecond intervals -> seconds since 1601-01-01
            secs = n / 10000000
            return _WIN_FILETIME_EPOCH + timedelta(seconds=secs)
    except (ValueError, TypeError):
        pass
    s = str(raw).strip()
    if not s:
        return None
    try:
        if len(s) >= 14 and s.isdigit():
            return timezone.make_aware(datetime.strptime(s[:14], "%Y%m%d%H%M%S"))
        if ".0Z" in s or s.endswith("Z"):
            s_ = s.replace(".0Z", "Z").replace(".0z", "Z")
            if len(s_) >= 15:
                return timezone.make_aware(datetime.strptime(s_[:15], "%Y%m%d%H%M%SZ"))
        if "-" in s and len(s) >= 10:
            return timezone.make_aware(datetime.strptime(s[:10], "%Y-%m-%d"))
        if len(s) >= 8 and s.isdigit():
            return timezone.make_aware(datetime.strptime(s[:8], "%Y%m%d"))
    except (ValueError, TypeError):
        pass
    return None


def _ldap_escape(s):
    """Escape a value for use in LDAP filter (RFC 4515)."""
    if s is None:
        return ""
    s = str(s)
    return s.replace("\\", "\\5c").replace("*", "\\2a").replace("(", "\\28").replace(")", "\\29").replace("\x00", "\\00")


def _sid_binary_to_string(binary_sid):
    """Convert Windows binary SID to string form S-1-5-21-..."""
    if not binary_sid or len(binary_sid) < 8:
        return None
    try:
        import struct
        rev = struct.unpack("B", binary_sid[0:1])[0]
        nsub = struct.unpack("B", binary_sid[1:2])[0]
        auth = struct.unpack(">Q", b"\x00\x00" + binary_sid[2:8])[0]
        parts = [f"S-{rev}-{auth}"]
        for i in range(min(nsub, 15)):
            if 8 + 4 * (i + 1) <= len(binary_sid):
                sub = struct.unpack("<I", binary_sid[8 + 4 * i : 12 + 4 * i])[0]
                parts.append(str(sub))
        return "-".join(parts)
    except Exception:
        return None


def _resolve_token_groups_to_names(conn, base_dn, token_groups_binary, limit=25):
    """Resolve tokenGroups (list of binary SIDs) to group names via LDAP search. Returns list of names."""
    if not token_groups_binary or not isinstance(token_groups_binary, list):
        return []
    try:
        from ldap3 import SUBTREE
    except ImportError:
        return []
    names = []
    for sid_bytes in token_groups_binary[:limit]:
        if not sid_bytes or not isinstance(sid_bytes, bytes):
            continue
        try:
            # LDAP filter: objectSid with binary escaped as \XX per byte
            escaped = "".join(f"\\{b:02X}" for b in sid_bytes)
            flt = f"(objectSid={escaped})"
            conn.search(base_dn, flt, search_scope=SUBTREE, attributes=["cn", "sAMAccountName"], size_limit=1)
            if conn.entries:
                e = conn.entries[0]
                name = getattr(e, "cn", None) or getattr(e, "sAMAccountName", None)
                if name:
                    val = name[0] if isinstance(name, list) and name else name
                    if val and str(val).strip():
                        names.append(str(val).strip())
        except Exception:
            continue
    return names


def _get_ldap_connection(server_url, port, use_ssl, bind_dn, bind_password):
    """Return ldap3 Connection or None on failure."""
    try:
        from ldap3 import Server, Connection, ALL, Tls
        from ldap3.core.exceptions import LDAPException
        import ssl
    except ImportError as e:
        logger.warning("ldap3 not installed; AD login disabled: %s", e)
        return None
    try:
        if use_ssl:
            # LDAPS: allow self-signed certs (typical for internal AD)
            tls = Tls(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLS_CLIENT)
            server = Server(server_url, port=port, use_ssl=True, tls=tls, get_info=ALL)
        else:
            server = Server(server_url, port=port, use_ssl=False, get_info=ALL)
        conn = Connection(
            server,
            user=bind_dn,
            password=bind_password,
            auto_bind=True,
        )
        return conn
    except LDAPException as e:
        logger.warning("LDAP bind failed for %s:%s: %s", server_url, port, e)
        return None


def _search_and_authenticate_user(conn, base_dn, search_filter, attrs, user_dn_attr, password):
    """
    Search for one user by filter, then try to bind as that user with password.
    Returns (user_dn, attributes_dict, bind_ok). When bind fails (e.g. account disabled),
    we still return (user_dn, attrs_dict, False) so caller can sync state from AD.
    """
    try:
        from ldap3 import SUBTREE
        from ldap3.core.exceptions import LDAPException
    except ImportError:
        return None, None, False
    try:
        conn.search(base_dn, search_filter, search_scope=SUBTREE, attributes=attrs)
        if not conn.entries:
            logger.debug("AD: search returned no entries (base_dn=%s, filter=%s)", base_dn, search_filter)
            return None, None, False
        entry = conn.entries[0]
        user_dn = str(entry.entry_dn)
        attrs_dict = {}
        for k, v in entry.entry_attributes_as_dict.items():
            if v is None or (isinstance(v, list) and len(v) == 0):
                continue
            if isinstance(v, list):
                if str(k).lower() == "memberof":
                    attrs_dict[k] = v  # keep full list for Groups
                else:
                    attrs_dict[k] = v[0]
            else:
                attrs_dict[k] = v
        # Bind as the user to verify password (disabled accounts will fail here)
        from ldap3 import Connection
        server = conn.server
        user_conn = Connection(server, user=user_dn, password=password, auto_bind=True)
        user_conn.unbind()
        return user_dn, attrs_dict, True
    except LDAPException as e:
        if conn.entries:
            entry = conn.entries[0]
            user_dn = str(entry.entry_dn)
            attrs_dict = {}
            for k, v in entry.entry_attributes_as_dict.items():
                if v is None or (isinstance(v, list) and len(v) == 0):
                    continue
                if isinstance(v, list):
                    if str(k).lower() == "memberof":
                        attrs_dict[k] = v
                    else:
                        attrs_dict[k] = v[0]
                else:
                    attrs_dict[k] = v
            logger.info("AD: user found but bind failed (e.g. disabled or wrong password): %s", e)
            return user_dn, attrs_dict, False
        logger.warning("AD: search or user bind failed: %s", e)
        return None, None, False


def _sync_ad_groups_to_cabinet_groups(cabinet_user):
    """
    Add user to Cabinet groups whose name matches one of their AD Member of groups.
    Only considers Cabinet groups for the user's company or global (company=None).
    """
    if not cabinet_user or not cabinet_user.company_id:
        return
    member_of = cabinet_user.ad_extra_attributes.get("memberOf") if cabinet_user.ad_extra_attributes else None
    if not member_of or not isinstance(member_of, list):
        return
    names = {str(n).strip() for n in member_of if n and str(n).strip()}
    if not names:
        return
    user = cabinet_user.user
    # Cabinet groups: same company or global (company__isnull=True); match by CabinetGroup.name or Group.name
    cabinet_groups = CabinetGroup.objects.filter(
        Q(company_id=cabinet_user.company_id) | Q(company__isnull=True)
    ).select_related("group")
    added = 0
    for cg in cabinet_groups:
        cg_name = (cg.name or "").strip()
        grp_name = (cg.group.name or "").strip() if cg.group else ""
        if (cg_name and cg_name in names) or (grp_name and grp_name in names):
            if not user.groups.filter(pk=cg.group_id).exists():
                user.groups.add(cg.group)
                added += 1
    if added:
        logger.info("AD group sync: added user %s to %d Cabinet group(s) (Member of: %s)", user.username, added, list(names)[:10])


def refresh_cabinet_user_from_ad(cabinet_user):
    """
    Refresh AD-synced user data (phone, dates, ad_extra_attributes including memberOf, is_active)
    by searching AD with the service account. No user password needed.
    Tries the user's company AD first, then all other active AD connections (same as login).
    Returns (True, None) on success, (False, error_message) on failure.
    """
    if not getattr(cabinet_user, "is_ad_synced", False) or not cabinet_user.company_id:
        return False, "User is not AD-synced or has no company"
    user = cabinet_user.user
    email = (user.email or "").strip()
    username = (user.username or "").strip()
    sam_part = username.split("__company_")[0] if "__company_" in username else username
    # Also add login part before @ (sAMAccountName in AD is usually without domain)
    login_part = None
    for t in (email, username, sam_part):
        if t and "@" in str(t):
            login_part = str(t).split("@")[0].strip()
            break
    terms = list(dict.fromkeys([t for t in [email, username, sam_part, login_part] if t]))
    if not terms:
        return False, "User has no email or username to search in AD"
    # Try user's company AD first, then all active connections (like authenticate)
    connections_to_try = []
    try:
        ac = cabinet_user.company.ad_connection
        if ac and ac.is_active:
            connections_to_try.append(ac)
    except Exception:
        pass
    seen_pk = {c.pk for c in connections_to_try}
    for ad_conn in CabinetADConnection.objects.filter(is_active=True).select_related("company"):
        if ad_conn.pk not in seen_pk:
            seen_pk.add(ad_conn.pk)
            connections_to_try.append(ad_conn)
    if not connections_to_try:
        return False, "No AD connection configured or inactive"
    from ldap3 import SUBTREE, BASE
    entry = None
    ad_conn = None
    conn = None
    ever_connected = False
    last_conn_result = None  # for logging when user not found
    last_search_base = None
    last_user_filter = None
    for ad_conn in connections_to_try:
        conn = _get_ldap_connection(
            ad_conn.server_url, ad_conn.port, ad_conn.use_ssl,
            ad_conn.bind_dn, ad_conn.bind_password,
        )
        if not conn:
            logger.warning(
                "AD refresh: could not connect to %s (%s)",
                getattr(ad_conn, "name", ""), ad_conn.server_url,
            )
            continue
        ever_connected = True
        try:
            search_base = ad_conn.base_dn
            if (ad_conn.user_search_ou or "").strip():
                search_base = f"{ad_conn.user_search_ou.strip()},{ad_conn.base_dn}"
            attr_username = ad_conn.attr_username or "sAMAccountName"
            user_filter_part = (ad_conn.user_filter or "").strip() or "(objectClass=user)"
            last_search_base = search_base
            last_user_filter = user_filter_part
            logger.info(
                "AD refresh: trying connection %s (%s), base_dn=%s, search_base=%s, user_filter=%s, terms=%s",
                getattr(ad_conn, "name", ""), ad_conn.server_url,
                ad_conn.base_dn, search_base, user_filter_part, terms,
            )
            end_date_attr = getattr(ad_conn, "attr_end_date", None) or "accountExpires"
            attrs = [
                attr_username, ad_conn.attr_email or "mail", ad_conn.attr_first_name or "givenName",
                ad_conn.attr_last_name or "sn", "userPrincipalName", "mail",
            ]
            if getattr(ad_conn, "attr_phone", None):
                attrs.append(ad_conn.attr_phone)
            if getattr(ad_conn, "attr_start_date", None):
                attrs.append(ad_conn.attr_start_date)
            if end_date_attr not in attrs:
                attrs.append(end_date_attr)
            if "userAccountControl" not in attrs:
                attrs.append("userAccountControl")
            for a in AD_EXTRA_ATTRS:
                if a not in attrs:
                    attrs.append(a)
            # Do not request tokenGroups in SUBTREE search: AD only returns it for BASE scope
            for term in terms:
                escaped = _ldap_escape(term)
                search_filter = f"(&{user_filter_part}(|({attr_username}={escaped})(userPrincipalName={escaped})(mail={escaped})))"
                for base in (search_base, ad_conn.base_dn):  # try OU first, then whole domain
                    if not base:
                        continue
                    conn.search(base, search_filter, search_scope=SUBTREE, attributes=attrs)
                    if conn.entries:
                        entry = conn.entries[0]
                        break
                if entry:
                    break
                # Fallback: minimal filter (no user_filter)
                if not entry:
                    fallback_filter = f"(|({attr_username}={escaped})(userPrincipalName={escaped})(mail={escaped}))"
                    for base in (search_base, ad_conn.base_dn):
                        if not base:
                            continue
                        conn.search(base, fallback_filter, search_scope=SUBTREE, attributes=attrs)
                        if conn.entries:
                            entry = conn.entries[0]
                            break
                # Fallback: single-attribute search (some servers prefer simple filters)
                if not entry:
                    for attr in (attr_username, "userPrincipalName", "mail"):
                        for base in (search_base, ad_conn.base_dn):
                            if not base:
                                continue
                            conn.search(base, f"({attr}={escaped})", search_scope=SUBTREE, attributes=attrs)
                            if conn.entries:
                                entry = conn.entries[0]
                                break
                        if entry:
                            break
                # Fallback: (objectClass=user) only (some AD/LDAP store objectCategory differently)
                if not entry and user_filter_part != "(objectClass=user)":
                    simple_user_filter = "(&(objectClass=user)(|({attr_username}={escaped})(userPrincipalName={escaped})(mail={escaped})))".format(
                        attr_username=attr_username, escaped=escaped
                    )
                    for base in (search_base, ad_conn.base_dn):
                        if not base:
                            continue
                        conn.search(base, simple_user_filter, search_scope=SUBTREE, attributes=attrs)
                        if conn.entries:
                            entry = conn.entries[0]
                            break
                if entry:
                    break
            if entry:
                break
        finally:
            if not entry and conn:
                last_conn_result = getattr(conn, "result", None)
                try:
                    conn.unbind()
                except Exception:
                    pass
                conn = None
    if not entry or not ad_conn or not conn:
        logger.warning(
            "AD refresh: user not found (tried terms: %s). Connection: %s (%s), search_base=%s, user_filter=%s. LDAP result: %s",
            terms,
            getattr(ad_conn, "name", "") if ad_conn else "—",
            getattr(ad_conn, "server_url", "") if ad_conn else "—",
            last_search_base or "—",
            last_user_filter or "—",
            last_conn_result,
        )
        if not ever_connected:
            return False, "Cannot connect to AD (check server URL and bind credentials)"
        tried = ", ".join(terms[:5]) if terms else "none"
        return False, (
            f"User not found in AD (searched: {tried}). "
            "Check that the user exists under the AD connection's search base and that the bind account has search rights."
        )
    attr_username = ad_conn.attr_username or "sAMAccountName"
    end_date_attr = getattr(ad_conn, "attr_end_date", None) or "accountExpires"
    try:
        raw_keys = list(entry.entry_attributes_as_dict.keys())
        logger.info("AD refresh entry attributes: %s", raw_keys)
        attrs_dict = {}
        for k, v in entry.entry_attributes_as_dict.items():
            if v is None:
                continue
            if isinstance(v, list):
                if len(v) == 0:
                    if str(k).lower() == "memberof":
                        attrs_dict["memberOf"] = []  # normalize key for frontend
                    continue
                if str(k).lower() == "memberof":
                    attrs_dict["memberOf"] = v  # normalize key
                elif str(k).lower() == "tokengroups":
                    attrs_dict["tokenGroups"] = v  # keep list of binary SIDs
                else:
                    attrs_dict[k] = v[0]
            else:
                attrs_dict[k] = v
        if "memberOf" not in attrs_dict:
            attrs_dict["memberOf"] = []
        # AD returns tokenGroups only for BASE scope; fetch in a second query
        if conn:
            try:
                user_dn = str(entry.entry_dn)
                conn.search(user_dn, "(objectClass=*)", search_scope=BASE, attributes=["tokenGroups", "memberOf"])
                if conn.entries:
                    for k, v in conn.entries[0].entry_attributes_as_dict.items():
                        if v is None:
                            continue
                        if str(k).lower() == "memberof" and v:
                            attrs_dict["memberOf"] = v if isinstance(v, list) else [v]
                        elif str(k).lower() == "tokengroups" and v:
                            attrs_dict["tokenGroups"] = v if isinstance(v, list) else [v]
            except Exception as e:
                logger.debug("AD refresh: could not fetch tokenGroups (BASE search): %s", e)
        # Build complete group list: tokenGroups (all security groups incl. nested
        # and primary) + memberOf DNs (may contain distribution groups not in tokenGroups).
        all_group_names = set()
        # Resolve tokenGroups SIDs → friendly names (always, not just as fallback)
        if attrs_dict.get("tokenGroups") and conn:
            tg = attrs_dict["tokenGroups"]
            resolved = _resolve_token_groups_to_names(conn, ad_conn.base_dn, tg, limit=50)
            logger.info("AD refresh: tokenGroups resolved to: %s", resolved)
            all_group_names.update(resolved)
        # Extract CN from memberOf DNs (these are full DNs like "CN=GroupName,OU=...")
        for dn in (attrs_dict.get("memberOf") or []):
            dn_str = str(dn).strip()
            if dn_str.upper().startswith("CN="):
                cn = dn_str[3:].split(",", 1)[0].strip()
                if cn:
                    all_group_names.add(cn)
            elif dn_str:
                all_group_names.add(dn_str)
        attrs_dict["memberOf"] = sorted(all_group_names) if all_group_names else []
        phone_val = attrs_dict.get(getattr(ad_conn, "attr_phone", None) or "telephoneNumber")
        if phone_val is not None and isinstance(phone_val, list):
            phone_val = phone_val[0] if phone_val else ""
        phone_str = (phone_val or "").strip() if phone_val else ""
        if len(phone_str) > 20:
            phone_str = phone_str[:20]
        start_dt = _parse_ldap_date(attrs_dict.get(ad_conn.attr_start_date)) if getattr(ad_conn, "attr_start_date", None) else None
        end_dt = _parse_ldap_date(attrs_dict.get(end_date_attr))
        update_cab = {}
        if getattr(ad_conn, "attr_phone", None):
            cabinet_user.phone = phone_str or None
            update_cab["phone"] = True
        if start_dt is not None:
            cabinet_user.start_date = start_dt
            update_cab["start_date"] = True
        if end_dt is not None:
            cabinet_user.end_date = end_dt
            update_cab["end_date"] = True
        cabinet_user.is_ad_synced = True
        update_cab["is_ad_synced"] = True

        def _attr_get(d, key):
            key_lower = (key or "").lower()
            for k, v in d.items():
                if k is not None and str(k).lower() == key_lower:
                    return v
            return None
        uac_raw = _attr_get(attrs_dict, "userAccountControl")
        try:
            uac_val = uac_raw
            if isinstance(uac_val, list) and uac_val:
                uac_val = uac_val[0]
            if hasattr(uac_val, "decode"):
                uac_val = uac_val.decode("utf-8", errors="replace") if isinstance(uac_val, bytes) else uac_val
            ad_account_disabled = (int(uac_val) & 2) != 0 if uac_val is not None else False
        except (TypeError, ValueError):
            ad_account_disabled = False
        extra = {"_ad_account_disabled": ad_account_disabled}
        core_keys = {
            attr_username, "userPrincipalName", ad_conn.attr_email or "mail", "mail",
            ad_conn.attr_first_name or "givenName", ad_conn.attr_last_name or "sn",
            getattr(ad_conn, "attr_phone", None) or "telephoneNumber",
            "tokenGroups",
        }
        for k in list(attrs_dict.keys()):
            if k and str(k).lower() == "useraccountcontrol":
                core_keys.add(k)
                break
        core_keys.add("userAccountControl")
        for x in (getattr(ad_conn, "attr_start_date", None), getattr(ad_conn, "attr_end_date", None), end_date_attr):
            if x:
                core_keys.add(x)
        for k, v in attrs_dict.items():
            if k in core_keys:
                continue
            if not v:
                if str(k).lower() == "memberof":
                    extra["memberOf"] = []
                continue
            norm = _normalize_ldap_value_for_json(v)
            if norm is not None:
                extra[k] = norm
        if "memberOf" not in extra:
            extra["memberOf"] = []
        cabinet_user.ad_extra_attributes = extra
        update_cab["ad_extra_attributes"] = True
        cabinet_user.save(update_fields=[x for x in ("phone", "start_date", "end_date", "is_ad_synced", "ad_extra_attributes") if update_cab.get(x)])
        if getattr(ad_conn, "sync_ad_groups_to_cabinet", False):
            _sync_ad_groups_to_cabinet_groups(cabinet_user)
        now = timezone.now()
        if ad_account_disabled:
            user.is_active = False
            user.save(update_fields=["is_active"])
        elif cabinet_user.start_date or cabinet_user.end_date:
            start = cabinet_user.start_date.date() if cabinet_user.start_date else None
            end = cabinet_user.end_date.date() if cabinet_user.end_date else None
            today = now.date()
            if start and end:
                user.is_active = start <= today <= end
            elif start:
                user.is_active = start <= today
            elif end:
                user.is_active = today <= end
            user.save(update_fields=["is_active"])
        logger.info("AD refresh success: user=%s", user.username)
        return True, None
    except Exception as e:
        logger.exception("AD refresh failed for %s: %s", cabinet_user.user.username, e)
        return False, str(e)
    finally:
        try:
            conn.unbind()
        except Exception:
            pass


class CabinetADBackend(ModelBackend):
    """
    Authenticate against each company's AD. On first successful bind,
    create User + CabinetUser (no manual sync).
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        username = (username or "").strip()
        connections = list(CabinetADConnection.objects.filter(is_active=True).select_related("company"))
        if not connections:
            logger.debug("AD login: no active CabinetADConnection configured.")
            return None
        logger.info("AD login attempt for %s across %d connection(s)", username, len(connections))
        for ad_conn in connections:
            conn = _get_ldap_connection(
                ad_conn.server_url,
                ad_conn.port,
                ad_conn.use_ssl,
                ad_conn.bind_dn,
                ad_conn.bind_password,
            )
            if not conn:
                continue
            logger.debug("AD: connected to %s, searching for user", ad_conn.server_url)
            try:
                # Build search base: base_dn or base_dn + user_search_ou
                search_base = ad_conn.base_dn
                if ad_conn.user_search_ou.strip():
                    search_base = f"{ad_conn.user_search_ou},{ad_conn.base_dn}"
                # Search by username: attr_username or mail / userPrincipalName
                attr_username = ad_conn.attr_username or "sAMAccountName"
                escaped = _ldap_escape(username)
                search_filter = f"(&{ad_conn.user_filter}(|({attr_username}={escaped})(userPrincipalName={escaped})(mail={escaped})))"
                attrs = [
                    attr_username,
                    ad_conn.attr_email or "mail",
                    ad_conn.attr_first_name or "givenName",
                    ad_conn.attr_last_name or "sn",
                    "userPrincipalName",
                    "mail",
                ]
                if getattr(ad_conn, "attr_phone", None):
                    attrs.append(ad_conn.attr_phone)
                if getattr(ad_conn, "attr_start_date", None):
                    attrs.append(ad_conn.attr_start_date)
                # End date: use configured attr or default to accountExpires (AD "Account expires - End of:")
                end_date_attr = getattr(ad_conn, "attr_end_date", None) or "accountExpires"
                if end_date_attr not in attrs:
                    attrs.append(end_date_attr)
                # Account disabled: userAccountControl bit 2 = ACCOUNTDISABLE
                if "userAccountControl" not in attrs:
                    attrs.append("userAccountControl")
                for a in AD_EXTRA_ATTRS:
                    if a not in attrs:
                        attrs.append(a)
                user_dn, attrs_dict, bind_ok = _search_and_authenticate_user(
                    conn, search_base, search_filter, attrs, attr_username, password
                )
            finally:
                try:
                    conn.unbind()
                except Exception:
                    pass
            if not user_dn or not attrs_dict:
                logger.warning("AD: user not found for %s on %s", username, ad_conn.server_url)
                continue
            # Resolve login and email for Django User
            login = attrs_dict.get(attr_username) or attrs_dict.get("userPrincipalName") or username
            if isinstance(login, list):
                login = login[0] if login else username
            email = attrs_dict.get(ad_conn.attr_email or "mail") or attrs_dict.get("mail") or ""
            if isinstance(email, list):
                email = email[0] if email else ""
            if not email and login and "@" in str(login):
                email = str(login)
            if not email:
                email = f"{login}@ad.local"
            first_name = attrs_dict.get(ad_conn.attr_first_name or "givenName") or ""
            last_name = attrs_dict.get(ad_conn.attr_last_name or "sn") or ""
            if isinstance(first_name, list):
                first_name = first_name[0] if first_name else ""
            if isinstance(last_name, list):
                last_name = last_name[0] if last_name else ""
            # Find existing user: include login form value (username) to match e.g. test_user@secboard.local
            possible_usernames = list(dict.fromkeys([
                x for x in (
                    (username or "").strip(),
                    (email or "").strip(),
                    str(login),
                    f"{login}__company_{ad_conn.company_id}",
                )
                if x
            ]))
            existing = User.objects.filter(
                cabinet__company_id=ad_conn.company_id,
            ).filter(
                Q(username__in=possible_usernames) | Q(email=email)
            ).first()
            # Avoid duplicate: if not in this company, find any Cabinet user with same username/email
            if not existing:
                existing = User.objects.filter(
                    Q(username__in=possible_usernames) | Q(email=email)
                ).filter(cabinet__isnull=False).first()
            # Sync phone, start_date, end_date from AD
            phone_val = attrs_dict.get(getattr(ad_conn, "attr_phone", None) or "telephoneNumber")
            if phone_val is not None and isinstance(phone_val, list):
                phone_val = phone_val[0] if phone_val else ""
            phone_str = (phone_val or "").strip() if phone_val else ""
            if len(phone_str) > 20:
                phone_str = phone_str[:20]
            start_dt = _parse_ldap_date(attrs_dict.get(ad_conn.attr_start_date)) if getattr(ad_conn, "attr_start_date", None) else None
            end_dt = _parse_ldap_date(attrs_dict.get(end_date_attr))

            def _attr_get(d, key):
                key_lower = (key or "").lower()
                for k, v in d.items():
                    if k is not None and str(k).lower() == key_lower:
                        return v
                return None

            # When bind failed (e.g. account disabled), sync existing user from AD so we see Disabled / end date, then deny login
            if not bind_ok:
                if not existing:
                    logger.warning("AD: user not found or password wrong for %s on %s", username, ad_conn.server_url)
                    continue
                user = existing
                cabinet_user = CabinetUser.objects.get(user=user)
                update_cab = {}
                if getattr(ad_conn, "attr_phone", None):
                    cabinet_user.phone = phone_str or None
                    update_cab["phone"] = True
                if start_dt is not None:
                    cabinet_user.start_date = start_dt
                    update_cab["start_date"] = True
                if end_dt is not None:
                    cabinet_user.end_date = end_dt
                    update_cab["end_date"] = True
                cabinet_user.is_ad_synced = True
                update_cab["is_ad_synced"] = True
                uac_raw = _attr_get(attrs_dict, "userAccountControl")
                try:
                    uac_val = uac_raw
                    if isinstance(uac_val, list) and uac_val:
                        uac_val = uac_val[0]
                    if hasattr(uac_val, "decode"):
                        uac_val = uac_val.decode("utf-8", errors="replace") if isinstance(uac_val, bytes) else uac_val
                    ad_account_disabled = (int(uac_val) & 2) != 0 if uac_val is not None else False
                except (TypeError, ValueError):
                    ad_account_disabled = False
                extra = {"_ad_account_disabled": ad_account_disabled}
                core_keys = {
                    attr_username, "userPrincipalName", ad_conn.attr_email or "mail", "mail",
                    ad_conn.attr_first_name or "givenName", ad_conn.attr_last_name or "sn",
                    getattr(ad_conn, "attr_phone", None) or "telephoneNumber",
                }
                for k in list(attrs_dict.keys()):
                    if k and str(k).lower() == "useraccountcontrol":
                        core_keys.add(k)
                        break
                core_keys.add("userAccountControl")
                for x in (getattr(ad_conn, "attr_start_date", None), getattr(ad_conn, "attr_end_date", None), end_date_attr):
                    if x:
                        core_keys.add(x)
                for k, v in attrs_dict.items():
                    if k in core_keys or not v:
                        continue
                    norm = _normalize_ldap_value_for_json(v)
                    if norm is not None:
                        extra[k] = norm
                cabinet_user.ad_extra_attributes = extra
                update_cab["ad_extra_attributes"] = True
                cabinet_user.save(update_fields=[x for x in ("phone", "start_date", "end_date", "is_ad_synced", "ad_extra_attributes") if update_cab.get(x)])
                if getattr(ad_conn, "sync_ad_groups_to_cabinet", False):
                    _sync_ad_groups_to_cabinet_groups(cabinet_user)
                now = timezone.now()
                if ad_account_disabled:
                    user.is_active = False
                    user.save(update_fields=["is_active"])
                elif cabinet_user.start_date or cabinet_user.end_date:
                    start = cabinet_user.start_date.date() if cabinet_user.start_date else None
                    end = cabinet_user.end_date.date() if cabinet_user.end_date else None
                    today = now.date()
                    if start and end:
                        user.is_active = start <= today <= end
                    elif start:
                        user.is_active = start <= today
                    elif end:
                        user.is_active = today <= end
                    user.save(update_fields=["is_active"])
                logger.info("AD: synced state for %s (login failed, e.g. account disabled)", user.username)
                return None

            if existing:
                user = existing
                created = False
                user.email = email or user.email
                user.first_name = first_name or user.first_name
                user.last_name = last_name or user.last_name
                user.save(update_fields=["email", "first_name", "last_name"])
                cabinet_user = CabinetUser.objects.get(user=user)
                # If user was found globally (other company), attach to current AD company
                if cabinet_user.company_id != ad_conn.company_id:
                    cabinet_user.company = ad_conn.company
                    cabinet_user.save(update_fields=["company"])
            else:
                django_username = (email or "").strip() or str(login)
                if not django_username or User.objects.filter(username=django_username).exists():
                    django_username = f"{login}__company_{ad_conn.company_id}"
                user, created = User.objects.get_or_create(
                    username=django_username,
                    defaults={
                        "email": email,
                        "first_name": first_name,
                        "last_name": last_name,
                        "is_active": True,
                    },
                )
                if created:
                    user.set_unusable_password()
                    user.save()
                else:
                    user.email = email or user.email
                    user.first_name = first_name or user.first_name
                    user.last_name = last_name or user.last_name
                    user.save(update_fields=["email", "first_name", "last_name"])
                cabinet_user, cab_created = CabinetUser.objects.get_or_create(
                    user=user,
                    defaults={"company": ad_conn.company, "is_profile_completed": True, "is_ad_synced": True},
                )
                if not cab_created and cabinet_user.company_id != ad_conn.company_id:
                    cabinet_user.company = ad_conn.company
                    cabinet_user.save(update_fields=["company"])
            # Update CabinetUser from AD: phone, start_date, end_date; then User.is_active from date range
            update_cab = {}
            if getattr(ad_conn, "attr_phone", None):
                cabinet_user.phone = phone_str or None
                update_cab["phone"] = True
            if start_dt is not None:
                cabinet_user.start_date = start_dt
                update_cab["start_date"] = True
            if end_dt is not None:
                cabinet_user.end_date = end_dt
                update_cab["end_date"] = True
            cabinet_user.is_ad_synced = True
            update_cab["is_ad_synced"] = True
            # Account disabled in AD: userAccountControl bit 2 = ACCOUNTDISABLE
            uac_raw = _attr_get(attrs_dict, "userAccountControl")
            try:
                uac_val = uac_raw
                if isinstance(uac_val, list) and uac_val:
                    uac_val = uac_val[0]
                if hasattr(uac_val, "decode"):
                    uac_val = uac_val.decode("utf-8", errors="replace") if isinstance(uac_val, bytes) else uac_val
                ad_account_disabled = (int(uac_val) & 2) != 0 if uac_val is not None else False
            except (TypeError, ValueError):
                ad_account_disabled = False
            # Store extra AD attributes (General, Address, Telephones, etc.) for display
            extra = {"_ad_account_disabled": ad_account_disabled}
            core_keys = {
                attr_username, "userPrincipalName", ad_conn.attr_email or "mail", "mail",
                ad_conn.attr_first_name or "givenName", ad_conn.attr_last_name or "sn",
                getattr(ad_conn, "attr_phone", None) or "telephoneNumber",
            }
            for k in list(attrs_dict.keys()):
                if k and k.lower() == "useraccountcontrol":
                    core_keys.add(k)
                    break
            if "userAccountControl" not in core_keys:
                core_keys.add("userAccountControl")
            for x in (getattr(ad_conn, "attr_start_date", None), getattr(ad_conn, "attr_end_date", None), end_date_attr):
                if x:
                    core_keys.add(x)
            for k, v in attrs_dict.items():
                if k in core_keys or not v:
                    continue
                norm = _normalize_ldap_value_for_json(v)
                if norm is not None:
                    extra[k] = norm
            cabinet_user.ad_extra_attributes = extra
            update_cab["ad_extra_attributes"] = True
            if update_cab:
                cabinet_user.save(update_fields=[k for k in ("phone", "start_date", "end_date", "is_ad_synced", "ad_extra_attributes") if update_cab.get(k)])
            if getattr(ad_conn, "sync_ad_groups_to_cabinet", False):
                _sync_ad_groups_to_cabinet_groups(cabinet_user)
            # Currently active: if AD account is disabled → inactive; else from start/end dates (same logic as is_active_employee); no dates → active
            now = timezone.now()
            if ad_account_disabled:
                user.is_active = False
                user.save(update_fields=["is_active"])
            elif cabinet_user.start_date or cabinet_user.end_date:
                start = cabinet_user.start_date.date() if cabinet_user.start_date else None
                end = cabinet_user.end_date.date() if cabinet_user.end_date else None
                today = now.date()
                if start and end:
                    user.is_active = start <= today <= end
                elif start:
                    user.is_active = start <= today
                elif end:
                    user.is_active = today <= end
                user.save(update_fields=["is_active"])
            if ad_conn.company.group:
                user.groups.add(ad_conn.company.group)
            logger.info("AD login success: user=%s company=%s", user.username, ad_conn.company.name)
            return user
        return None
