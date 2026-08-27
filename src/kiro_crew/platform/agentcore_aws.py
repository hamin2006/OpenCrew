"""Optional AWS AgentCore adapter — installed by IaC, not the default wheel.

The public ``DefaultAgentIdentityProvider`` stays a no-op. Bootstrap
imports this module on standalone boot and attaches the adapter only
when :func:`opted_in` is true (workload name plus ``KIROCREW_AGENTCORE_AWS=1``
or a ``workload``/``login`` posture). ``boto3`` is loaded inside methods so
``import kiro_crew.platform.agentcore_aws`` does not pull AWS into a
process that never opted in. The ``agentcore`` extra / ``install.sh
--agentcore`` is what IaC installs on the box.

A workload access token is first-party Identity material. It is never the
Gateway inbound credential and never appears in ``status()``.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from typing import Any

from kiro_crew.platform.interfaces import (
    InboundToken,
    SessionPrincipal,
    WorkloadIdentity,
)

logger = logging.getLogger(__name__)

ENV_AWS = "KIROCREW_AGENTCORE_AWS"
ENV_WORKLOAD = "KIROCREW_AGENTCORE_WORKLOAD_NAME"
ENV_GATEWAY_URL = "KIROCREW_AGENTCORE_GATEWAY_URL"
ENV_POSTURE = "KIROCREW_AGENTCORE_POSTURE"
# boto3 client name (lazy). Not the ``bedrock-agentcore`` SDK package.
_CLIENT = "bedrock-agentcore"
_JWT_FALLBACK_TTL_SECS = 300.0


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def extra_available() -> bool:
    """True when the ``agentcore`` extra (boto3) can be imported."""
    try:
        import boto3  # noqa: F401
    except ImportError:
        return False
    return True


def opted_in() -> bool:
    """Template/operator opt-in. Workload name alone must not flip a test host."""
    if not _env(ENV_WORKLOAD):
        return False
    flag = _env(ENV_AWS).lower()
    if flag in {"1", "true", "yes"}:
        return True
    return _env(ENV_POSTURE).lower() in {"workload", "login"}


def try_aws_agent_identity() -> "AwsAgentIdentityProvider | None":
    """Return the AWS adapter when opted in and boto3 is installed, else None."""
    if not opted_in():
        return None
    if not extra_available():
        logger.warning(
            "KIROCREW_AGENTCORE_AWS is set but boto3 is missing; "
            "install kirocrew[agentcore] (the EC2 template does this)"
        )
        return None
    return AwsAgentIdentityProvider()


class AwsAgentIdentityProvider:
    """AgentIdentityProvider backed by instance-role boto3 calls."""

    def enabled(self) -> bool:
        return bool(_env(ENV_WORKLOAD))

    def workload_identity(self) -> WorkloadIdentity | None:
        name = _env(ENV_WORKLOAD)
        if not name:
            return None
        return WorkloadIdentity(name=name, arn=_workload_arn(name))

    def status(self) -> dict[str, object]:
        posture = _env(ENV_POSTURE).lower()
        kind = "m2m" if posture == "workload" else "user"
        return {
            "credentialKind": kind,
            "vaultedOwnerToken": False,
            "gatewayUrlConfigured": bool(_env(ENV_GATEWAY_URL)),
            "adapter": "aws",
        }

    def gateway_mcp_spec(self) -> dict[str, object] | None:
        url = _env(ENV_GATEWAY_URL)
        if not url.startswith("https://"):
            return None
        return {"url": url}

    async def annotate_principal(self, principal: SessionPrincipal) -> SessionPrincipal:
        return principal

    async def vend_workload_access_token(self, principal: SessionPrincipal) -> str | None:
        name = _env(ENV_WORKLOAD)
        if not name:
            return None
        client = _client()
        if client is None:
            return None
        try:
            if principal.user_jwt:
                resp = client.get_workload_access_token_for_jwt(
                    workloadName=name, userToken=principal.user_jwt
                )
            else:
                resp = client.get_workload_access_token(workloadName=name)
        except Exception:
            logger.warning("GetWorkloadAccessToken failed; no token", exc_info=True)
            return None
        token = resp.get("workloadAccessToken") if isinstance(resp, dict) else None
        return token if isinstance(token, str) and token else None

    async def vend_gateway_inbound_token(self, principal: SessionPrincipal) -> InboundToken | None:
        # WAT is first-party only. Login inbound is the operator IdP JWT
        # Gateway's CUSTOM_JWT authorizer already accepts.
        jwt = principal.user_jwt
        if not jwt:
            return None
        return InboundToken(
            scheme="bearer",
            token=jwt,
            expires_at=_jwt_exp(jwt),
            audience=_env(ENV_GATEWAY_URL),
        )


def _client() -> Any:
    try:
        import boto3
    except ImportError:
        return None
    return boto3.client(_CLIENT)


def _workload_arn(name: str) -> str:
    """Best-effort ARN from the instance session. Empty account stays explicit."""
    try:
        import boto3
    except ImportError:
        return ""
    session = boto3.session.Session()
    region = session.region_name or _env("AWS_REGION") or _env("AWS_DEFAULT_REGION") or "us-east-1"
    account = ""
    try:
        account = str(boto3.client("sts").get_caller_identity().get("Account") or "")
    except Exception:
        logger.debug("STS account lookup failed; ARN omits account", exc_info=True)
    if not account:
        account = "unknown"
    return (
        f"arn:aws:bedrock-agentcore:{region}:{account}:"
        f"workload-identity-directory/default/workload-identity/{name}"
    )


def _jwt_exp(token: str) -> float:
    """Read ``exp`` from an unverified JWT payload. Fallback is a short TTL."""
    try:
        payload = token.split(".")[1]
        pad = "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload + pad))
        exp = data.get("exp")
        if isinstance(exp, (int, float)):
            return float(exp)
    except Exception:
        logger.debug("inbound JWT exp unreadable; using fallback TTL", exc_info=True)
    return time.time() + _JWT_FALLBACK_TTL_SECS
