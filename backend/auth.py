import os
import msal
from flask import session, redirect, url_for, request
from config import config

# Azure AD Configuration (Environment variables are preferred for security)
client_id = config.AZ_AUTH_CLIENT_ID
client_secret = config.AZ_AUTH_CLIENT_SECRET
authority = f"https://login.microsoftonline.com/{config.AZ_AUTH_TENANT_ID}"
redirect_uri = 'https://quickscribewebapp.azurewebsites.net/auth/callback'

# MSAL Authentication methods
def build_msal_app():
    return msal.ConfidentialClientApplication(
        client_id, authority=authority, client_credential=client_secret
    )

def login():
    msal_app = build_msal_app()
    auth_url = msal_app.get_authorization_request_url(
        scopes=["User.Read"],
        redirect_uri=redirect_uri
    )
    return redirect(auth_url)

def handle_auth_callback():
    msal_app = build_msal_app()
    code = request.args.get('code')
    result = msal_app.acquire_token_by_authorization_code(
        code,
        scopes=["User.Read"],
        redirect_uri=redirect_uri
    )
    if "access_token" in result:
        session["user"] = result["id_token_claims"]
        return redirect(url_for('index'))
    return "Login failed", 400

def get_user():
    return session.get("user")
