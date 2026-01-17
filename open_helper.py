"""Helper module for non-blocking Freebox API opening."""
from __future__ import annotations

import asyncio
import logging
import ssl
from os import path
from typing import Any

from aiohttp import ClientSession, TCPConnector
import freebox_api.aiofreepybox as aiofreepybox
from freebox_api.aiofreepybox import (
    Access,
    Airmedia,
    Call,
    Connection,
    Dhcp,
    Download,
    Freeplug,
    Freepybox,
    Fs,
    Ftp,
    Fw,
    Home,
    Lan,
    Lcd,
    Netshare,
    Notifications,
    Parental,
    Phone,
    Player,
    Remote,
    Rrd,
    Storage,
    Switch,
    System,
    Tv,
    Upnpav,
    Upnpigd,
    Wifi,
)
from freebox_api.exceptions import AuthorizationError, InvalidTokenError

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def async_open_freebox(
    hass: HomeAssistant, api: Freepybox, host: str, port: int
) -> None:
    """Open Freebox API without blocking the event loop.

    The upstream freebox_api uses synchronous SSL context creation and token file
    reads/writes inside its `open` coroutine. These calls trigger blocking-call
    warnings on Python 3.13+, so we offload them to the executor while keeping
    the remaining logic unchanged.
    """

    if not api._is_app_desc_valid(api.app_desc):  # noqa: SLF001 - upstream helper
        raise InvalidTokenError("Invalid application descriptor")

    cert_path = path.join(path.dirname(aiofreepybox.__file__), "freebox_certificates.pem")

    def _build_ssl_context() -> ssl.SSLContext:
        ctx = ssl.create_default_context()
        ctx.load_verify_locations(cafile=cert_path)
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
        return ctx

    ssl_ctx = await hass.async_add_executor_job(_build_ssl_context)
    conn = TCPConnector(ssl_context=ssl_ctx)
    api._session = ClientSession(connector=conn)  # noqa: SLF001 - upstream attribute

    base_url = api._get_base_url(host, port, api.api_version)  # noqa: SLF001

    app_token: str | None
    track_id: int | None
    file_app_desc: dict[str, Any] | None
    app_token, track_id, file_app_desc = await hass.async_add_executor_job(
        api._readfile_app_token, api.token_file  # noqa: SLF001
    )

    try:
        if app_token is None or file_app_desc != api.app_desc:
            app_token, track_id = await api._get_app_token(  # noqa: SLF001
                base_url, api.app_desc, api.timeout
            )

            out_msg_flag = False
            status: str | None = None
            while status != "granted":
                status = await api._get_authorization_status(  # noqa: SLF001
                    base_url, track_id, api.timeout
                )

                if status == "denied":
                    raise AuthorizationError(
                        "The app token is invalid or has been revoked"
                    )

                if status == "pending":
                    if not out_msg_flag:
                        out_msg_flag = True
                        _LOGGER.warning(
                            "Please confirm the authentication request on the Freebox"
                        )
                    await asyncio.sleep(1)

                if status == "timeout":
                    raise AuthorizationError("Authorization timed out")

            await hass.async_add_executor_job(
                api._writefile_app_token,  # noqa: SLF001
                app_token,
                track_id,
                api.app_desc,
                api.token_file,
            )

        api._access = Access(  # noqa: SLF001
            api._session, base_url, app_token, api.app_desc["app_id"], api.timeout
        )

        api.tv = Tv(api._access)
        api.system = System(api._access)
        api.dhcp = Dhcp(api._access)
        api.airmedia = Airmedia(api._access)
        api.player = Player(api._access)
        api.switch = Switch(api._access)
        api.lan = Lan(api._access)
        api.storage = Storage(api._access)
        api.lcd = Lcd(api._access)
        api.wifi = Wifi(api._access)
        api.phone = Phone(api._access)
        api.ftp = Ftp(api._access)
        api.fs = Fs(api._access)
        api.fw = Fw(api._access)
        api.freeplug = Freeplug(api._access)
        api.call = Call(api._access)
        api.connection = Connection(api._access)
        api.download = Download(api._access)
        api.home = Home(api._access)
        api.parental = Parental(api._access)
        api.netshare = Netshare(api._access)
        api.notifications = Notifications(api._access)
        api.remote = Remote(api._access)
        api.rrd = Rrd(api._access)
        api.upnpav = Upnpav(api._access)
        api.upnpigd = Upnpigd(api._access)
    except Exception:
        if api._session and not api._session.closed:
            await api._session.close()
        raise
