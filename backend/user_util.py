from config import config
from db_handlers.user_handler import UserHandler

def get_user(request):
    # Try to get the user_id from cookies
    user_id = request.cookies.get('user_id')

    user_handler = UserHandler(config.COSMOS_URL, config.COSMOS_KEY, config.COSMOS_DB_NAME, config.COSMOS_CONTAINER_NAME)

    if user_id:
        # Fetch user by ID if the user_id exists in the cookie
        user = user_handler.get_user(user_id)
    else:
        # If no user_id in cookie, fetch user by name 'cbird'
        users = user_handler.get_user_by_name('cbird')
        user = users[0] if users else None  # Assuming 'cbird' is unique, take the first result

    return user