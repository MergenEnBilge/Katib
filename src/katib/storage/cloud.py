"""Reading pictures out of a cloud bucket.

Katib signs its own requests rather than carrying a software kit for each provider, which keeps
the install small and means there is no third-party code holding your keys. Two schemes cover the
services people use:

* **S3**, which is Amazon S3 and everything that speaks its language: MinIO, Cloudflare R2,
  Backblaze B2, and Google Cloud Storage through the HMAC keys it calls interoperability keys.
* **Azure Blob Storage**, which signs differently.

Only reading is implemented. Katib never writes to a bucket, so a key that can only read is
enough, and is what to give it.
"""

import base64
import datetime as dt
import hashlib
import hmac
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Literal

from defusedxml import ElementTree as SafeXml

#: How long a request may take before Katib gives up on it.
TIMEOUT = 30
#: The most objects one listing asks for. The provider may return fewer.
PAGE = 1000
#: A listing stops here, so a bucket with millions of objects cannot fill the machine's memory.
MAX_OBJECTS = 200_000
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
AZURE_VERSION = "2021-08-06"

Provider = Literal["s3", "azure"]


class CloudError(RuntimeError):
    """Something went wrong reaching the bucket. The message is shown to the person."""


@dataclass(frozen=True)
class Source:
    """Where a bucket is and how to sign for it. `secret` never leaves the server."""

    name: str
    provider: Provider
    bucket: str
    access_key: str
    secret: str
    #: Only for S3. Amazon needs it; MinIO and R2 accept "auto" or "us-east-1".
    region: str = "us-east-1"
    #: A service that is not Amazon, such as "https://play.min.io" or an R2 endpoint. For Azure
    #: this is the account's own address, which Katib works out from the account name if empty.
    endpoint: str = ""
    #: Only objects whose names start with this are used.
    prefix: str = ""


@dataclass(frozen=True)
class CloudObject:
    key: str
    size: int


def list_objects(source: Source, prefix: str = "", limit: int = MAX_OBJECTS) -> list[CloudObject]:
    """Every object under `prefix`, or under the source's own prefix when none is given."""
    where = prefix or source.prefix
    if source.provider == "azure":
        return _azure_list(source, where, limit)
    return _s3_list(source, where, limit)


def fetch(source: Source, key: str, max_bytes: int) -> bytes:
    """One object's bytes. Raises CloudError when it is larger than `max_bytes`."""
    if source.provider == "azure":
        request = _azure_request(source, "GET", f"/{source.bucket}/{key}", {})
    else:
        request = _s3_request(source, "GET", key, {})
    with _open(request) as response:
        body = response.read(max_bytes + 1)
    if len(body) > max_bytes:
        raise CloudError(f"{key} is larger than the {max_bytes // (1024 * 1024)} MB limit.")
    return body


def check(source: Source) -> int:
    """Count what Katib can see, so someone can tell at once that the details are right."""
    return len(list_objects(source, limit=PAGE))


def _open(request: urllib.request.Request) -> Any:
    try:
        return urllib.request.urlopen(request, timeout=TIMEOUT)  # noqa: S310 -- https, built above
    except urllib.error.HTTPError as err:
        raise CloudError(_why(err)) from None
    except (urllib.error.URLError, TimeoutError) as err:
        raise CloudError(f"Could not reach the bucket: {err}") from None


def _why(err: urllib.error.HTTPError) -> str:
    """A message worth showing, rather than a bare status code."""
    reasons = {
        403: "The bucket refused those keys. Check the access key, the secret and the region.",
        404: "That bucket or object does not exist.",
        400: "The bucket refused the request. Check the region and the endpoint.",
    }
    return reasons.get(err.code, f"The bucket answered {err.code} {err.reason}.")


def _quote(value: str) -> str:
    """Percent-encode a path, leaving the separators alone, the way signing expects."""
    return urllib.parse.quote(value, safe="/~")


# --- S3 -------------------------------------------------------------------------------------


def _s3_host(source: Source) -> tuple[str, str, bool]:
    """The host to call, the scheme, and whether the bucket goes in the path.

    A service of someone's own is addressed with the bucket in the path, which is what MinIO and
    the like expect and what works with a plain address. Amazon takes the bucket in the host.
    """
    if source.endpoint:
        parts = urllib.parse.urlsplit(
            source.endpoint if "//" in source.endpoint else f"https://{source.endpoint}"
        )
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise CloudError("The endpoint has to be an http or https address.")
        return parts.netloc, parts.scheme, True
    return f"{source.bucket}.s3.{source.region}.amazonaws.com", "https", False


