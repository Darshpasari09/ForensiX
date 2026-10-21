
from functools import wraps

from flask import abort, session


def roles_required(*allowed_roles):
    def decorator(view_function):
        @wraps(view_function)
        def wrapped_view(*args, **kwargs):
            user_role = session.get("role")

            if not user_role:
                abort(403)

            if user_role not in allowed_roles:
                abort(403)

            return view_function(*args, **kwargs)

        return wrapped_view

    return decorator
