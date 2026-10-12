from knox.auth import TokenAuthentication


class CookieTokenAuthentication(TokenAuthentication):
    """
    Extends Knox TokenAuthentication to check request cookies for 'token'
    if the HTTP_AUTHORIZATION header is not set.
    Allows client-side fetch requests in Svelte components to authenticate seamlessly.
    """

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION")
        if auth_header:
            return super().authenticate(request)

        token_cookie = request.COOKIES.get("token")
        if token_cookie:
            return self.authenticate_credentials(token_cookie.encode("utf-8"))

        return None