def _s3_request(
    source: Source, method: str, key: str, query: dict[str, str]
) -> urllib.request.Request:
    host, scheme, path_style = _s3_host(source)
    path = f"/{source.bucket}/{_quote(key)}" if path_style else f"/{_quote(key)}"
    if key == "":
        path = f"/{source.bucket}" if path_style else "/"
    now = dt.datetime.now(dt.UTC)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    day = now.strftime("%Y%m%d")
    canonical_query = "&".join(
        f"{urllib.parse.quote(k, safe='-_.~')}={urllib.parse.quote(v, safe='-_.~')}"
        for k, v in sorted(query.items())
    )
    headers = {
        "host": host,
        "x-amz-content-sha256": EMPTY_SHA256,
        "x-amz-date": stamp,
    }
    signed = ";".join(sorted(headers))
    canonical_headers = "".join(f"{k}:{headers[k]}\n" for k in sorted(headers))
    canonical = "\n".join([method, path, canonical_query, canonical_headers, signed, EMPTY_SHA256])
    scope = f"{day}/{source.region}/s3/aws4_request"
    to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            stamp,
            scope,
            hashlib.sha256(canonical.encode()).hexdigest(),
        ]
    )
    signature = hmac.new(_s3_key(source, day), to_sign.encode(), hashlib.sha256).hexdigest()
    headers["Authorization"] = (
        f"AWS4-HMAC-SHA256 Credential={source.access_key}/{scope}, "
        f"SignedHeaders={signed}, Signature={signature}"
    )
    url = f"{scheme}://{host}{path}" + (f"?{canonical_query}" if canonical_query else "")
    return urllib.request.Request(url, headers=headers, method=method)  # noqa: S310


def _s3_key(source: Source, day: str) -> bytes:
    key = f"AWS4{source.secret}".encode()
    for part in (day, source.region, "s3", "aws4_request"):
        key = hmac.new(key, part.encode(), hashlib.sha256).digest()
    return key


def _s3_list(source: Source, prefix: str, limit: int) -> list[CloudObject]:
    found: list[CloudObject] = []
    token = ""
    while len(found) < limit:
        query = {"list-type": "2", "max-keys": str(PAGE)}
        if prefix:
            query["prefix"] = prefix
        if token:
            query["continuation-token"] = token
        with _open(_s3_request(source, "GET", "", query)) as response:
            root = SafeXml.fromstring(response.read())
        namespace = root.tag.split("}")[0] + "}" if "}" in root.tag else ""
        for item in root.findall(f"{namespace}Contents"):
            key = item.findtext(f"{namespace}Key") or ""
            size = int(item.findtext(f"{namespace}Size") or 0)
            if key and not key.endswith("/"):
                found.append(CloudObject(key, size))
        token = root.findtext(f"{namespace}NextContinuationToken") or ""
        if (root.findtext(f"{namespace}IsTruncated") or "").lower() != "true" or not token:
            break
    return found[:limit]


# --- Azure ----------------------------------------------------------------------------------


def _azure_host(source: Source) -> tuple[str, str]:
    if source.endpoint:
        parts = urllib.parse.urlsplit(
            source.endpoint if "//" in source.endpoint else f"https://{source.endpoint}"
        )
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise CloudError("The endpoint has to be an http or https address.")
        return parts.netloc, parts.scheme
    return f"{source.access_key}.blob.core.windows.net", "https"


def _azure_request(
    source: Source, method: str, path: str, query: dict[str, str]
) -> urllib.request.Request:
    """A Shared Key signed request. The access key is the storage account's name."""
    host, scheme = _azure_host(source)
    stamp = dt.datetime.now(dt.UTC).strftime("%a, %d %b %Y %H:%M:%S GMT")
    headers = {"x-ms-date": stamp, "x-ms-version": AZURE_VERSION}
    canonical_headers = "".join(f"{k}:{headers[k]}\n" for k in sorted(headers))
    canonical_resource = f"/{source.access_key}{path}" + "".join(
        f"\n{k}:{query[k]}" for k in sorted(query)
    )
    to_sign = "\n".join(
        [
            method,
            "",  # Content-Encoding
            "",  # Content-Language
            "",  # Content-Length
            "",  # Content-MD5
            "",  # Content-Type
            "",  # Date, replaced by x-ms-date
            "",  # If-Modified-Since
            "",  # If-Match
            "",  # If-None-Match
            "",  # If-Unmodified-Since
            "",  # Range
            canonical_headers + canonical_resource,
        ]
    )
    try:
        secret = base64.b64decode(source.secret)
    except ValueError:
        raise CloudError("An Azure key is the base64 value from the portal.") from None
    signature = base64.b64encode(
        hmac.new(secret, to_sign.encode("utf-8"), hashlib.sha256).digest()
    ).decode()
    headers["Authorization"] = f"SharedKey {source.access_key}:{signature}"
    search = urllib.parse.urlencode(query)
    url = f"{scheme}://{host}{path}" + (f"?{search}" if search else "")
    return urllib.request.Request(url, headers=headers, method=method)  # noqa: S310


def _azure_list(source: Source, prefix: str, limit: int) -> list[CloudObject]:
    found: list[CloudObject] = []
    marker = ""
    while len(found) < limit:
        query = {
            "restype": "container",
            "comp": "list",
            "maxresults": str(PAGE),
        }
        if prefix:
            query["prefix"] = prefix
        if marker:
            query["marker"] = marker
        request = _azure_request(source, "GET", f"/{source.bucket}", query)
        with _open(request) as response:
            root = SafeXml.fromstring(response.read())
        for blob in root.iter("Blob"):
            key = blob.findtext("Name") or ""
            size = int(blob.findtext("Properties/Content-Length") or 0)
            if key and not key.endswith("/"):
                found.append(CloudObject(key, size))
        marker = root.findtext("NextMarker") or ""
        if not marker:
            break
    return found[:limit]
