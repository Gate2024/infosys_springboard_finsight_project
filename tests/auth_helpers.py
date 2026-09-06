def auth_form(client, **fields):
    """Obtain the public form token just as a browser does before submitting."""
    client.get("/login")
    with client.session_transaction() as session:
        return {"_auth_csrf_token": session["auth_csrf_token"], **fields}


def post_login(client, url, data):
    return client.post(url, data=auth_form(client, **data))
