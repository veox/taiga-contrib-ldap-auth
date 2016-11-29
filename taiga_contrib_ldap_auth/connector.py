# Copyright (C) 2014 Andrey Antukh <niwi@niwi.be>
# Copyright (C) 2014 Jesús Espino <jespinog@gmail.com>
# Copyright (C) 2014 David Barragán <bameda@dbarragan.com>
# Copyright (C) 2015 Ensky Lin <enskylin@gmail.com>
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from ldap3 import Server, Connection, SIMPLE, ANONYMOUS, SYNC, SIMPLE, SYNC, ASYNC, SUBTREE, NONE

from django.conf import settings
from taiga.base.connectors.exceptions import ConnectorBaseException


class LDAPLoginError(ConnectorBaseException):
    pass


SERVER = getattr(settings, "LDAP_SERVER", "")
PORT = getattr(settings, "LDAP_PORT", "")

SEARCH_BASE = getattr(settings, "LDAP_SEARCH_BASE", "")
SEARCH_FILTER_ADDITIONAL = getattr(settings, "LDAP_SEARCH_FILTER_ADDITIONAL", "")
BIND_DN = getattr(settings, "LDAP_BIND_DN", "")
BIND_PASSWORD = getattr(settings, "LDAP_BIND_PASSWORD", "")

USERNAME_ATTRIBUTE = getattr(settings, "LDAP_USERNAME_ATTRIBUTE", "")
EMAIL_ATTRIBUTE = getattr(settings, "LDAP_EMAIL_ATTRIBUTE", "")
FULL_NAME_ATTRIBUTE = getattr(settings, "LDAP_FULL_NAME_ATTRIBUTE", "")

def login(login: str, password: str) -> tuple:
    """
    Connect to LDAP server, perform a search and attempt a bind.

    Can raise `exc.LDAPLoginError` exceptions if any of the
    operations fail.

    :returns: tuple (username, email, full_name)

    """

    try:
        if SERVER.lower().startswith("ldaps://"):
            use_ssl = True
        else:
            use_ssl = False
        server = Server(SERVER, port = PORT, get_info = NONE, use_ssl = use_ssl)

        if BIND_DN is not None and BIND_DN != '':
            user = BIND_DN
            password = BIND_PASSWORD
            authentication = SIMPLE
        else:
            user = None
            password = None
            authentication = ANONYMOUS
        c = Connection(server, auto_bind = True, client_strategy = SYNC, check_names = True,
                       user = user, password = password, authentication = authentication)

    except Exception as e:
        error = "Error connecting to LDAP server: %s" % e
        raise LDAPLoginError({"error_message": error})

    search_filter = '(|(%s=%s)(%s=%s))' % (USERNAME_ATTRIBUTE, login, EMAIL_ATTRIBUTE, login)
    if SEARCH_FILTER_ADDITIONAL:
        search_filter = '(&%s%s)' % (search_filter, SEARCH_FILTER_ADDITIONAL)

    try:
        c.search(search_base = SEARCH_BASE,
                 search_filter = search_filter,
                 search_scope = SUBTREE,
                 attributes = [USERNAME_ATTRIBUTE, EMAIL_ATTRIBUTE, FULL_NAME_ATTRIBUTE],
                 paged_size = 5)
    except Exception as e:
        error = "LDAP login incorrect: %s" % e
        raise LDAPLoginError({"error_message": error})

    # TODO: handle multiple matches
    if len(c.response) > 0:
        username = c.response[0].get('raw_attributes').get(USERNAME_ATTRIBUTE)[0].decode('utf-8')
        email = c.response[0].get('raw_attributes').get(EMAIL_ATTRIBUTE)[0].decode('utf-8')
        full_name = c.response[0].get('raw_attributes').get(FULL_NAME_ATTRIBUTE)[0].decode('utf-8')
    else:
        raise LDAPLoginError({"error_message": "LDAP login not found"})

    try:
        dn = c.response[0].get('dn')
        user_conn = Connection(server, auto_bind = True, client_strategy = SYNC,
                               check_names = True, authentication = SIMPLE,
                               user = dn, password = password)
        return (username, email, full_name)
    except Exception as e:
        error = "LDAP bind failed: %s" % e
        raise LDAPLoginError({"error_message": error})

