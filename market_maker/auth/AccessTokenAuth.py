from requests.auth import AuthBase


class AccessTokenAuth(AuthBase):

    """Attaches Access Token Authentication to the given Request object."""

    def __init__(self, accessToken):
        """Init with Token."""
        self.token = accessToken

    def __call__(self, r):
        """Called when forming a request - generates access token header."""
        if (self.token):
            r.headers['access-token'] = self.token
        return r
