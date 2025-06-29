import json
import time
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

CROSSREF_API_BASE_URL = "https://api.crossref.org"
DEFAULT_REQUEST_TIMEOUT = (10, 30)
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_FACTOR = 0.5
DEFAULT_STATUS_FORCELIST = (429, 500, 502, 503, 504)


def get_crossref_api_session(
    max_retries=DEFAULT_MAX_RETRIES,
    backoff_factor=DEFAULT_BACKOFF_FACTOR,
    status_forcelist=DEFAULT_STATUS_FORCELIST,
    session=None,
):

    session = session or requests.Session()
    retry_strategy = Retry(
        total=max_retries,
        read=max_retries,
        connect=max_retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=["HEAD", "GET", "OPTIONS"],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def crossref_rest_api_call(
    route,
    params,
    mailto,
    user_agent,
    session=None,
    timeout=DEFAULT_REQUEST_TIMEOUT,
    max_retries=DEFAULT_MAX_RETRIES,
    backoff_factor=DEFAULT_BACKOFF_FACTOR,
    status_forcelist=DEFAULT_STATUS_FORCELIST,
):

    url = f"{CROSSREF_API_BASE_URL}/{route.lstrip('/')}"
    headers = {'User-Agent': user_agent}
    if isinstance(params, dict):
        params["mailto"] = mailto
    else:
        params = {"mailto": mailto}

    local_session = False
    if session is None:
        try:
            session = get_crossref_api_session(
                max_retries=max_retries,
                backoff_factor=backoff_factor,
                status_forcelist=status_forcelist
            )
            local_session = True
        except Exception as e:
            logger.error(f"Failed to create requests session: {e}", exc_info=True)
            return None, f"Session creation failed: {e}"

    try:
        start_time = time.monotonic()
        response = session.get(url, params=params, headers=headers, timeout=timeout)
        elapsed = time.monotonic() - start_time
        code = response.status_code

        logger.debug(f"Crossref API call to {route} completed with status {code} in {elapsed:.2f}s.")

        if code == 200:
            try:
                result = response.json()
                return code, result.get("message", result)
            except json.JSONDecodeError as e:
                logger.warning(f"Non-JSON response from {route} (status 200). Error: {e}. Response text (start): {response.text[:200]}...")
                return code, f"JSONDecodeError: {e}. Response: {response.text[:200]}"
        else:
            logger.warning(f"Crossref API call to {route} failed with status code {code}. Response (start): {response.text[:200]}...")
            return code, response.text

    except requests.exceptions.Timeout as e:
        logger.error(f"Timeout during Crossref API call to {route} after configured retries: {e}", exc_info=False)
        return None, f"Request Timeout: {e}"
    except requests.exceptions.ConnectionError as e:
        logger.error(f"ConnectionError during Crossref API call to {route} after configured retries: {e}", exc_info=False)
        return None, f"Connection Error: {e}"
    except requests.exceptions.RequestException as e:
        logger.error(f"Unhandled RequestException during Crossref API call to {route} after configured retries: {e}", exc_info=True)
        return None, f"Request Exception: {e}"
    except Exception as e:
        logger.error(f"Unexpected error during Crossref API call to {route}: {e}", exc_info=True)
        return None, f"Unexpected Error: {e}"
    finally:
        if local_session and session:
            session.close()


def doi_id(doi_str):
    if doi_str is None:
        return None
    doi_str = str(doi_str).lower().replace("doi:", "").strip()
    if not doi_str or not doi_str.startswith("10."):
        logger.debug(f"Potentially invalid DOI format encountered: '{doi_str}'")
        return doi_str
    return f"https://doi.org/{doi_str}"


class AsciiJSONResponse(JSONResponse):
    def render(self, content):
        return json.dumps(content, ensure_ascii=True).encode("utf-8")