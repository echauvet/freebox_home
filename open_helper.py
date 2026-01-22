"""Freebox API connection helper for asynchronous communication.

Handles secure WebSocket connections and token management.
"""
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
    """ Open Freebox API connection without blocking the event loop.
    This function reimplements Freepybox.open() with executor-based offloading
    of blocking I/O operations. It:
    
    1. Validates the application descriptor
    2. Creates an SSL context in executor (blocking I/O offloaded)
    3. Initializes HTTP session with SSL context
    4. Reads stored token file in executor (blocking I/O offloaded)
    5. If no valid token exists:
       - Requests new token from Freebox
       - Waits for user confirmation on device
       - Writes token file in executor (blocking I/O offloaded)
    6. Creates Access object for API communication
    7. Instantiates all Freepybox API sub-modules
    
    The function is designed to be a drop-in replacement for Freepybox.open()
    but without the event loop blocking issues.
        Args:
            hass: The Home Assistant instance
        Args:
            api: The Freepybox API instance to initialize
        Args:
            host: The Freebox router hostname or IP address
        Args:
            port: The Freebox router HTTPS port number
        Returns:
            void (modifies @p api in-place)
        Raises:
            InvalidTokenError If the application descriptor is invalid
        Raises:
            AuthorizationError If Freebox authorization fails or times out
        Raises:
            ssl.SSLError If SSL context creation fails
        Raises:
            aiohttp.ClientError If HTTP connection fails
        See Also:
            https://github.com/hacf-fr/freebox_api
        See Also:
            https://developers.home-assistant.io/docs/asyncio_blocking_operations/
    
    @warning
    - Modifies @p api object state (sets session, access, and API modules)
    - On exception, may leave @p api in inconsistent state; caller should clean up
    - User must press button on Freebox device when prompted for first-time auth
    """

    if not api._is_app_desc_valid(api.app_desc):  # noqa: SLF001 - upstream helper
        _LOGGER.error("Invalid Freebox application descriptor")
        raise InvalidTokenError("Invalid application descriptor")

    cert_path = path.join(path.dirname(aiofreepybox.__file__), "freebox_certificates.pem")
    _LOGGER.debug("Loading Freebox SSL certificates from %s", cert_path)

    def _build_ssl_context() -> ssl.SSLContext:
        """ Create and configure SSL context for Freebox communication.
        Creates an SSL context that:
        - Uses system certificates for initial validation
        - Loads Freebox-specific certificates from @p cert_path
        - Disables strict X.509 validation for self-signed certs
        
        This function runs in executor thread to avoid event loop blocking.
        Returns:
            Configured ssl.SSLContext instance
        Raises:
            ssl.SSLError If certificate loading fails
        """
        ctx = ssl.create_default_context()
        ctx.load_verify_locations(cafile=cert_path)
        # Disable strict validation for self-signed Freebox certificates
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
        return ctx

    try:
        ssl_ctx = await hass.async_add_executor_job(_build_ssl_context)
        _LOGGER.debug("SSL context created successfully")
    except Exception as err:
        _LOGGER.error("Failed to create SSL context: %s", err)
        raise
    
    conn = TCPConnector(
        ssl_context=ssl_ctx,
        force_close=False,  # Allow connection reuse
        enable_cleanup_closed=True,  # Clean up closed connections
    )
    api._session = ClientSession(connector=conn)  # noqa: SLF001 - upstream attribute

    base_url = api._get_base_url(host, port, api.api_version)  # noqa: SLF001
    _LOGGER.debug("Connecting to Freebox at %s", base_url)

    app_token: str | None
    track_id: int | None
    file_app_desc: dict[str, Any] | None
    app_token, track_id, file_app_desc = await hass.async_add_executor_job(
        api._readfile_app_token, api.token_file  # noqa: SLF001
    )

    try:
        if app_token is None or file_app_desc != api.app_desc:
            _LOGGER.info("No valid application token found, requesting new one from Freebox")
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
                    _LOGGER.error("Freebox authorization was denied")
                    raise AuthorizationError(
                        "The app token is invalid or has been revoked"
                    )

                if status == "pending":
                    if not out_msg_flag:
                        out_msg_flag = True
                        _LOGGER.warning(
                            "Please confirm the authentication request on the Freebox device"
                        )
                    await asyncio.sleep(1)

                if status == "timeout":
                    _LOGGER.error("Freebox authorization request timed out")
                    raise AuthorizationError("Authorization timed out")

            _LOGGER.info("Application token obtained from Freebox")
            await hass.async_add_executor_job(
                api._writefile_app_token,  # noqa: SLF001
                app_token,
                track_id,
                api.app_desc,
                api.token_file,
            )
            _LOGGER.debug("Application token saved to %s", api.token_file)
        else:
            _LOGGER.debug("Using existing application token")

        api._access = Access(  # noqa: SLF001
            api._session, base_url, app_token, api.app_desc["app_id"], api.timeout
        )
        _LOGGER.debug("Freebox API access initialized")

        # Instantiate all API modules
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
        
        _LOGGER.info("Successfully connected to Freebox at %s", host)
    except Exception:
        if api._session and not api._session.closed:
            await api._session.close()
        raise
